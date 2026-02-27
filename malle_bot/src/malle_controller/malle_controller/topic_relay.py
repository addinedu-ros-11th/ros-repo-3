#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32


class TopicRelay(Node):

    def __init__(self):
        super().__init__('topic_relay')

        robot_ns = self.declare_parameter('robot_ns', 'robot1').value

        self._odom_pub = self.create_publisher(
            Odometry, f'/{robot_ns}/odom', 10)
        self._battery_pub = self.create_publisher(
            Float32, f'/{robot_ns}/battery', 10)

        self.create_subscription(Odometry, '/odom', self._odom_pub.publish, 10)
        self.create_subscription(Float32, '/battery/present', self._battery_pub.publish, 10)

        self.get_logger().info(
            f'[TopicRelay] /odom → /{robot_ns}/odom, '
            f'/battery/present → /{robot_ns}/battery'
        )


def main():
    rclpy.init()
    node = TopicRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
