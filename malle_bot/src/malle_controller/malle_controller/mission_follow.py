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
from flask import Flask, Response
from picamera2 import Picamera2
from libcamera import Transform
from pupil_apriltags import Detector

# ==========================================
# [1. Flask & Camera 전역 설정]
# ==========================================
app = Flask(__name__)

# 카메라 초기화
picam2 = Picamera2()
config = picam2.create_video_configuration(
    main={"size": (320, 240), "format": "RGB888"},
    transform=Transform(hflip=True, vflip=True)
)
picam2.configure(config)
picam2.start()
picam2.set_controls({"ExposureTime": 15000}) 

global_frame = None
latest_gray_frame = None
frame_lock = threading.Lock()

@app.route('/')
def index():
    return '<html><body style="background:black; margin:0; display:flex; justify-content:center; align-items:center; height:100vh;"><img src="/video_feed" style="width:100%; max-width:640px; border:2px solid #333;"></body></html>'

def gen_frames():
    while True:
        with frame_lock:
            if global_frame is None: continue
            frame = global_frame
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.04)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# 카메라 캡처 스레드 함수
def capture_thread():
    global global_frame, latest_gray_frame
    while True:
        frame = picam2.capture_array()
        latest_gray_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        _, buffer = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
        with frame_lock: global_frame = buffer.tobytes()
        time.sleep(0.01)


# ==========================================
# [2. 통합된 ROS2 제어 노드]
# ==========================================
class MissionFollowNode(Node):

    def __init__(self):
        super().__init__('mission_follow')

        # Publisher & Subscriber
        self.cmd_pub    = self.create_publisher(Twist, '/cmd_vel', 10)
        self.result_pub = self.create_publisher(String, '/malle/mission_result', 10)
        self.trigger_sub = self.create_subscription(String, '/malle/mission_trigger', self._on_trigger, 10)
        
        # Service Clients (Pinky LED/Emotion)
        self.led_client = self.create_client(SetLed, '/set_led')
        self.emotion_client = self.create_client(Emotion, '/set_emotion')

        # AprilTag 디텍터
        self.detector = Detector(families='tag36h11', nthreads=4)

        # 상태 변수 초기화
        self.active = False
        self.state = "IDLE"
        self.target_id = 0 # 기본 추종할 태그 ID (trigger에서 변경 가능)
        self.last_seen_direction = 1.0
        self.lost_time = None
        self.start_time = 0.0
        
        # [코너링 최적화 파라미터]
        self.target_dist = 0.08
        self.linear_speed = 0.10        
        self.kp = 20.0                  
        self.kd = 3.5                   
        self.last_error_x = 0.0         
        self.max_angular = 15.0         
        self.search_turn_speed = 1.5    

        # 초기 표정 설정
        self.set_emotion("hello")
        
        # 제어 루프 타이머
        self.create_timer(0.02, self._control_loop)

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
        # Trigger 명령: "start_follow" 또는 "start_follow_N" (N은 태그 ID)
        if msg.data.startswith('start_follow'):
            self.active = True
            
            # 태그 ID 파싱 (ex: 'start_follow_5' 이면 ID 5를 추적)
            parts = msg.data.split('_')
            if len(parts) == 3 and parts[2].isdigit():
                self.target_id = int(parts[2])
            else:
                self.target_id = 0 # 기본 ID
            
            self.get_logger().info(f"Started following target ID: {self.target_id}")
            
            # 시작 상태 초기화 (기존 코드의 BACKING 로직 적용)
            self.state = "BACKING"
            self.start_time = time.time()
            self.set_led(255, 0, 0)
            self.set_emotion("basic")

        elif msg.data == 'idle':
            self.get_logger().info("Mission Idle requested.")
            self.active = False
            self.state = "IDLE"
            self.cmd_pub.publish(Twist())  # 즉시 정지
            self.set_led(0, 0, 0)          # LED 끄기
            self.set_emotion("hello")

    def _control_loop(self):
        global latest_gray_frame
        
        if not self.active or self.state == "IDLE":
            return
            
        twist = Twist()

        # 1. 초기 후진 로직
        if self.state == "BACKING":
            if time.time() - self.start_time < 7.0:
                twist.linear.x = -0.1
            else:
                self.state = "SEARCHING"
                self.set_led(0, 0, 255)
                self.set_emotion("interest")
            self.cmd_pub.publish(twist)
            return

        # 2. 태그 인식 및 추종 로직
        if latest_gray_frame is not None:
            tags = self.detector.detect(latest_gray_frame, estimate_tag_pose=True, 
                                        camera_params=(285, 285, 160, 120), tag_size=0.04)
            target = next((t for t in tags if t.tag_id == self.target_id), None)

            if target:
                self.lost_time = None
                if self.state == "SEARCHING":
                    self.state = "FOLLOWING"
                    self.set_led(0, 255, 0)
                    self.set_emotion("fun")

                tx, tz = float(target.pose_t[0]), float(target.pose_t[2])
                self.last_seen_direction = 1.0 if tx < 0 else -1.0

                # PD 제어 연산
                current_error = -tx
                error_diff = current_error - self.last_error_x
                angular_vel = (current_error * self.kp) + (error_diff * self.kd)
                
                # [지연 회전 알고리즘 / 코너링 최적화]
                is_sharp_turn = abs(tx) > 0.12
                proximity_boost = 1.0 + (0.05 / (tz + 0.05))
                raw_angular = angular_vel * proximity_boost

                if is_sharp_turn:
                    twist.linear.x = 0.10
                    twist.angular.z = float(np.clip(raw_angular * 0.7, -self.max_angular, self.max_angular))
                else:
                    twist.linear.x = self.linear_speed if tz > self.target_dist + 0.02 else 0.0
                    twist.angular.z = float(np.clip(raw_angular, -self.max_angular, self.max_angular))

                if tz <= self.target_dist:
                    twist.linear.x = 0.08 if is_sharp_turn else 0.0
                    
                    # (선택) 목적지에 안정적으로 도달했다면 Result를 Publish 할 수 있습니다.
                    # self._publish_result('success')
                
                self.last_error_x = current_error 
            
            else:
                # 태그 상실 시 로직
                if self.state == "FOLLOWING":
                    if self.lost_time is None: 
                        self.lost_time = time.time()
                    
                    if time.time() - self.lost_time > 5.0:
                        self.state = "SEARCHING"
                        self.set_led(0, 0, 255)
                        self.set_emotion("interest")
                    else:
                        twist.linear.x = 0.0
                        twist.angular.z = 0.0
                elif self.state == "SEARCHING":
                    twist.angular.z = self.search_turn_speed * self.last_seen_direction
        
        self.cmd_pub.publish(twist)

    def _publish_result(self, result: str):
        msg = String()
        msg.data = result
        self.result_pub.publish(msg)

# ==========================================
# [3. 메인 실행부]
# ==========================================
def main():
    rclpy.init()
    node = MissionFollowNode()
    
    # 카메라 캡처 및 웹 스트리밍 스레드 시작
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