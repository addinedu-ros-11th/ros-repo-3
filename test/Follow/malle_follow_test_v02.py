import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from pinky_interfaces.srv import SetLed, Emotion
import cv2
import numpy as np
import threading
import time
from flask import Flask, Response
from picamera2 import Picamera2
from libcamera import Transform
from pupil_apriltags import Detector

# [1. Flask 설정]
app = Flask(__name__)

# [2. 카메라 설정]
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

# [3. 로봇 제어 노드]
class PinkyController(Node):
    def __init__(self):
        super().__init__('pinky_ultra_node')
        
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.led_client = self.create_client(SetLed, '/set_led')
        self.emotion_client = self.create_client(Emotion, '/set_emotion')
        
        self.detector = Detector(families='tag36h11', nthreads=4)
        
        self.state = "IDLE"
        self.target_id = -1
        self.last_seen_direction = 1.0
        self.lost_time = None
        self.first_run = True 
        
        # --- [코너링 최적화 파라미터] ---
        self.target_dist = 0.08         # 20cm로 늘려 여유 공간 확보 (내륜차 해결 핵심)
        self.linear_speed = 0.10        
        self.kp = 20.0                  # 회전 민감도를 살짝 낮춤
        self.kd = 3.5                   # D 게인을 높여서 회전을 묵직하게
        self.last_error_x = 0.0         
        self.max_angular = 15.0         
        self.search_turn_speed = 1.5    
        # -------------------------------

        self.set_emotion("hello")
        self.timer = self.create_timer(0.02, self.control_loop)

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

    def control_loop(self):
        global latest_gray_frame
        twist = Twist()
        
        if self.state == "IDLE": return

        if self.state == "BACKING":
            if time.time() - self.start_time < 7.0:
                twist.linear.x = -0.1
            else:
                self.state = "SEARCHING"
                self.first_run = False
                self.set_led(0, 0, 255); self.set_emotion("interest")
            self.cmd_pub.publish(twist); return

        if latest_gray_frame is not None:
            tags = self.detector.detect(latest_gray_frame, estimate_tag_pose=True, 
                                        camera_params=(285, 285, 160, 120), tag_size=0.04)
            target = next((t for t in tags if t.tag_id == self.target_id), None)

            if target:
                self.lost_time = None
                if self.state == "SEARCHING":
                    self.state = "FOLLOWING"
                    self.set_led(0, 255, 0); self.set_emotion("fun")

                tx, tz = float(target.pose_t[0]), float(target.pose_t[2])
                self.last_seen_direction = 1.0 if tx < 0 else -1.0

                # PD 제어 연산
                current_error = -tx
                error_diff = current_error - self.last_error_x
                angular_vel = (current_error * self.kp) + (error_diff * self.kd)
                
                # [지연 회전 알고리즘]
                # 태그가 옆으로 많이 치우쳤을 때(급코너) 로직
                is_sharp_turn = abs(tx) > 0.12
                
                proximity_boost = 1.0 + (0.05 / (tz + 0.05))
                raw_angular = angular_vel * proximity_boost

                if is_sharp_turn:
                    # 1. 태그가 옆에 있어도 즉시 꺾지 않고 전진 속도를 유지하여 '크게' 돌게 함
                    twist.linear.x = 0.10  # 최소 전진 속도 확보
                    # 2. 회전력을 원래의 70% 수준으로 억제하여 즉각적인 꺾임 방지
                    twist.angular.z = float(np.clip(raw_angular * 0.7, -self.max_angular, self.max_angular))
                else:
                    # 일반 주행 시
                    twist.linear.x = self.linear_speed if tz > self.target_dist + 0.02 else 0.0
                    twist.angular.z = float(np.clip(raw_angular, -self.max_angular, self.max_angular))

                # 거리 제어 보정
                if tz <= self.target_dist:
                    # 너무 가까우면 회전만 하되, 급코너 중이면 살짝 전진해서 빠져나옴
                    twist.linear.x = 0.08 if is_sharp_turn else 0.0
                
                self.last_error_x = current_error 
            
            else:
                # 태그 상실 시 로직 (기존과 동일)
                if self.state == "FOLLOWING":
                    if self.lost_time is None: self.lost_time = time.time()
                    if time.time() - self.lost_time > 5.0:
                        self.state = "SEARCHING"
                        self.set_led(0, 0, 255); self.set_emotion("interest")
                    else:
                        twist.linear.x = 0.0; twist.angular.z = 0.0
                elif self.state == "SEARCHING":
                    twist.angular.z = self.search_turn_speed * self.last_seen_direction
        
        self.cmd_pub.publish(twist)

# [4. 스레드 실행]
def capture_thread():
    global global_frame, latest_gray_frame
    while True:
        frame = picam2.capture_array()
        latest_gray_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        _, buffer = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
        with frame_lock: global_frame = buffer.tobytes()
        time.sleep(0.01)

def input_thread(node):
    while rclpy.ok():
        val = input("\n[Pinky Delayed Turn] Enter Tag ID (0-15): ")
        if val.strip().isdigit():
            node.target_id = int(val)
            if node.first_run:
                node.state = "BACKING"; node.start_time = time.time()
                node.set_led(255, 0, 0); node.set_emotion("basic")
            else:
                node.state = "SEARCHING"; node.set_led(0, 0, 255); node.set_emotion("interest")

def main():
    rclpy.init()
    node = PinkyController()
    threading.Thread(target=capture_thread, daemon=True).start()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True).start()
    threading.Thread(target=input_thread, args=(node,), daemon=True).start()
    try: rclpy.spin(node)
    except: pass
    finally: node.set_emotion("hello"); rclpy.shutdown(); picam2.stop()

if __name__ == '__main__': main()