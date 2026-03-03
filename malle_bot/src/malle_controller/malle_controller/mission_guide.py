#!/usr/bin/env python3
"""
mission_guide.py — 가이드 미션 실행기

흐름:
  1. bridge_node → /bridge/navigate 수신
  2. MissionExecutor → GuideExecutor.start(session_id, first_item)
  3. GuideExecutor → 서버 guide_queue 조회 → POI 좌표로 Nav2 이동
  4. 도착 → PATCH /guide-queue/{item_id} status=ARRIVED → advance() 대기
  5. Robot UI "Next Stop" / Mobile "Mark as Arrived" → advance() → DONE → 다음 항목
"""

import threading
from collections import deque

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from malle_controller.nav_core import NavCore
from malle_controller.api_client import ApiClient
from malle_controller.poi_manager import PoiManager


class GuideExecutor(NavCore):
    """
    가이드 미션 실행기.
    Node를 상속하지 않고 NavCore 믹스인만 사용 —
    MissionExecutor(Node)에서 nav_core_init(self)를 통해 초기화.
    """

    def __init__(self, node: Node, api: ApiClient, poi_mgr: PoiManager):
        self.nav_core_init(node)
        self._node    = node
        self._api     = api
        self._poi_mgr = poi_mgr
        self._log     = node.get_logger()

        self._active         = False
        self._waiting_at_poi = False   # 도착 후 advance() 대기 중
        self._session_id: int | None = None
        self._queue: deque[dict] = deque()  # guide_queue_item dicts
        self._current_item: dict | None = None
        self._lock = threading.Lock()

    # ── 외부 인터페이스 ──────────────────────────────────────────────────────

    def start(self, session_id: int, queue_items: list[dict]):
        """
        가이드 시작.
        queue_items: guide_queue API 응답 (PENDING 항목만)
        """
        with self._lock:
            self._session_id     = session_id
            self._queue          = deque(queue_items)
            self._active         = True
            self._waiting_at_poi = False

        self._log.info(
            f'[GuideExecutor] 시작 session={session_id} '
            f'항목={len(queue_items)}개'
        )
        self._navigate_next()

    def stop(self):
        """강제 중지 (세션 종료 / E-Stop 등)."""
        with self._lock:
            self._active         = False
            self._waiting_at_poi = False
            self._queue.clear()
            self._current_item   = None
        self.cancel_navigation()
        self.cmd_vel(0.0, 0.0)
        self._log.info('[GuideExecutor] 중지')

    def advance(self):
        """
        다음 POI로 이동.
        Robot UI 'Next Stop' 또는 Mobile 'Mark as Arrived' 눌렀을 때 호출.
        대기 중이 아닐 때는 무시.
        """
        with self._lock:
            if not self._waiting_at_poi:
                self._log.warn('[GuideExecutor] advance() — 대기 중 아님, 무시')
                return
            self._waiting_at_poi = False
            item = self._current_item

        if item:
            session_id = self._session_id
            item_id    = item.get('id')
            if session_id and item_id:
                try:
                    self._api.update_guide_item(session_id, item_id, 'DONE')
                    self._log.info(
                        f'[GuideExecutor] DONE 보고: item_id={item_id}'
                    )
                except Exception as e:
                    self._log.warn(f'[GuideExecutor] DONE 보고 실패: {e}')

        self._navigate_next()

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_waiting(self) -> bool:
        return self._waiting_at_poi

    # ── 내부 ────────────────────────────────────────────────────────────────

    def _navigate_next(self):
        with self._lock:
            if not self._active:
                return
            if not self._queue:
                self._active = False
                self._log.info('[GuideExecutor] 모든 POI 완료')
                return
            item = self._queue.popleft()
            self._current_item = item

        poi_id   = item.get('poi_id')
        item_id  = item.get('id')
        poi_name = item.get('poi_name') or f'POI#{poi_id}'

        # POI 좌표 — poi_manager에서 우선 조회, 없으면 서버 응답에서 직접 사용
        poi = self._poi_mgr.get(str(poi_id))
        if poi:
            # wait_point 우선 (매장 앞 대기 위치)
            x = float(poi.get('wait_x_m') or poi.get('x_m') or poi.get('x', 0.0))
            y = float(poi.get('wait_y_m') or poi.get('y_m') or poi.get('y', 0.0))
        else:
            self._log.warn(f'[GuideExecutor] POI {poi_id} 없음, 건너뜀')
            self._navigate_next()
            return

        self._log.info(
            f'[GuideExecutor] → {poi_name} '
            f'item_id={item_id} ({x:.3f}, {y:.3f})'
        )

        self.navigate_to_pose(
            x=x, y=y, yaw=0.0,
            done_callback=lambda f: self._on_nav_done(f, item_id, poi_name),
        )

    def _on_nav_done(self, future, item_id: int, poi_name: str):
        """Nav2 액션 완료 콜백."""
        try:
            status = future.result().status
        except Exception as e:
            self._log.error(f'[GuideExecutor] 결과 수신 실패: {e}')
            self._on_nav_failed(item_id)
            return

        # action_msgs/GoalStatus: SUCCEEDED = 4
        if status == 4:
            self._log.info(f'[GuideExecutor] 도착: {poi_name}')
            self._on_arrived(item_id, poi_name)
        else:
            self._log.warn(
                f'[GuideExecutor] 이동 실패 status={status}: {poi_name}'
            )
            self._on_nav_failed(item_id)

    def _on_arrived(self, item_id: int, poi_name: str):
        """POI 도착 처리 — 서버에 ARRIVED 보고 후 advance() 대기."""
        session_id = self._session_id
        if session_id and item_id:
            try:
                self._api.update_guide_item(session_id, item_id, 'ARRIVED')
                self._log.info(
                    f'[GuideExecutor] ARRIVED 보고: item_id={item_id}'
                )
            except Exception as e:
                self._log.warn(f'[GuideExecutor] ARRIVED 보고 실패: {e}')

        # advance() 호출 전까지 대기 (Robot UI "Next Stop" / Mobile "Mark as Arrived")
        with self._lock:
            self._waiting_at_poi = True
        self._log.info(f'[GuideExecutor] 대기 중: {poi_name}')

    def _on_nav_failed(self, item_id: int):
        """이동 실패 처리 — 항목 SKIPPED 처리 후 다음 항목 시도."""
        session_id = self._session_id
        if session_id and item_id:
            try:
                self._api.update_guide_item(session_id, item_id, 'SKIPPED')
            except Exception as e:
                self._log.warn(f'[GuideExecutor] SKIPPED 보고 실패: {e}')

        self._navigate_next()


# ── 독립 실행용 (테스트) ─────────────────────────────────────────────────────

class MissionGuideNode(Node, NavCore):
    """bridge_node 없이 단독 테스트용."""

    def __init__(self):
        Node.__init__(self, 'mission_guide')
        self.nav_core_init(self)

        api_url = self.declare_parameter(
            'api_base_url', 'http://localhost:8000/api/v1'
        ).value

        self._api     = ApiClient(base_url=api_url, logger=self.get_logger())
        self._poi_mgr = PoiManager(self._api, logger=self.get_logger())
        self._poi_mgr.load()

        self._executor = GuideExecutor(self, self._api, self._poi_mgr)

        # /malle/mission_trigger 구독 (mission_executor에서 발행)
        self.trigger_sub = self.create_subscription(
            String, '/malle/mission_trigger', self._on_trigger, 10)

        self.get_logger().info('[MissionGuideNode] 준비 완료')

    def _on_trigger(self, msg: String):
        token = msg.data.strip()

        if token.startswith('start_guide:'):
            # 포맷: "start_guide:{session_id}"
            try:
                session_id = int(token.split(':', 1)[1])
            except ValueError:
                self.get_logger().error(f'[MissionGuide] 잘못된 trigger: {token}')
                return
            self._fetch_and_start(session_id)

        elif token in ('stop_guide', 'idle'):
            self._executor.stop()

    def _fetch_and_start(self, session_id: int):
        """서버에서 guide_queue 조회 후 실행."""
        try:
            items = self._api.get_guide_queue(session_id)
            pending = [i for i in items if i.get('status') == 'PENDING' and i.get('is_active')]
            if not pending:
                self.get_logger().warn(
                    f'[MissionGuide] session={session_id} 실행할 항목 없음'
                )
                return
            self._executor.start(session_id, pending)
        except Exception as e:
            self.get_logger().error(f'[MissionGuide] queue 조회 실패: {e}')


def main():
    rclpy.init()
    node = MissionGuideNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()