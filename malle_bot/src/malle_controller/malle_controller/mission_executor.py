#!/usr/bin/env python3
"""
mission_executor.py — HTTP 기반 미션 디스패처

역할:
  - bridge_node의 /bridge/navigate 요청을 받아 GuideExecutor 실행
  - 향후 follow / pickup 실행기도 여기서 분기
  - 세션 상태 변화(E-Stop, 세션 종료)에 따른 실행기 중지

아키텍처:
  bridge_node(:9100)
    └─ POST /bridge/navigate → MissionExecutor.dispatch_guide()
                                     └─ GuideExecutor.start()
                                           └─ NavCore.navigate_to_pose()
                                                 └─ Nav2 NavigateToPose action
                                                       └─ 도착 콜백
                                                             └─ ApiClient.update_guide_item(ARRIVED)
"""

import threading

import rclpy
from rclpy.node import Node

from malle_controller.nav_core import NavCore
from malle_controller.api_client import ApiClient
from malle_controller.poi_manager import PoiManager
from malle_controller.mission_guide import GuideExecutor


class MissionExecutor(Node, NavCore):
    """
    미션 디스패처 노드.
    bridge_node에서 직접 메서드를 호출하거나,
    단독 실행 시 ROS2 토픽으로도 트리거 가능.
    """

    def __init__(self, api_base_url: str = 'http://localhost:8000/api/v1'):
        Node.__init__(self, 'mission_executor')
        self.nav_core_init(self)

        self._api     = ApiClient(base_url=api_base_url, logger=self.get_logger())
        self._poi_mgr = PoiManager(self._api, logger=self.get_logger())
        self._poi_mgr.load()

        self._guide    = GuideExecutor(self, self._api, self._poi_mgr)
        # TODO: self._follow  = FollowExecutor(...)
        # TODO: self._pickup  = PickupExecutor(...)

        self._lock = threading.Lock()
        self.get_logger().info('[MissionExecutor] 준비 완료')

    # ── 외부 인터페이스 (bridge_node에서 직접 호출) ──────────────────────────

    def dispatch_guide(self, session_id: int,
                       queue_items: list[dict] | None = None):
        """
        가이드 미션 시작.

        Parameters
        ----------
        session_id   : 세션 ID
        queue_items  : 이미 조회된 queue item 목록 (없으면 서버에서 재조회)
        """
        with self._lock:
            # 진행 중인 미션 중지
            if self._guide.is_active:
                self._guide.stop()

        # queue_items가 없으면 서버에서 조회
        if queue_items is None:
            try:
                items = self._api.get_guide_queue(session_id)
                queue_items = [
                    i for i in items
                    if i.get('status') == 'PENDING' and i.get('is_active')
                ]
            except Exception as e:
                self.get_logger().error(
                    f'[MissionExecutor] guide_queue 조회 실패: {e}'
                )
                return

        if not queue_items:
            self.get_logger().warn(
                f'[MissionExecutor] session={session_id} 실행할 항목 없음'
            )
            return

        self._guide.start(session_id, queue_items)

    def stop_all(self):
        """모든 실행 중인 미션 중지 (E-Stop / 세션 종료 시)."""
        self._guide.stop()
        self.get_logger().info('[MissionExecutor] 전체 미션 중지')

    @property
    def guide_active(self) -> bool:
        return self._guide.is_active


def main():
    rclpy.init()
    node = MissionExecutor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()