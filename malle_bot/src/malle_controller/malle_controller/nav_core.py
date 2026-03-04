#!/usr/bin/env python3
import math
import os
import time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped, Twist
from std_msgs.msg import String as StringMsg
from nav2_msgs.action import NavigateToPose
from tf2_ros import Buffer, TransformListener

# 네비게이션 상수
MAX_LINEAR_VEL      = 0.15          # PID 최대 선속도 (m/s)
MAX_ANGULAR_VEL     = 1.0           # PID 최대 각속도 (rad/s)
ROTATE_FIRST_ANGLE  = math.radians(30)  # 이 각도 이상이면 제자리 회전 우선 (rad)
ZONE_CHECK_PERIOD   = 0.1           # zone 체크 타이머 주기 (s)
PID_PERIOD          = 0.02          # PID 루프 타이머 주기 (s)
NAV_RETRY_MAX       = 1             # Nav2 실패 시 최대 재시도 횟수


class NavCore:
    """Nav2 + cmd_vel 공용 엔진 (Node 믹스인용)."""

    def nav_core_init(self, node: Node):
        """미션 노드의 __init__에서 호출"""
        self._node = node

        self._nav_client = ActionClient(node, NavigateToPose, '/navigate_to_pose')
        self._cmd_pub = node.create_publisher(Twist, '/cmd_vel', 10)
        _ros_ns = os.getenv("ROBOT_NAMESPACE", "").strip("/")
        _topic_ns = f"/{_ros_ns}" if _ros_ns else ""
        self._nav_mode_pub = node.create_publisher(
            StringMsg, f"{_topic_ns}/nav_mode" if _topic_ns else "nav_mode", 10
        )
        _occ_topic = f"{_topic_ns}/occupied_poi_ids" if _topic_ns else "occupied_poi_ids"
        self._occ_sub = node.create_subscription(
            StringMsg, _occ_topic, self._on_occupied_poi_ids_cb, 10
        )

        self._current_goal_handle = None
        self._nav_gen = 0

        self._cx   = 0.0
        self._cy   = 0.0
        self._cyaw = 0.0
        self._pose_received = False
        self._tf_buffer   = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, node)
        self._base_frame  = 'base_footprint'

        self._nav_mode    = 'IDLE' # 'IDLE' | 'NAV2' | 'PID'
        self._goal_x      = 0.0
        self._goal_y      = 0.0
        self._goal_yaw    = 0.0
        self._nav_done_cb = None
        self._poi_id      = None   # 현재 목적지 POI ID (int), None이면 체크 없음
        self._waiting_at_zone  = False
        self._occupied_poi_ids: set[int] = set()

        self._zone_timer  = None
        self._pid_timer   = None
        self._retry_timer = None
        self._nav_retry_count = 0

        self._pid_int_dist  = 0.0
        self._pid_int_ang   = 0.0
        self._pid_prev_dist = 0.0
        self._pid_prev_ang  = 0.0
        self._pid_last_t    = 0.0

        self.pid_kp_lin = 0.5
        self.pid_ki_lin = 0.0
        self.pid_kd_lin = 0.1
        self.pid_kp_ang = 1.5
        self.pid_ki_ang = 0.0
        self.pid_kd_ang = 0.2

        # 목표 도달 판정 임계값 (m)
        self.pid_goal_threshold = 0.05

    def navigate_to_pose(self, x: float, y: float, yaw: float = 0.0,
                         done_callback=None, pid_zone_radius: float = 0.5,
                         poi_id: int | None = None):
        """
        Nav2로 목표 지점까지 이동. pid_zone_radius 안에 들어오면 PID로 전환.

        Parameters
        ----------
        done_callback : Callable[[bool], None]
            완료 시 success(bool) 를 인자로 호출됨
        pid_zone_radius : float
            PID 전환 거리 (m). 0 이하이면 PID 전환 없이 Nav2만 사용.
        """
        if not self._nav_client.wait_for_server(timeout_sec=3.0):
            self._node.get_logger().error('[NavCore] navigate_to_pose: 액션 서버 없음')
            if done_callback:
                done_callback(False)
            return

        self._nav_gen        += 1
        self._nav_retry_count = 0
        my_gen               = self._nav_gen
        self._goal_x         = x
        self._goal_y         = y
        self._goal_yaw       = yaw
        self._nav_done_cb    = done_callback
        self._pid_zone_radius = pid_zone_radius
        self._poi_id         = poi_id
        self._waiting_at_zone = False
        self._nav_mode       = 'NAV2'

        goal = NavigateToPose.Goal()
        goal.pose = self._make_pose_stamped(x, y, yaw)

        future = self._nav_client.send_goal_async(goal)
        future.add_done_callback(lambda f, g=my_gen: self._on_goal_accepted(f, g))

        self._restart_timer('zone')

    def cancel_navigation(self):
        """진행 중인 Nav2 목표 및 PID 루프를 모두 취소"""
        self._nav_mode = 'IDLE'
        self._pub_nav_mode('IDLE')
        self._poi_id = None
        self._waiting_at_zone = False
        self._cancel_timer('zone')
        self._cancel_timer('pid')
        if self._retry_timer is not None:
            self._retry_timer.cancel()
            self._retry_timer = None
        if self._current_goal_handle is not None:
            self._current_goal_handle.cancel_goal_async()
            self._current_goal_handle = None

    def cmd_vel(self, linear_x: float = 0.0, angular_z: float = 0.0):
        """Twist를 /cmd_vel에 직접 퍼블리시"""
        msg = Twist()
        msg.linear.x  = float(linear_x)
        msg.angular.z = float(angular_z)
        self._cmd_pub.publish(msg)

    def _update_pose_from_tf(self) -> bool:
        """TF에서 map → base_footprint 변환을 읽어 _cx/_cy/_cyaw 갱신. 성공 여부 반환."""
        try:
            t = self._tf_buffer.lookup_transform(
                'map', self._base_frame, rclpy.time.Time())
        except Exception:
            return False
        tr = t.transform.translation
        q  = t.transform.rotation
        self._cx = tr.x
        self._cy = tr.y
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self._cyaw = math.atan2(siny_cosp, cosy_cosp)
        self._pose_received = True
        return True

    def _zone_check(self):
        if self._nav_mode != 'NAV2':
            return
        if not self._update_pose_from_tf():
            return
        dist = math.hypot(self._goal_x - self._cx, self._goal_y - self._cy)
        if self._pid_zone_radius > 0 and dist <= self._pid_zone_radius:
            # 점유 체크: 다른 로봇이 같은 POI의 PID 구간에 있으면 대기
            if self._poi_id is not None and self._poi_id in self._occupied_poi_ids:
                if not self._waiting_at_zone:
                    self._node.get_logger().info(
                        f'[NavCore] poi_id={self._poi_id} 점유 중 — PID 진입 대기')
                    self._waiting_at_zone = True
                return  # 다음 zone_check에서 재시도
            if self._waiting_at_zone:
                self._node.get_logger().info('[NavCore] 점유 해제 — PID 진입')
            self._waiting_at_zone = False
            self._node.get_logger().info(
                f'[NavCore] PID 구간 진입 (dist={dist:.2f}m)')
            self._switch_to_pid()

    def _switch_to_pid(self):
        self._nav_mode = 'PID'
        self._pub_nav_mode('PID')
        self._cancel_timer('zone')

        # Nav2 취소
        if self._current_goal_handle is not None:
            self._current_goal_handle.cancel_goal_async()
            self._current_goal_handle = None

        # PID 상태 초기화
        self._pid_int_dist  = 0.0
        self._pid_int_ang   = 0.0
        self._pid_prev_dist = math.hypot(
            self._goal_x - self._cx, self._goal_y - self._cy)
        self._pid_prev_ang  = 0.0
        self._pid_last_t    = time.time()

        self._restart_timer('pid')

    def _pid_loop(self):
        if self._nav_mode != 'PID':
            return

        now = time.time()
        dt  = now - self._pid_last_t
        if dt <= 0.0:
            return
        self._pid_last_t = now

        if not self._update_pose_from_tf():
            self.cmd_vel(0.0, 0.0)
            return

        dx   = self._goal_x - self._cx
        dy   = self._goal_y - self._cy
        dist = math.hypot(dx, dy)

        # 목표 도달
        if dist < self.pid_goal_threshold:
            self.cmd_vel(0.0, 0.0)
            self._cancel_timer('pid')
            self._nav_mode = 'IDLE'
            self._pub_nav_mode('IDLE')
            self._node.get_logger().info('[NavCore] PID 목표 도달')
            if self._nav_done_cb:
                self._nav_done_cb(True)
            return

        # 각도 오차
        target_ang = math.atan2(dy, dx)
        ang_err    = math.atan2(
            math.sin(target_ang - self._cyaw),
            math.cos(target_ang - self._cyaw))

        # Linear PID
        d_dist = (dist - self._pid_prev_dist) / dt
        self._pid_int_dist += dist * dt
        linear = (self.pid_kp_lin * dist
                  + self.pid_ki_lin * self._pid_int_dist
                  + self.pid_kd_lin * d_dist)
        linear = float(max(0.0, min(linear, MAX_LINEAR_VEL)))

        # Angular PID
        d_ang = (ang_err - self._pid_prev_ang) / dt
        self._pid_int_ang += ang_err * dt
        angular = (self.pid_kp_ang * ang_err
                   + self.pid_ki_ang * self._pid_int_ang
                   + self.pid_kd_ang * d_ang)
        angular = float(max(-MAX_ANGULAR_VEL, min(angular, MAX_ANGULAR_VEL)))

        self._pid_prev_dist = dist
        self._pid_prev_ang  = ang_err

        # 방향이 크게 틀리면 제자리 회전 우선
        if abs(ang_err) > ROTATE_FIRST_ANGLE:
            linear = 0.0

        self.cmd_vel(linear, angular)

    def _on_goal_accepted(self, future, gen: int):
        if gen != self._nav_gen:
            return
        goal_handle = future.result()
        if not goal_handle.accepted:
            self._node.get_logger().warn('[NavCore] 목표 거절됨')
            return
        self._current_goal_handle = goal_handle
        goal_handle.get_result_async().add_done_callback(
            lambda f, g=gen: self._on_nav2_result(f, g))

    def _on_nav2_result(self, future, gen: int):
        if gen != self._nav_gen:
            return
        if self._nav_mode == 'PID':
            return
        self._cancel_timer('zone')
        success = (future.result().status == 4)

        if not success and self._nav_retry_count < NAV_RETRY_MAX:
            self._nav_retry_count += 1
            self._node.get_logger().warn(
                f'[NavCore] Nav2 실패, 1초 후 재시도 ({self._nav_retry_count}/{NAV_RETRY_MAX})')
            self._nav_mode = 'IDLE'
            self._pub_nav_mode('IDLE')
            self._retry_timer = self._node.create_timer(1.0, self._on_retry_timer)
            return

        self._nav_retry_count = 0
        self._nav_mode = 'IDLE'
        self._pub_nav_mode('IDLE')
        if self._nav_done_cb:
            self._nav_done_cb(success)

    def _on_retry_timer(self):
        self._retry_timer.cancel()
        self._retry_timer = None
        if self._nav_mode != 'IDLE':
            return
        self._nav_mode = 'NAV2'
        goal = NavigateToPose.Goal()
        goal.pose = self._make_pose_stamped(self._goal_x, self._goal_y, self._goal_yaw)
        future = self._nav_client.send_goal_async(goal)
        future.add_done_callback(lambda f, g=self._nav_gen: self._on_goal_accepted(f, g))
        self._restart_timer('zone')

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

    def _restart_timer(self, kind: str):
        """kind: 'zone' | 'pid'"""
        if kind == 'zone':
            self._cancel_timer('zone')
            self._zone_timer = self._node.create_timer(ZONE_CHECK_PERIOD, self._zone_check)
        elif kind == 'pid':
            self._cancel_timer('pid')
            self._pid_timer = self._node.create_timer(PID_PERIOD, self._pid_loop)

    def _cancel_timer(self, kind: str):
        if kind == 'zone' and self._zone_timer is not None:
            self._zone_timer.cancel()
            self._zone_timer = None
        elif kind == 'pid' and self._pid_timer is not None:
            self._pid_timer.cancel()
            self._pid_timer = None

    @staticmethod
    def _make_pose_stamped(x: float, y: float, yaw: float) -> PoseStamped:
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        return pose

    def _on_occupied_poi_ids_cb(self, msg: StringMsg):
        """bridge_node가 발행한 occupied POI ID 목록 수신 (콤마 구분 문자열)."""
        data = msg.data.strip()
        self._occupied_poi_ids = (
            {int(x) for x in data.split(',') if x.strip()} if data else set()
        )

    def _pub_nav_mode(self, mode: str):
        msg = StringMsg()
        msg.data = mode
        self._nav_mode_pub.publish(msg)

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
