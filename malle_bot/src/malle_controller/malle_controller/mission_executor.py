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
from enum import Enum, auto

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import String, Float32

from malle_controller.msg import TaskCommand, RobotMessage
from malle_controller.nav_core import NavCore
from malle_controller.api_client import ApiClient
from malle_controller.poi_manager import PoiManager
from malle_controller.mission_guide import GuideExecutor

try:
    import cv2
    import time
    from pinkylib import Camera
    from malle_controller.mission_follow import MissionFollowNode
    from malle_controller.tag_tracker import TagTrackerNode
    from malle_controller.mission_parking11 import PinkyParkingNode
    _CAMERA_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    _CAMERA_AVAILABLE = False


class RobotState(Enum):
    CHARGING  = auto()
    IDLE      = auto()
    GUIDE     = auto()
    FOLLOW    = auto()
    ERRAND    = auto()
    BOX_EMPTY = auto()
    BOX_FULL  = auto()
    PARKING   = auto()
    EXCEPTION = auto()


class MissionExecutor(Node, NavCore):

    def __init__(self, api_base_url: str = 'http://localhost:8000'):
        Node.__init__(self, 'mission_executor')
        self.nav_core_init(self)

        self.state           = RobotState.IDLE
        self.robot_id        = 'malle_01'
        self.battery         = 0.0
        self.current_task_id = ''
        self._poi_ids        = ''

        self._api     = ApiClient(base_url=api_base_url, logger=self.get_logger())
        self._poi_mgr = PoiManager(self._api, logger=self.get_logger())
        self._poi_mgr.load()

        self._guide = GuideExecutor(self, self._api, self._poi_mgr)
        # TODO: self._follow = FollowExecutor(...)
        # TODO: self._pickup = PickupExecutor(...)

        self._lock = threading.Lock()

        self.cmd_sub = self.create_subscription(
            TaskCommand, '/malle/command', self._on_command, 10)
        self.result_sub = self.create_subscription(
            String, '/malle/mission_result', self._on_mission_result, 10)
        self.battery_sub = self.create_subscription(
            String, '/malle/battery_status', self._on_battery, 10)
        self.battery_pct_sub = self.create_subscription(
            Float32, '/battery/present', self._on_battery_pct, 10)
        self.guide_advance_sub = self.create_subscription(
            String, '/malle/guide_advance', self._on_guide_advance, 10)

        self.state_pub   = self.create_publisher(RobotMessage, '/malle/robot_state', 10)
        self.trigger_pub = self.create_publisher(String, '/malle/mission_trigger', 10)

        self.create_timer(1.0, self._publish_state)
        self.get_logger().info(f'[MissionExecutor] 준비 완료 (상태: {self.state.name})')

    # ── 외부 인터페이스 (bridge_node에서 직접 호출) ──────────────────────────

    def dispatch_guide(self, session_id: int,
                       queue_items: list[dict] | None = None):
        """
        가이드 미션 시작 (HTTP 경로).
        _transition() 을 거치지 않아 ROS2 트리거를 발행하지 않음.

        Parameters
        ----------
        session_id  : 세션 ID
        queue_items : 이미 조회된 queue item 목록 (없으면 서버에서 재조회)
        """
        with self._lock:
            if self._guide.is_active:
                self._guide.stop()

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

        self.get_logger().info(f'[MissionExecutor] {self.state.name} → GUIDE')
        self.state = RobotState.GUIDE
        self._guide.start(session_id, queue_items)

    def stop_all(self):
        """모든 실행 중인 미션 중지 (E-Stop / 세션 종료 시)."""
        self._guide.stop()
        self._transition(RobotState.IDLE)
        self.get_logger().info('[MissionExecutor] 전체 미션 중지')

    # ── ROS2 토픽 인터페이스 ─────────────────────────────────────────────────

    def _on_command(self, msg: TaskCommand):
        task_type = msg.task_type.strip().upper()
        self.get_logger().info(f"[CMD] {task_type} / task_id={msg.task_id} (현재: {self.state.name})")

        if self.state in (RobotState.CHARGING, RobotState.EXCEPTION):
            self.get_logger().warn(f"{self.state.name} 중 - 명령 무시")
            return

        self.current_task_id = msg.task_id
        self._poi_ids        = msg.poi_ids

        handler = {
            'GUIDE':   self._cmd_guide,
            'BROWSE':  self._cmd_browse,
            'ERRAND':  self._cmd_errand,
            'PARKING': self._cmd_parking,
        }.get(task_type)

        if handler:
            handler()
        else:
            self.get_logger().warn(f"알 수 없는 task_type: '{task_type}'")

    def _cmd_guide(self):
        if self.state in (RobotState.IDLE, RobotState.GUIDE, RobotState.FOLLOW):
            session_id_str = self.current_task_id
            if not session_id_str.isdigit():
                self.get_logger().warn(f"GUIDE 명령: 유효하지 않은 session_id '{session_id_str}'")
                return
            self.state = RobotState.GUIDE
            session_id = int(session_id_str)
            threading.Thread(
                target=lambda: self.dispatch_guide(session_id),
                daemon=True,
            ).start()
        else:
            self.get_logger().warn(f"GUIDE 명령 무시 (현재: {self.state.name})")

    def _cmd_browse(self):
        if self.state == RobotState.IDLE:
            self._transition(RobotState.FOLLOW)
        else:
            self.get_logger().warn(f"BROWSE 명령 무시 (현재: {self.state.name})")

    def _cmd_errand(self):
        if self.state in (RobotState.IDLE, RobotState.FOLLOW):
            self._transition(RobotState.ERRAND)
        else:
            self.get_logger().warn(f"ERRAND 명령 무시 (현재: {self.state.name})")

    def _cmd_parking(self):
        if self.state == RobotState.IDLE:
            self._transition(RobotState.PARKING)
        else:
            self.get_logger().warn(f"PARKING 명령 무시 (현재: {self.state.name})")

    def _on_mission_result(self, msg: String):
        result = msg.data.strip().lower()
        self.get_logger().info(f"[RESULT] '{result}' (현재: {self.state.name})")

        if result == 'exception':
            self._transition(RobotState.EXCEPTION)
            return

        next_state = {
            ('guide_done',         RobotState.GUIDE)     : RobotState.IDLE,
            ('errand_done',        RobotState.ERRAND)    : RobotState.IDLE,
            ('arrived_store',      RobotState.ERRAND)    : RobotState.BOX_EMPTY,
            ('box_loaded',         RobotState.BOX_EMPTY) : RobotState.BOX_FULL,
            ('user_auth_done',     RobotState.BOX_FULL)  : RobotState.ERRAND,
            ('parked',             RobotState.PARKING)   : RobotState.IDLE,
            ('exception_resolved', RobotState.EXCEPTION) : RobotState.IDLE,
        }.get((result, self.state))

        if next_state:
            self._transition(next_state)
        else:
            self.get_logger().warn(f"처리되지 않은 result: '{result}' (state: {self.state.name})")

    def _on_guide_advance(self, msg: String):
        """bridge_node /bridge/guide/advance → 다음 POI로 이동."""
        if self._guide.is_waiting:
            threading.Thread(target=self._guide.advance, daemon=True).start()
        else:
            self.get_logger().warn('[MissionExecutor] guide_advance 수신 — 대기 중 아님, 무시')

    def _on_battery(self, msg: String):
        try:
            self.battery = float(msg.data)
        except ValueError:
            pass

    def _on_battery_pct(self, msg: Float32):
        self.battery = float(msg.data)

    # ── 상태 관리 ────────────────────────────────────────────────────────────

    def _transition(self, new_state: RobotState):
        self.get_logger().info(
            f'[MissionExecutor] {self.state.name} → {new_state.name}'
        )
        self.state = new_state

        trigger = {
            RobotState.IDLE      : 'idle',
            RobotState.GUIDE     : f'start_guide:{self._poi_ids}',
            RobotState.FOLLOW    : f'start_follow:{self._poi_ids}',
            RobotState.ERRAND    : f'start_errand:{self._poi_ids}',
            RobotState.BOX_EMPTY : 'open_box',
            RobotState.BOX_FULL  : 'lock_box',
            RobotState.PARKING   : 'start_parking',
            RobotState.EXCEPTION : 'handle_exception',
        }.get(new_state)

        if trigger:
            msg = String()
            msg.data = trigger
            self.trigger_pub.publish(msg)

    def _publish_state(self):
        msg = RobotMessage()
        msg.header.robot_id       = self.robot_id
        msg.header.message_type   = 'STATUS'
        msg.header.timestamp_sec  = self.get_clock().now().seconds_nanoseconds()[0]
        msg.header.timestamp_nsec = self.get_clock().now().seconds_nanoseconds()[1]
        msg.robot_status          = self.state.name
        msg.battery               = self.battery
        msg.command               = self.current_task_id
        msg.error_message         = ''
        self.state_pub.publish(msg)

    # ── 프로퍼티 ─────────────────────────────────────────────────────────────

    @property
    def guide_active(self) -> bool:
        return self._guide.is_active


def main():
    import os
    rclpy.init()
    executor = MultiThreadedExecutor()
    api_url = os.getenv('MALLE_SERVICE_URL', 'http://localhost:8000/api/v1')
    executor.add_node(MissionExecutor(api_base_url=api_url))

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
