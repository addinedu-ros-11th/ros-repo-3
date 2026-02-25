import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import cv2
import numpy as np
from pupil_apriltags import Detector
from pinkylib import Camera

class PinkyTask3ROS(Node):
    def __init__(self):
        super().__init__('pinky_task_3_ros')
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        try:
            self.cam = Camera()
        except Exception as e:
            self.get_logger().error(f"Camera Init Fail: {e}")
            exit(1)

        self.detector = Detector(families="tag36h11", nthreads=2)
        self.width, self.height = 640, 480
        self.TAG_SIZE_MM, self.FOCAL_LENGTH = 40.0, 570.0
        
        # 상태: 찾기 -> 블랙 감지 정지 -> 1m 정렬 -> 30cm 전진 -> 우회전 -> 2초 전진
        self.state = "FIND_11"
        self.start_time = 0
        self.ignore_until = 0  # 블랙 픽셀 감지 무시 시간 (쿨타임)
        
        self.cam.start(width=self.width, height=self.height)
        self.create_timer(0.05, self.control_loop)
        self.get_logger().info(">>> PINKY TASK 3 (Smart Scan & T-Junction) START <<<")

    def send_velocity(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x, msg.angular.z = float(linear_x), float(angular_z)
        self.cmd_pub.publish(msg)

    def is_black_cluster_present(self, gray_frame):
        """화면에 검은색 픽셀 뭉치가 있는지 확인"""
        _, black_mask = cv2.threshold(gray_frame, 60, 255, cv2.THRESH_BINARY_INV)
        black_pixels = np.sum(black_mask == 255)
        return black_pixels > 1500

    def control_loop(self):
        frame = self.cam.get_frame()
        if frame is None: return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 11번 태그만 감지
        dets = self.detector.detect(gray)
        target = next((d for d in dets if d.tag_id == 11), None)

        # --- 상태별 로직 ---
        
        # 1. 태그 찾는 중 (회전)
        if self.state == "FIND_11":
            if target:
                self.state = "ALIGN_1M"
            # 무시 시간이 지났고 검은 뭉치가 보이면 정지 스캔
            elif time.time() > self.ignore_until and self.is_black_cluster_present(gray):
                self.send_velocity(0.0, 0.0)
                self.state = "SCAN_STILL"
                self.start_time = time.time()
                self.get_logger().info("Black detected. Stopping to check ID 11...")
            else:
                self.send_velocity(0.0, 0.5)

        # 1-2. 정지 스캔 (11번인지 확인)
        elif self.state == "SCAN_STILL":
            if target:
                self.get_logger().info("ID 11 confirmed!")
                self.state = "ALIGN_1M"
            elif time.time() - self.start_time > 1.0:
                # 1초간 봤는데 11번이 아니면 다시 회전 + 1.2초간 블랙 감지 무시(쿨타임)
                self.get_logger().info("Not ID 11. Resuming search...")
                self.ignore_until = time.time() + 1.2 
                self.state = "FIND_11"
            else:
                self.send_velocity(0.0, 0.0)

        # 2. 11번 태그 1m(1000mm) 앞에 정렬
        elif self.state == "ALIGN_1M":
            if not target:
                self.state = "FIND_11"
                return
            tag_w = max(target.corners[:, 0]) - min(target.corners[:, 0])
            dist = (self.TAG_SIZE_MM * self.FOCAL_LENGTH) / tag_w
            
            if dist <= 1000:
                self.send_velocity(0.0, 0.0)
                self.state = "STEP_FORWARD"
                self.start_time = time.time()
            else:
                # 보정값 1.8 적용
                err_x = target.center[0] - (self.width / 1.8)
                turn_val = -float(err_x / (self.width / 2.0)) * 0.5
                self.send_velocity(0.1, turn_val)

        # 3. 앞으로 30cm 전진
        elif self.state == "STEP_FORWARD":
            if time.time() - self.start_time < 2.2:
                self.send_velocity(0.15, 0.0)
            else:
                self.send_velocity(0.0, 0.0)
                self.state = "TURN_RIGHT"
                self.start_time = time.time()

        # 4. 우회전 (1.0초)
        elif self.state == "TURN_RIGHT":
            if time.time() - self.start_time < 1.00:
                self.send_velocity(0.0, -1.57)
            else:
                self.send_velocity(0.0, 0.0)
                self.state = "FINAL_DRIVE"
                self.start_time = time.time()

        # 5. 앞으로 2초간 전진
        elif self.state == "FINAL_DRIVE":
            if time.time() - self.start_time < 2.0:
                self.send_velocity(0.2, 0.0)
            else:
                self.send_velocity(0.0, 0.0)
                self.state = "DONE"

        elif self.state == "DONE":
            self.send_velocity(0.0, 0.0)

    def shutdown_robot(self):
        self.send_velocity(0.0, 0.0); self.cam.close()

def main():
    rclpy.init(); node = PinkyTask3ROS()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.shutdown_robot(); node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__': main()