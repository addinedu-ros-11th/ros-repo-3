#!/usr/bin/env python3
# ================================================================
# main_park.py
#
# [구조]
#   configs/stores.json  ← 매장별 좌표값 (여기서만 수정)
#   main_park.py         ← 실행 로직 (이 파일)
#
# [ROS2 Topic]
#   /go_store      (subscribe) : 단일 매장 이동  → "ABC_Mart"
#   /go_stores     (subscribe) : 다중 매장 이동  → "ABC_Mart,Barbie,Dior"
#   /cancel_queue  (subscribe) : 전체 취소
#   /park_status   (publish)   : 현재 상태 → UI로 피드백
#
# [실행 방법]
#   ros2 run store_park main_park
#
# [터미널 테스트]
#   단일: ros2 topic pub --once /go_store  std_msgs/String "data: 'ABC_Mart'"
#   다중: ros2 topic pub --once /go_stores std_msgs/String "data: 'ABC_Mart,Barbie,Dior'"
#   취소: ros2 topic pub --once /cancel_queue std_msgs/String "data: 'cancel'"
#   상태: ros2 topic echo /park_status
# ================================================================

import math
import json
import os
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose

# AprilTag 주차 함수 (AprilTag 사용 매장에서만 호출)
from store_park.parking import main as parking_main
from ament_index_python.packages import get_package_share_directory


# ================================================================
# 유틸 함수
# ================================================================
def yaw_to_quat(yaw_rad: float):
    """요각(yaw, rad) → 쿼터니언 (x,y,z,w) 변환 (평면 이동용)"""
    half = yaw_rad * 0.5
    return (0.0, 0.0, math.sin(half), math.cos(half))


# ================================================================
# Nav2 이동 Node
# ================================================================
class GoToXY(Node):
    def __init__(self, action_name: str):
        super().__init__("go_to_xy_client")
        self._client = ActionClient(self, NavigateToPose, action_name)
        self._arrived = False

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
            return

        self.get_logger().info(f"목표 전송: x={x}, y={y}, yaw={yaw_rad}rad")
        send_future = self._client.send_goal_async(goal)
        send_future.add_done_callback(self._goal_response_cb)

    def _goal_response_cb(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("목표가 거절되었습니다.")
            return
        self.get_logger().info("목표 수락됨. 결과를 기다리는 중...")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_cb)

    def _result_cb(self, future):
        result = future.result()
        status = result.status
        if status == 4:
            print("해당구역 도착")
            self._arrived = True
        else:
            print(f"아직 도착하지 못했습니다. (status={status})")


# ================================================================
# 메인 Park Node (UI 연동 + Queue 관리)
# ================================================================
class ParkNode(Node):
    def __init__(self):
        super().__init__("park_node")

        # ===== stores.json 로드 =====
        config_path = os.path.join(
            get_package_share_directory('store_park'),
            'configs',
            'stores.json'
        )
        if not os.path.exists(config_path):
            self.get_logger().error(f"stores.json 없음: {config_path}")
            raise FileNotFoundError(f"stores.json 없음: {config_path}")

        with open(config_path, "r") as f:
            self.store_configs = json.load(f)

        self.get_logger().info(f"매장 {len(self.store_configs)}개 로드 완료")

        # ===== Queue 초기화 =====
        self.queue      = deque()
        self.is_running = False

        # 0.1초마다 Queue 체크
        self.create_timer(0.1, self.process_queue)

        # ===== Subscriber =====
        # 단일 매장: "/go_store"  → "ABC_Mart"
        self.create_subscription(
            String, "/go_store",
            self.single_store_callback, 10
        )
        # 다중 매장: "/go_stores" → "ABC_Mart,Barbie,Dior"
        self.create_subscription(
            String, "/go_stores",
            self.multi_store_callback, 10
        )
        # 취소: "/cancel_queue"
        self.create_subscription(
            String, "/cancel_queue",
            self.cancel_callback, 10
        )

        # ===== Publisher (UI 피드백) =====
        self.pub_status = self.create_publisher(String, "/park_status", 10)

        self.get_logger().info("ParkNode 실행 중... UI 명령 대기")
        self.get_logger().info(f"등록된 매장: {list(self.store_configs.keys())}")

    # ================================================================
    # 단일 매장 처리
    # ================================================================
    def single_store_callback(self, msg):
        store_name = msg.data.strip()
        self.get_logger().info(f"단일 매장 요청: {store_name}")

        if store_name not in self.store_configs:
            self.get_logger().error(f"'{store_name}' 없음")
            self.pub_status.publish(String(data=f"오류: '{store_name}' 없음"))
            return

        self.queue.append(store_name)
        self.pub_status.publish(
            String(data=f"Queue 추가: {store_name} | 대기: {len(self.queue)}개")
        )
        # Timer가 알아서 process_queue() 호출

    # ================================================================
    # 다중 매장 처리
    # ================================================================
    def multi_store_callback(self, msg):
        store_list = [s.strip() for s in msg.data.split(",")]
        self.get_logger().info(f"다중 매장 요청: {store_list}")

        valid = []
        for store_name in store_list:
            if store_name not in self.store_configs:
                self.get_logger().error(f"'{store_name}' 없음 → 건너뜀")
                continue
            self.queue.append(store_name)
            valid.append(store_name)

        if valid:
            self.pub_status.publish(
                String(data=f"Queue 추가: {valid} | 총 대기: {len(self.queue)}개")
            )
        # Timer가 알아서 process_queue() 호출

    # ================================================================
    # Queue 순서대로 실행
    # ================================================================
    def process_queue(self):
        if self.is_running or len(self.queue) == 0:
            return

        self.is_running = True
        store_name = self.queue.popleft()
        config     = self.store_configs[store_name]

        GOAL_X        = config["goal_x"]
        GOAL_Y        = config["goal_y"]
        GOAL_YAW      = config["goal_yaw"]
        has_april_tag = "target_id" in config
        TARGET_ID     = config.get("target_id", None)

        self.get_logger().info(
            f"[{store_name}] 이동 시작 → "
            f"x:{GOAL_X} y:{GOAL_Y} yaw:{GOAL_YAW} | "
            f"AprilTag: {'있음 (ID=' + str(TARGET_ID) + ')' if has_april_tag else '없음'} | "
            f"남은 Queue: {len(self.queue)}개"
        )
        self.pub_status.publish(
            String(data=f"이동 중: {store_name} | 남은: {len(self.queue)}개")
        )

        # ===== Nav2 이동 =====
        nav_node = GoToXY("/navigate_to_pose")
        nav_node.send_goal(x=GOAL_X, y=GOAL_Y, yaw_rad=GOAL_YAW)

        executor = rclpy.executors.SingleThreadedExecutor()
        executor.add_node(nav_node)
        while not nav_node._arrived and rclpy.ok():
            executor.spin_once(timeout_sec=0.1)
        executor.shutdown()
        nav_node.destroy_node()

        # ===== 도착 후 처리 =====
        if nav_node._arrived:
            if has_april_tag:
                self.get_logger().info(
                    f"[{store_name}] AprilTag({TARGET_ID}) 정밀 주차 시작"
                )
                parking_main(target_id=TARGET_ID)
            else:
                self.get_logger().info(
                    f"[{store_name}] 좌표 도착 완료 (AprilTag 없음)"
                )
            self.on_goal_reached(store_name)
        else:
            self.get_logger().error(f"[{store_name}] 이동 실패 → 다음 매장으로")
            self.pub_status.publish(String(data=f"실패: {store_name} | 다음 매장으로"))
            self.is_running = False

    # ================================================================
    # 목표 도달 완료 → 다음 Queue 자동 실행
    # ================================================================
    def on_goal_reached(self, store_name):
        self.get_logger().info(f"[{store_name}] 완료")
        self.pub_status.publish(
            String(data=f"완료: {store_name} | 남은: {len(self.queue)}개")
        )
        self.is_running = False
        # Timer가 알아서 다음 매장 process_queue() 호출

    # ================================================================
    # 전체 취소
    # ================================================================
    def cancel_callback(self, msg):
        count = len(self.queue)
        self.queue.clear()
        self.is_running = False
        self.get_logger().info(f"Queue 취소 ({count}개 삭제)")
        self.pub_status.publish(String(data=f"취소 완료: {count}개 삭제됨"))


# ================================================================
# 실행 진입점
# ================================================================
def main(args=None):
    rclpy.init(args=args)
    try:
        node = ParkNode()
        rclpy.spin(node)
    except FileNotFoundError as e:
        print(f"[오류] {e}")
    except KeyboardInterrupt:
        print("ParkNode 종료")
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()