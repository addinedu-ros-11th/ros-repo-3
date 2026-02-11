#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from malle_controller.msg import RobotMessage
import asyncio
import httpx
from fastapi import FastAPI
import threading
import uvicorn

app = FastAPI()

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

@app.get("/")
def read_root():
    return {"status": "malle_service running", "port": 8000}

def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == '__main__':
    main()
