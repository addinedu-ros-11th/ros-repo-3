#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# sensor_msgs가 설치된 환경에서만 사용
try:
    from sensor_msgs.msg import BatteryState as RosBatteryState
    _HAS_BATTERY_MSG = True
except ImportError:
    _HAS_BATTERY_MSG = False

_THR_CHARGED  = 0.95
_THR_LOW      = 0.25
_THR_CRITICAL = 0.10

class BatteryMonitor(Node):

    def __init__(self):
        super().__init__('battery_monitor')

        self._thr_charged  = self.declare_parameter('thr_charged',  _THR_CHARGED ).value
        self._thr_low      = self.declare_parameter('thr_low',      _THR_LOW     ).value
        self._thr_critical = self.declare_parameter('thr_critical',  _THR_CRITICAL).value
        battery_topic      = self.declare_parameter('battery_topic', '/battery_state').value

        self._status_pub = self.create_publisher(String, '/malle/battery_status', 10)

        if _HAS_BATTERY_MSG:
            self._bat_sub = self.create_subscription(
                RosBatteryState, battery_topic, self._on_battery_state, 10)
            self.get_logger().info(
                f'[BatteryMonitor] 구독: {battery_topic}')
        else:
            self.get_logger().warn(
                '[BatteryMonitor] sensor_msgs 없음 - 폴링 모드로 전환')
            self.create_timer(5.0, self._poll_battery)

        self._percentage   = 1.0
        self._power_supply_status = 0   # UNKNOWN

    def _on_battery_state(self, msg):
        self._percentage = float(msg.percentage)
        self._power_supply_status = int(msg.power_supply_status)
        self._evaluate_and_publish()

    def _poll_battery(self):
        # TODO: pinky pro 에서 읽기
        self._evaluate_and_publish()

    def _evaluate_and_publish(self):
        p = self._percentage

        if self._power_supply_status == 1:
            status = 'charging'
        elif p >= self._thr_charged:
            status = 'charged'
        elif p <= self._thr_critical:
            status = 'critical'
            self.get_logger().error(f'[BatteryMonitor] 임계 배터리: {p:.0%}')
        elif p <= self._thr_low:
            status = 'low'
            self.get_logger().warn(f'[BatteryMonitor] 저배터리: {p:.0%}')
        else:
            status = 'normal'

        msg = String()
        msg.data = status
        self._status_pub.publish(msg)


def main():
    rclpy.init()
    node = BatteryMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
