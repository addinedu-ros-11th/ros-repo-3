#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class LockboxController(Node):

    def __init__(self):
        super().__init__('lockbox_controller')

        self._interface = self.declare_parameter('interface', 'mock').value # 옵션: 'gpio' | 'serial' | 'mock'

        self._cmd_sub    = self.create_subscription(
            String, '/malle/lockbox_cmd', self._on_cmd, 10)
        self._status_pub = self.create_publisher(
            String, '/malle/lockbox_status', 10)

        self._locked = True   # 초기 상태: 잠김
        self._hw = self._init_hw()

        self.get_logger().info(
            f'[LockboxController] interface={self._interface}')

    def _init_hw(self):
        if self._interface == 'gpio':
            return self._init_gpio()
        elif self._interface == 'serial':
            return self._init_serial()
        else:
            self.get_logger().warn('[LockboxController] mock 모드 (하드웨어 없음)')
            return None

    def _init_gpio(self):
        try:
            import RPi.GPIO as GPIO
            pin = self.declare_parameter('gpio_pin', 17).value
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            self.get_logger().info(f'[LockboxController] GPIO pin={pin}')
            return {'type': 'gpio', 'GPIO': GPIO, 'pin': pin}
        except ImportError:
            self.get_logger().error('[LockboxController] RPi.GPIO 없음')
            return None

    def _init_serial(self):
        try:
            import serial
            port = self.declare_parameter('serial_port', '/dev/ttyUSB0').value
            baud = self.declare_parameter('baud_rate',   9600).value
            ser  = serial.Serial(port, baud, timeout=1.0)
            self.get_logger().info(f'[LockboxController] Serial {port}@{baud}')
            return {'type': 'serial', 'ser': ser}
        except Exception as e:
            self.get_logger().error(f'[LockboxController] 시리얼 초기화 실패: {e}')
            return None

    def _on_cmd(self, msg: String):
        cmd = msg.data.strip().lower()
        if cmd == 'open':
            self._open()
        elif cmd == 'lock':
            self._lock()
        else:
            self.get_logger().warn(f'[LockboxController] 알 수 없는 명령: {cmd}')

    def _open(self):
        self.get_logger().info('[LockboxController] 열기')
        self._hw_write('OPEN')
        self._locked = False
        # TODO: 실제 물건 적재 감지 후 'loaded' 퍼블리시
        self._publish_status('opened')

    def _lock(self):
        self.get_logger().info('[LockboxController] 잠금')
        self._hw_write('LOCK')
        self._locked = True
        self._publish_status('locked')

    def _hw_write(self, cmd: str):
        if self._hw is None:
            return  # mock 모드

        hw_type = self._hw.get('type')
        if hw_type == 'gpio':
            GPIO = self._hw['GPIO']
            pin  = self._hw['pin']
            GPIO.output(pin, GPIO.HIGH if cmd == 'OPEN' else GPIO.LOW)

        elif hw_type == 'serial':
            ser = self._hw['ser']
            ser.write(f'{cmd}\n'.encode())

    def _publish_status(self, status: str):
        msg = String()
        msg.data = status
        self._status_pub.publish(msg)

    def destroy_node(self):
        if self._hw and self._hw.get('type') == 'gpio':
            self._hw['GPIO'].cleanup()
        if self._hw and self._hw.get('type') == 'serial':
            self._hw['ser'].close()
        super().destroy_node()


def main():
    rclpy.init()
    node = LockboxController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
