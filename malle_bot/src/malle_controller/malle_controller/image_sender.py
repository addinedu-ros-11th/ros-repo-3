import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import cv2
from cv_bridge import CvBridge
import numpy as np

class ImagePublisher(Node):
    def __init__(self):
        super().__init__('pinky_camera_node')
        # 압축된 이미지 토픽 발행
        self.publisher_ = self.create_publisher(CompressedImage, '/camera/image_raw/compressed', 10)
        self.timer = self.create_timer(0.1, self.timer_callback) # 10 FPS 설정 (네트워크 최적화)
        self.cap = cv2.VideoCapture(0) # 카메라 인덱스
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)  # 해상도 최적화
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        self.bridge = CvBridge()

    def timer_callback(self):
        ret, frame = self.cap.read()
        if ret:
            # 메시지 생성 및 JPEG 압축
            msg = CompressedImage()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.format = "jpeg"
            # cv2.imencode로 압축 (퀄리티 70 정도로 설정하여 용량 최적화)
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            msg.data = np.array(buffer).tobytes()
            
            self.publisher_.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = ImagePublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()