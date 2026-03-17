import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage  # Image 대신 CompressedImage 사용
from pinky_interfaces.msg import Detection
import cv2
import numpy as np
import onnxruntime as ort

class PCInferenceNode(Node):
    def __init__(self):
        super().__init__('pc_inference_node')
        # 토픽 이름을 /camera/image_raw/compressed로 변경하고 타입을 바꿉니다.
        self.subscription = self.create_subscription(
            CompressedImage, '/camera/image_raw/compressed', self.image_callback, 10)
        
        self.result_pub = self.create_publisher(Detection, '/detection_result', 10)
        
        # ONNX 모델 로드
        self.session = ort.InferenceSession("best.onnx", providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.get_logger().info("YOLO 압축 이미지 추론 노드 시작!")

    def image_callback(self, msg):
        # 1. 압축된 데이터를 넘파이 배열로 변환 후 디코딩 (해제)
        np_arr = np.frombuffer(msg.data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR) # JPEG -> BGR 이미지로 변환

        if frame is None:
            return

        # 2. YOLO 전처리 및 추론
        # 320x240을 모델 크기(640x640)로 리사이징
        input_img = cv2.resize(frame, (640, 640))
        input_img = input_img.transpose(2, 0, 1) # HWC -> CHW
        input_img = np.expand_dims(input_img, axis=0).astype(np.float32) / 255.0
        
        outputs = self.session.run(None, {self.input_name: input_img})

        # 3. 결과 분석
        predictions = np.squeeze(outputs[0])
        res = Detection()
        res.stop_signal = False
        
        # YOLOv8 출력 해석 (predictions.T는 보통 [8400, 6] 형태)
        # 0,1,2,3: box, 4: score, 5: class (모델 구조에 따라 확인 필요)
        for pred in predictions.T:
            score = pred[4]
            if score > 0.6: 
                res.stop_signal = True
                break
        
        self.result_pub.publish(res)

        # 4. 화면 출력 및 정지 신호 표시
        if res.stop_signal:
            cv2.putText(frame, "STOP!! OBSTACLE", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        cv2.imshow('YOLO_PC_VIEW_COMPRESSED', frame)
        cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = PCInferenceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    cv2.destroyAllWindows()
    rclpy.shutdown()

if __name__ == '__main__':
    main()