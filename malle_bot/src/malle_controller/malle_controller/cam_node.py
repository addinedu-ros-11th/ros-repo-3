#!/usr/bin/env python3
"""
cam_node.py — 카메라 통합 노드

역할:
1. Picamera2(pinkylib Camera)를 단일 프로세스에서 열어 충돌 방지
2. /camera/image_raw (sensor_msgs/Image, rgb8) 발행 → bridge_node MJPEG 스트리밍용
3. Gray 프레임 콜백 → MissionFollowNode / TagTrackerNode / PinkyParkingNode 공급

실행:
    ros2 run malle_controller cam_node
    CAMERA_FPS=10 ros2 run malle_controller cam_node
"""

import os
import threading
import time

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import Image as RosImage

CAMERA_WIDTH  = int(os.getenv("CAMERA_WIDTH",  "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))
CAMERA_FPS    = int(os.getenv("CAMERA_FPS",    "15"))

try:
    import cv2
    import numpy as np
    from pinkylib import Camera
    from malle_controller.mission_follow import MissionFollowNode
    from malle_controller.tag_tracker import TagTrackerNode
    from malle_controller.mission_parking11 import PinkyParkingNode
    _DEPS_AVAILABLE = True
except Exception as e:
    _DEPS_AVAILABLE = False
    print(f"[cam_node] 의존성 없음: {e}")


class CamNode(Node):

    def __init__(self):
        super().__init__('cam_node')
        self._pub  = self.create_publisher(RosImage, '/camera/image_raw', 1)
        self._lock = threading.Lock()
        self._latest_gray = None

        threading.Thread(target=self._capture_loop, daemon=True).start()
        self.get_logger().info(
            f'[cam_node] 시작 ({CAMERA_WIDTH}x{CAMERA_HEIGHT} @ {CAMERA_FPS}fps)'
        )

    def get_gray_frame(self):
        """비전 노드가 동기적으로 호출하는 gray 프레임 콜백."""
        with self._lock:
            return self._latest_gray

    def _capture_loop(self):
        interval = 1.0 / CAMERA_FPS
        while rclpy.ok():
            cam = None
            try:
                cam = Camera()
                cam.start(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
                self.get_logger().info('[cam_node] Picamera2 열림')

                while rclpy.ok():
                    t0 = time.monotonic()
                    frame = cam.get_frame()  # RGB888, shape (H, W, 3)

                    with self._lock:
                        self._latest_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

                    msg = RosImage()
                    msg.header.stamp    = self.get_clock().now().to_msg()
                    msg.header.frame_id = 'camera'
                    msg.height   = frame.shape[0]
                    msg.width    = frame.shape[1]
                    msg.encoding = 'rgb8'
                    msg.step     = frame.shape[1] * 3
                    msg.data     = frame.tobytes()
                    self._pub.publish(msg)

                    elapsed = time.monotonic() - t0
                    wait = interval - elapsed
                    if wait > 0:
                        time.sleep(wait)

            except RuntimeError as e:
                self.get_logger().warn(f'[cam_node] 카메라 오류: {e} — 3초 후 재시도')
                if cam:
                    try: cam.close()
                    except Exception: pass
                time.sleep(3.0)
            except Exception as e:
                self.get_logger().warn(f'[cam_node] 예외: {e} — 5초 후 재시도')
                if cam:
                    try: cam.close()
                    except Exception: pass
                time.sleep(5.0)


def main():
    rclpy.init()

    if not _DEPS_AVAILABLE:
        rclpy.logging.get_logger('cam_node').error(
            'pinkylib / cv2 없음 — 카메라 노드를 시작할 수 없습니다.'
        )
        rclpy.shutdown()
        return

    cam_node = CamNode()
    nodes = [cam_node]

    try:
        nodes += [
            MissionFollowNode(cam_node.get_gray_frame),
            TagTrackerNode(cam_node.get_gray_frame),
            PinkyParkingNode(cam_node.get_gray_frame),
        ]
    except Exception as e:
        rclpy.logging.get_logger('cam_node').warn(
            f'[cam_node] 비전 노드 초기화 실패: {e}'
        )

    executor = MultiThreadedExecutor()
    for node in nodes:
        executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        for node in nodes:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
