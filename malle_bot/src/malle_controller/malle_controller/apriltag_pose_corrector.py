import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from pupil_apriltags import Detector
import numpy as np
import math
import cv2
import sys

# ── 태그 정보 (태그가 map 기준으로 바라보는 방향) ───────────────────────────────
# TODO: 실제 배치 후 아래 값들을 실측값으로 교체
TAG_INFO = {
    13: {'yaw': 2.812},   # ≈ 161.1도
    16: {'yaw': 4.709},   # ≈ 269.8도
    17: {'yaw': 3.105},   # ≈ 177.9도
}

# ── 카메라 파라미터 ─────────────────────────────────────────────────────────────
CAM_FX, CAM_FY = 570.34, 570.34
CAM_CX, CAM_CY = 320.0, 240.0
CAMERA_PARAMS  = (CAM_FX, CAM_FY, CAM_CX, CAM_CY)

TAG_SIZE = 0.05   # 태그 한 변 길이 (미터)

# ── 교정 트리거 조건 ────────────────────────────────────────────────────────────
MAX_DETECT_DIST = 0.3   # 태그까지 거리 상한 (미터)
MAX_ANGLE_DEG   = 10.0  # 태그 정면 기준 허용 각도 (도)
COOLDOWN_SEC    = 10.0  # 교정 후 재교정 최소 대기 시간 (초)

# ── 스트림 설정 ─────────────────────────────────────────────────────────────────
W, H = 640, 480
FRAME_SIZE = W * H * 3 // 2


def compute_robot_yaw(tag_id: int, R_cam: np.ndarray) -> float:
    """
    pose_R에서 로봇의 map 기준 yaw를 계산합니다.
    태그 z축(R[:,2])의 수평 성분으로 태그가 카메라에 얼마나 기울어졌는지 계산,
    태그 map yaw에서 그 각도를 빼서 로봇 yaw를 구합니다.
    """
    tag_yaw_in_map = TAG_INFO[tag_id]['yaw']
    tag_z = R_cam[:, 2]
    angle_h = math.atan2(float(tag_z[0]), float(tag_z[2]))
    robot_yaw = tag_yaw_in_map + math.pi - angle_h
    return math.atan2(math.sin(robot_yaw), math.cos(robot_yaw))


def yaw_to_quaternion(yaw: float):
    return math.sin(yaw / 2.0), math.cos(yaw / 2.0)


class AprilTagPoseCorrectorNode(Node):
    def __init__(self):
        super().__init__('apriltag_pose_corrector')

        self.initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10)

        self.amcl_sub = self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose',
            self._amcl_callback, 10)

        self.detector = Detector(families='tag36h11', nthreads=4)

        self._current_x = None
        self._current_y = None
        self._current_qz = None
        self._current_qw = None
        self._last_correction_time = None

        self.get_logger().info('AprilTag Pose Corrector 시작 (yaw 교정 모드)')

    def _amcl_callback(self, msg: PoseWithCovarianceStamped):
        self._current_x = msg.pose.pose.position.x
        self._current_y = msg.pose.pose.position.y
        self._current_qz = msg.pose.pose.orientation.z
        self._current_qw = msg.pose.pose.orientation.w

    def spin_stream(self):
        while rclpy.ok():
            data = sys.stdin.buffer.read(FRAME_SIZE)
            if len(data) < FRAME_SIZE:
                break

            rclpy.spin_once(self, timeout_sec=0.0)

            yuv = np.frombuffer(data, dtype=np.uint8).reshape((H * 3 // 2, W))
            frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            tags = self.detector.detect(
                gray,
                estimate_tag_pose=True,
                camera_params=CAMERA_PARAMS,
                tag_size=TAG_SIZE,
            )

            for tag in tags:
                if tag.tag_id not in TAG_INFO:
                    continue

                tz = float(tag.pose_t[2].item())
                if tz > MAX_DETECT_DIST:
                    self.get_logger().debug(f'ID:{tag.tag_id} 거리 초과 스킵 ({tz:.2f}m)')
                    continue

                tx_val = float(tag.pose_t[0].item())
                angle_deg = abs(math.degrees(math.atan2(tx_val, tz)))
                if angle_deg > MAX_ANGLE_DEG:
                    self.get_logger().debug(f'ID:{tag.tag_id} 각도 초과 스킵 ({angle_deg:.1f}°)')
                    continue

                if self._current_x is None:
                    self.get_logger().warn('AMCL pose 아직 없음, 스킵')
                    continue

                now = self.get_clock().now()
                if self._last_correction_time is not None:
                    elapsed = (now - self._last_correction_time).nanoseconds * 1e-9
                    if elapsed < COOLDOWN_SEC:
                        continue

                robot_yaw = compute_robot_yaw(tag.tag_id, tag.pose_R)

                if self._current_qz is not None:
                    before_yaw = math.degrees(2 * math.atan2(self._current_qz, self._current_qw))
                    self.get_logger().info(
                        f'ID:{tag.tag_id} | dist={tz:.2f}m | '
                        f'교정 전={before_yaw:.1f}° → 교정 후={math.degrees(robot_yaw):.1f}°')
                else:
                    self.get_logger().warn('AMCL pose 아직 없음, initialpose 스킵')
                    continue

                self._publish_initialpose(self._current_x, self._current_y, robot_yaw)
                self._last_correction_time = now
                break

    def _publish_initialpose(self, x: float, y: float, yaw: float):
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'

        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.position.z = 0.0

        qz, qw = yaw_to_quaternion(yaw)
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw

        cov = [0.0] * 36
        cov[0]  = 0.05 ** 2
        cov[7]  = 0.05 ** 2
        cov[35] = math.radians(5) ** 2
        msg.pose.covariance = cov

        self.initialpose_pub.publish(msg)


def main():
    try:
        rclpy.init()
        node = AprilTagPoseCorrectorNode()
        node.spin_stream()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()