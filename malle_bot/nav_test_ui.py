import sys
import threading
import time
import math

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.executors import MultiThreadedExecutor
from geometry_msgs.msg import PoseStamped
from visualization_msgs.msg import Marker, MarkerArray

# Nav2 임포트
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult

# TF2 임포트 (현재 위치 확인용)
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

# PyQt6 임포트
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QLabel, QTextEdit
)
from PyQt6.QtCore import pyqtSignal, QObject


# =====================================================================
# [1. 맵 데이터 및 통로 설정]
# =====================================================================
POINTS = {
    "p0": {"x": 0.391, "y": 0.351},
    "p1": {"x": 0.391, "y": 0.845},
    "p2": {"x": 0.396, "y": 1.950},
    "p3": {"x": 1.200, "y": 1.950},
    "p4": {"x": 1.199, "y": 0.850},
    "p5": {"x": 1.650, "y": 0.850},
    "p6": {"x": 2.074, "y": 0.856},
    "p7": {"x": 1.200, "y": 1.400},
    "p8": {"x": 2.100, "y": 0.247},
    "p9": {"x": 2.397, "y": 0.254},
    "p10": {"x": 2.388, "y": 1.297},
    "p11": {"x": 1.804, "y": 1.950},
    "p12": {"x": 0.917, "y": 0.300},
    "p13": {"x": 0.917, "y": 0.845},
    "p14": {"x": 1.199, "y": 0.300},
    "p15": {"x": 2.000, "y": 1.400},
    "p16": {"x": 1.800, "y": 0.300},
    "charger1": {"x": 0.250, "y": 0.650},
    "charger2": {"x": 0.450, "y": 0.650},
    "p2-1": {"x": 0.396, "y": 1.700}, 
    "p3-1": {"x": 1.200, "y": 1.700}, 
    "p11-1": {"x": 1.804, "y": 1.700},
}

WAYPOINT_GRAPH = {
    'p0': ['p1','charger1' ,'charger2'],
    'p1': ['p0', 'p2-1', 'p13'],
    'p2': ['p1', 'p3','p2-1'],
    'p3': ['p2', 'p4', 'p7',],
    'p4': ['p3', 'p5', 'p13'],
    'p5': ['p4', 'p6'],
    'p6': ['p5', 'p8', 'p15'],
    'p7': ['p3-1', 'p4'],
    'p8': ['p6', 'p9', 'p16'],
    'p9': ['p8'],
    'p10': ['p7', 'p15'],
    'p11': ['p3'],
    'p12': ['p13', 'p14'],
    'p13': ['p1', 'p12', 'p4'],
    'p14': ['p12', 'p16'],
    'p15': ['p6', 'p11-1', 'p10'],
    'p16': ['p8', 'p14'],
    'p2-1': ['p3-1','p1'],
    'p3-1': ['p11-1', 'p7'],     # 가다가 중간(p4)으로 빠질 수 있음
    'p11-1': ['p15','p3-1','p11'],
}


# =====================================================================
# [2. ROS2 Node & Nav2 제어 클래스]
# =====================================================================
class Nav2WaypointNavigator(Node):
    def __init__(self, gui_signals):
        super().__init__('nav2_smart_navigator')
        self.signals = gui_signals
        self.marker_pub = self.create_publisher(MarkerArray, 'waypoint_markers', 10)
        self.current_target_name = ""
        self.abort_flag = False
        
        # TF2 설정 (현재 위치 파악용)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # Nav2 초기화
        self.nav = BasicNavigator()
        self.timer = self.create_timer(0.5, self.publish_markers)
        
        self.signals.log_signal.emit('⏳ Nav2 활성화를 기다리는 중...')
        # 스레드가 막히지 않도록 백그라운드에서 대기
        threading.Thread(target=self.wait_for_nav2, daemon=True).start()

    def wait_for_nav2(self):
        """Nav2 활성화 대기"""
        self.nav.waitUntilNav2Active()
        self.signals.log_signal.emit('✅ Nav2 준비 완료! 주행을 시작할 수 있습니다.')

    # --- 길찾기 알고리즘 ---
    def find_shortest_path(self, start, goal):
        """BFS로 최단 경로 탐색"""
        if start == goal:
            return [start]
        
        explored = []
        queue = [[start]]
        
        while queue:
            path = queue.pop(0)
            node = path[-1]
            
            if node not in explored:
                for neighbour in WAYPOINT_GRAPH.get(node, []):
                    new_path = list(path)
                    new_path.append(neighbour)
                    queue.append(new_path)
                    if neighbour == goal:
                        return new_path
                explored.append(node)
        return None

    def get_current_waypoint(self):
        """TF를 통해 현재 위치에서 가장 가까운 웨이포인트 탐색"""
        try:
            trans = self.tf_buffer.lookup_transform(
                'map', 'base_footprint', Time(), 
                timeout=rclpy.duration.Duration(seconds=1.0)
            )
            curr_x = trans.transform.translation.x
            curr_y = trans.transform.translation.y
            
            nearest_wp = None
            min_dist = float('inf')
            for name, coord in POINTS.items():
                dist = math.hypot(coord['x'] - curr_x, coord['y'] - curr_y)
                if dist < min_dist:
                    min_dist = dist
                    nearest_wp = name
            return nearest_wp
        except Exception as e:
            self.signals.log_signal.emit(f"⚠️ 위치 확인 실패: {e}")
            return None

    def create_pose(self, pt_name):
        """웨이포인트 좌표로 PoseStamped 메시지 생성"""
        coord = POINTS[pt_name]
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = coord['x']
        pose.pose.position.y = coord['y']
        pose.pose.orientation.w = 1.0
        return pose

    # --- 주행 실행 함수 ---
    def execute_navigation(self, target_list):
        """목적지 리스트 순서대로 Nav2 주행 실행"""
        self.abort_flag = False
        start_wp = self.get_current_waypoint()
        
        if not start_wp:
            self.signals.log_signal.emit("❌ 로봇의 현재 위치를 파악할 수 없어 주행을 취소합니다.")
            return

        self.signals.log_signal.emit(f"🏁 지정된 순서대로 주행 시작: {' -> '.join(target_list)}")
        current_wp = start_wp

        for final_target in target_list:
            if self.abort_flag:
                break
            
            # 세부 경로(경유지 리스트) 계산
            path_sequence = self.find_shortest_path(current_wp, final_target)
            if not path_sequence:
                self.signals.log_signal.emit(f"❌ {final_target}로 가는 길을 찾을 수 없습니다.")
                continue

            self.signals.log_signal.emit(f"🎯 다음 목적지 [{final_target}] (세부경로: {path_sequence})")

            # 세부 경유지를 하나씩 Nav2에 넘김
            for i in range(1, len(path_sequence)):
                if self.abort_flag:
                    break
                
                next_pt = path_sequence[i]
                self.current_target_name = next_pt
                goal_pose = self.create_pose(next_pt)
                
                self.signals.log_signal.emit(f"  -> 경유지 [{next_pt}] 이동 중...")
                self.nav.goToPose(goal_pose)

                # Nav2 작업 완료 대기
                while not self.nav.isTaskComplete():
                    if self.abort_flag:
                        self.nav.cancelTask()
                        self.signals.log_signal.emit("🛑 주행 강제 취소됨!")
                        return
                    time.sleep(0.1)

                result = self.nav.getResult()
                if result != TaskResult.SUCCEEDED:
                    self.signals.log_signal.emit(f"❌ [{next_pt}] 이동 실패. Nav2 문제 발생.")
                    return  # 실패 시 주행 전체 취소
                
                time.sleep(0.5)  # 포인트 도착 후 안정화 대기

            if self.abort_flag:
                break
            self.signals.log_signal.emit(f"✅ 최종 목적지 [{final_target}] 도착!")
            time.sleep(2.0)
            current_wp = final_target

        if not self.abort_flag:
            self.signals.log_signal.emit("✨ 모든 미션 완료!")
        self.current_target_name = ""

    def emergency_stop(self):
        """긴급 정지"""
        self.abort_flag = True
        self.nav.cancelTask()

    # --- RViz 시각화 ---
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
                sphere.color.r, sphere.color.g, sphere.color.b = 1.0, 1.0, 0.0  # 노란색(현재 목표)
            else:
                sphere.color.r, sphere.color.g, sphere.color.b = 1.0, 0.0, 0.0  # 빨간색
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
# [3. PyQt6 GUI 클래스]
# =====================================================================
class CommSignals(QObject):
    log_signal = pyqtSignal(str)


class Nav2GuiApp(QWidget):
    def __init__(self):
        super().__init__()
        self.target_queue = []
        self.signals = CommSignals()
        self.init_ui()
        
        # ROS2 Node 초기화 및 실행
        rclpy.init()
        self.ros_node = Nav2WaypointNavigator(self.signals)
        self.executor = MultiThreadedExecutor(num_threads=2)
        self.executor.add_node(self.ros_node)
        
        self.ros_thread = threading.Thread(target=self.executor.spin, daemon=True)
        self.ros_thread.start()

    def init_ui(self):
        """GUI UI 초기화"""
        self.setWindowTitle("Nav2 Smart Navigator (Neto)")
        layout = QVBoxLayout()

        # 웨이포인트 버튼들
        btn_layout = QHBoxLayout()
        for wp_name in sorted(POINTS.keys()):
            btn = QPushButton(wp_name)
            btn.setFixedWidth(40)
            btn.clicked.connect(lambda checked, name=wp_name: self.add_destination(name))
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        # 목적지 리스트
        self.list_widget = QListWidget()
        layout.addWidget(QLabel("방문 예정 목적지 (입력한 순서대로 Nav2 주행):"))
        layout.addWidget(self.list_widget)

        # 제어 버튼들
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("주행 시작")
        self.start_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.start_btn.clicked.connect(self.start_navigation)
        
        self.clear_btn = QPushButton("리스트 초기화")
        self.clear_btn.clicked.connect(self.clear_targets)

        self.stop_btn = QPushButton("🛑 Nav2 긴급 정지")
        self.stop_btn.setStyleSheet(
            "background-color: #f44336; color: white; font-weight: bold;"
        )
        self.stop_btn.clicked.connect(self.emergency_stop)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addWidget(self.stop_btn)
        layout.addLayout(control_layout)

        # 로그 표시창
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
        self.signals.log_signal.connect(self.update_log)

        self.setLayout(layout)
        self.resize(800, 600)

    def add_destination(self, name):
        """목적지 추가"""
        self.target_queue.append(name)
        self.list_widget.addItem(name)
        self.update_log(f"➕ 목적지 추가: {name}")

    def clear_targets(self):
        """목적지 리스트 초기화"""
        self.target_queue = []
        self.list_widget.clear()
        self.update_log("🧹 목적지 리스트 초기화됨")

    def update_log(self, text):
        """로그 업데이트"""
        self.log_display.append(f"[{time.strftime('%H:%M:%S')}] {text}")

    def emergency_stop(self):
        """긴급 정지"""
        self.update_log("🚨 긴급 정지! Nav2 작업을 취소합니다.")
        self.ros_node.emergency_stop()

    def closeEvent(self, event):
        """윈도우 종료 처리"""
        self.emergency_stop()
        rclpy.shutdown()
        event.accept()

    def start_navigation(self):
        """주행 시작"""
        if not self.target_queue:
            self.update_log("⚠️ 목적지를 먼저 선택해주세요!")
            return
        
        # 주행 명령을 별도 스레드로 실행하여 GUI가 멈추지 않게 함
        targets_to_run = self.target_queue.copy()
        nav_thread = threading.Thread(
            target=self.ros_node.execute_navigation, 
            args=(targets_to_run,)
        )
        nav_thread.start()


def main(args=None):
    app = QApplication(sys.argv)
    gui = Nav2GuiApp()
    gui.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
