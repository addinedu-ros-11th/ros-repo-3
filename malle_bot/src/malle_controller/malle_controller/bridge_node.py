#!/usr/bin/env python3
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from malle_controller.msg import TaskCommand, RobotMessage
from malle_controller.api_client import ApiClient


class BridgeNode(Node):

    def __init__(self):
        super().__init__('bridge_node')

        self._robot_id  = self.declare_parameter('robot_id',    'malle_01').value
        self._api_url   = self.declare_parameter('api_base_url', 'http://localhost:8000').value
        self._poll_hz   = self.declare_parameter('poll_hz',     1.0).value

        self._api = ApiClient(base_url=self._api_url, logger=self.get_logger())

        self._cmd_pub   = self.create_publisher(TaskCommand,  '/malle/command',     10)
        self._state_sub = self.create_subscription(
            RobotMessage, '/malle/robot_state', self._on_robot_state, 10)

        self.create_timer(1.0 / self._poll_hz, self._poll_server)

        self.get_logger().info(
            f'[BridgeNode] robot_id={self._robot_id}, api={self._api_url}')

    def _poll_server(self):
        """서버에서 미처리 태스크를 가져와 /malle/command에 퍼블리시"""
        try:
            tasks = self._api.get(f'/robots/{self._robot_id}/pending_tasks')
            for task in tasks:
                self._dispatch_task(task)
        except Exception as e:
            self.get_logger().warn(f'[BridgeNode] 폴링 실패: {e}')

    def _dispatch_task(self, task: dict):
        msg = TaskCommand()
        msg.robot_id   = self._robot_id
        msg.task_id    = task.get('id', '')
        msg.task_type  = task.get('type', '').upper()
        msg.target_x   = float(task.get('target_x', 0.0))
        msg.target_y   = float(task.get('target_y', 0.0))
        msg.timestamp  = int(task.get('timestamp', 0))
        self._cmd_pub.publish(msg)
        self.get_logger().info(
            f'[BridgeNode] 태스크 디스패치: {msg.task_type} / {msg.task_id}')

    def _on_robot_state(self, msg: RobotMessage):
        """로봇 상태를 서버에 비동기 보고"""
        threading.Thread(
            target=self._report_state, args=(msg,), daemon=True
        ).start()

    def _report_state(self, msg: RobotMessage):
        try:
            self._api.report_status(
                robot_id=msg.header.robot_id or self._robot_id,
                status=msg.robot_status,
                battery=float(msg.battery),
                task_id=msg.command,
            )
        except Exception as e:
            self.get_logger().warn(f'[BridgeNode] 상태 보고 실패: {e}')


def main():
    rclpy.init()
    node = BridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
