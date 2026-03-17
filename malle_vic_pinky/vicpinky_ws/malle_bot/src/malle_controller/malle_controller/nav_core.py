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
ARRIVAL_THRESHOLD   = 0.05          # 도착 판정 거리 (m)


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
# AprilTag Config Loader
# ─────────────────────────────────────────────────────────────

def _load_apriltag_config(yaml_path: str | None = None) -> tuple[dict, tuple, float, dict]:
    """
    apriltag_poses.yaml 로드.

    Returns:
        tag_info:   { tag_id(int): {"yaw": float} }
        cam_params: (fx, fy, cx, cy)
        tag_size:   float (미터)
        corr_cfg:   { max_detect_dist, max_angle_deg, cooldown_sec }
    """
    if yaml_path is None:
        yaml_path = os.path.join(
            ament.get_package_share_directory('malle_controller'),
            'config', 'apriltag_poses.yaml'
        )
    try:
        import yaml
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        tag_info = {int(k): v for k, v in data.get('tags', {}).items()}
        cam = data.get('camera', {})
        cam_params = (
            float(cam.get('fx', 570.34)),
            float(cam.get('fy', 570.34)),
            float(cam.get('cx', 320.0)),
            float(cam.get('cy', 240.0)),
        )
        tag_size = float(data.get('tag_size', 0.05))
        corr = data.get('correction', {})
        corr_cfg = {
            'max_detect_dist': float(corr.get('max_detect_dist', 0.3)),
            'max_angle_deg':   float(corr.get('max_angle_deg',   10.0)),
            'cooldown_sec':    float(corr.get('cooldown_sec',    10.0)),
        }
        return tag_info, cam_params, tag_size, corr_cfg
    except Exception as e:
        print(f"[NavCore] apriltag_poses.yaml 로드 실패: {e} — 교정 비활성화")
        return {}, (570.34, 570.34, 320.0, 240.0), 0.05, {
            'max_detect_dist': 0.3, 'max_angle_deg': 10.0, 'cooldown_sec': 10.0,
        }


# ─────────────────────────────────────────────────────────────
# NavCore Mixin
# ─────────────────────────────────────────────────────────────

class NavCore:
    """Nav2 + PID + 웨이포인트 경로 계획 공용 엔진 (Node 믹스인용)."""

    def nav_core_init(self, node: Node, waypoint_yaml: str | None = None, robot_id: int | None = None, api=None):
        """미션 노드의 __init__에서 호출."""
        self._node = node
        self._nav_robot_id = robot_id
        self._nav_api = api 

        # cmd_vel 퍼블리셔 (relative topic — 노드 네임스페이스 자동 적용)
        self._cmd_pub = node.create_publisher(Twist, 'cmd_vel', 10)

        # Nav2 액션 클라이언트
        self._nav_client = ActionClient(node, NavigateToPose, '/navigate_to_pose')
        self._current_goal_handle = None
        self._nav_abort = False

        # 목표 상태
        self._nav_gen         = 0
        self._nav_retry_count = 0
        self._goal_x          = 0.0
        self._goal_y          = 0.0
        self._goal_yaw        = 0.0
        self._nav_done_cb     = None
        self._nav_mode        = 'IDLE'   # 'IDLE' | 'NAV2' | 'PID'
        self._pid_zone_radius = 0.3      # 기본 PID 전환 반경 (m)

        # 타이머
        self._zone_timer = None
        self._pid_timer  = None

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

        # AprilTag pose 교정 (Nav2 이동 중 yaw 재정렬)
        self._tag_detector        = None
        self._tag_frame           = None
        self._tag_frame_lock      = threading.Lock()
        self._tag_last_correction = None

        try:
            import cv2 as _cv2
            from pupil_apriltags import Detector as _Detector
            _tag_info, _cam_params, _tag_size, _corr_cfg = _load_apriltag_config()
            if _tag_info:
                from sensor_msgs.msg import Image as _RosImage
                from geometry_msgs.msg import PoseWithCovarianceStamped as _PWCS
                self._tag_cv2        = _cv2
                self._tag_detector   = _Detector(families='tag36h11', nthreads=2)
                self._tag_info       = _tag_info
                self._tag_cam_params = _cam_params
                self._tag_size       = _tag_size
                self._tag_corr_cfg   = _corr_cfg
                self._initialpose_pub = node.create_publisher(_PWCS, '/initialpose', 10)
                node.create_subscription(_RosImage, '/camera/image_raw', self._tag_image_cb, 1)
                node.create_timer(0.5, self._tag_correction_tick)
                node.get_logger().info(
                    f'[NavCore] AprilTag 교정 활성화 ({len(_tag_info)}개 태그)'
                )
        except Exception as e:
            node.get_logger().info(f'[NavCore] AprilTag 교정 비활성화: {e}')

    # ── Nav2 단순 이동 ────────────────────────────────────────

    def navigate_to_pose(self, x: float, y: float, yaw: float = 0.0,
                         done_callback=None, pid_zone_radius: float = 0.3):
        """Nav2 NavigateToPose 액션 전송. 목표 반경 내 진입 시 PID로 전환."""
        if not self._nav_client.wait_for_server(timeout_sec=3.0):
            self._node.get_logger().error('[NavCore] navigate_to_pose: 액션 서버 없음')
            if done_callback:
                done_callback(False)
            return

        self._nav_gen        += 1
        self._nav_retry_count = 0
        self._goal_x         = x
        self._goal_y         = y
        self._goal_yaw       = yaw
        self._nav_done_cb    = done_callback
        self._pid_zone_radius = pid_zone_radius
        self._nav_mode       = 'NAV2'

        goal = NavigateToPose.Goal()
        goal.pose = self._make_pose_stamped(x, y, yaw)

        my_gen = self._nav_gen
        future = self._nav_client.send_goal_async(goal)
        future.add_done_callback(lambda f, g=my_gen: self._on_goal_accepted(f, g))

        self._restart_timer('zone')

    # ── 웨이포인트 경유 이동 ──────────────────────────────────

    def navigate_via_waypoints(self, target_x: float, target_y: float,
                                target_yaw: float = 0.0,
                                done_callback=None,
                                pid_zone_radius: float = 0.0):
        """
        웨이포인트 그래프 경유 후 최종 좌표로 이동.

        흐름:
          1. 현재 위치 → 가장 가까운 시작 웨이포인트
          2. 목적지 (target_x, target_y) → 가장 가까운 끝 웨이포인트
          3. BFS로 시작 wp → 끝 wp 경로 계산
          4. 경유 wp 순차 이동
          5. 최종 목적지: pid_zone_radius > 0 이면 PID 전환, 아니면 Nav2 직접 이동
          6. done_callback 호출

        웨이포인트 그래프가 비어있으면 navigate_to_pose() 로 폴백.
        """
        if not self._wp_points:
            self._node.get_logger().warn(
                "[NavCore] 웨이포인트 그래프 없음 — 직접 이동으로 폴백"
            )
            self.navigate_to_pose(target_x, target_y, target_yaw, done_callback,
                                  pid_zone_radius=pid_zone_radius)
            return

        threading.Thread(
            target=self._waypoint_nav_thread,
            args=(target_x, target_y, target_yaw, done_callback, pid_zone_radius),
            daemon=True,
        ).start()

    def cancel_navigation(self):
        """진행 중인 Nav2 목표 및 웨이포인트 주행 취소."""
        self._nav_abort = True
        self._nav_mode  = 'IDLE'
        self._cancel_timer('zone')
        self._cancel_timer('pid')
        if self._current_goal_handle is not None:
            self._current_goal_handle.cancel_goal_async()
            self._current_goal_handle = None
        if self._nav_api and self._nav_robot_id:
            try:
                self._nav_api.clear_route(self._nav_robot_id)
            except Exception:
                pass            

    # ── Zone 체크 (Nav2 → PID 전환) ──────────────────────────

    def _zone_check(self):
        """
        목표 지점 반경 내 진입 시 Nav2 취소 → PID 모드 전환.
        ZONE_CHECK_PERIOD(0.1s) 마다 호출.
        """
        if self._nav_mode != 'NAV2':
            return

        curr_x, curr_y = self._get_current_position()
        if curr_x is None:
            return

        dist = math.hypot(self._goal_x - curr_x, self._goal_y - curr_y)
        if dist > self._pid_zone_radius:
            return

        # PID 모드 전환
        self._nav_mode = 'PID'
        self._cancel_timer('zone')

        if self._current_goal_handle is not None:
            self._current_goal_handle.cancel_goal_async()
            self._current_goal_handle = None

        self._node.get_logger().info(
            f'[NavCore] PID 모드 전환 (거리={dist:.3f}m, 반경={self._pid_zone_radius}m)'
        )
        self._restart_timer('pid')

    # ── PID 제어 루프 ─────────────────────────────────────────

    def _pid_loop(self):
        """
        목표 좌표를 향해 직접 cmd_vel 발행.
        PID_PERIOD(0.02s) 마다 호출.
        """
        curr_x, curr_y = self._get_current_position()
        if curr_x is None:
            return

        dx   = self._goal_x - curr_x
        dy   = self._goal_y - curr_y
        dist = math.hypot(dx, dy)

        # 도착 판정
        if dist < ARRIVAL_THRESHOLD:
            self.stop()
            self._cancel_timer('pid')
            self._nav_mode = 'IDLE'
            self._node.get_logger().info('[NavCore] PID 도착')
            if self._nav_done_cb:
                self._nav_done_cb(True)
                self._nav_done_cb = None
            return

        target_yaw = math.atan2(dy, dx)
        curr_yaw   = self._get_current_yaw()
        if curr_yaw is None:
            return

        yaw_err = math.atan2(
            math.sin(target_yaw - curr_yaw),
            math.cos(target_yaw - curr_yaw),
        )

        # 각도 오차 큰 경우 제자리 회전 우선
        if abs(yaw_err) > ROTATE_FIRST_ANGLE:
            linear_x = 0.0
        else:
            linear_x = min(MAX_LINEAR_VEL, 0.5 * dist)

        angular_z = max(-MAX_ANGULAR_VEL, min(MAX_ANGULAR_VEL, 2.0 * yaw_err))
        self.cmd_vel(linear_x, angular_z)

    # ── 웨이포인트 주행 스레드 ────────────────────────────────

    def _waypoint_nav_thread(self, target_x: float, target_y: float,
                              target_yaw: float, done_callback,
                              pid_zone_radius: float = 0.0):
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

        # ★ NEW — 경로를 malle_service로 전송
        if self._nav_api and self._nav_robot_id:
            try:
                route_coords = [
                    {"wp_id": wp, "x": self._wp_points[wp]["x"], "y": self._wp_points[wp]["y"]}
                    for wp in path
                ]
                route_coords.append({"wp_id": "_target", "x": target_x, "y": target_y})
                self._nav_api.report_route(self._nav_robot_id, route_coords)
            except Exception as e:
                self._node.get_logger().warn(f"[NavCore] 경로 전송 실패: {e}")        

        # 4. 경유 웨이포인트 순차 이동 (마지막 wp는 최종 목적지로 대체)
        for wp_id in path[:-1]:
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
            + (f" [PID r={pid_zone_radius:.2f}m]" if pid_zone_radius > 0 else "")
        )
        if pid_zone_radius > 0.0:
            success = self._blocking_navigate_with_pid(
                target_x, target_y, target_yaw, pid_zone_radius
            )
        else:
            success = self._blocking_navigate(target_x, target_y, target_yaw)

        # ★ NEW — 경로 완료 시 클리어
        if self._nav_api and self._nav_robot_id:
            try:
                self._nav_api.clear_route(self._nav_robot_id)
            except Exception:
                pass

        if done_callback:
            done_callback(success)

    def _blocking_navigate_with_pid(self, x: float, y: float, yaw: float = 0.0,
                                     pid_zone_radius: float = 0.3) -> bool:
        """
        Nav2로 이동 시작 후, pid_zone_radius 이내 진입 시 PID로 전환하는 블로킹 이동.

        흐름:
          1. 목표 상태 설정 + zone_check 타이머 시작
          2. Nav2 goal 전송
          3. Nav2 완료 or PID 전환을 폴링으로 대기
             - zone_check가 PID로 전환하면 Nav2가 취소되고 _pid_loop 시작
             - _pid_loop 도착 시 _nav_done_cb 호출 → done_event set
          4. 결과 반환
        """
        if not self._nav_client.wait_for_server(timeout_sec=10.0):
            self._node.get_logger().error('[NavCore] _blocking_navigate_with_pid: 액션 서버 없음')
            return False

        # 목표 상태 설정
        self._goal_x          = x
        self._goal_y          = y
        self._goal_yaw        = yaw
        self._pid_zone_radius = pid_zone_radius
        self._nav_mode        = 'NAV2'
        self._nav_abort       = False

        done_event   = threading.Event()
        result_store = [False]

        def _on_done(success):
            result_store[0] = bool(success)
            done_event.set()

        self._nav_done_cb = _on_done

        # Nav2 goal 전송
        goal = NavigateToPose.Goal()
        goal.pose = self._make_pose_stamped(x, y, yaw)
        send_future = self._nav_client.send_goal_async(goal)

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

        # zone_check 타이머 시작 (PID 전환 감시)
        self._restart_timer('zone')

        # Nav2 완료 또는 done_event(PID 완료) 대기
        while not result_future.done() and not done_event.is_set():
            if self._nav_abort:
                goal_handle.cancel_goal_async()
                self._cancel_timer('zone')
                self._cancel_timer('pid')
                self._nav_mode = 'IDLE'
                return False
            time.sleep(0.05)

        if done_event.is_set():
            # PID가 먼저 완료됨
            return result_store[0]

        # Nav2가 먼저 완료됨
        if self._nav_mode == 'PID':
            # zone_check가 Nav2를 취소하고 PID 진행 중 → PID 완료 대기
            done_event.wait()
            return result_store[0]

        # PID 전환 없이 Nav2 직접 완료
        self._cancel_timer('zone')
        self._nav_mode    = 'IDLE'
        self._nav_done_cb = None
        return result_future.result().status == 4

    def _blocking_navigate(self, x: float, y: float, yaw: float = 0.0) -> bool:
        if not self._nav_client.wait_for_server(timeout_sec=10.0):
            self._node.get_logger().error('[NavCore] 액션 서버 없음')
            return False

        self._nav_mode = 'NAV2'

        goal = NavigateToPose.Goal()
        goal.pose = self._make_pose_stamped(x, y, yaw)

        send_future = self._nav_client.send_goal_async(goal)

        deadline = time.time() + 10.0
        while not send_future.done():
            if self._nav_abort:
                self._nav_mode = 'IDLE'
                return False
            if time.time() > deadline:
                self._node.get_logger().error('[NavCore] goal 전송 타임아웃')
                self._nav_mode = 'IDLE'
                return False
            time.sleep(0.05)

        goal_handle = send_future.result()
        if not goal_handle.accepted:
            self._node.get_logger().warn('[NavCore] goal 거절됨')
            self._nav_mode = 'IDLE'
            return False

        self._current_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()

        while not result_future.done():
            if self._nav_abort:
                goal_handle.cancel_goal_async()
                self._nav_mode = 'IDLE'
                return False
            time.sleep(0.1)

        self._current_goal_handle = None
        self._nav_mode = 'IDLE'
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

        # edges는 단방향 정의이지만 양방향으로 취급
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

    def _get_current_yaw(self) -> float | None:
        """TF로 현재 로봇 yaw 반환. 실패 시 None."""
        if not self._has_tf:
            return None
        try:
            import rclpy.duration
            trans = self._tf_buffer.lookup_transform(
                'map', 'base_footprint', rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=1.0)
            )
            q = trans.transform.rotation
            return math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z),
            )
        except Exception as e:
            self._node.get_logger().warn(f'[NavCore] TF yaw 실패: {e}')
            return None

    # ── 타이머 관리 ───────────────────────────────────────────

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

    @staticmethod
    def _make_pose_stamped(x: float, y: float, yaw: float) -> PoseStamped:
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        return pose

    def _on_goal_accepted(self, future, gen: int):
        """비동기 navigate_to_pose 콜백."""
        if gen != self._nav_gen:
            return  # 이전 세대 goal — 무시
        goal_handle = future.result()
        if not goal_handle.accepted:
            self._node.get_logger().warn('[NavCore] 목표 거절됨')
            return
        self._current_goal_handle = goal_handle

    # ── AprilTag pose 교정 ────────────────────────────────────

    def _tag_image_cb(self, msg):
        """최신 gray 프레임을 버퍼에 저장."""
        if self._tag_detector is None:
            return
        import numpy as np
        frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        gray = self._tag_cv2.cvtColor(frame, self._tag_cv2.COLOR_RGB2GRAY)
        with self._tag_frame_lock:
            self._tag_frame = gray

    def _tag_correction_tick(self):
        """0.5s 타이머 — AprilTag 검출 후 yaw 교정 시도."""
        if self._tag_detector is None:
            return
        with self._tag_frame_lock:
            gray = self._tag_frame
        if gray is None:
            return
        self._try_tag_correction(gray)

    def _try_tag_correction(self, gray):
        now = self._node.get_clock().now()
        if self._tag_last_correction is not None:
            elapsed = (now - self._tag_last_correction).nanoseconds * 1e-9
            if elapsed < self._tag_corr_cfg['cooldown_sec']:
                return

        tags = self._tag_detector.detect(
            gray,
            estimate_tag_pose=True,
            camera_params=self._tag_cam_params,
            tag_size=self._tag_size,
        )

        for tag in tags:
            if tag.tag_id not in self._tag_info:
                continue

            tz = float(tag.pose_t[2].item())
            if tz > self._tag_corr_cfg['max_detect_dist']:
                self._node.get_logger().debug(
                    f'[NavCore] AprilTag ID:{tag.tag_id} 거리 초과 스킵 ({tz:.2f}m)'
                )
                continue

            tx = float(tag.pose_t[0].item())
            if abs(math.degrees(math.atan2(tx, tz))) > self._tag_corr_cfg['max_angle_deg']:
                self._node.get_logger().debug(
                    f'[NavCore] AprilTag ID:{tag.tag_id} 각도 초과 스킵'
                )
                continue

            curr_x, curr_y = self._get_current_position()
            if curr_x is None:
                self._node.get_logger().warn('[NavCore] AprilTag 교정: TF 없음, 스킵')
                continue

            robot_yaw = self._compute_yaw_from_tag(tag.tag_id, tag.pose_R)
            self._do_initialpose(curr_x, curr_y, robot_yaw)
            self._tag_last_correction = now
            self._node.get_logger().info(
                f'[NavCore] AprilTag ID:{tag.tag_id} | dist={tz:.2f}m '
                f'| yaw 교정 → {math.degrees(robot_yaw):.1f}°'
            )
            break  # 한 프레임에 하나의 태그만 처리

    def _compute_yaw_from_tag(self, tag_id: int, R_cam) -> float:
        """태그 회전 행렬 → 로봇의 map 기준 yaw."""
        tag_yaw = self._tag_info[tag_id]['yaw']
        tag_z   = R_cam[:, 2]
        angle_h = math.atan2(float(tag_z[0]), float(tag_z[2]))
        robot_yaw = tag_yaw + math.pi - angle_h
        return math.atan2(math.sin(robot_yaw), math.cos(robot_yaw))

    def _do_initialpose(self, x: float, y: float, yaw: float):
        """AMCL에 /initialpose 발행하여 yaw 교정."""
        from geometry_msgs.msg import PoseWithCovarianceStamped
        msg = PoseWithCovarianceStamped()
        msg.header.stamp    = self._node.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        cov = [0.0] * 36
        cov[0]  = 0.05 ** 2   # x 공분산
        cov[7]  = 0.05 ** 2   # y 공분산
        cov[35] = math.radians(5) ** 2  # yaw 공분산
        msg.pose.covariance = cov
        self._initialpose_pub.publish(msg)

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