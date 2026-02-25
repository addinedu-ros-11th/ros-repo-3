#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import UInt16MultiArray
import cv2
import numpy as np
import sys

class LineTracker:
    def __init__(self):
        # ROS 초기화
        rclpy.init()
        self.node = rclpy.create_node('line_tracker')
        self.pub = self.node.create_publisher(Twist, '/cmd_vel', 10)

        # IR 센서 구독
        self.ir_sub = self.node.create_subscription(
            UInt16MultiArray,
            '/ir_sensor/range',
            self.ir_callback,
            10
        )

        # 상태
        self.state = 'CAMERA_ALIGN'  # CAMERA_ALIGN → CAMERA_FORWARD → IR_LINE_FOLLOW
        self.last_error = 0.0

        # 카메라 기반 제어 파라미터
        self.cam_turn_gain = 0.01
        self.cam_deadband = 5       # ±5px
        self.black_threshold = 60   # grayscale
        self.forward_speed_cam = 0.15
        self.forward_speed_ir = 0.20

        # 카메라 스트림 설정
        self.W, self.H = 640, 480
        self.FRAME_SIZE = self.W * self.H * 3 // 2  # YUV420

        # IR 파라미터
        self.ir_line_detect_threshold = 300
        self.max_ir = 4095

        print("Camera + IR Line Tracker started (headless mode)")

    # ==============================
    # IR 콜백
    # ==============================
    def ir_callback(self, msg):
        if self.state != 'IR_LINE_FOLLOW':
            return

        if len(msg.data) != 3:
            return
        R, C, L = msg.data
        wL = self.max_ir - L
        wC = self.max_ir - C
        wR = self.max_ir - R
        weight_sum = wL + wC + wR

        if weight_sum < 200:
            self.search_line()
            return

        error = (1.0 * wL - 1.0 * wR) / weight_sum
        self.last_error = error

        cmd = Twist()
        # 중앙 정렬
        if abs(error) < 0.08:
            cmd.linear.x = self.forward_speed_ir
            cmd.angular.z = 0.0
        else:
            turn = np.clip(1.2 * error, -0.6, 0.6)
            cmd.linear.x = 0.0
            cmd.angular.z = turn

        self.pub.publish(cmd)

    # ==============================
    # 카메라 기반 정렬
    # ==============================
    def camera_step(self):
        data = sys.stdin.buffer.read(self.FRAME_SIZE)
        if len(data) < self.FRAME_SIZE:
            return False

        yuv = np.frombuffer(data, dtype=np.uint8).reshape((self.H * 3 // 2, self.W))
        frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)

        # 멀리서 관찰 (상단 ROI)
        roi = frame[0:int(self.H*0.4), :]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, self.black_threshold, 255, cv2.THRESH_BINARY_INV)
        coords = np.column_stack(np.where(mask > 0))

        cmd = Twist()

        if len(coords) == 0:
            # 라인 안보이면 천천히 회전
            cmd.linear.x = 0.0
            cmd.angular.z = 0.25
            self.pub.publish(cmd)
            return True

        mean_x = np.mean(coords[:, 1])
        img_center = self.W / 2
        error = mean_x - img_center
        self.last_error = error

        if abs(error) > self.cam_deadband:
            cmd.linear.x = 0.0
            cmd.angular.z = np.clip(-self.cam_turn_gain * error, -0.5, 0.5)
        else:
            # 중앙 맞춤 완료 → 전진
            cmd.linear.x = self.forward_speed_cam
            cmd.angular.z = 0.0
            # IR 센서로 라인 감지되면 IR_LINE_FOLLOW 모드로 전환
            # (IR 콜백에서 상태 전환)
            if self.ir_detected():
                self.state = 'IR_LINE_FOLLOW'
                print("IR line detected → IR_LINE_FOLLOW mode")

        self.pub.publish(cmd)
        return True

    # ==============================
    # IR 임시 체크 (라인 감지용)
    # 실제 IR 데이터가 들어올 때 상태 전환됨
    # ==============================
    def ir_detected(self):
        # /ir_sensor/range 메시지의 마지막 값 기반 체크
        # 임시: last_error 값으로 시뮬레이션 가능
        # 실제 환경에서는 ir_callback에서 상태 전환
        return False  # IR 센서가 아직 안들어왔으면 False

    # ==============================
    # 라인 서치
    # ==============================
    def search_line(self):
        cmd = Twist()
        cmd.linear.x = 0.0
        cmd.angular.z = 0.35 if self.last_error >= 0 else -0.35
        self.pub.publish(cmd)

    # ==============================
    # 메인 루프
    # ==============================
    def run(self):
        try:
            while True:
                if self.state in ['CAMERA_ALIGN', 'CAMERA_FORWARD']:
                    if not self.camera_step():
                        break
                # IR_LINE_FOLLOW 상태는 IR 콜백에서 처리
        except KeyboardInterrupt:
            pass
        finally:
            self.node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    tracker = LineTracker()
    tracker.run()
