#!/usr/bin/env python3
import sys
import time
import threading
import asyncio
import httpx
from fastapi import FastAPI
import uvicorn
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from malle_controller.msg import RobotMessage
from exception import MalleBotNodeNotFoundError

app = FastAPI()


def check_malle_bot_node(max_retries: int = 3, retry_interval: float = 2.0):
    """malle_bot 노드가 실행 중인지 확인합니다."""
    rclpy.init()
    checker_node = Node('malle_service_checker')

    for attempt in range(1, max_retries + 1):
        node_names = checker_node.get_node_names()
        bot_nodes = [
            name for name in node_names
            if name != 'malle_service_checker'
        ]

        if bot_nodes:
            checker_node.get_logger().info(
                f'malle_bot 노드 발견: {bot_nodes}'
            )
            checker_node.destroy_node()
            rclpy.shutdown()
            return bot_nodes

        checker_node.get_logger().warn(
            f'malle_bot 노드를 찾을 수 없습니다. '
            f'재시도 중... ({attempt}/{max_retries})'
        )
        time.sleep(retry_interval)

    checker_node.destroy_node()
    rclpy.shutdown()
    raise MalleBotNodeNotFoundError()


class RobotSubscriberNode(Node):
    def __init__(self):
        super().__init__('robot_subscriber_node')

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE
        )

        self.subscription = self.create_subscription(
            RobotMessage,
            'robot_test_topic',
            self.listener_callback,
            qos_profile
        )
        self.get_logger().info('로컬 서버 Subscriber 시작!')

    def listener_callback(self, msg):
        self.get_logger().info(
            f'메시지 수신: robot_id={msg.header.robot_id}, '
            f'battery={msg.battery}, status={msg.robot_status}'
        )
        asyncio.run(self.process_message(msg))

    async def process_message(self, msg):
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                ai_response = await client.post(
                    'http://localhost:5000/ai/process',
                    json={
                        'message_id': msg.header.message_id,
                        'robot_id': msg.header.robot_id,
                        'battery': msg.battery,
                        'status': msg.robot_status,
                        'timestamp': f'{msg.header.timestamp_sec}.{msg.header.timestamp_nsec}'
                    }
                )

                await client.post(
                    'http://localhost:8001/web/update',
                    json={
                        'message_id': msg.header.message_id,
                        'ai_result': ai_response.json(),
                        'timing': {}
                    }
                )

            except Exception as e:
                self.get_logger().error(f'처리 중 오류: {str(e)}')

def ros_spin():
    rclpy.init()
    node = RobotSubscriberNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=ros_spin, daemon=True)
    thread.start()
    thread.join(timeout=5.0)


@app.get("/")
def read_root():
    return {"status": "malle_service running", "port": 8000}

def main():
    check_malle_bot_node()
    print('[INFO] malle_bot 노드 확인 완료. malle_service를 시작합니다.')
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == '__main__':
    main()
