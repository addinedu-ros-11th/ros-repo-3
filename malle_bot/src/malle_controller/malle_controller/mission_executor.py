#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import String, Float32
from enum import Enum, auto

from malle_controller.msg import TaskCommand, RobotMessage, MessageHeader

try:
    import cv2
    import threading
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
    EXCEPTION = auto()


class MissionExecutor(Node):

    def __init__(self):
        super().__init__('mission_executor')

        self.state           = RobotState.IDLE
        self.robot_id        = 'malle_01'
        self.battery         = 0.0
        self.current_task_id = ''
        self._poi_ids        = ''

        self.cmd_sub = self.create_subscription(
            TaskCommand, '/malle/command', self._on_command, 10)
        self.result_sub = self.create_subscription(
            String, '/malle/mission_result', self._on_mission_result, 10)
        self.battery_sub = self.create_subscription(
            String, '/malle/battery_status', self._on_battery, 10)
        self.battery_pct_sub = self.create_subscription(
            Float32, '/battery/present', self._on_battery_pct, 10)

        self.state_pub   = self.create_publisher(RobotMessage, '/malle/robot_state', 10)
        self.trigger_pub = self.create_publisher(String, '/malle/mission_trigger', 10)

        self.create_timer(1.0, self._publish_state)
        self.get_logger().info(f"[MissionExecutor] 초기 상태: {self.state.name}")

    def _on_command(self, msg: TaskCommand):
        task_type = msg.task_type.strip().upper()
        self.get_logger().info(f"[CMD] {task_type} / task_id={msg.task_id} (현재: {self.state.name})")

        if self.state in (RobotState.CHARGING, RobotState.EXCEPTION):
            self.get_logger().warn(f"{self.state.name} 중 - 명령 무시")
            return

        self.current_task_id = msg.task_id
        self._poi_ids        = msg.poi_ids

        handler = {
            'GUIDE':  self._cmd_guide,
            'BROWSE': self._cmd_browse,
            'ERRAND': self._cmd_errand,
        }.get(task_type)

        if handler:
            handler()
        else:
            self.get_logger().warn(f"알 수 없는 task_type: '{task_type}'")

    def _cmd_guide(self):
        if self.state in (RobotState.IDLE, RobotState.GUIDE, RobotState.FOLLOW):
            self._transition(RobotState.GUIDE)
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
            ('exception_resolved', RobotState.EXCEPTION) : RobotState.IDLE,
        }.get((result, self.state))

        if next_state:
            self._transition(next_state)
        else:
            self.get_logger().warn(f"처리되지 않은 result: '{result}' (state: {self.state.name})")

    def _on_battery_pct(self, msg: Float32):
        self.battery = msg.data

    def _on_battery(self, msg: String):
        if msg.data.strip().lower() == 'charged' and self.state == RobotState.CHARGING:
            self._transition(RobotState.IDLE)

    def _transition(self, new_state: RobotState):
        self.get_logger().info(f"[TRANSITION] {self.state.name} → {new_state.name}")
        self.state = new_state

        trigger = {
            RobotState.IDLE      : 'idle',
            RobotState.GUIDE     : f'start_guide:{self._poi_ids}',
            RobotState.FOLLOW    : f'start_follow:{self._poi_ids}',
            RobotState.ERRAND    : f'start_errand:{self._poi_ids}',
            RobotState.BOX_EMPTY : 'open_box',
            RobotState.BOX_FULL  : 'lock_box',
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


def main():
    rclpy.init()
    executor = MultiThreadedExecutor()
    nodes = [MissionExecutor()]

    camera = None

    if _CAMERA_AVAILABLE:
        # == 카메라 초기화 (단일 소유) ====================
        try:
            cam = Camera()
            cam.start(width=640, height=480)
            camera = cam

            _latest_gray = None
            _frame_lock = threading.Lock()

            def _capture():
                nonlocal _latest_gray
                while True:
                    frame = cam.get_frame()
                    if frame is not None:
                        with _frame_lock:
                            _latest_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                    time.sleep(0.01)

            def get_gray_frame():
                with _frame_lock:
                    return _latest_gray

            threading.Thread(target=_capture, daemon=True).start()

            nodes += [
                MissionFollowNode(get_gray_frame),
                TagTrackerNode(get_gray_frame),
                PinkyParkingNode(get_gray_frame),
            ]
        except Exception as e:
            rclpy.logging.get_logger('mission_executor').warn(
                f'카메라 초기화 실패 - 카메라 노드 비활성화: {e}')
            camera = None
    else:
        rclpy.logging.get_logger('mission_executor').warn(
            'pinkylib 없음 - 카메라 노드 비활성화')

    for node in nodes:
        executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        for node in nodes:
            node.destroy_node()
        rclpy.shutdown()
        if camera is not None:
            camera.close()


if __name__ == '__main__':
    main()
