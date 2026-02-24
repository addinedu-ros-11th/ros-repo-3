import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import cv2
import numpy as np
from pupil_apriltags import Detector
from pinkylib import Camera

class PinkyTask2ROS(Node):
    def __init__(self):
        super().__init__('pinky_task_2_ros')
        
        # Publisher 생성: 브링업 노드에 속도 명령 전달
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        try:
            self.cam = Camera()
        except Exception as e:
            self.get_logger().error(f"Camera Init Fail: {e}")
            exit(1)

        self.detector = Detector(families="tag36h11", nthreads=2)
        self.width, self.height = 640, 480
        
        # 설정값 (1번 코드와 동일하게 유지)
        self.TAG_SIZE_MM = 40.0 
        self.FOCAL_LENGTH = 570.0 
        
        # 초기 상태: 10번 태그 찾기
        self.state = "FIND_10"
        self.start_time = 0
        
        self.cam.start(width=self.width, height=self.height)
        self.create_timer(0.05, self.control_loop) 
        self.get_logger().info(">>> PINKY TASK 2 (Left Turn to Tag 16) START <<<")

    def send_velocity(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.cmd_pub.publish(msg)

    def get_distance(self, pixel_width):
        return (self.TAG_SIZE_MM * self.FOCAL_LENGTH) / pixel_width

    def control_loop(self):
        frame = self.cam.get_frame()
        if frame is None: return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dets = self.detector.detect(gray)
        
        # 상태에 따라 찾는 태그 번호 결정 (10번 -> 16번)
        target_id = 10 if self.state in ["FIND_10", "ALIGN_10"] else 16
        target = next((d for d in dets if d.tag_id == target_id), None)

        # 1. 10번 태그 찾기 (제자리 회전)
        if self.state == "FIND_10":
            if target: 
                self.state = "ALIGN_10"
            else: 
                self.send_velocity(0.0, 0.5)

        # 2. 10번 태그 정렬 및 40cm 앞 정지
        elif self.state == "ALIGN_10":
            if not target:
                self.state = "FIND_10"
                return
            cx, _ = target.center
            # 사용하신 보정값 1.8 유지
            err_x = cx - (self.width / 1.8)
            tag_w = max(target.corners[:, 0]) - min(target.corners[:, 0])
            dist = self.get_distance(tag_w)

            if dist <= 400: # 40cm
                self.send_velocity(0.0, 0.0)
                self.state = "GO_FORWARD"
                self.start_time = time.time()
            else:
                turn_val = -float(err_x / (self.width / 2.0)) * 0.5
                self.send_velocity(0.1, turn_val)

        # 3. 앞으로 전진 (1.8초)
        elif self.state == "GO_FORWARD":
            if time.time() - self.start_time < 1.8:
                self.send_velocity(0.2, 0.0)
            else:
                self.send_velocity(0.0, 0.0)
                self.state = "TURN_LEFT" # 좌회전으로 변경
                self.start_time = time.time()

        # 4. 제자리 좌회전 (1.2초, 각속도 양수)
        elif self.state == "TURN_LEFT":
            if time.time() - self.start_time < 1.2: 
                self.send_velocity(0.0, 1.57) # 양수(+)는 좌회전
            else:
                self.send_velocity(0.0, 0.0)
                self.state = "FIND_16" # 16번 태그 찾기 시작

        # 5. 16번 태그 찾기
        elif self.state == "FIND_16":
            if target: 
                self.state = "ALIGN_16"
            else: 
                self.send_velocity(0.0, 0.5)

        # 6. 16번 태그 정렬 및 40cm 앞 정지
        elif self.state == "ALIGN_16":
            if not target:
                self.state = "FIND_16"
                return
            cx, _ = target.center
            err_x = cx - (self.width / 2.0)
            tag_w = max(target.corners[:, 0]) - min(target.corners[:, 0])
            dist = self.get_distance(tag_w)

            if dist <= 400: # 40cm 정지 요청
                self.send_velocity(0.0, 0.0)
                self.state = "DONE"
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
    node = PinkyTask2ROS()
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