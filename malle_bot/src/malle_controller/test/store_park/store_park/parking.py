#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from pupil_apriltags import Detector
from pinkylib import Camera

# ===== 설정(수정 포인트) =====
TAG_FAMILY = "tag36h11"

WIDTH, HEIGHT = 640, 480

FWD_SPEED = 0.08              # <-- 직진 속도 (linear.x, 0.05~0.1 권장)
STOP_TAG_SIZE_PX = 280        # <-- 이 값 이상 커지면 "가까움"으로 보고 정지

# 태그가 안 보일 때 동작:
SEARCH_IF_NOT_FOUND = True
SEARCH_TURN_SPEED = 0.3       # <-- 회전 탐색 속도 (angular.z, 0이면 그냥 정지)
SEARCH_TURN_DIR = 1           # 1 또는 -1

LOOP_SLEEP = 0.03


def tag_size_px_from_corners(corners) -> float:
    c = np.array(corners, dtype=np.float32)
    top = np.linalg.norm(c[1] - c[0])
    bottom = np.linalg.norm(c[2] - c[3])
    return float(0.5 * (top + bottom))


def to_gray_uint8(frame):
    """frame이 gray/BGR/bytes(jpeg) 어떤 형태든 gray uint8로 변환"""
    if frame is None:
        return None

    if isinstance(frame, (bytes, bytearray)):
        arr = np.frombuffer(frame, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray

    if not isinstance(frame, np.ndarray):
        return None

    if frame.ndim == 2:
        gray = frame
    else:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if gray.dtype != np.uint8:
        gray = gray.astype(np.uint8)

    return gray


def get_target_detection(detector, gray, target_id):
    dets = detector.detect(gray)
    for d in dets:
        if d.tag_id == target_id:
            return d
    return None


class ParkingNode(Node):
    """/cmd_vel 토픽으로 모터를 제어하는 주차 노드"""

    def __init__(self):
        super().__init__("parking_node")
        self._pub = self.create_publisher(Twist, "/cmd_vel", 10)

    def move(self, linear_x: float, angular_z: float = 0.0):
        msg = Twist()
        msg.linear.x = linear_x
        msg.angular.z = angular_z
        self._pub.publish(msg)

    def stop(self):
        self.move(0.0, 0.0)


def main(target_id: int):
    # rclpy가 이미 초기화 안 되어있을 때만 init
    if not rclpy.ok():
        rclpy.init()

    node = ParkingNode()
    cam = Camera()
    detector = Detector(
        families=TAG_FAMILY,
        nthreads=2,
        quad_decimate=2.0,
        quad_sigma=0.0,
        refine_edges=1,
        decode_sharpening=0.25,
        debug=0
    )

    try:
        cam.start(width=WIDTH, height=HEIGHT)
        print(f"[INFO] Start forward-only parking. TARGET_ID={target_id}")
        print(f"[INFO] FWD_SPEED={FWD_SPEED}, STOP_TAG_SIZE_PX={STOP_TAG_SIZE_PX}")

        while True:
            frame = cam.get_frame()
            gray = to_gray_uint8(frame)
            if gray is None:
                continue

            target = get_target_detection(detector, gray, target_id)

            if target is None:
                # 태그 없으면 회전 탐색 또는 정지
                if SEARCH_IF_NOT_FOUND and SEARCH_TURN_SPEED > 0:
                    node.move(0.0, SEARCH_TURN_SPEED * SEARCH_TURN_DIR)
                else:
                    node.stop()
                time.sleep(LOOP_SLEEP)
                continue

            # 태그 있으면 크기 계산
            tag_size_px = tag_size_px_from_corners(target.corners)
            print(f"[TAG] size={tag_size_px:.1f}px (stop>={STOP_TAG_SIZE_PX})")

            # 가까우면 정지
            if tag_size_px >= STOP_TAG_SIZE_PX:
                node.stop()
                print("[DONE] Close enough -> STOP.")
                break

            # 아니면 직진
            node.move(FWD_SPEED)
            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted.")

    finally:
        try:
            node.stop()
        except Exception:
            pass
        try:
            cam.close()
        except Exception:
            pass
        try:
            node.destroy_node()
            # rclpy.shutdown() 제거 ← main_park.py가 rclpy 생명주기 관리
        except Exception:
            pass
        print("[INFO] Closed.")


if __name__ == "__main__":
    main(target_id=99)  # ← 직접 실행할 때만 여기서 지정