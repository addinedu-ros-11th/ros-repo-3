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
# [2. 통합된 Mission Tracker 노드]
# ==========================================
class MissionFollowNode(Node):

    def __init__(self):
        super().__init__('mission_follow_node')

        # ROS2 통신 설정
        self.cmd_pub    = self.create_publisher(Twist, '/cmd_vel', 10)
        self.result_pub = self.create_publisher(String, '/malle/mission_result', 10)
        self.trigger_sub = self.create_subscription(String, '/malle/mission_trigger', self._on_trigger, 10)
        
        self.led_client = self.create_client(SetLed, '/set_led')
        self.emotion_client = self.create_client(Emotion, '/set_emotion')

        # AprilTag 디텍터
        self.detector = Detector(families='tag36h11', nthreads=4)

        # 제어 파라미터 (제공된 코드 기반 최적화)
        self._mode = 'idle'            # 'idle', 'follow', 'dock'
        self.target_id = 0
        self.target_dist_follow = 0.12 # 팔로우 유지 거리 (m)
        self.target_dist_dock = 0.08   # 도킹 목표 거리 (m)
        
        self.kp_lin = 1.2
        self.kp_ang = 15.0
        self.kd_ang = 3.5
        self.last_error_x = 0.0
        
        self.max_linear = 0.25
        self.max_angular = 15.0
        self.search_turn_speed = 1.5

        # 상태 변수
        self.detected = False
        self.last_seen_direction = 1.0
        self.lost_time = None
        
        self.set_emotion("hello")
        self.create_timer(0.033, self._control_loop) # 약 30Hz

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
        
        # 'start_follow_N' 또는 'dock_N' 형태로 ID 지정 가능
        if 'start_follow' in token:
            self._mode = 'follow'
            self._update_target_id(token)
            self.set_led(0, 255, 0); self.set_emotion("fun")
            self.get_logger().info(f'[Mission] Follow Mode Start (ID:{self.target_id})')
            
        elif 'dock' in token:
            self._mode = 'dock'
            self._update_target_id(token)
            self.set_led(255, 100, 0); self.set_emotion("interest")
            self.get_logger().info(f'[Mission] Docking Mode Start (ID:{self.target_id})')
            
        elif token in ('idle', 'stop'):
            self._mode = 'idle'
            self.cmd_pub.publish(Twist())
            self.set_led(0, 0, 0); self.set_emotion("hello")
            self.get_logger().info('[Mission] Idle Mode')

    def _update_target_id(self, token):
        parts = token.split('_')
        if len(parts) >= 3 and parts[-1].isdigit():
            self.target_id = int(parts[-1])

    def _control_loop(self):
        global latest_gray_frame
        if self._mode == 'idle' or latest_gray_frame is None:
            return

        twist = Twist()
        tags = self.detector.detect(latest_gray_frame, estimate_tag_pose=True, 
                                    camera_params=(285, 285, 160, 120), tag_size=0.04)
        
        target = next((t for t in tags if t.tag_id == self.target_id), None)

        if target:
            self.detected = True
            self.lost_time = None
            
            tx = float(target.pose_t[0]) # 가로 오차
            tz = float(target.pose_t[2]) # 거리(깊이)
            
            self.last_seen_direction = 1.0 if tx < 0 else -1.0
            
            # 1. 거리 제어 (Linear)
            target_dist = self.target_dist_dock if self._mode == 'dock' else self.target_dist_follow
            err_lin = tz - target_dist
            
            if abs(err_lin) > 0.02:
                twist.linear.x = float(np.clip(err_lin * self.kp_lin, -self.max_linear, self.max_linear))
            
            # 2. 방향 제어 (Angular + PD)
            current_error_x = -tx
            error_diff = current_error_x - self.last_error_x
            raw_angular = (current_error_x * self.kp_ang) + (error_diff * self.kd_ang)
            
            # 근접 시 회전 보정 (내륜차 방지 로직 포함)
            proximity_boost = 1.0 + (0.05 / (tz + 0.05))
            twist.angular.z = float(np.clip(raw_angular * proximity_boost, -self.max_angular, self.max_angular))
            
            self.last_error_x = current_error_x

            # 3. 도킹 완료 판정
            if self._mode == 'dock' and abs(err_lin) < 0.05 and abs(tx) < 0.03:
                self._mode = 'idle'
                self.cmd_pub.publish(Twist())
                self._publish_result('docked')
                self.set_led(0, 255, 0); self.set_emotion("happy")
                self.get_logger().info('[Mission] Docking Completed')

        else:
            # 태그 상실 시: 제자리에서 회전하며 찾기
            self.detected = False
            if self.lost_time is None: self.lost_time = time.time()
            
            # 2초 동안은 정지 후 대기, 그 이후부터는 회전하며 검색
            if time.time() - self.lost_time > 2.0:
                twist.angular.z = self.search_turn_speed * self.last_seen_direction
            else:
                twist.linear.x = 0.0
                twist.angular.z = 0.0

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