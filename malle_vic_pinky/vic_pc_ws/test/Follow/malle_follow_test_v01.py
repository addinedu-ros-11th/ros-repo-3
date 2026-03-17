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

# [2. 카메라 및 디텍터 설정]
picam2 = Picamera2()
config = picam2.create_video_configuration(
    main={"size": (320, 240), "format": "RGB888"},
    transform=Transform(hflip=True, vflip=True)
)
picam2.configure(config)
picam2.start()

# 모션 블러 방지를 위한 노출 조절 (선택 사항, 주변이 밝을 때 효과적)
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
        time.sleep(0.04) # 약 25fps

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
        self.first_run = True  # 첫 실행 시에만 후진하기 위한 플래그
        
        # --- [초고반응성 PD 제어 파라미터] ---
        self.target_dist = 0.10         # 10cm 유지
        self.linear_speed = 0.10        # 전진 속도
        self.kp = 30                  # P Gain: 현재 오차 반응 (높을수록 중앙으로 빨리 복귀)
        self.kd = 2.8                   # D Gain: 오차 변화율 감쇄 (높을수록 떨림 방지)
        self.last_error_x = 0.0         # 이전 오차 저장
        self.max_angular = 30          # 최대 회전 속도 (매우 빠름)
        self.search_turn_speed = 1.5    # 탐색 시 회전 속도
        # ------------------------------------

        self.set_emotion("hello")
        # 반응 속도를 위해 타이머를 0.02초(50Hz)로 설정
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

        # 1. 후진 모드 (완전 처음 시작할 때만 작동)
        if self.state == "BACKING":
            if time.time() - self.start_time < 7.0:
                twist.linear.x = -0.1
            else:
                self.state = "SEARCHING"
                self.first_run = False
                self.set_led(0, 0, 255); self.set_emotion("interest")
            self.cmd_pub.publish(twist); return

        # 2. 메인 제어 루프
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

                # [PD 제어 연산]
                current_error = -tx
                error_diff = current_error - self.last_error_x
                
                # P(현재 오차) + D(오차의 변화량)
                angular_vel = (current_error * self.kp) + (error_diff * self.kd)
                
                # 근접 시 반응성 증폭 (가까울수록 더 빡세게 회전)
                proximity_boost = 1.0 + (0.05 / (tz + 0.05))
                twist.angular.z = float(np.clip(angular_vel * proximity_boost, -self.max_angular, self.max_angular))

                # 거리 제어 (10cm 유지)
                if tz > self.target_dist + 0.02:
                    twist.linear.x = self.linear_speed
                else:
                    twist.linear.x = 0.0
                
                self.last_error_x = current_error # 다음 연산을 위해 저장
            
            else:
                # 태그 상실 시
                if self.state == "FOLLOWING":
                    if self.lost_time is None: self.lost_time = time.time()
                    
                    # 5초간 대기 (정지)
                    if time.time() - self.lost_time > 5.0:
                        self.state = "SEARCHING"
                        self.set_led(0, 0, 255); self.set_emotion("interest")
                    else:
                        twist.linear.x = 0.0; twist.angular.z = 0.0

                elif self.state == "SEARCHING":
                    # 마지막 방향으로 탐색 회전
                    twist.angular.z = self.search_turn_speed * self.last_seen_direction
        
        self.cmd_pub.publish(twist)

# [4. 스레드 실행부]
def capture_thread():
    global global_frame, latest_gray_frame
    while True:
        frame = picam2.capture_array()
        latest_gray_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        # JPEG 압축 화질 조절 (70: 용량 대 화질 최적)
        _, buffer = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
        with frame_lock:
            global_frame = buffer.tobytes()
        time.sleep(0.01)

def input_thread(node):
    while rclpy.ok():
        val = input("\n[Pinky Final] Enter Tag ID (0-15): ")
        if val.strip().isdigit():
            node.target_id = int(val)
            if node.first_run:
                node.state = "BACKING"
                node.start_time = time.time()
                node.set_led(255, 0, 0); node.set_emotion("basic")
                print(f"-> FIRST RUN: Backing 7s for Target {val}...")
            else:
                node.state = "SEARCHING"
                node.set_led(0, 0, 255); node.set_emotion("interest")
                print(f"-> NEW TARGET: Searching {val} immediately...")

def main():
    rclpy.init()
    node = PinkyController()
    
    # 스레드 생성
    t1 = threading.Thread(target=capture_thread, daemon=True)
    t2 = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True)
    t3 = threading.Thread(target=input_thread, args=(node,), daemon=True)
    
    t1.start(); t2.start(); t3.start()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.set_emotion("hello")
        rclpy.shutdown()
        picam2.stop()

if __name__ == '__main__':
    main()