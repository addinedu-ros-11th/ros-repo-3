import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import math
from ultralytics import YOLO
from pinkylib import Camera

class PreciseAvoidance20cmTunedNode(Node):
    def __init__(self):
        super().__init__('precise_avoidance_20cm_tuned')
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.model = YOLO('best.onnx', task='detect')
        self.camera = Camera()
        self.camera.start(width=640, height=480)

        # 설정 및 상수
        self.REAL_WIDTHS = {'big_box': 0.055, 'cone': 0.125, 'pinky_pro': 0.115}
        self.FOCAL_LENGTH = 557.487
        self.CX = 325.290

        # --- 주행 변수 ---
        self.linear_speed = 0.15
        self.target_dist = 1.0     
        self.current_dist = 0.0    
        
        # [20cm 반경 설정]
        self.radius = 0.20  
        self.angular_speed = self.linear_speed / self.radius # 0.75 rad/s
        
        # --- 각도 보정 핵심 파라미터 ---
        # 더 돈다고 하셨으므로 보정 계수를 1.05에서 0.98로 낮춥니다.
        # 이 값을 0.01 단위로 조절하며 수평을 맞추세요.
        # 값이 작아질수록 덜 돌고, 커질수록 더 돕니다.
        self.angle_correction_factor = 0.98 
        self.arc_duration = (math.pi / self.angular_speed) * self.angle_correction_factor 
        
        # 90도 제자리 회전 시간 (이것도 조금 더 돈다면 2.1에서 미세하게 줄이세요)
        self.turn_speed = 0.8
        self.turn_90_time = 2.05 # 2.1에서 2.05로 미세 조정

        self.last_time = time.time()
        self.is_maneuvering = False
        
        self.timer = self.create_timer(1.0 / 20.0, self.control_loop)
        self.get_logger().info(f"🏁 20cm 정밀 보정 주행 시작 (Factor: {self.angle_correction_factor})")

    def execute_avoidance(self, direction):
        self.is_maneuvering = True
        twist = Twist()

        # 1. 제자리 90도 회전
        start = time.time()
        while time.time() - start < self.turn_90_time:
            twist.linear.x = 0.0
            twist.angular.z = -self.turn_speed * direction
            self.cmd_pub.publish(twist)
            time.sleep(0.05)

        # 2. 20cm 반원 주행
        start = time.time()
        while time.time() - start < self.arc_duration:
            twist.linear.x = self.linear_speed
            twist.angular.z = self.angular_speed * direction
            self.cmd_pub.publish(twist)
            time.sleep(0.05)
        
        # 3. 제자리 90도 복귀 회전
        start = time.time()
        while time.time() - start < self.turn_90_time:
            twist.linear.x = 0.0
            twist.angular.z = -self.turn_speed * direction
            self.cmd_pub.publish(twist)
            time.sleep(0.05)

        # 거리 보정 (지름 0.4m)
        self.current_dist += (self.radius * 2) 
        self.get_logger().info(f"✅ 회피 완료. 각도 보정 적용됨.")
        
        self.last_time = time.time() 
        self.is_maneuvering = False

    def control_loop(self):
        if self.is_maneuvering: return

        now = time.time()
        dt = now - self.last_time
        self.last_time = now

        if self.current_dist >= self.target_dist:
            self.stop_robot()
            return

        frame = self.camera.get_frame()
        if frame is None: return
        results = self.model.predict(frame, conf=0.6, verbose=False, imgsz=640)

        for r in results:
            for box in r.boxes:
                label = self.model.names[int(box.cls[0])]
                if label not in self.REAL_WIDTHS: continue
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                dist = (self.FOCAL_LENGTH * self.REAL_WIDTHS[label]) / (x2 - x1)

                if dist < 0.20:
                    offset_x = (x1 + x2) / 2 - self.CX
                    direction = -1 if offset_x < 0 else 1
                    self.execute_avoidance(direction)
                    return

        twist = Twist()
        twist.linear.x = self.linear_speed
        twist.angular.z = 0.0
        self.cmd_pub.publish(twist)
        self.current_dist += self.linear_speed * dt

    def stop_robot(self):
        self.cmd_pub.publish(Twist())

    def destroy_node(self):
        self.stop_robot(); self.camera.close()
        super().destroy_node()

def main():
    rclpy.init(); node = PreciseAvoidance20cmTunedNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__': main()