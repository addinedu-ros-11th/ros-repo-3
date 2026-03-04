#!/usr/bin/env python3
import math
import os
import threading
import time
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose

import ament_index_python.packages as ament

# 네비게이션 상수
MAX_LINEAR_VEL      = 0.15          # PID 최대 선속도 (m/s)
MAX_ANGULAR_VEL     = 1.0           # PID 최대 각속도 (rad/s)
ROTATE_FIRST_ANGLE  = math.radians(30)  # 이 각도 이상이면 제자리 회전 우선 (rad)
ZONE_CHECK_PERIOD   = 0.1           # zone 체크 타이머 주기 (s)
PID_PERIOD          = 0.02          # PID 루프 타이머 주기 (s)
NAV_RETRY_MAX       = 1             # Nav2 실패 시 최대 재시도 횟수


# ─────────────────────────────────────────────────────────────
# Waypoint Graph Loader
# ─────────────────────────────────────────────────────────────

def _load_waypoint_graph(yaml_path: str | None = None) -> tuple[dict, dict]:
    """
    waypoint_graph.yaml 로드.

    Returns:
        points: { wp_id: {"x": float, "y": float} }
        edges:  { wp_id: [wp_id, ...] }  (단방향 — BFS에서 양방향 취급)
    """
    if yaml_path is None:
        yaml_path = os.path.join(
            os.path.dirname(__file__), '..', 'config', 'waypoint_graph.yaml'
        )

    try:
        import yaml
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        points = {k: {"x": float(v["x"]), "y": float(v["y"])}
                  for k, v in data.get("waypoints", {}).items()}
        edges = {k: list(v) for k, v in data.get("edges", {}).items()}
        return points, edges
    except Exception as e:
        print(f"[NavCore] waypoint_graph.yaml 로드 실패: {e} — 빈 그래프 사용")
        return {}, {}


# ─────────────────────────────────────────────────────────────
# NavCore Mixin
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# Waypoint Graph Loader
# ─────────────────────────────────────────────────────────────

def _load_waypoint_graph(yaml_path: str | None = None) -> tuple[dict, dict]:
    """
    waypoint_graph.yaml 로드.

    Returns:
        points: { wp_id: {"x": float, "y": float} }
        edges:  { wp_id: [wp_id, ...] }  (단방향 — BFS에서 양방향 취급)
    """
    if yaml_path is None:
        yaml_path = os.path.join(
            ament.get_package_share_directory('malle_controller'),
            'config', 'waypoint_graph.yaml'
        )

    try:
        import yaml
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        points = {k: {"x": float(v["x"]), "y": float(v["y"])}
                  for k, v in data.get("waypoints", {}).items()}
        edges = {k: list(v) for k, v in data.get("edges", {}).items()}
        return points, edges
    except Exception as e:
        print(f"[NavCore] waypoint_graph.yaml 로드 실패: {e} — 빈 그래프 사용")
        return {}, {}


# ─────────────────────────────────────────────────────────────
# NavCore Mixin
# ─────────────────────────────────────────────────────────────

class NavCore:
    """Nav2 + cmd_vel + 웨이포인트 경로 계획 공용 엔진 (Node 믹스인용)."""

    def nav_core_init(self, node: Node, waypoint_yaml: str | None = None):
        """미션 노드의 __init__에서 호출"""
        self._node = node

        self._nav_client = ActionClient(node, NavigateToPose, '/navigate_to_pose')
        self._cmd_pub = node.create_publisher(Twist, _ns('cmd_vel'), 10)

        self._current_goal_handle = None
        self._nav_abort = False  # 웨이포인트 주행 중단 플래그

        # 웨이포인트 그래프 로드
        self._wp_points, self._wp_edges = _load_waypoint_graph(waypoint_yaml)
        node.get_logger().info(
            f"[NavCore] 웨이포인트 {len(self._wp_points)}개 로드 완료"
        )

        # TF (현재 위치 파악용)
        try:
            from tf2_ros.buffer import Buffer
            from tf2_ros.transform_listener import TransformListener
            self._tf_buffer = Buffer()
            self._tf_listener = TransformListener(self._tf_buffer, node)
            self._has_tf = True
        except Exception:
            self._has_tf = False
            node.get_logger().warn("[NavCore] TF2 사용 불가 — 현재 위치 추정 비활성화")

    # ── 기존 단순 이동 ────────────────────────────────────────

    def navigate_to_pose(self, x: float, y: float, yaw: float = 0.0,
                         done_callback=None):
        """Nav2 NavigateToPose 액션 직접 전송 (경유지 없음)."""
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
        self._nav_mode       = 'NAV2'

        goal = NavigateToPose.Goal()
        goal.pose = self._make_pose_stamped(x, y, yaw)

        future = self._nav_client.send_goal_async(goal)
        future.add_done_callback(lambda f, g=my_gen: self._on_goal_accepted(f, g))

        self._restart_timer('zone')

    # ── 웨이포인트 경유 이동 (핵심 추가) ─────────────────────

    def navigate_via_waypoints(self, target_x: float, target_y: float,
                                target_yaw: float = 0.0,
                                done_callback=None):
        """
        웨이포인트 그래프 경유 후 최종 좌표로 이동.

        흐름:
          1. 현재 위치 → 가장 가까운 시작 웨이포인트
          2. 목적지 (target_x, target_y) → 가장 가까운 끝 웨이포인트
          3. BFS로 시작 wp → 끝 wp 경로 계산
          4. 경유 wp 순차 이동
          5. 마지막에 실제 (target_x, target_y, target_yaw) 로 최종 이동
          6. done_callback 호출

        웨이포인트 그래프가 비어있으면 navigate_to_pose() 로 폴백.
        """
        if not self._wp_points:
            self._node.get_logger().warn(
                "[NavCore] 웨이포인트 그래프 없음 — 직접 이동으로 폴백"
            )
            self.navigate_to_pose(target_x, target_y, target_yaw, done_callback)
            return

        threading.Thread(
            target=self._waypoint_nav_thread,
            args=(target_x, target_y, target_yaw, done_callback),
            daemon=True,
        ).start()

    # ── 웨이포인트 경유 이동 (핵심 추가) ─────────────────────

    def navigate_via_waypoints(self, target_x: float, target_y: float,
                                target_yaw: float = 0.0,
                                done_callback=None):
        """
        웨이포인트 그래프 경유 후 최종 좌표로 이동.

        흐름:
          1. 현재 위치 → 가장 가까운 시작 웨이포인트
          2. 목적지 (target_x, target_y) → 가장 가까운 끝 웨이포인트
          3. BFS로 시작 wp → 끝 wp 경로 계산
          4. 경유 wp 순차 이동
          5. 마지막에 실제 (target_x, target_y, target_yaw) 로 최종 이동
          6. done_callback 호출

        웨이포인트 그래프가 비어있으면 navigate_to_pose() 로 폴백.
        """
        if not self._wp_points:
            self._node.get_logger().warn(
                "[NavCore] 웨이포인트 그래프 없음 — 직접 이동으로 폴백"
            )
            self.navigate_to_pose(target_x, target_y, target_yaw, done_callback)
            return

        threading.Thread(
            target=self._waypoint_nav_thread,
            args=(target_x, target_y, target_yaw, done_callback),
            daemon=True,
        ).start()

    def cancel_navigation(self):
        """진행 중인 Nav2 목표 및 웨이포인트 주행 취소."""
        self._nav_abort = True
        if self._current_goal_handle is not None:
            self._current_goal_handle.cancel_goal_async()
            self._current_goal_handle = None

    # ── 웨이포인트 주행 스레드 ────────────────────────────────

    def _waypoint_nav_thread(self, target_x: float, target_y: float,
                              target_yaw: float, done_callback):
        self._nav_abort = False

        # 1. 현재 위치 파악
        curr_x, curr_y = self._get_current_position()
        if curr_x is None:
            self._node.get_logger().warn(
                "[NavCore] 현재 위치 파악 실패 — 직접 이동으로 폴백"
            )
            self._blocking_navigate(target_x, target_y, target_yaw)
            if done_callback:
                done_callback(None)
            return

        # 2. 시작/끝 웨이포인트 찾기
        start_wp, start_dist = self._nearest_waypoint(curr_x, curr_y)
        end_wp,   end_dist   = self._nearest_waypoint(target_x, target_y)

        self._node.get_logger().info(
            f"[NavCore] {start_wp}({start_dist:.2f}m) → "
            f"{end_wp}({end_dist:.2f}m) | 목적지: ({target_x:.3f}, {target_y:.3f})"
        )

        # 3. BFS 경로
        path = self._bfs(start_wp, end_wp)
        if not path:
            self._node.get_logger().warn(
                f"[NavCore] 경로 없음 ({start_wp}→{end_wp}) — 직접 이동"
            )
            self._blocking_navigate(target_x, target_y, target_yaw)
            if done_callback:
                done_callback(None)
            return

        self._node.get_logger().info(
            f"[NavCore] 경로: {' → '.join(path)} → 최종목적지"
        )

        # 4. 경유 웨이포인트 순차 이동 (마지막 wp 제외 — 최종 목적지로 대체)
        waypoints_to_visit = path[:-1]  # 마지막 wp는 최종 목적지로 대체

        for wp_id in waypoints_to_visit:
            if self._nav_abort:
                self._node.get_logger().info("[NavCore] 웨이포인트 주행 중단")
                return

            wp = self._wp_points[wp_id]
            self._node.get_logger().info(f"[NavCore] → 웨이포인트 [{wp_id}]")

            success = self._blocking_navigate(wp["x"], wp["y"], 0.0)
            if not success:
                self._node.get_logger().warn(
                    f"[NavCore] [{wp_id}] 이동 실패 — 주행 중단"
                )
                if done_callback:
                    done_callback(None)
                return

        if self._nav_abort:
            return

        # 5. 최종 목적지로 이동
        self._node.get_logger().info(
            f"[NavCore] → 최종 목적지 ({target_x:.3f}, {target_y:.3f})"
        )
        success = self._blocking_navigate(target_x, target_y, target_yaw)

        # 6. 완료 콜백
        if done_callback:
            done_callback(success)

    def _blocking_navigate(self, x: float, y: float, yaw: float = 0.0) -> bool:
        if not self._nav_client.wait_for_server(timeout_sec=10.0):
            self._node.get_logger().error('[NavCore] 액션 서버 없음')
            return False

        goal = NavigateToPose.Goal()
        goal.pose = self._make_pose_stamped(x, y, yaw)

        send_future = self._nav_client.send_goal_async(goal)

        # executor가 MultiThreadedExecutor이므로 이미 스핀 중 — 폴링으로 대기
        deadline = time.time() + 10.0
        while not send_future.done():
            if self._nav_abort:
                return False
            if time.time() > deadline:
                self._node.get_logger().error('[NavCore] goal 전송 타임아웃')
                return False
            time.sleep(0.05)

        goal_handle = send_future.result()
        if not goal_handle.accepted:
            self._node.get_logger().warn('[NavCore] goal 거절됨')
            return False

        self._current_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()

        # 주행 완료 대기 — 타임아웃 없이 폴링 (주행 시간 예측 불가)
        while not result_future.done():
            if self._nav_abort:
                goal_handle.cancel_goal_async()
                return False
            time.sleep(0.1)

        self._current_goal_handle = None
        return result_future.result().status == 4

    # ── 웨이포인트 유틸 ──────────────────────────────────────

    def _nearest_waypoint(self, x: float, y: float) -> tuple[str, float]:
        """가장 가까운 웨이포인트 이름과 거리 반환."""
        best_id, best_dist = None, float('inf')
        for wp_id, coord in self._wp_points.items():
            d = math.hypot(coord['x'] - x, coord['y'] - y)
            if d < best_dist:
                best_dist = d
                best_id = wp_id
        return best_id, best_dist

    def _bfs(self, start: str, goal: str) -> list[str] | None:
        """BFS로 웨이포인트 그래프에서 start → goal 최단 경로."""
        if start == goal:
            return [start]

        # edges는 단방향으로 정의되어 있지만 양방향으로 취급
        adj: dict[str, set[str]] = {}
        for wp_id, neighbors in self._wp_edges.items():
            adj.setdefault(wp_id, set()).update(neighbors)
            for nb in neighbors:
                adj.setdefault(nb, set()).add(wp_id)

        visited = {start}
        queue = deque([[start]])

        while queue:
            path = queue.popleft()
            node = path[-1]
            for nb in adj.get(node, []):
                if nb not in visited:
                    new_path = path + [nb]
                    if nb == goal:
                        return new_path
                    visited.add(nb)
                    queue.append(new_path)
        return None

    def _get_current_position(self) -> tuple[float | None, float | None]:
        """TF로 현재 로봇 위치 반환. 실패 시 (None, None)."""
        if not self._has_tf:
            return None, None
        try:
            import rclpy.duration
            trans = self._tf_buffer.lookup_transform(
                'map', 'base_footprint', rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=1.0)
            )
            return (
                trans.transform.translation.x,
                trans.transform.translation.y,
            )
        except Exception as e:
            self._node.get_logger().warn(f'[NavCore] TF 실패: {e}')
            return None, None

    # ── 기타 유틸 ─────────────────────────────────────────────

    def cmd_vel(self, linear_x: float = 0.0, angular_z: float = 0.0):
        """Twist를 /cmd_vel에 직접 퍼블리시."""
        msg = Twist()
        msg.linear.x  = float(linear_x)
        msg.angular.z = float(angular_z)
        self._cmd_pub.publish(msg)

    def stop(self):
        """로봇 정지 (cmd_vel 0 발행)."""
        self.cmd_vel(0.0, 0.0)

    @staticmethod
    def point_in_zone(px: float, py: float, zone: dict) -> bool:
        z_type = zone.get('type', 'rect')
        if z_type == 'rect':
            x, y, w, h = zone['x'], zone['y'], zone['w'], zone['h']
            return x <= px <= x + w and y <= py <= y + h
        if z_type == 'circle':
            return math.hypot(px - zone['cx'], py - zone['cy']) <= zone['r']
        if z_type == 'polygon':
            return NavCore._ray_cast(px, py, zone['points'])
        return False

    def get_zone_id(self, px: float, py: float, zones: dict) -> str | None:
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

    def _on_goal_accepted(self, future, done_callback):
        """비동기 navigate_to_pose용 콜백 (기존 호환)."""
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
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > py) != (yj > py)) and \
               (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside