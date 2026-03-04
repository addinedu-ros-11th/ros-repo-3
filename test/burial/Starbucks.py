#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


def yaw_to_quat(yaw_rad: float):
    """요각(yaw, rad) -> 쿼터니언 (x,y,z,w) 변환 (평면 이동용)"""
    half = yaw_rad * 0.5
    return (0.0, 0.0, math.sin(half), math.cos(half))


class GoToXY(Node):
    def __init__(self, action_name: str):
        super().__init__("go_to_xy_client")
        self._client = ActionClient(self, NavigateToPose, action_name)

    def send_goal(self, x: float, y: float, yaw_rad: float = 0.0):
        goal = NavigateToPose.Goal()

        pose = PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()

        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)

        qx, qy, qz, qw = yaw_to_quat(yaw_rad)
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw

        goal.pose = pose

        self.get_logger().info("Nav2 액션 서버를 기다리는 중...")
        if not self._client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error("Nav2 액션 서버를 사용할 수 없습니다.")
            rclpy.shutdown()
            return

        self.get_logger().info(f"목표 전송: x={x}, y={y}, yaw={yaw_rad}rad")
        send_future = self._client.send_goal_async(goal)
        send_future.add_done_callback(self._goal_response_cb)

    def _goal_response_cb(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("목표가 거절되었습니다.")
            rclpy.shutdown()
            return

        self.get_logger().info("목표가 수락되었습니다. 결과를 기다리는 중...")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_cb)

    def _result_cb(self, future):
        result = future.result()
        status = result.status

        # Nav2 status codes: SUCCEEDED=4 (commonly), but we don't hardcode meaning—print anyway.
        if status == 4:
            print("해당구역 도착")
        else:
            print(f"아직 도착하지 못했습니다. (status={status})")

        rclpy.shutdown()


def main():
    rclpy.init()

    # 'ros2 action list'에서 확인한 실제 액션 이름으로 바꾸세요.
    ACTION_NAME = "/navigate_to_pose"

    node = GoToXY(ACTION_NAME)
    node.send_goal(x=1.780, y=1.730, yaw_rad=0)

    rclpy.spin(node)

if __name__ == "__main__":
    main()