import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import cv2
import numpy as np
from pupil_apriltags import Detector
from pinkylib import Camera

class PinkyTask5ROS(Node):
    def __init__(self):
        super().__init__('pinky_task_5_ros')
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        try:
            self.cam = Camera()
        except Exception as e:
            self.get_logger().error(f"Camera Init Fail: {e}")
            exit(1)

        self.detector = Detector(families="tag36h11", nthreads=2)
        self.width, self.height = 640, 480
        self.TAG_SIZE_MM, self.FOCAL_LENGTH = 40.0, 570.0
        
        # 상태: 찾기 -> 40cm까지 정밀 추적 전진 -> 종료
        self.state = "FIND_16"
        
        self.cam.start(width=self.width, height=self.height)
        self.create_timer(0.05, self.control_loop)
        self.get_logger().info(">>> PINKY TASK 5 (Tag 16 Follow & Stop at 40cm) <<<")

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

        if self.state == "FIND_16":
            if target: self.state = "APPROACH_40CM"
            else: self.send_velocity(0.0, 0.5)

        elif self.state == "APPROACH_40CM":
            if not target:
                self.send_velocity(0.0, 0.5) # 태그 소실 시 탐색 회전
                return
            
            tag_w = max(target.corners[:, 0]) - min(target.corners[:, 0])
            dist = (self.TAG_SIZE_MM * self.FOCAL_LENGTH) / tag_w
            
            # 40cm(400mm) 도달 시 정지
            if dist <= 400:
                self.send_velocity(0.0, 0.0)
                self.get_logger().info("Arrived at 40cm. Done.")
                self.state = "DONE"
            else:
                # 중앙 정렬 보정 (성공했던 1.8 보정값 적용)
                err_x = target.center[0] - (self.width / 1.8)
                turn_val = -float(err_x / (self.width / 2.0)) * 0.5
                self.send_velocity(0.15, turn_val)

        elif self.state == "DONE":
            self.send_velocity(0.0, 0.0)

    def shutdown_robot(self):
        self.send_velocity(0.0, 0.0); self.cam.close()

def main():
    rclpy.init(); node = PinkyTask5ROS()
    try: rclpy.spin(node)
    except: pass
    finally: node.shutdown_robot(); node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__': main()