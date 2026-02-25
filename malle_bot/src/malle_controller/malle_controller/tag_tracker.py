#!/usr/bin/env python3
import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String

from apriltag_msgs.msg import AprilTagDetectionArray

_TAG_TOPIC = '/apriltag/detections'     # TODO: 실제 토픽으로 교체

# 제어 파라미터 (추후 ROS 파라미터로 이동 권장)
_FOLLOW_DIST  = 0.8   # m – 팔로우 목표 거리
_DOCK_DIST    = 0.25  # m – 도킹 목표 거리
_MAX_LINEAR   = 0.3   # m/s
_MAX_ANGULAR  = 0.8   # rad/s
_KP_LINEAR    = 0.6
_KP_ANGULAR   = 1.2


class TagTrackerNode(Node):

    def __init__(self):
        super().__init__('tag_tracker')

        self._target_id: int | None = \
            self.declare_parameter('target_tag_id', -1).value
        if self._target_id == -1:
            self._target_id = None  # 아무 태그나 추종

        self._mode = 'idle'

        self._cmd_pub    = self.create_publisher(Twist,  '/cmd_vel',              10)
        self._result_pub = self.create_publisher(String, '/malle/mission_result', 10)
        self._trigger_sub = self.create_subscription(
            String, '/malle/mission_trigger', self._on_trigger, 10)

        self._tag_sub = self.create_subscription(AprilTagDetectionArray, _TAG_TOPIC, self._on_detections, 10)

        self.create_timer(0.05, self._control_loop)

        self._last_err_x  = 0.0
        self._last_dist   = float('inf')
        self._detected    = False

        self.get_logger().info('[TagTracker] 준비 완료')

    def _on_trigger(self, msg: String):
        token = msg.data.strip()
        if token == 'start_follow':
            self._mode = 'follow'
            self.get_logger().info('[TagTracker] follow 모드 시작')
        elif token == 'dock':
            self._mode = 'dock'
            self.get_logger().info('[TagTracker] dock 모드 시작')
        elif token in ('idle', 'stop_follow'):
            self._mode = 'idle'
            self._stop()

    def _on_detections(self, msg):
        """
        AprilTagDetectionArray 콜백 - 메시지 타입에 맞게 구현
        태그의 pose.position.z 를 거리, pose.position.x 를 가로 오차로 활용
        """
        self._detected = False
        for det in msg.detections:
            # TODO: det.id[0] 또는 det.family + det.id 등 패키지마다 다름
            tag_id = det.id[0] if hasattr(det, 'id') else None
            if self._target_id is not None and tag_id != self._target_id:
                continue

            pos = det.pose.pose.pose.position
            self._last_dist  = pos.z          # 태그까지의 깊이 (m)
            self._last_err_x = pos.x          # 가로 오차 (m)
            self._detected   = True
            break

    def _control_loop(self):
        if self._mode == 'idle':
            return

        if not self._detected:
            self._cmd_vel(0.0, 0.3)
            return

        target_dist = _FOLLOW_DIST if self._mode == 'follow' else _DOCK_DIST
        err_lin = self._last_dist  - target_dist
        err_ang = self._last_err_x

        lin = max(-_MAX_LINEAR,  min(_MAX_LINEAR,  _KP_LINEAR  * err_lin))
        ang = max(-_MAX_ANGULAR, min(_MAX_ANGULAR, -_KP_ANGULAR * err_ang))
        self._cmd_vel(lin, ang)

        if self._mode == 'dock' and abs(err_lin) < 0.05 and abs(err_ang) < 0.05:
            self._stop()
            self._mode = 'idle'
            self.get_logger().info('[TagTracker] 도킹 완료')
            self._publish_result('docked')

    def _cmd_vel(self, linear_x: float, angular_z: float):
        msg = Twist()
        msg.linear.x  = float(linear_x)
        msg.angular.z = float(angular_z)
        self._cmd_pub.publish(msg)

    def _stop(self):
        self._cmd_vel(0.0, 0.0)

    def _publish_result(self, result: str):
        msg = String()
        msg.data = result
        self._result_pub.publish(msg)


def main():
    rclpy.init()
    node = TagTrackerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
