import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import cv2
import numpy as np
from pupil_apriltags import Detector
from pinkylib import Camera

class PinkyTask6ROS(Node):
    def __init__(self):
        super().__init__('pinky_task_6_ros')
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        try:
            self.cam = Camera()
        except Exception as e:
            self.get_logger().error(f"Camera Init Fail: {e}")
            exit(1)

        self.detector = Detector(families="tag36h11", nthreads=2)
        self.width, self.height = 640, 480
        self.TAG_SIZE_MM, self.FOCAL_LENGTH = 40.0, 570.0
        
        # 상태: 찾기 -> 75cm 접근 -> 좌회전 -> 2초 전진 -> 종료
        self.state = "FIND_16"
        self.start_time = 0
        
        self.cam.start(width=self.width, height=self.height)
        self.create_timer(0.05, self.control_loop)
        self.get_logger().info(">>> PINKY TASK 6 (Turn at 75cm & Drive 2s) START <<<")

    def send_velocity(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x, msg.angular.z = float(linear_x), float(angular_z)
        self.cmd_pub.publish(msg)

    def control_loop(self):
        frame = self.cam.get_frame()
        if frame is None: return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dets = self.detector.detect(gray)
        target = next((d for d in dets if d.tag_id == 16), None)

        # 1. 16번 태그 찾기
        if self.state == "FIND_16":
            if target: 
                self.state = "APPROACH_75CM"
            else: 
                self.send_velocity(0.0, 0.5)

        # 2. 정렬하며 75cm(750mm) 지점까지 접근
        elif self.state == "APPROACH_75CM":
            if not target:
                self.send_velocity(0.0, 0.5)
                return
            
            tag_w = max(target.corners[:, 0]) - min(target.corners[:, 0])
            dist = (self.TAG_SIZE_MM * self.FOCAL_LENGTH) / tag_w
            
            # 800에서 750으로 수정
            if dist <= 750:
                self.send_velocity(0.0, 0.0)
                self.state = "TURN_LEFT"
                self.start_time = time.time()
            else:
                # 사용하셨던 보정값 1.8 유지
                err_x = target.center[0] - (self.width / 1.8)
                turn_val = -float(err_x / (self.width / 2.0)) * 0.5
                self.send_velocity(0.15, turn_val)

        # 3. 제자리 좌회전 (기존 성공 시간 1.05초 유지)
        elif self.state == "TURN_LEFT":
            if time.time() - self.start_time < 1.05:
                self.send_velocity(0.0, 1.57) 
            else:
                self.send_velocity(0.0, 0.0)
                self.state = "FINAL_DRIVE" # 회전 후 전진 상태로 전환
                self.start_time = time.time()

        # 4. 추가된 로직: 앞으로 2초간 전진
        elif self.state == "FINAL_DRIVE":
            if time.time() - self.start_time < 3.0:
                self.send_velocity(0.2, 0.0) # 적절한 전진 속도
            else:
                self.send_velocity(0.0, 0.0)
                self.state = "DONE"

        elif self.state == "DONE":
            self.send_velocity(0.0, 0.0)

    def shutdown_robot(self):
        self.send_velocity(0.0, 0.0); self.cam.close()

def main():
    rclpy.init(); node = PinkyTask6ROS()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.shutdown_robot(); node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__': main()