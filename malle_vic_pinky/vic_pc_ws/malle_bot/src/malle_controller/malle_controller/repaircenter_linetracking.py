#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from pinky_interfaces.srv import SetLed, Emotion

import cv2
import numpy as np
import threading
import time
import subprocess
from flask import Flask, Response
from picamera2 import Picamera2
from libcamera import Transform

# ==========================================
# [1. Flask & Camera 전역 설정]
# ==========================================
app = Flask(__name__)

picam2 = Picamera2()
config = picam2.create_video_configuration(
    main={"size": (320, 240), "format": "RGB888"}, # 분석 효율을 위해 320x240 유지
    transform=Transform(hflip=True, vflip=True)
)
picam2.configure(config)
picam2.start()

global_frame_bytes = None
global_frame_raw = None
frame_lock = threading.Lock()

@app.route('/')
def index():
    return '<html><body style="background:black; margin:0; display:flex; justify-content:center; align-items:center; height:100vh;"><img src="/video_feed" style="width:100%; max-width:640px; border:2px solid #333;"></body></html>'

def gen_frames():
    while True:
        with frame_lock:
            if global_frame_bytes is None: continue
            frame = global_frame_bytes
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.04)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def capture_thread():
    global global_frame_bytes, global_frame_raw
    while True:
        frame = picam2.capture_array()
        # ROS 분석용 (BGR)
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        # 스트리밍용 인코딩
        _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
        
        with frame_lock:
            global_frame_raw = frame_bgr
            global_frame_bytes = buffer.tobytes()
        time.sleep(0.01)

# ==========================================
# [2. Pinky Color Aligner 노드]
# ==========================================
class PinkyAlignerNode(Node):

    def __init__(self):
        super().__init__('pinky_aligner_node')

        # ROS2 통신 설정
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.result_pub = self.create_publisher(String, '/malle/mission_result', 10)
        self.trigger_sub = self.create_subscription(String, '/malle/mission_trigger', self._on_trigger, 10)
        
        self.led_client = self.create_client(SetLed, '/set_led')
        self.emotion_client = self.create_client(Emotion, '/set_emotion')

        # 상태 변수
        self.active = False
        self.state = 0  # 0:빨간점 정렬, 1:직진/소멸, 2:회전탐색, 3:검은선 정렬, 4:진입완료
        
        # 색상 범위 설정 (HSV)
        self.lower_red = np.array([0, 100, 100])
        self.upper_red = np.array([10, 255, 255])
        self.lower_black = np.array([0, 0, 0])
        self.upper_black = np.array([180, 255, 50])

        self.set_emotion("hello")
        self.create_timer(0.1, self._control_loop)

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

    def _on_trigger(self, msg: String):
        token = msg.data.strip()
        if token == 'start_align':
            self.active = True
            self.state = 0
            self.set_led(255, 0, 0)
            self.set_emotion("interest")
            self.get_logger().info(">>> ALIGN MISSION START <<<")
        elif token in ('idle', 'stop'):
            self.active = False
            self._send_twist(0.0, 0.0)
            self.set_led(0, 0, 0)

    def _control_loop(self):
        global global_frame_raw
        if not self.active or global_frame_raw is None:
            return

        frame = None
        with frame_lock:
            frame = global_frame_raw.copy()
            
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        twist = Twist()

        if self.state == 0:  # 빨간 점 중앙 정렬
            mask = cv2.inRange(hsv, self.lower_red, self.upper_red)
            if self._align_to_target(mask, twist):
                self.state = 1
                self.get_logger().info("State 0 -> 1: Red Aligned")

        elif self.state == 1:  # 직진하며 빨간 점 소멸 대기
            mask = cv2.inRange(hsv, self.lower_red, self.upper_red)
            if np.sum(mask) < 500: # 빨간색이 사라지면
                self.get_logger().info("Red dot lost. Moving forward...")
                self._move_straight(0.7)
                self.state = 2
            else:
                twist.linear.x = 0.08
                twist.angular.z = 0.0

        elif self.state == 2:  # 반시계 회전하며 검은 선 탐색
            mask = cv2.inRange(hsv, self.lower_black, self.upper_black)
            if np.sum(mask) > 5000: # 검은 선 발견
                self.state = 3
                self.set_led(0, 0, 255)
                self.get_logger().info("State 2 -> 3: Black Line Found")
            else:
                twist.linear.x = 0.0
                twist.angular.z = 0.4

        elif self.state == 3:  # 검은 선 중앙 정렬
            mask = cv2.inRange(hsv, self.lower_black, self.upper_black)
            if self._align_to_target(mask, twist):
                self.state = 4
                self.get_logger().info("State 3 -> 4: Black Aligned")

        elif self.state == 4:  # 최종 진입 및 외부 스크립트 실행
            self._move_straight(1.2)
            self.get_logger().info("Alignment Complete! Launching newcurve.py...")
            self.active = False
            self._publish_result("aligned")
            self._launch_next_script()
            return

        self.cmd_pub.publish(twist)

    def _align_to_target(self, mask, twist_msg):
        """대상 마스크를 중앙(160)에 맞추는 헬퍼 함수"""
        M = cv2.moments(mask)
        if M['m00'] > 500:
            cx = int(M['m10']/M['m00'])
            err = 160 - cx
            twist_msg.linear.x = 0.06
            twist_msg.angular.z = float(err * 0.006)
            return abs(err) < 8
        else:
            # 대상을 놓치면 제자리 회전하며 찾기
            twist_msg.linear.x = 0.0
            twist_msg.angular.z = 0.3
            return False

    def _move_straight(self, duration):
        start = time.time()
        while time.time() - start < duration:
            msg = Twist()
            msg.linear.x = 0.12
            self.cmd_pub.publish(msg)
            time.sleep(0.1)
        self._send_twist(0.0, 0.0)

    def _launch_next_script(self):
        self._send_twist(0.0, 0.0)
        self.set_led(0, 255, 0)
        self.set_emotion("happy")
        # 외부 프로세스로 newcurve.py 실행
        try:
            subprocess.Popen(["python3", "newcurve.py"])
        except Exception as e:
            self.get_logger().error(f"Failed to launch newcurve.py: {e}")

    def _send_twist(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.cmd_pub.publish(msg)

    def _publish_result(self, result: str):
        msg = String()
        msg.data = result
        self.result_pub.publish(msg)

# ==========================================
# [3. 메인 실행부]
# ==========================================
def main():
    rclpy.init()
    node = PinkyAlignerNode()
    
    threading.Thread(target=capture_thread, daemon=True).start()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True).start()
    
    try: 
        rclpy.spin(node)
    except KeyboardInterrupt: 
        pass
    finally: 
        node.set_emotion("hello")
        node.destroy_node()
        rclpy.shutdown()
        picam2.stop()

if __name__ == '__main__': 
    main()