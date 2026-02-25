import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from apriltag_msgs.msg import AprilTagDetectionArray

import cv2
import numpy as np
from pupil_apriltags import Detector

from pinkylib import Camera


class AprilTagFollowerNode(Node):
    def __init__(self):
        super().__init__('apriltag_follower_node')

        # ROS2 publisher
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.det_pub = self.create_publisher(
            AprilTagDetectionArray, '/apriltag_detections', 10
        )

        # AprilTag detector
        self.detector = Detector(
            families='tag36h11',
            nthreads=4,
            quad_decimate=1.0,
            quad_sigma=0.0,
            refine_edges=1,
            decode_sharpening=0.25
        )

        # Camera 설정
        self.W, self.H = 640, 480
        self.camera = Camera()
        self.camera.start(width=self.W, height=self.H)

        # Camera calibration (예시 값, 사용 중인 값 그대로 유지)
        self.camera_params = (570.34, 570.34, 320.0, 240.0)
        self.tag_size = 0.04  # meter

        # ---------- 제어 파라미터 ----------
        self.target_id = 12
        self.target_z = 0.20  # 20cm 유지

        self.linear_gain = 1.2
        self.max_linear_speed = 0.25
        self.min_linear_speed = 0.12

        self.angular_gain = 10.0
        self.max_angular_speed = 20.0
        self.min_angular_speed = 0.5
        # ----------------------------------

        self.get_logger().info(
            f"Targeting ID:{self.target_id} | Pinky Camera Mode"
        )

        # 메인 루프 타이머 (30Hz 근처)
        self.timer = self.create_timer(1.0 / 30.0, self.process_frame)

    def process_frame(self):
        frame = self.camera.get_frame()
        if frame is None:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        tags = self.detector.detect(
            gray,
            estimate_tag_pose=True,
            camera_params=self.camera_params,
            tag_size=self.tag_size
        )

        twist = Twist()
        target_tag = next(
            (t for t in tags if t.tag_id == self.target_id),
            None
        )

        if target_tag:
            tx = float(target_tag.pose_t[0].item())
            tz = float(target_tag.pose_t[2].item())
            z_error = tz - self.target_z

            # ---- 전진 / 후진 ----
            if abs(z_error) > 0.02:
                raw_linear = z_error * self.linear_gain
                if raw_linear > 0:
                    twist.linear.x = max(raw_linear, self.min_linear_speed)
                else:
                    twist.linear.x = min(raw_linear, -self.min_linear_speed)

            # ---- 회전 제어 ----
            if abs(tx) > 0.015:
                raw_angular = tx * self.angular_gain
                if raw_angular > 0:
                    twist.angular.z = max(raw_angular, self.min_angular_speed)
                else:
                    twist.angular.z = min(raw_angular, -self.min_angular_speed)

            # 속도 제한
            twist.linear.x = float(
                np.clip(
                    twist.linear.x,
                    -self.max_linear_speed,
                    self.max_linear_speed
                )
            )
            twist.angular.z = float(
                np.clip(
                    twist.angular.z,
                    -self.max_angular_speed,
                    self.max_angular_speed
                )
            )

            self.get_logger().info(
                f"ID:{self.target_id} | Dist:{tz*100:.1f}cm | "
                f"Lin:{twist.linear.x:.2f} | Ang:{twist.angular.z:.2f}"
            )
        else:
            # 태그 놓치면 즉시 정지
            twist.linear.x = 0.0
            twist.angular.z = 0.0

        self.cmd_pub.publish(twist)

    def destroy_node(self):
        self.camera.close()
        super().destroy_node()


def main():
    rclpy.init()
    node = AprilTagFollowerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
