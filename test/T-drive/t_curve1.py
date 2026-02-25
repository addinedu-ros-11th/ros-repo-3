import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import cv2
import numpy as np
from pupil_apriltags import Detector
from pinkylib import Camera

class PinkyTask1ROS(Node):
    def __init__(self):
        super().__init__('pinky_task_1_ros')
        # Publisher 생성: /cmd_vel 토픽으로 속도 명령 전달
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        try:
            self.cam = Camera()
        except Exception as e:
            self.get_logger().error(f"Camera Init Fail: {e}")
            exit(1)

        self.detector = Detector(families="tag36h11", nthreads=2)
        self.width, self.height = 640, 480
        
        # 설정값 (에이프릴 태그 물리 크기 및 카메라 초점 거리)
        self.TAG_SIZE_MM = 40.0
        self.FOCAL_LENGTH = 570.0
        
        # 초기 상태 설정
        self.state = "FIND_10"
        self.prev_state = "" # SCAN_STILL 이후 복귀할 상태 저장
        self.start_time = 0
        
        self.cam.start(width=self.width, height=self.height)
        self.create_timer(0.05, self.control_loop)
        self.get_logger().info(">>> PINKY TASK 1 (Smart ID Scan & Turn) START <<<")

    def send_velocity(self, linear_x, angular_z):
        """ Twist 메시지를 생성하여 /cmd_vel로 발행 """
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.cmd_pub.publish(msg)

    def is_black_cluster_present(self, gray_frame):
        """ 화면에 검은색 픽셀 뭉치(태그 후보)가 있는지 확인 """
        _, black_mask = cv2.threshold(gray_frame, 60, 255, cv2.THRESH_BINARY_INV)
        black_pixels = np.sum(black_mask == 255)
        return black_pixels > 1500

    def control_loop(self):
        frame = self.cam.get_frame()
        if frame is None: return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dets = self.detector.detect(gray)
        
        # 현재 타겟 ID 결정 (상태에 따라 10번 혹은 11번)
        target_id = 10 if "10" in self.state else 11
        
        # [중요] 리스트에서 현재 목표하는 target_id만 필터링
        target = next((d for d in dets if d.tag_id == target_id), None)

        # 1. 태그 찾는 중 (회전 탐색)
        if self.state in ["FIND_10", "FIND_11"]:
            if target:
                self.state = "ALIGN_10" if target_id == 10 else "ALIGN_11"
            elif self.is_black_cluster_present(gray):
                # 타겟은 안 보이지만 검은 물체가 감지되면 정지 스캔
                self.send_velocity(0.0, 0.0)
                self.prev_state = self.state
                self.state = "SCAN_STILL"
                self.start_time = time.time()
                self.get_logger().info(f"Black cluster found during {self.prev_state}! Scanning...")
            else:
                self.send_velocity(0.0, 0.5)

        # 1-2. 정지 스캔 (원하는 ID가 아니면 다시 회전)
        elif self.state == "SCAN_STILL":
            if target:
                self.get_logger().info(f"Target {target_id} confirmed!")
                self.state = "ALIGN_10" if target_id == 10 else "ALIGN_11"
            elif time.time() - self.start_time > 1.0:
                # 1초 대기 후 타겟이 아니라고 판단되면 다시 회전 모드로 복귀
                self.get_logger().info(f"Target {target_id} not here. Resume searching...")
                self.state = self.prev_state
            else:
                self.send_velocity(0.0, 0.0)

        # 2. 10번 태그 정렬 및 40cm 앞 정지
        elif self.state == "ALIGN_10":
            if not target:
                self.state = "FIND_10"
                return
            cx, _ = target.center
            err_x = cx - (self.width / 1.8) # 1.8 보정값 적용
            tag_w = max(target.corners[:, 0]) - min(target.corners[:, 0])
            dist = (self.TAG_SIZE_MM * self.FOCAL_LENGTH) / tag_w

            if dist <= 400: # 40cm 도달
                self.send_velocity(0.0, 0.0)
                self.state = "GO_FORWARD"
                self.start_time = time.time()
            else:
                turn_val = -float(err_x / (self.width / 2.0)) * 0.5
                self.send_velocity(0.1, turn_val)

        # 3. 우회전을 위한 짧은 전진 (1.8초)
        elif self.state == "GO_FORWARD":
            if time.time() - self.start_time < 1.8:
                self.send_velocity(0.2, 0.0)
            else:
                self.send_velocity(0.0, 0.0)
                self.state = "TURN_RIGHT"
                self.start_time = time.time()

        # 4. 제자리 우회전 (1.0초, 우회전은 각속도 음수)
        elif self.state == "TURN_RIGHT":
            if time.time() - self.start_time < 1.0:
                self.send_velocity(0.0, -1.57)
            else:
                self.send_velocity(0.0, 0.0)
                self.state = "FIND_11"

        # 5. 11번 태그 정렬 및 20cm 앞 최종 정지
        elif self.state == "ALIGN_11":
            if not target:
                self.state = "FIND_11"
                return
            cx, _ = target.center
            err_x = cx - (self.width / 2.0)
            tag_w = max(target.corners[:, 0]) - min(target.corners[:, 0])
            dist = (self.TAG_SIZE_MM * self.FOCAL_LENGTH) / tag_w

            if dist <= 200: # 최종 20cm 정지
                self.send_velocity(0.0, 0.0)
                self.state = "DONE"
                self.get_logger().info("Task 1 Completed!")
            else:
                turn_val = -float(err_x / (self.width / 2.0)) * 0.5
                self.send_velocity(0.1, turn_val)

        elif self.state == "DONE":
            self.send_velocity(0.0, 0.0)

    def shutdown_robot(self):
        self.send_velocity(0.0, 0.0)
        self.cam.close()

def main():
    rclpy.init()
    node = PinkyTask1ROS()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown_robot()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()