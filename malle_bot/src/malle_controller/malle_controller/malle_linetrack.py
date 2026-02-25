# 실행하기 전에 
# ros2 launch pinky_bringup bringup_robot.launch.xml
# ros2 run pinky_sensor_adc main_node

import cv2
import time
import threading
import subprocess  # 추가: 외부 스크립트 실행용
import numpy as np
from flask import Flask, Response, render_template
from picamera2 import Picamera2
from libcamera import Transform

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

app = Flask(__name__)

# --- Picamera2 설정 ---
picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    main={"size": (320, 240)}, 
    transform=Transform(hflip=True, vflip=True)
)
picam2.configure(video_config)
picam2.start()

# 전역 변수
global_frame_bytes = None  # Flask 스트리밍용 (JPEG)
global_frame_raw = None    # ROS2 분석용 (Numpy)
frame_lock = threading.Lock()

# --- ROS2 제어 노드 ---
class PinkyAligner(Node):
    def __init__(self):
        super().__init__('pinky_aligner')
        self.publisher = self.create_publisher(Twist, '/cmd_vel', 10)
        self.cmd = Twist()
        self.state = 0  # 0:빨간점 정렬, 1:직진/소멸, 2:회전탐색, 3:검은선 정렬, 4:진입
        self.is_running = True

    def process_logic(self):
        global global_frame_raw
        while rclpy.ok() and self.is_running:
            frame = None
            with frame_lock:
                if global_frame_raw is not None:
                    frame = global_frame_raw.copy()
            
            if frame is None:
                time.sleep(0.1)
                continue

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 색상 범위 (환경에 맞춰 조정 필요)
            lower_red = np.array([0, 100, 100])
            upper_red = np.array([10, 255, 255])
            lower_black = np.array([0, 0, 0])
            upper_black = np.array([180, 255, 50])

            if self.state == 0:  # 빨간 점 중앙 정렬
                mask = cv2.inRange(hsv, lower_red, upper_red)
                self.align_to_target(mask, next_state=1)

            elif self.state == 1:  # 직진 및 빨간 점 소멸 대기
                mask = cv2.inRange(hsv, lower_red, upper_red)
                if np.sum(mask) < 500: # 사라지면
                    self.get_logger().info("Red dot lost. Moving forward...")
                    self.move_straight(0.7)
                    self.state = 2
                else:
                    self.cmd.linear.x = 0.08
                    self.cmd.angular.z = 0.0

            elif self.state == 2:  # 반시계 회전하며 검은 선 탐색
                mask = cv2.inRange(hsv, lower_black, upper_black)
                if np.sum(mask) > 5000: # 검은 선 발견
                    self.state = 3
                else:
                    self.cmd.linear.x = 0.0
                    self.cmd.angular.z = 0.3

            elif self.state == 3:  # 검은 선 중앙 정렬
                mask = cv2.inRange(hsv, lower_black, upper_black)
                self.align_to_target(mask, next_state=4)

            elif self.state == 4:  # 최종 진입
                self.move_straight(1.2)
                self.get_logger().info("Alignment Complete! Executing curve.py...")
                self.stop_and_launch_curve()
                break

            self.publisher.publish(self.cmd)
            time.sleep(0.1)

    def align_to_target(self, mask, next_state):
        M = cv2.moments(mask)
        if M['m00'] > 500:
            cx = int(M['m10']/M['m00'])
            err = 160 - cx
            self.cmd.linear.x = 0.05
            self.cmd.angular.z = err * 0.005
            if abs(err) < 7: self.state = next_state
        else:
            self.cmd.linear.x = 0.0
            self.cmd.angular.z = 0.2

    def move_straight(self, duration):
        start = time.time()
        while time.time() - start < duration:
            self.cmd.linear.x = 0.1
            self.cmd.angular.z = 0.0
            self.publisher.publish(self.cmd)
            time.sleep(0.1)

    def stop_and_launch_curve(self):
        # 로봇 정지
        self.cmd.linear.x = 0.0
        self.cmd.angular.z = 0.0
        self.publisher.publish(self.cmd)
        self.is_running = False
        # curve.py 실행 (경로를 실제 파일 위치로 수정하세요)
        subprocess.Popen(["python3", "newcurve.py"]) 

# --- 프레임 캡처 스레드 (수정됨) ---
def capture_frames():
    global global_frame_bytes, global_frame_raw
    while True:
        frame_data = picam2.capture_array()
        frame_bgr = cv2.cvtColor(frame_data, cv2.COLOR_RGB2BGR)
        
        # ROS 로직용 원본 데이터 저장
        with frame_lock:
            global_frame_raw = frame_bgr
            
            # Flask 스트리밍용 JPEG 인코딩
            ret, buffer = cv2.imencode('.jpg', frame_bgr)
            if ret:
                global_frame_bytes = buffer.tobytes()
        
        time.sleep(0.01)

# --- Flask 라우팅 ---
@app.route('/')
def index():
    return render_template('index.html')

def gen_frames():
    while True:
        with frame_lock:
            frame = global_frame_bytes
        if frame is None:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.01)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    rclpy.init()
    ros_node = PinkyAligner()

    # 스레드 1: 카메라 캡처
    t_cap = threading.Thread(target=capture_frames, daemon=True)
    # 스레드 2: ROS 제어 로직
    t_ros = threading.Thread(target=ros_node.process_logic, daemon=True)

    t_cap.start()
    t_ros.start()

    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        picam2.stop()
        rclpy.shutdown()