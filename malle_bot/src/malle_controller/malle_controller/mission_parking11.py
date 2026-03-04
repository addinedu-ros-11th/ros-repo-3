#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String, UInt16MultiArray
from pinky_interfaces.srv import SetLed, Emotion

import time
from pupil_apriltags import Detector


# ==========================================
# [Pinky Safe Vertical Parking 노드]
# ==========================================
class PinkyParkingNode(Node):

    def __init__(self, get_gray_frame):
        super().__init__('pinky_parking_node')
        self.get_gray_frame = get_gray_frame

        # ROS2 통신 설정
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.result_pub = self.create_publisher(String, '/malle/mission_result', 10)
        self.trigger_sub = self.create_subscription(String, '/malle/mission_trigger', self._on_trigger, 10)
        self.ir_sub = self.create_subscription(UInt16MultiArray, '/ir_sensor/range', self._ir_callback, 10)

        self.led_client = self.create_client(SetLed, '/set_led')
        self.emotion_client = self.create_client(Emotion, '/set_emotion')

        # AprilTag 디텍터
        self.detector = Detector(families='tag36h11', nthreads=2)

        # 제어 파라미터 및 상태
        self.target_id = 11
        self.width, self.height = 640, 480
        self.state = "IDLE"
        
        # IR 및 라인 감지 변수
        self.ir_data = [4095, 4095, 4095]
        self.lines_encountered = 0
        self.line_on_flag = False
        self.continuous_detect_count = 0
        
        self.last_target_time = time.time()

        self.set_emotion("hello")
        self.create_timer(0.05, self._control_loop)

    def set_led(self, r, g, b):
        if self.led_client.service_is_ready():
            req = SetLed.Request()
            req.command, req.pixels, req.r, req.g, req.b = 'set_pixel', [4,5,6,7], r, g, b
            self.led_client.call_async(req)

    def set_emotion(self, name):
        if self.emotion_client.service_is_ready():
            req = Emotion.Request()
            req.emotion = name
            self.emotion_client.call_async(req)

    def _ir_callback(self, msg):
        self.ir_data = msg.data
        is_black = any(val < 250 for val in self.ir_data)
        
        if is_black:
            self.continuous_detect_count += 1
        else:
            self.continuous_detect_count = 0
            
        if self.continuous_detect_count >= 3:
            if not self.line_on_flag:
                self.lines_encountered += 1
                self.line_on_flag = True
                self.get_logger().info(f"Line detected! Count: {self.lines_encountered}")
        else:
            if not is_black:
                self.line_on_flag = False

    def _on_trigger(self, msg: String):
        token = msg.data.strip()
        if token == 'start_parking':
            self.state = "FIND_TAG"
            self.lines_encountered = 0
            self.set_led(0, 0, 255)
            self.set_emotion("interest")
            self.get_logger().info(">>> PARKING MISSION START <<<")
        elif token in ('idle', 'stop'):
            self.state = "IDLE"
            self._send_twist(0.0, 0.0)
            self.set_led(0, 0, 0)
            self.set_emotion("hello")

    def _control_loop(self):
        gray = self.get_gray_frame()
        if self.state in ["IDLE", "DONE"] or gray is None:
            return

        # 1. 태그 감지
        tags = self.detector.detect(gray)
        target = next((d for d in tags if d.tag_id == self.target_id), None)

        # 2. 태그가 없을 때 처리
        if not target:
            if self.state != "UTURN" and time.time() - self.last_target_time > 0.3:
                self._send_twist(0.0, 0.5)
            return

        self.last_target_time = time.time()
        cx, _ = target.center
        c = target.corners
        tag_left, tag_right = min(c[:, 0]), max(c[:, 0])
        tag_top, tag_bottom = min(c[:, 1]), max(c[:, 1])
        size = tag_right - tag_left
        
        err_x = cx - (self.width / 2.0)
        abs_err = abs(err_x)

        # 3. 주차 완료 시퀀스 (매우 근접 시 180도 회전)
        if size > 250:
            self._perform_uturn()
            return

        # 4. 최종 접근 (라인 감지 또는 근접 시)
        if tag_top < 10 or tag_bottom > 470 or size > 250:
            if self.lines_encountered >= 2:
                self._perform_uturn()
                return
            else:
                self.state = "FINAL_APPROACH"
                self._send_twist(0.12, 0.0)
                return

        # 5. 소실 방지 및 정밀 정렬
        if tag_left < 20:
            self._send_twist(0.0, 0.4)
            return
        elif tag_right > 620:
            self._send_twist(0.0, -0.4)
            return

        # 6. 정밀 정렬 주행 (Precision Align)
        self.state = "PRECISION_ALIGN"
        base_linear = 0.10
        turn_gain = 0.001 if abs_err > 100 else 0.002
        angular_z = -err_x * turn_gain
        self._send_twist(base_linear, angular_z)

    def _perform_uturn(self):
        self.get_logger().info("!!! ARRIVED - PERFORMING 180 TURN !!!")
        self.state = "UTURN"
        self.set_led(255, 255, 0)

        start_u = time.time()
        while time.time() - start_u < 1.1:
            self._send_twist(0.0, 3.0)
            time.sleep(0.01)
            
        self._send_twist(0.0, 0.0)
        self.state = "DONE"
        self.set_led(0, 255, 0)
        self.set_emotion("happy")
        self._publish_result("parked")

    def _send_twist(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.cmd_pub.publish(msg)

    def _publish_result(self, result: str):
        msg = String()
        msg.data = result
        self.result_pub.publish(msg)
