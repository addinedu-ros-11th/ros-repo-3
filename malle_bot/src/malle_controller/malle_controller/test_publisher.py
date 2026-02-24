#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from malle_controller.msg import RobotMessage, MessageHeader
import time
import uuid


class TestPublisher(Node):
    def __init__(self):
        super().__init__('test_publisher')
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE
        )
        self.publisher_ = self.create_publisher(
            RobotMessage,
            'robot_test_topic',
            qos_profile
        )
        self.timer = self.create_timer(1.0, self.timer_callback)  # 1초마다 발행
        self.count = 0
        self.get_logger().info('테스트 Publisher 시작!')

    def timer_callback(self):
        msg = RobotMessage()

        # Header 설정
        msg.header.message_id = str(uuid.uuid4())
        current_time = time.time()
        msg.header.timestamp_sec = int(current_time)
        msg.header.timestamp_nsec = int((current_time % 1) * 1e9)
        msg.header.robot_id = "connect_test"
        msg.header.message_type = "status"
        msg.header.priority = 1
        msg.header.sequence = self.count

        # Body 설정
        msg.battery = 85.5
        msg.robot_status = "running"
        msg.command = ""
        msg.error_message = ""

        self.publisher_.publish(msg)
        self.get_logger().info(f'메시지 발행 #{self.count} - 시간: {msg.header.timestamp_sec}.{msg.header.timestamp_nsec}')
        self.count += 1


def main(args=None):
    rclpy.init(args=args)
    node = TestPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
