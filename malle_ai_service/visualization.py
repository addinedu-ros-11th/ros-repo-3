import cv2
import time
import math
import threading
import numpy as np
from flask import Flask, Response
from ultralytics import YOLO
from picamera2 import Picamera2
from libcamera import Transform

# ==========================================
# 1. 설정
# ==========================================
MODEL_PATH = 'best.onnx'
FOCAL_LENGTH = 557.487
CX = 325.290

REAL_WIDTHS = {
    'big_box': 0.065,
    'cone': 0.0435,
    'pinky_pro': 0.103
}

app = Flask(__name__)

# ==========================================
# 2. 카메라 초기화 (⭐ 하나만 사용)
# ==========================================
picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    main={"size": (640, 480)},
    transform=Transform(hflip=True, vflip=True)
)
picam2.configure(video_config)
picam2.start()

# ==========================================
# 3. YOLO 로드
# ==========================================
model = YOLO(MODEL_PATH, task='detect')

global_frame = None
frame_lock = threading.Lock()

# ==========================================
# 4. 캡처 + YOLO + 시각화 스레드
# ==========================================
def capture_and_detect():
    global global_frame

    while True:
        frame = picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        results = model.predict(frame, conf=0.5, verbose=False, imgsz=640)

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]

                if label not in REAL_WIDTHS:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                pixel_width = x2 - x1
                if pixel_width <= 0:
                    continue

                # 거리 계산
                dist = (FOCAL_LENGTH * REAL_WIDTHS[label]) / pixel_width

                # 각도 계산
                center_x = (x1 + x2) / 2
                raw_offset = center_x - CX
                angle_deg = math.degrees(math.atan2(raw_offset, FOCAL_LENGTH))

                # 방향 판단
                if angle_deg > 7:
                    direction = "Right"
                    color = (0, 0, 255)
                elif angle_deg < -7:
                    direction = "Left"
                    color = (255, 0, 0)
                else:
                    direction = "Center"
                    color = (0, 255, 0)

                # 🔥 터미널 로그
                print(f"[{label:10}] 거리: {dist:.2f}m | 각도: {angle_deg:5.1f}° | 위치: {direction}")

                # 🔥 화면 시각화
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                text = f"{label} {dist:.2f}m {angle_deg:.1f}deg"
                cv2.putText(frame, text,
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, color, 2)

        # 중앙 기준선
        cv2.line(frame, (int(CX), 0), (int(CX), 480), (0, 255, 255), 2)

        # JPEG 인코딩
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        with frame_lock:
            global_frame = buffer.tobytes()

        time.sleep(0.03)

# ==========================================
# 5. 스트리밍 제너레이터
# ==========================================
def gen_frames():
    while True:
        with frame_lock:
            frame = global_frame
        if frame is None:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        time.sleep(0.03)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return """
    <html>
        <body>
            <h2>Pinky YOLO Distance Detection</h2>
            <img src="/video_feed" width="640">
        </body>
    </html>
    """

# ==========================================
# 6. 실행
# ==========================================
if __name__ == '__main__':
    thread = threading.Thread(target=capture_and_detect)
    thread.daemon = True
    thread.start()

    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        picam2.stop()