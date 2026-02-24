import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt16MultiArray
import time
import cv2
import numpy as np
from pupil_apriltags import Detector
from pinkylib import Camera, Motor

class PinkySafeVerticalParking(Node):
    def __init__(self):
        super().__init__('pinky_safe_vertical_parking')
        self.sub = self.create_subscription(UInt16MultiArray, '/ir_sensor/range', self.ir_callback, 10)
        
        try:
            self.cam = Camera()
            self.motor = Motor()
        except RuntimeError as e:
            self.get_logger().error(f"Hardware Fail: {e}")
            exit(1)

        self.detector = Detector(families="tag36h11", nthreads=2)
        self.target_id = 11
        self.width, self.height = 640, 480
        
        self.state = "FIND_TAG"
        self.ir_data = [4095, 4095, 4095]
        self.last_target_time = time.time()
        self.lines_encountered = 0
        self.line_on_flag = False
        self.continuous_detect_count = 0
        
        self.cam.start(width=self.width, height=self.height)
        self.motor.enable_motor()
        self.create_timer(0.05, self.control_loop)
        self.get_logger().info(">>> PINKY SAFE-VERTICAL PARKING START <<<")

    def ir_callback(self, msg):
        self.ir_data = msg.data
        is_black = any(val < 250 for val in self.ir_data)
        if is_black:
            self.continuous_detect_count += 1
        else:
            self.continuous_detect_count = 0
        if self.continuous_detect_count >= 3:
            if not self.line_on_flag:
                self.lines_encountered += 1
                self.line_on_flag = True
        else:
            if not is_black:
                self.line_on_flag = False

    def control_loop(self):
        if self.state == "DONE":
            self.motor.move(0, 0)
            return

        frame = self.cam.get_frame()
        if frame is None: return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dets = self.detector.detect(gray)
        target = next((d for d in dets if d.tag_id == self.target_id), None)

        if not target:
            if self.state not in ["DONE", "UTURN"] and time.time() - self.last_target_time > 0.3:
                self.motor.move(17, -17) # 태그 탐색 회전
            return

        self.last_target_time = time.time()
        cx, _ = target.center
        c = target.corners
        tag_left, tag_right = min(c[:, 0]), max(c[:, 0])
        tag_top, tag_bottom = min(c[:, 1]), max(c[:, 1])
        size = tag_right - tag_left
        
        # 화면 중앙 오차 계산
        err_x = cx - (self.width / 2.0)
        abs_err = abs(err_x)

        # 1. 180도 회전 및 종료 (매우 근접 시)
        if size > 320:
            self.perform_uturn()
            return

        # 2. FINAL_APPROACH (라인 감지 또는 근접 시)
        if tag_top < 10 or tag_bottom > 470 or size > 250:
            if self.lines_encountered >= 2:
                self.perform_uturn()
                return
            else:
                self.state = "FINAL_APPROACH"
                self.motor.move(22, 22)
                return

        # 3. [소실 방지 벽] 완화: 급격한 꺾임보다는 부드러운 복귀 유도
        if tag_left < 20: 
            self.motor.move(-22, 22)
            return
        elif tag_right > 620:
            self.motor.move(22, -22)
            return

        # 4. [수정된 정밀 정렬 로직]
        # 속도가 너무 빠르면 곡선 반경이 커지므로 베이스 속도를 안정화합니다.
        base_linear = 24 

        # turn_gain 수정: 
        # 기존 0.16은 바퀴 속도 차이를 너무 크게 벌립니다 (ex: 오차 50일 때 속도차 16).
        # 0.08~0.1 사이로 조정하여 부드러운 곡선을 유도합니다.
        if abs_err > 100:
            turn_gain = 0.03  # 먼 거리에서는 완만하게
        else:
            turn_gain = 0.07  # 가까워질수록 조금 더 정밀하게

        turn_adj = int(err_x * turn_gain)
        
        # 좌우 속도 할당 (바깥쪽 바퀴가 너무 튀지 않도록 제어)
        l_spd = base_linear + turn_adj
        r_spd = base_linear - turn_adj
        
        self.state = "PRECISION_ALIGN"
        l_spd, r_spd = self.final_output(l_spd, r_spd)
        self.motor.move(l_spd, r_spd)

    def perform_uturn(self):
        self.get_logger().info("!!! ARRIVED - PERFORMING 180 TURN !!!")
        self.state = "UTURN"
        start_u = time.time()
        while time.time() - start_u < 1.1:
            self.motor.move(50, -50)
            time.sleep(0.01)
        self.motor.move(0, 0)
        self.state = "DONE"

    def final_output(self, l, r):
        # 모터가 움직이기 시작하는 최소 전압(Deadzone) 고려 및 최대 속도 제한
        def dz(s):
            if s == 0: return 0
            # 최소 동작 속도 유지 (22)
            if 0 < s < 22: return 22
            if -22 < s < 0: return -22
            # 곡선 주행 시 너무 빨라지지 않도록 상한선 하향 (36)
            return max(-36, min(36, s))
        return int(dz(l)), int(dz(r))

    def shutdown_robot(self):
        self.motor.move(0, 0)
        self.motor.disable_motor()
        self.cam.close()

def main():
    rclpy.init()
    node = PinkySafeVerticalParking()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown_robot()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()