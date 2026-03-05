#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    from pinkylib import Battery
    _HAS_PINKYLIB = True
except ImportError:
    _HAS_PINKYLIB = False

_VOLT_CHARGED  = 8.0
_VOLT_LOW      = 6.8
_VOLT_CRITICAL = 6.5

class BatteryMonitor(Node):

    def __init__(self):
        super().__init__('battery_monitor')

        self._volt_charged  = self.declare_parameter('volt_charged',  _VOLT_CHARGED ).value
        self._volt_low      = self.declare_parameter('volt_low',      _VOLT_LOW     ).value
        self._volt_critical = self.declare_parameter('volt_critical',  _VOLT_CRITICAL).value

        self._status_pub = self.create_publisher(String, '/malle/battery_status', 10)

        if _HAS_PINKYLIB:
            self._battery = Battery()
            self.create_timer(5.0, self._poll_battery)
            self.get_logger().info('[BatteryMonitor] pinkylib.Battery 폴링 모드')
        else:
            self.get_logger().warn('[BatteryMonitor] pinkylib 없음 – 더미 모드 (charged 고정)')
            self.create_timer(5.0, self._poll_battery)

    def _poll_battery(self):
        if not _HAS_PINKYLIB:
            self._publish('charged')
            return

        try:
            voltage = self._battery.get_voltage()
            percentage = self._battery.battery_percentage()
        except Exception as e:
            self.get_logger().warn(f'[BatteryMonitor] 배터리 읽기 실패: {e}')
            return

        if voltage <= self._volt_critical:
            status = 'critical'
            self.get_logger().error(
                f'[BatteryMonitor] 위험 배터리: {percentage}% ({voltage:.2f}V)')
        elif voltage <= self._volt_low:
            status = 'low'
            self.get_logger().warn(
                f'[BatteryMonitor] 저배터리: {percentage}% ({voltage:.2f}V)')
        elif voltage >= self._volt_charged:
            status = 'charged'
            self.get_logger().info(
                f'[BatteryMonitor] 충전 완료: {percentage}% ({voltage:.2f}V)')
        else:
            status = 'normal'

        self._publish(status)

    def _publish(self, status: str):
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
