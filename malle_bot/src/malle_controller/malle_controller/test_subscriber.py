#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from malle_controller.msg import RobotMessage


class TestSubscriber(Node):
    def __init__(self):
        super().__init__('test_subscriber')
        self.subscription = self.create_subscription(
            RobotMessage,
            'robot_test_topic',
            self.listener_callback,
            10)
        self.get_logger().info('테스트 Subscriber 시작! 메시지 대기 중...')

    def listener_callback(self, msg):
        self.get_logger().info('=' * 50)
        self.get_logger().info(f'메시지 ID: {msg.header.message_id}')
        self.get_logger().info(f'시간: {msg.header.timestamp_sec}.{msg.header.timestamp_nsec}')
        self.get_logger().info(f'로봇 ID: {msg.header.robot_id}')
        self.get_logger().info(f'메시지 타입: {msg.header.message_type}')
        self.get_logger().info(f'시퀀스: {msg.header.sequence}')
        self.get_logger().info(f'배터리: {msg.battery}%')
        self.get_logger().info(f'상태: {msg.robot_status}')
        self.get_logger().info('=' * 50)


def main(args=None):
    rclpy.init(args=args)
    node = TestSubscriber()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()