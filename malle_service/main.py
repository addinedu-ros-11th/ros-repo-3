#!/usr/bin/env python3
import sys
import time
import threading
import asyncio
import httpx
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from malle_controller.msg import RobotMessage, TaskCommand
from nav_msgs.msg import Odometry
from datetime import datetime
from typing import Optional

from exception import MalleBotNodeNotFoundError
from services.robot_dispatcher import RobotDispatcherService
from schemas import RobotStatusUpdate, RobotCommandRequest, TaskRequest

dispatcher = RobotDispatcherService(battery_threshold=20)

ros_node: Optional['MalleServiceNode'] = None

@asynccontextmanager
async def lifespan(app):
    thread = threading.Thread(target=ros_spin, daemon=True)
    thread.start()
    yield

app = FastAPI(lifespan=lifespan)


@app.post("/api/robots/state/update")
async def update_robot_state(status: RobotStatusUpdate):
    dispatcher.update_robot_state(
        robot_id=status.robot_id,
        mode=status.mode,
        battery=status.battery,
        pos_x=status.position_x,
        pos_y=status.position_y,
    )
    return {"status": "ok"}

@app.post("/api/robots/command")
async def send_robot_command(command: RobotCommandRequest):
    robot_id, status = dispatcher.dispatch_task(
        session_id=command.task_id,
        task_type=command.task_type,
        target_x=command.target_x,
        target_y=command.target_y,
    )

    if ros_node is not None:
        cmd_msg = TaskCommand()
        cmd_msg.robot_id = command.robot_id
        cmd_msg.task_type = command.task_type
        cmd_msg.target_x = command.target_x
        cmd_msg.target_y = command.target_y
        cmd_msg.timestamp = int(time.time())
        cmd_msg.task_id = command.task_id
        ros_node.command_publisher.publish(cmd_msg)
        ros_node.get_logger().info(
            f'TaskCommand 발행: robot_id={command.robot_id}, '
            f'task={command.task_type}, task_id={command.task_id}'
        )

    return {"status": status, "assigned_robot": robot_id}

@app.get("/dispatch/status")
async def get_status():
    return dispatcher.get_status()

@app.post("/robots/{robot_id}/completion_time")
async def set_completion_time(
    robot_id: str,
    completion_time: datetime
):
    dispatcher.set_task_completion_time(robot_id, completion_time)
    return {"message": "ok"}


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


class MalleServiceNode(Node):
    VALID_MODES = {'IDLE', 'CHARGING', 'GUIDE', 'ERRAND', 'BROWSE', 'FOLLOW', 'BOX_EMPTY', 'BOX_FULL', 'EXCEPTION'}

    # 추후 DB 연동 필요 (gazebo를 이용해 임시 테스트)
    ROBOT_IDS = ['robot1', 'robot2', 'robot3']

    def __init__(self):
        super().__init__('malle_service_node')

        self.robot_positions = {}
        self.robot_states = {}

        best_effort_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE
        )

        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE
        )

        self.subscription = self.create_subscription(
            RobotMessage,
            'robot_test_topic',
            self.listener_callback,
            best_effort_qos
        )

        for robot_id in self.ROBOT_IDS:
            self.create_subscription(
                Odometry,
                f'/{robot_id}/odom',
                lambda msg, rid=robot_id: self.odom_callback(msg, rid),
                reliable_qos
            )

        self.command_publisher = self.create_publisher(
            TaskCommand,
            'robot_command_topic',
            best_effort_qos
        )

        self.get_logger().info(
            'MalleServiceNode 시작: '
            'subscriber(robot_test_topic, /robot[1-3]/odom) + publisher(robot_command_topic)'
        )

    def listener_callback(self, msg):
        robot_id = msg.header.robot_id
        battery = int(msg.battery)
        raw_mode = msg.robot_status.upper() if msg.robot_status else 'IDLE'
        mode = raw_mode if raw_mode in self.VALID_MODES else 'IDLE'

        self.robot_states[robot_id] = (mode, battery)
        pos_x, pos_y = self.robot_positions.get(robot_id, (0.0, 0.0))

        self.get_logger().info(
            f'로봇 상태 수신: robot_id={robot_id}, battery={battery}, mode={mode}, '
            f'pos=({pos_x:.2f}, {pos_y:.2f})'
        )

        dispatcher.update_robot_state(
            robot_id=robot_id,
            mode=mode,
            battery=battery,
            pos_x=pos_x,
            pos_y=pos_y,
        )

        asyncio.run(self.process_message(msg))

    async def process_message(self, msg):
        """로봇 메시지를 AI 서비스 → 웹 대시보드로 전달"""
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1) AI 서비스로 로봇 데이터 전송
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
            except httpx.ConnectError:
                return
            except Exception as e:
                self.get_logger().error(f'AI 서비스 오류: {str(e)}')
                return

            # 2) AI 결과를 웹 대시보드로 전달
            try:
                await client.post(
                    'http://localhost:8001/web/update',
                    json={
                        'message_id': msg.header.message_id,
                        'ai_result': ai_response.json(),
                        'robot_id': msg.header.robot_id,
                    }
                )
            except httpx.ConnectError:
                return
            except Exception as e:
                self.get_logger().error(f'웹 대시보드 오류: {str(e)}')

    def odom_callback(self, msg, robot_id):
        pos_x = msg.pose.pose.position.x
        pos_y = msg.pose.pose.position.y

        self.robot_positions[robot_id] = (pos_x, pos_y)

        mode, battery = self.robot_states.get(robot_id, ('IDLE', 100))

        dispatcher.update_robot_state(
            robot_id=robot_id,
            mode=mode,
            battery=battery,
            pos_x=pos_x,
            pos_y=pos_y,
        )


def ros_spin():
    global ros_node
    rclpy.init()
    ros_node = MalleServiceNode()
    rclpy.spin(ros_node)
    ros_node.destroy_node()
    rclpy.shutdown()

@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=ros_spin, daemon=True)
    thread.start()


@app.get("/")
def read_root():
    return {"status": "malle_service running", "port": 8000}

def main():
    check_malle_bot_node()
    print('[INFO] malle_bot 노드 확인 완료. malle_service를 시작합니다.')
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == '__main__':
    main()
