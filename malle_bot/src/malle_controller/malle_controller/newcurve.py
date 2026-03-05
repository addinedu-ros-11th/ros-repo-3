#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt16MultiArray
from geometry_msgs.msg import Twist
import time

class LineTracker(Node):
    def __init__(self):
        super().__init__('line_tracker')

        self.sub = self.create_subscription(
            UInt16MultiArray,
            '/ir_sensor/range',
            self.ir_callback,
            10
        )
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # ===== PD 제어 파라미터 =====
        self.kp = 2.2
        self.kd = 1.5
        self.base_speed = 0.08
        self.min_speed = 0.05
        self.max_turn_speed = 1.2
        self.max_ir = 4095
        self.last_error = 0.0
        self.threshold_lost = 00 

        # ===== 정지 로직 관련 변수 =====
        self.lost_time = None  # 라인을 놓친 시점 저장
        self.stop_threshold = 1.0  # 1초 이상 라인이 없으면 멈춤

        self.get_logger().info("PID Line Tracker with Auto-Stop started")

    def ir_callback(self, msg):
        if len(msg.data) != 3:
            return

        R, C, L = msg.data[0], msg.data[1], msg.data[2]
        wL = self.max_ir - L
        wC = self.max_ir - C
        wR = self.max_ir - R
        weight_sum = wL + wC + wR

        # [상태 1] 라인을 놓친 경우
        if weight_sum < self.threshold_lost:
            if self.lost_time is None:
                self.lost_time = time.time()  # 처음 놓친 시각 기록
            
            # 놓친 지 1초가 넘었는지 확인
            if time.time() - self.lost_time > self.stop_threshold:
                self.stop_robot()
            else:
                self.search_line()
            return

        # 라인을 다시 찾으면 타이머 리셋
        self.lost_time = None

        # [상태 2] 중심 오차 계산 및 PD 제어
        error = (wL - wR) / weight_sum
        derivative = error - self.last_error
        turn = (self.kp * error) + (self.kd * derivative)
        self.last_error = error

        turn = max(-self.max_turn_speed, min(self.max_turn_speed, turn))
        cmd = Twist()
        
        if abs(error) > 0.7: 
            cmd.linear.x = self.min_speed
            cmd.angular.z = turn * 1.3
        else:
            cmd.linear.x = max(self.min_speed, self.base_speed * (1.0 - abs(error)))
            cmd.angular.z = turn

        self.pub.publish(cmd)

    def search_line(self):
        """라인을 찾기 위해 제자리 회전"""
        cmd = Twist()
        cmd.linear.x = 0.0
        search_speed = 0.6
        cmd.angular.z = search_speed if self.last_error > 0 else -search_speed
        self.pub.publish(cmd)

    def stop_robot(self):
        """로봇을 멈추고 노드 종료"""
        self.get_logger().info("Line ended. Stopping robot...")
        cmd = Twist()
        cmd.linear.x = 0.0
        cmd.angular.z = 0.0
        self.pub.publish(cmd)
        # 잠시 대기 후 종료 (메시지가 전달될 시간 확보)
        time.sleep(0.5)
        rclpy.shutdown()

def main():
    rclpy.init()
    node = LineTracker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()