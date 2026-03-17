import cv2
import time
import math
import numpy as np

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Vector3

from ultralytics import YOLO
from picamera2 import Picamera2
from libcamera import Transform


MODEL_PATH = 'best.onnx'
FOCAL_LENGTH = 557.487
CX = 325.290

REAL_WIDTHS = {
    'big_box': 0.065,
    'cone': 0.0435,
    'pinky_pro': 0.103
}


class ObstaclePublisher(Node):

    def __init__(self):

        super().__init__('yolo_obstacle_detector')

        self.publisher = self.create_publisher(
            Vector3,
            '/obstacle',
            10
        )

        self.model = YOLO(MODEL_PATH, task='detect')

        self.picam2 = Picamera2()
        video_config = self.picam2.create_video_configuration(
            main={"size": (640, 480)},
            transform=Transform(hflip=True, vflip=True)
        )

        self.picam2.configure(video_config)
        self.picam2.start()

        self.timer = self.create_timer(0.05, self.process_frame)


    def process_frame(self):

        frame = self.picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        results = self.model.predict(frame, conf=0.5, verbose=False, imgsz=640)

        for r in results:
            for box in r.boxes:

                cls_id = int(box.cls[0])
                label = self.model.names[cls_id]

                if label not in REAL_WIDTHS:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                pixel_width = x2 - x1

                if pixel_width <= 0:
                    continue

                dist = (FOCAL_LENGTH * REAL_WIDTHS[label]) / pixel_width

                center_x = (x1 + x2) / 2
                raw_offset = center_x - CX

                angle_deg = math.degrees(
                    math.atan2(raw_offset, FOCAL_LENGTH)
                )

                if angle_deg > 7:
                    direction = 1
                elif angle_deg < -7:
                    direction = -1
                else:
                    direction = 0

                msg = Vector3()
                msg.x = float(dist)
                msg.y = float(angle_deg)
                msg.z = float(direction)

                self.publisher.publish(msg)

                self.get_logger().info(
                    f"{label} dist:{dist:.2f} angle:{angle_deg:.1f}"
                )


def main():

    rclpy.init()

    node = ObstaclePublisher()

    rclpy.spin(node)

    node.picam2.stop()
    node.destroy_node()

    rclpy.shutdown()


if __name__ == '__main__':
    main()