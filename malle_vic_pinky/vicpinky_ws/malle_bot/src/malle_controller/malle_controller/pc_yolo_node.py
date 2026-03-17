import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from pinky_interfaces.msg import Detection  # 이제 PC에서도 임포트 가능!
import cv2
import numpy as np
import onnxruntime as ort

class PCInferenceNode(Node):
    def __init__(self):
        super().__init__('pc_inference_node')
        # 1. 로봇의 압축 이미지 구독
        self.subscription = self.create_subscription(
            CompressedImage, '/camera/image_raw/compressed', self.image_callback, 10)
        
        # 2. 로봇에게 보낼 감지 결과 발행
        self.result_pub = self.create_publisher(Detection, '/detection_result', 10)
        
        # 3. ONNX 모델 로드 (best.onnx 파일이 같은 폴더에 있어야 함)
        # GPU가 있다면 ['CUDAExecutionProvider'] 사용 가능
        self.session = ort.InferenceSession("best.onnx", providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.get_logger().info("YOLO 모델 로드 완료!")

    def image_callback(self, msg):
        # 압축 해제
        np_arr = np.frombuffer(msg.data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # --- [여기에 YOLO 추론 로직 추가] ---
        # 예시로 640x640 리사이징 및 더미 결과 생성
        # 실제로는 여기서 모델 추론 후 class_name, x, y 등을 뽑아내야 합니다.
        
        # 4. 결과 전송 (예시: 항상 감지되었다고 가정)
        res = Detection()
        res.class_name = "obstacle"
        res.confidence = 0.88
        res.stop_signal = True  # 일단 테스트를 위해 True 전송
        
        self.result_pub.publish(res)
        
        # 화면 확인용
        cv2.imshow('Robot View (Compressed)', frame)
        cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = PCInferenceNode()
    rclpy.spin(node)
    cv2.destroyAllWindows()
    rclpy.shutdown()

if __name__ == '__main__':
    main()