#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from pinky_interfaces.srv import SetLed, Emotion

import numpy as np
import time
from pupil_apriltags import Detector


# ==========================================
# [통합된 ROS2 제어 노드]
# ==========================================
class MissionFollowNode(Node):

    def __init__(self, get_gray_frame):
        super().__init__('mission_follow')
        self.get_gray_frame = get_gray_frame

        # Publisher & Subscriber
        self.cmd_pub    = self.create_publisher(Twist, '/cmd_vel', 10)
        self.result_pub = self.create_publisher(String, '/malle/mission_result', 10)
        self.trigger_sub = self.create_subscription(String, '/malle/mission_trigger', self._on_trigger, 10)

        # Service Clients
        self.led_client = self.create_client(SetLed, '/set_led')
        self.emotion_client = self.create_client(Emotion, '/set_emotion')

        # AprilTag 디텍터
        self.detector = Detector(families='tag36h11', nthreads=4)

        # 상태 변수
        self.active = False
        self.state = "IDLE"
        self.target_id = 0
        self.last_seen_direction = 1.0
        self.lost_time = None
        self.start_time = 0.0

        # [코너링 최적화 파라미터]
        self.target_dist = 0.08
        self.linear_speed = 0.10
        self.kp = 20.0
        self.kd = 3.5
        self.last_error_x = 0.0
        self.max_angular = 15.0
        self.search_turn_speed = 1.5

        self.set_emotion("hello")
        self.create_timer(0.02, self._control_loop)

    def set_led(self, r, g, b):
        if self.led_client.service_is_ready():
            req = SetLed.Request()
            req.command, req.pixels, req.r, req.g, req.b = 'set_pixel', [4,5,6,7], r, g, b
            self.led_client.call_async(req)

    def set_emotion(self, name):
        if self.emotion_client.service_is_ready():
            req = Emotion.Request()
            req.emotion = name
            self.emotion_client.call_async(req)

    def _on_trigger(self, msg: String):
        token = msg.data.strip()
        if token.startswith('start_follow'):
            self.active = True
            if ':' in token:
                first = token.split(':', 1)[1].split(',')[0]
                self.target_id = int(first) if first.isdigit() else 0
            else:
                self.target_id = 0
            self.get_logger().info(f"Started following target ID: {self.target_id}")
            self.state = "BACKING"
            self.start_time = time.time()
            self.set_led(255, 0, 0)
            self.set_emotion("basic")

        elif msg.data == 'idle':
            self.get_logger().info("Mission Idle requested.")
            self.active = False
            self.state = "IDLE"
            self.cmd_pub.publish(Twist())
            self.set_led(0, 0, 0)
            self.set_emotion("hello")

    def _control_loop(self):
        gray = self.get_gray_frame()

        if not self.active or self.state == "IDLE":
            return

        twist = Twist()

        # 1. 초기 후진 로직
        if self.state == "BACKING":
            if time.time() - self.start_time < 7.0:
                twist.linear.x = -0.1
            else:
                self.state = "SEARCHING"
                self.set_led(0, 0, 255)
                self.set_emotion("interest")
            self.cmd_pub.publish(twist)
            return

        # 2. 태그 인식 및 추종 로직
        if gray is not None:
            tags = self.detector.detect(gray, estimate_tag_pose=True,
                                        camera_params=(285, 285, 160, 120), tag_size=0.04)
            target = next((t for t in tags if t.tag_id == self.target_id), None)

            if target:
                self.lost_time = None
                if self.state == "SEARCHING":
                    self.state = "FOLLOWING"
                    self.set_led(0, 255, 0)
                    self.set_emotion("fun")

                tx, tz = float(target.pose_t[0]), float(target.pose_t[2])
                self.last_seen_direction = 1.0 if tx < 0 else -1.0

                current_error = -tx
                error_diff = current_error - self.last_error_x
                angular_vel = (current_error * self.kp) + (error_diff * self.kd)

                is_sharp_turn = abs(tx) > 0.12
                proximity_boost = 1.0 + (0.05 / (tz + 0.05))
                raw_angular = angular_vel * proximity_boost

                if is_sharp_turn:
                    twist.linear.x = 0.10
                    twist.angular.z = float(np.clip(raw_angular * 0.7, -self.max_angular, self.max_angular))
                else:
                    twist.linear.x = self.linear_speed if tz > self.target_dist + 0.02 else 0.0
                    twist.angular.z = float(np.clip(raw_angular, -self.max_angular, self.max_angular))

                if tz <= self.target_dist:
                    twist.linear.x = 0.08 if is_sharp_turn else 0.0
                
               self.last_error_x = current_error 
            
            else:
                if self.state == "FOLLOWING":
                    if self.lost_time is None:
                        self.lost_time = time.time()
                    if time.time() - self.lost_time > 5.0:
                        self.state = "SEARCHING"
                        self.set_led(0, 0, 255)
                        self.set_emotion("interest")
                    else:
                        twist.linear.x = 0.0
                        twist.angular.z = 0.0
                elif self.state == "SEARCHING":
                    twist.angular.z = self.search_turn_speed * self.last_seen_direction
        
        self.cmd_pub.publish(twist)

    def _publish_result(self, result: str):
        msg = String()
        msg.data = result
        self.result_pub.publish(msg)
