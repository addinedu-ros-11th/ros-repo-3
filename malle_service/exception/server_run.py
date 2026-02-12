import sys


class MalleBotNodeNotFoundError(Exception):
    def __init__(self, message=None):
        if message is None:
            message = (
                'malle_bot 노드가 실행되고 있지 않습니다. '
                'malle_service를 시작하기 전에 malle_bot 노드를 먼저 실행해주세요. '
                '예: ros2 run malle_controller test_publisher'
            )
        super().__init__(message)
        print(f'\n[ERROR] {message}\n')
        sys.exit(1)
