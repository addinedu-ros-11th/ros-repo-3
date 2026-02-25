#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String


class MissionFollowNode(Node):

    def __init__(self):
        super().__init__('mission_follow')

        self.cmd_pub    = self.create_publisher(Twist, '/cmd_vel', 10)
        self.result_pub = self.create_publisher(String, '/malle/mission_result', 10)
        self.trigger_sub = self.create_subscription(
            String, '/malle/mission_trigger', self._on_trigger, 10)

        self.active = False

        # TODO: 카메라, detector 등 초기화

        self.create_timer(0.02, self._control_loop)

    def _on_trigger(self, msg: String):
        if msg.data == 'start_follow':
            self.active = True
            # TODO: 시작 시 필요한 초기화
        elif msg.data == 'idle':
            self.active = False
            self.cmd_pub.publish(Twist())  # 정지

    def _control_loop(self):
        if not self.active:
            return
        # TODO: 팔로우 로직

    def _publish_result(self, result: str):
        msg = String()
        msg.data = result
        self.result_pub.publish(msg)


def main():
    rclpy.init()
    node = MissionFollowNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()