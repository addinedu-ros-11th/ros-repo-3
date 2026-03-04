#!/usr/bin/env python3
"""
nav_node.py — Headless ROS2 웨이포인트 네비게이션 노드

기능:
  1. /task_command 토픽 구독 → JSON 명령 수신
  2. BFS 최단 경로 계산 → Nav2 순차 주행
  3. POI 이름 → 웨이포인트 자동 매핑 (좌표 근접 매칭)
  4. RViz 웨이포인트 마커 발행

명령 JSON 포맷:
  {"action": "navigate_to_waypoint", "waypoint": "p3"}
  {"action": "navigate_to_poi", "poi_name": "스타벅스", "x": 1.20, "y": 1.95}
  {"action": "navigate_to_pose", "x": 1.20, "y": 1.95}
  {"action": "emergency_stop"}

데이터 흐름:
  malle_service → bridge_node (task_command 발행) → 이 노드 (구독 → Nav2 주행)
"""

import json
import math
import os
import threading
import time
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.executors import MultiThreadedExecutor
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from visualization_msgs.msg import Marker, MarkerArray

from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult

from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener


# =====================================================================
# [1. 맵 데이터 및 통로 설정]
# =====================================================================
POINTS = {
    "p0":       {"x": 0.391, "y": 0.351},
    "p1":       {"x": 0.391, "y": 0.845},
    "p2":       {"x": 0.396, "y": 1.950},
    "p3":       {"x": 1.200, "y": 1.950},
    "p4":       {"x": 1.199, "y": 0.850},
    "p5":       {"x": 1.650, "y": 0.850},
    "p6":       {"x": 2.074, "y": 0.856},
    "p7":       {"x": 1.200, "y": 1.400},
    "p8":       {"x": 2.100, "y": 0.247},
    "p9":       {"x": 2.397, "y": 0.254},
    "p10":      {"x": 2.388, "y": 1.297},
    "p11":      {"x": 1.804, "y": 1.950},
    "p12":      {"x": 0.917, "y": 0.300},
    "p13":      {"x": 0.917, "y": 0.845},
    "p14":      {"x": 1.199, "y": 0.300},
    "p15":      {"x": 2.000, "y": 1.400},
    "p16":      {"x": 1.800, "y": 0.300},
    "charger1": {"x": 0.250, "y": 0.650},
    "charger2": {"x": 0.450, "y": 0.650},
    "p2-1":     {"x": 0.396, "y": 1.700},
    "p3-1":     {"x": 1.200, "y": 1.700},
    "p11-1":    {"x": 1.804, "y": 1.700},
}

WAYPOINT_GRAPH = {
    'p0':    ['p1', 'charger1', 'charger2'],
    'p1':    ['p0', 'p2-1', 'p13'],
    'p2':    ['p1', 'p3', 'p2-1'],
    'p3':    ['p2', 'p4', 'p7'],
    'p4':    ['p3', 'p5', 'p13'],
    'p5':    ['p4', 'p6'],
    'p6':    ['p5', 'p8', 'p15'],
    'p7':    ['p3-1', 'p4'],
    'p8':    ['p6', 'p9', 'p16'],
    'p9':    ['p8'],
    'p10':   ['p7', 'p15'],
    'p11':   ['p3'],
    'p12':   ['p13', 'p14'],
    'p13':   ['p1', 'p12', 'p4'],
    'p14':   ['p12', 'p16'],
    'p15':   ['p6', 'p11-1', 'p10'],
    'p16':   ['p8', 'p14'],
    'p2-1':  ['p3-1', 'p1'],
    'p3-1':  ['p11-1', 'p7'],
    'p11-1': ['p15', 'p3-1', 'p11'],
}


# =====================================================================
# [2. POI → 웨이포인트 매핑 테이블]
# =====================================================================
#
# malle_service에서 POI 이름(가게 이름)으로 명령이 올 때,
# 해당 POI에 가장 가까운 웨이포인트로 매핑합니다.
#
# 방법 1: 직접 매핑 (정확한 매핑이 필요한 경우 여기에 추가)
#   키: POI 이름 (malle_service DB의 poi.name과 일치)
#   값: 웨이포인트 이름 (POINTS 딕셔너리의 키)
#
# 방법 2: 좌표 근접 매칭 (아래 테이블에 없으면 자동 매칭)
#   POI와 함께 전달된 (x, y) 좌표로 가장 가까운 웨이포인트를 자동 탐색
#
# ★ 가게를 추가할 때 여기에 한 줄만 추가하면 됩니다 ★
POI_TO_WAYPOINT: dict[str, str] = {
    # "가게이름": "웨이포인트",   ← 이 형식으로 추가
    # 예시:
    # "스타벅스": "p3",
    # "올리브영": "p11",
    # "충전소A": "charger1",
    # "충전소B": "charger2",
}

# =====================================================================
# [2-1. POI 매핑 거리 임계값]
# =====================================================================
# 좌표 자동 매칭 시 이 거리(m) 이내의 웨이포인트만 매칭합니다.
# 이 거리 밖이면 매칭 실패로 처리합니다.
POI_MATCH_THRESHOLD_M = 0.5


# =====================================================================
# [3. Nav2 Waypoint Navigator Node (Headless)]
# =====================================================================
class Nav2WaypointNavigator(Node):
    """
    PyQt6 없이 동작하는 순수 ROS2 노드.
    /task_command 토픽으로 목적지 명령을 받아 BFS 경로 계산 후 Nav2 주행.
    """

    def __init__(self):
        super().__init__('nav2_waypoint_navigator')

        # ── Nav2 ────────────────────────────────────────────────────
        self.nav = BasicNavigator()
        self.current_target_name = ""
        self.abort_flag = False
        self._nav_busy = False  # 주행 중 중복 명령 방지

        # ── TF2 (현재 위치 확인용) ──────────────────────────────────
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # ── RViz 마커 ──────────────────────────────────────────────
        self.marker_pub = self.create_publisher(MarkerArray, 'waypoint_markers', 10)
        self.create_timer(0.5, self.publish_markers)

        # ── 명령 수신 토픽 구독 ──────────────────────────────────────
        # bridge_node가 발행하는 task_command 토픽을 구독
        # 네임스페이스가 있으면 /{namespace}/task_command, 없으면 /task_command
        ns = os.getenv("ROBOT_NAMESPACE", "")
        topic_name = f"/{ns}/task_command" if ns else "/task_command"

        self.create_subscription(String, topic_name, self._on_command, 10)
        self.get_logger().info(f'📡 명령 대기 중: {topic_name}')

        # ── 상태 피드백 발행 ──────────────────────────────────────────
        # 주행 상태를 bridge_node나 다른 노드에 알려주기 위한 토픽
        status_topic = f"/{ns}/nav_status" if ns else "/nav_status"
        self.status_pub = self.create_publisher(String, status_topic, 10)

        # ── Nav2 활성화 대기 (백그라운드) ────────────────────────────
        self.get_logger().info('⏳ Nav2 활성화 대기 중...')
        threading.Thread(target=self._wait_for_nav2, daemon=True).start()

    # =================================================================
    # [4. 명령 수신 및 디스패치]
    # =================================================================
    def _on_command(self, msg: String):
        """task_command 토픽 콜백: JSON 명령을 파싱하여 적절한 액션 실행"""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'❌ JSON 파싱 실패: {e}')
            return

        action = data.get('action', '')
        self.get_logger().info(f'📨 명령 수신: {action} | {data}')

        if action == 'navigate_to_waypoint':
            # 웨이포인트 이름으로 직접 주행
            waypoint = data.get('waypoint', '')
            self._handle_navigate_to_waypoint(waypoint)

        elif action == 'navigate_to_poi':
            # POI 이름 + 좌표 → 웨이포인트 매핑 후 주행
            poi_name = data.get('poi_name', '')
            x = data.get('x')
            y = data.get('y')
            self._handle_navigate_to_poi(poi_name, x, y)

        elif action == 'navigate_to_pose':
            # 좌표 → 가장 가까운 웨이포인트 매핑 후 주행
            x = data.get('x')
            y = data.get('y')
            self._handle_navigate_to_pose(x, y)

        elif action == 'emergency_stop':
            self.emergency_stop()

        else:
            self.get_logger().warn(f'⚠️ 알 수 없는 액션: {action}')

    # =================================================================
    # [5. 명령 핸들러]
    # =================================================================
    def _handle_navigate_to_waypoint(self, waypoint: str):
        """웨이포인트 이름으로 직접 주행"""
        if waypoint not in POINTS:
            self.get_logger().error(f'❌ 알 수 없는 웨이포인트: {waypoint}')
            self._publish_status('error', f'unknown waypoint: {waypoint}')
            return
        self._start_navigation([waypoint])

    def _handle_navigate_to_poi(self, poi_name: str, x: float = None, y: float = None):
        """
        POI 이름으로 주행.
        
        매핑 우선순위:
          1. POI_TO_WAYPOINT 테이블에 직접 매핑이 있으면 사용
          2. 없으면 (x, y) 좌표로 가장 가까운 웨이포인트 자동 매칭
        """
        self.get_logger().info(f'🏪 POI 명령: name="{poi_name}", x={x}, y={y}')

        # 1단계: 직접 매핑 테이블 확인
        if poi_name in POI_TO_WAYPOINT:
            target_wp = POI_TO_WAYPOINT[poi_name]
            self.get_logger().info(f'  → 직접 매핑: "{poi_name}" → {target_wp}')
            self._start_navigation([target_wp])
            return

        # 2단계: 좌표로 가장 가까운 웨이포인트 자동 매칭
        if x is not None and y is not None:
            nearest_wp, dist = self._find_nearest_waypoint(x, y)
            if nearest_wp and dist <= POI_MATCH_THRESHOLD_M:
                self.get_logger().info(
                    f'  → 좌표 매칭: ({x:.3f}, {y:.3f}) → {nearest_wp} (거리: {dist:.3f}m)'
                )
                self._start_navigation([nearest_wp])
                return
            else:
                self.get_logger().warn(
                    f'  ⚠️ 가장 가까운 웨이포인트 {nearest_wp}이(가) '
                    f'{dist:.3f}m 떨어져 있음 (임계값: {POI_MATCH_THRESHOLD_M}m). '
                    f'직접 좌표로 이동합니다.'
                )
                # 임계값 초과 시에도 가장 가까운 웨이포인트로 이동
                # (필요 시 아래 줄을 주석 처리하고 Nav2 직접 좌표 이동으로 변경 가능)
                self._start_navigation([nearest_wp])
                return

        # 매핑 실패
        self.get_logger().error(
            f'❌ POI "{poi_name}" 매핑 실패: '
            f'POI_TO_WAYPOINT 테이블에 없고, 좌표도 없음'
        )
        self._publish_status('error', f'POI mapping failed: {poi_name}')

    def _handle_navigate_to_pose(self, x: float, y: float):
        """좌표 → 가장 가까운 웨이포인트 매핑 후 주행"""
        if x is None or y is None:
            self.get_logger().error('❌ 좌표 누락 (x, y 필수)')
            return

        nearest_wp, dist = self._find_nearest_waypoint(x, y)
        if nearest_wp:
            self.get_logger().info(
                f'📍 좌표 ({x:.3f}, {y:.3f}) → 웨이포인트 {nearest_wp} (거리: {dist:.3f}m)'
            )
            self._start_navigation([nearest_wp])
        else:
            self.get_logger().error('❌ 매칭 가능한 웨이포인트 없음')

    # =================================================================
    # [6. 웨이포인트 매핑 유틸리티]
    # =================================================================
    def _find_nearest_waypoint(self, x: float, y: float) -> tuple[str | None, float]:
        """
        (x, y) 좌표에 가장 가까운 웨이포인트를 찾습니다.
        
        Returns:
            (웨이포인트 이름, 거리) 튜플. 웨이포인트가 없으면 (None, inf).
        """
        nearest = None
        min_dist = float('inf')
        for name, coord in POINTS.items():
            dist = math.hypot(coord['x'] - x, coord['y'] - y)
            if dist < min_dist:
                min_dist = dist
                nearest = name
        return nearest, min_dist

    # =================================================================
    # [7. BFS 경로 탐색]
    # =================================================================
    def find_shortest_path(self, start: str, goal: str) -> list[str] | None:
        """BFS로 WAYPOINT_GRAPH에서 start → goal 최단 경로 탐색"""
        if start == goal:
            return [start]

        explored = set()
        queue = deque([[start]])

        while queue:
            path = queue.popleft()
            node = path[-1]

            if node not in explored:
                for neighbour in WAYPOINT_GRAPH.get(node, []):
                    new_path = list(path) + [neighbour]
                    if neighbour == goal:
                        return new_path
                    queue.append(new_path)
                explored.add(node)
        return None

    # =================================================================
    # [8. 현재 위치 파악]
    # =================================================================
    def get_current_waypoint(self) -> str | None:
        """TF를 통해 현재 로봇 위치에서 가장 가까운 웨이포인트 반환"""
        try:
            trans = self.tf_buffer.lookup_transform(
                'map', 'base_footprint', Time(),
                timeout=rclpy.duration.Duration(seconds=1.0)
            )
            curr_x = trans.transform.translation.x
            curr_y = trans.transform.translation.y

            nearest, _ = self._find_nearest_waypoint(curr_x, curr_y)
            return nearest
        except Exception as e:
            self.get_logger().warn(f'⚠️ TF 위치 확인 실패: {e}')
            return None

    # =================================================================
    # [9. Nav2 주행 실행]
    # =================================================================
    def _start_navigation(self, target_list: list[str]):
        """주행 스레드를 시작 (GUI 대신 토픽 명령으로 호출됨)"""
        if self._nav_busy:
            self.get_logger().warn('⚠️ 이미 주행 중입니다. 현재 주행을 취소하고 새 목적지로 이동합니다.')
            self.emergency_stop()
            time.sleep(0.5)  # 취소 안정화 대기

        nav_thread = threading.Thread(
            target=self.execute_navigation,
            args=(target_list,),
            daemon=True,
        )
        nav_thread.start()

    def execute_navigation(self, target_list: list[str]):
        """목적지 리스트 순서대로 BFS 경로 계산 → Nav2 주행 실행"""
        self.abort_flag = False
        self._nav_busy = True
        start_wp = self.get_current_waypoint()

        if not start_wp:
            self.get_logger().error('❌ 로봇의 현재 위치를 파악할 수 없습니다.')
            self._publish_status('error', 'cannot determine current position')
            self._nav_busy = False
            return

        self.get_logger().info(
            f'🏁 주행 시작: 현재 위치={start_wp} → 목적지={" → ".join(target_list)}'
        )
        self._publish_status('started', f'{start_wp} → {" → ".join(target_list)}')
        current_wp = start_wp

        for final_target in target_list:
            if self.abort_flag:
                break

            path_sequence = self.find_shortest_path(current_wp, final_target)
            if not path_sequence:
                self.get_logger().error(f'❌ {final_target}로 가는 경로를 찾을 수 없습니다.')
                self._publish_status('error', f'no path to {final_target}')
                continue

            self.get_logger().info(
                f'🎯 목적지 [{final_target}] | 경로: {" → ".join(path_sequence)}'
            )

            for i in range(1, len(path_sequence)):
                if self.abort_flag:
                    break

                next_pt = path_sequence[i]
                self.current_target_name = next_pt
                goal_pose = self._create_pose(next_pt)

                self.get_logger().info(f'  → [{next_pt}] 이동 중...')
                self._publish_status('navigating', next_pt)
                self.nav.goToPose(goal_pose)

                while not self.nav.isTaskComplete():
                    if self.abort_flag:
                        self.nav.cancelTask()
                        self.get_logger().info('🛑 주행 강제 취소!')
                        self._publish_status('cancelled', '')
                        self._nav_busy = False
                        return
                    time.sleep(0.1)

                result = self.nav.getResult()
                if result != TaskResult.SUCCEEDED:
                    self.get_logger().error(f'❌ [{next_pt}] 이동 실패 (Nav2 오류)')
                    self._publish_status('error', f'nav2 failed at {next_pt}')
                    self._nav_busy = False
                    return

                time.sleep(0.5)

            if self.abort_flag:
                break
            self.get_logger().info(f'✅ 목적지 [{final_target}] 도착!')
            self._publish_status('arrived', final_target)
            time.sleep(2.0)
            current_wp = final_target

        if not self.abort_flag:
            self.get_logger().info('✨ 모든 미션 완료!')
            self._publish_status('completed', '')
        self.current_target_name = ""
        self._nav_busy = False

    # =================================================================
    # [10. 헬퍼 함수들]
    # =================================================================
    def _create_pose(self, pt_name: str) -> PoseStamped:
        """웨이포인트 좌표로 PoseStamped 메시지 생성"""
        coord = POINTS[pt_name]
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = coord['x']
        pose.pose.position.y = coord['y']
        pose.pose.orientation.w = 1.0
        return pose

    def emergency_stop(self):
        """긴급 정지"""
        self.abort_flag = True
        self.nav.cancelTask()
        self.get_logger().info('🛑 긴급 정지 실행')
        self._publish_status('emergency_stop', '')

    def _wait_for_nav2(self):
        """Nav2 활성화 대기 (백그라운드 스레드)"""
        self.nav.waitUntilNav2Active()
        self.get_logger().info('✅ Nav2 준비 완료! 명령 대기 중.')

    def _publish_status(self, status: str, detail: str):
        """주행 상태를 /nav_status 토픽으로 발행"""
        msg = String()
        msg.data = json.dumps({
            'status': status,
            'detail': detail,
            'current_target': self.current_target_name,
        })
        self.status_pub.publish(msg)

    # =================================================================
    # [11. RViz 마커 시각화]
    # =================================================================
    def publish_markers(self):
        """RViz용 웨이포인트 마커 발행"""
        marker_array = MarkerArray()
        now = self.get_clock().now().to_msg()

        for i, (name, pt) in enumerate(POINTS.items()):
            # 스피어 마커
            sphere = Marker()
            sphere.header.frame_id = "map"
            sphere.header.stamp = now
            sphere.ns = "waypoints"
            sphere.id = i
            sphere.type = Marker.SPHERE
            sphere.action = Marker.ADD
            sphere.pose.position.x = pt['x']
            sphere.pose.position.y = pt['y']
            sphere.pose.position.z = 0.02
            sphere.scale.x = sphere.scale.y = sphere.scale.z = 0.07

            if name == self.current_target_name:
                sphere.color.r, sphere.color.g, sphere.color.b = 1.0, 1.0, 0.0
            else:
                sphere.color.r, sphere.color.g, sphere.color.b = 1.0, 0.0, 0.0
            sphere.color.a = 0.8
            marker_array.markers.append(sphere)

            # 텍스트 라벨
            text = Marker()
            text.header.frame_id = "map"
            text.header.stamp = now
            text.ns = "labels"
            text.id = i + 100
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose.position.x = pt['x']
            text.pose.position.y = pt['y']
            text.pose.position.z = 0.2
            text.scale.z = 0.1
            text.color.r = text.color.g = text.color.b = 0.5
            text.color.a = 1.0
            text.text = name
            marker_array.markers.append(text)

        self.marker_pub.publish(marker_array)


# =====================================================================
# [12. 메인 엔트리포인트]
# =====================================================================
def main(args=None):
    rclpy.init(args=args)

    node = Nav2WaypointNavigator()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        node.get_logger().info('🚀 Nav2 Waypoint Navigator 시작')
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info('👋 노드 종료')
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
