#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose
import os

ROBOT_NAMESPACE = os.getenv("ROBOT_NAMESPACE", "")

def _ns(name: str) -> str:
    return f"/{ROBOT_NAMESPACE}/{name.lstrip('/')}" if ROBOT_NAMESPACE else f"/{name.lstrip('/')}"


class NavCore:
    """Nav2 + cmd_vel 공용 엔진 (Node 믹스인용)."""
    def nav_core_init(self, node: Node):
        """미션 노드의 __init__에서 호출"""
        self._node = node

        self._nav_client = ActionClient(node, NavigateToPose, _ns('navigate_to_pose'))
        self._cmd_pub = node.create_publisher(Twist, _ns('cmd_vel'), 10)

        self._current_goal_handle = None

    def navigate_to_pose(self, x: float, y: float, yaw: float = 0.0,
                         done_callback=None):
        """
        Nav2 NavigateToPose 액션을 전송

        Parameters
        ----------
        x, y      : 목표 좌표 (map 프레임)
        yaw       : 목표 방향 (라디안)
        done_callback : action 완료 시 호출될 콜백 (선택)
        """
        if not self._nav_client.wait_for_server(timeout_sec=3.0):
            self._node.get_logger().error('[NavCore] navigate_to_pose: 액션 서버 없음')
            return

        goal = NavigateToPose.Goal()
        goal.pose = self._make_pose_stamped(x, y, yaw)

        future = self._nav_client.send_goal_async(goal)
        future.add_done_callback(
            lambda f: self._on_goal_accepted(f, done_callback)
        )

    def cancel_navigation(self):
        """진행 중인 Nav2 목표를 취소"""
        if self._current_goal_handle is not None:
            self._current_goal_handle.cancel_goal_async()
            self._current_goal_handle = None

    def cmd_vel(self, linear_x: float = 0.0, angular_z: float = 0.0):
        """Twist를 /cmd_vel에 직접 퍼블리시"""
        msg = Twist()
        msg.linear.x  = float(linear_x)
        msg.angular.z = float(angular_z)
        self._cmd_pub.publish(msg)

    @staticmethod
    def point_in_zone(px: float, py: float, zone: dict) -> bool:
        """
        zone dict 포맷 예시:
          { "type": "rect",   "x": 1.0, "y": 2.0, "w": 3.0, "h": 2.0 }
          { "type": "circle", "cx": 1.0, "cy": 2.0, "r": 1.5 }
          { "type": "polygon","points": [[x0,y0],[x1,y1],...] }
        """
        z_type = zone.get('type', 'rect')

        if z_type == 'rect':
            x, y, w, h = zone['x'], zone['y'], zone['w'], zone['h']
            return x <= px <= x + w and y <= py <= y + h

        if z_type == 'circle':
            dx = px - zone['cx']
            dy = py - zone['cy']
            return math.hypot(dx, dy) <= zone['r']

        if z_type == 'polygon':
            return NavCore._ray_cast(px, py, zone['points'])

        return False

    def get_zone_id(self, px: float, py: float, zones: dict) -> str | None:
        """
        zones: { zone_id: zone_dict, ... }
        반환: 해당 좌표가 속한 첫 번째 zone_id, 없으면 None
        """
        for zone_id, zone in zones.items():
            if self.point_in_zone(px, py, zone):
                return zone_id
        return None

    @staticmethod
    def _make_pose_stamped(x: float, y: float, yaw: float) -> PoseStamped:
        import math
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        return pose

    def _on_goal_accepted(self, future, done_callback):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self._node.get_logger().warn('[NavCore] 목표 거절됨')
            return
        self._current_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        if done_callback:
            result_future.add_done_callback(done_callback)

    @staticmethod
    def _ray_cast(px: float, py: float, polygon: list) -> bool:
        """Ray casting 알고리즘으로 폴리곤 내부 판단."""
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside
