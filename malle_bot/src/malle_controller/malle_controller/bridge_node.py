#!/usr/bin/env python3
"""
bridge_node.py — ROS2 ↔ malle_service HTTP bridge.

세 가지 역할:
1. ROS2 → HTTP: odom, battery 구독 → malle_service PATCH (0.5Hz)
2. HTTP → ROS2: FastAPI :9100 명령 수신 → MissionExecutor 또는 cmd_vel 발행
3. 카메라 MJPEG: Picamera2(pinkylib Camera) → GET /camera/{robot_id}/stream

실행 (로봇마다 다른 네임스페이스/ID):
    ROBOT_NAMESPACE=malle_15 ROBOT_ID=1 python3 bridge_node.py
    ROBOT_NAMESPACE=malle_17 ROBOT_ID=2 python3 bridge_node.py
    ROBOT_NAMESPACE=malle_19 ROBOT_ID=3 python3 bridge_node.py
    ROBOT_NAMESPACE=malle_vic ROBOT_ID=4 python3 bridge_node.py
"""

import asyncio
import math
import os
import sys
import threading
import time
from typing import Optional

import httpx

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
ROBOT_ID        = int(os.getenv("ROBOT_ID", "1"))
ROBOT_NAMESPACE = os.getenv("ROBOT_NAMESPACE", "malle_15")

MALLE_SERVICE_URL     = os.getenv("MALLE_SERVICE_URL", "http://localhost:8000/api/v1")
BRIDGE_HTTP_PORT      = int(os.getenv("BRIDGE_HTTP_PORT", "9100"))
BRIDGE_SELF_URL       = os.getenv("BRIDGE_SELF_URL", "")  # 예: http://192.168.4.10:9100
STATE_UPDATE_INTERVAL = 0.5


def _topic(name: str) -> str:
    return f"/{ROBOT_NAMESPACE}/{name.lstrip('/')}"


TOPIC_ODOM           = _topic("odom")
TOPIC_BATTERY        = _topic("battery/present")
TOPIC_CMD_VEL_TELEOP = _topic("cmd_vel_teleop")
TOPIC_PREEMPT_TELEOP = _topic("preempt_teleop")
TOPIC_TASK_COMMAND   = _topic("task_command")

JPEG_QUALITY        = 70
STREAM_MAX_FPS      = 15
CAMERA_WIDTH        = 640
CAMERA_HEIGHT       = 480
CAMERA_PUSH_FPS     = 10   # malle_service로 push 하는 속도 (로컬 스트림은 STREAM_MAX_FPS 유지)
CAMERA_PUSH_ENABLED = os.getenv("CAMERA_PUSH_ENABLED", "1") == "1"

# ─────────────────────────────────────────────────────────────
# ROS2 import
# ─────────────────────────────────────────────────────────────
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.action import ActionClient
    from geometry_msgs.msg import Twist, PoseStamped
    from nav_msgs.msg import Odometry
    from std_msgs.msg import String, Float32, Empty
    from nav2_msgs.action import NavigateToPose
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False
    print("[bridge_node] WARNING: ROS2 not available. HTTP-only mode.")

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# ─────────────────────────────────────────────────────────────
# FastAPI import
# ─────────────────────────────────────────────────────────────
try:
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

    print("[bridge_node] WARNING: FastAPI not available.")


# ─────────────────────────────────────────────────────────────
# 전역 참조 (main()에서 주입)
# ─────────────────────────────────────────────────────────────
_ros_node = None


class CameraFrameBuffer:
    def __init__(self):
        self._frame: Optional[bytes] = None
        self._lock = threading.Lock()

    def put(self, jpeg_bytes: bytes):
        with self._lock:
            self._frame = jpeg_bytes

    def get(self) -> Optional[bytes]:
        with self._lock:
            return self._frame

camera_buffer = CameraFrameBuffer()


# ─────────────────────────────────────────────────────────────
# HTTP API server (:9100)
# ─────────────────────────────────────────────────────────────

if HAS_FASTAPI:
    async def _push_frames_to_service():
        """camera_buffer의 프레임을 malle_service에 주기적으로 HTTP POST."""
        push_url = f"{MALLE_SERVICE_URL}/robots/{ROBOT_ID}/camera/frame"
        active_interval = 1.0 / CAMERA_PUSH_FPS
        idle_interval = 2.0

        async with httpx.AsyncClient(timeout=httpx.Timeout(0.3)) as client:
            has_viewers = False
            while True:
                frame = camera_buffer.get()
                try:
                    if frame and has_viewers:
                        resp = await client.post(
                            push_url,
                            content=frame,
                            headers={"Content-Type": "image/jpeg"},
                        )
                    else:
                        resp = await client.post(push_url, content=b"")
                    data = resp.json()
                    has_viewers = data.get("viewers", 0) > 0
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass
                except Exception as e:
                    print(f"[bridge_node] camera push error: {e}")

                await asyncio.sleep(active_interval if has_viewers else idle_interval)

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        task = None
        if CAMERA_PUSH_ENABLED:
            task = asyncio.create_task(_push_frames_to_service())
            print(f"[bridge_node] camera push → {MALLE_SERVICE_URL}/robots/{ROBOT_ID}/camera/frame  @ {CAMERA_PUSH_FPS}fps")
        yield
        if task:
            task.cancel()

    bridge_app = FastAPI(title="Mall-E Bridge Node", version="0.4.0", lifespan=_lifespan)

    class CommandRequest(BaseModel):
        command: str = ""

    class TeleopCmdRequest(BaseModel):
        linear_x: float = 0.0
        angular_z: float = 0.0

    class NavigateRequest(BaseModel):
        x: float
        y: float
        theta: float = 0.0
        session_id: Optional[int] = None
        item_id: Optional[int] = None
        poi_name: Optional[str] = None

    class FollowRequest(BaseModel):
        session_id: Optional[int] = None
        tag_id: int = 11

    class ErrandRequest(BaseModel):
        session_id: Optional[int] = None
        order_id: Optional[int] = None
        store_poi_id: Optional[int] = None
        meet_poi_id: Optional[int] = None
        meet_x_m: Optional[float] = None
        meet_y_m: Optional[float] = None        

    @bridge_app.post("/bridge/follow/start")
    async def follow_start(req: FollowRequest):
        if _ros_node:
            _ros_node.publish_trigger(f"start_follow_{req.tag_id}")
        return {"ok": True}

    @bridge_app.post("/bridge/follow/stop")
    async def follow_stop():
        if _ros_node:
            _ros_node.publish_trigger("idle")
        return {"ok": True}

    # 전역 참조는 모듈 최상위로 이동 (아래 참조)

    @bridge_app.get("/health")
    async def health():
        return {
            "status": "ok",
            "robot_id": ROBOT_ID,
            "namespace": ROBOT_NAMESPACE,
            "camera": camera_buffer.get() is not None,
            "topics": {
                "odom":           TOPIC_ODOM,
                "battery":        TOPIC_BATTERY,
                "cmd_vel_teleop": TOPIC_CMD_VEL_TELEOP,
                "preempt_teleop": TOPIC_PREEMPT_TELEOP,
            },
        }

    @bridge_app.post("/bridge/command")
    async def receive_command(req: CommandRequest):
        if _ros_node:
            _ros_node.publish_command(req.command)
        return {"ok": True}

    @bridge_app.post("/bridge/teleop/start")
    async def teleop_start():
        if _ros_node:
            _ros_node.set_teleop_mode(True)
        return {"ok": True}

    @bridge_app.post("/bridge/teleop/stop")
    async def teleop_stop():
        if _ros_node:
            _ros_node.publish_cmd_vel(0.0, 0.0)
            _ros_node.set_teleop_mode(False)
        return {"ok": True}

    @bridge_app.post("/bridge/teleop/cmd")
    async def teleop_cmd(req: TeleopCmdRequest):
        if _ros_node:
            _ros_node.publish_cmd_vel(req.linear_x, req.angular_z)
        return {"ok": True}

    @bridge_app.post("/bridge/navigate")
    async def navigate_to(req: NavigateRequest):
        """
        malle_service → 이 엔드포인트 호출.
        session_id 있으면 TaskCommand를 /malle/command에 발행 (mission_executor가 처리).
        없으면 단순 좌표 이동.
        """
        if req.session_id and _ros_node:
            _ros_node.publish_task_command("GUIDE", str(req.session_id), "")
            return {"ok": True, "mode": "guide", "session_id": req.session_id}

        if _ros_node:
            _ros_node.send_nav_goal(req.x, req.y, req.theta)
        return {"ok": True, "mode": "fallback_nav"}

    @bridge_app.post("/bridge/guide/advance")
    async def guide_advance():
        """다음 POI로 이동 (Robot UI 'Next Stop' / Mobile 'Mark as Arrived')."""
        if _ros_node:
            _ros_node.publish_guide_advance()
        return {"ok": True}

    @bridge_app.post("/bridge/guide/stop")
    async def guide_stop():
        if _ros_node:
            _ros_node.publish_trigger("stop_guide")
        return {"ok": True}

    @bridge_app.post("/bridge/stop")
    async def stop_mission():
        """E-Stop 또는 세션 종료 시 모든 미션 중지."""
        if _ros_node:
            _ros_node.publish_cmd_vel(0.0, 0.0)
            _ros_node.publish_trigger("idle")
        return {"ok": True}
    
    @bridge_app.post("/bridge/errand/start")
    async def errand_start(req: ErrandRequest):
        """pickup.py → mission_errand.py 트리거.
        store_poi_id만 전달 (meetup은 /errand/meetup에서 별도 처리).
        """
        if _ros_node and req.store_poi_id:
            _ros_node.publish_trigger(
                f"start_errand:{req.store_poi_id},"
            )
        return {"ok": True}

    @bridge_app.post("/bridge/errand/meetup")
    async def errand_meetup(req: ErrandRequest):
        """meetup 위치 확정 → mission_errand.py에 meetup poi 전달."""
        if _ros_node and req.meet_poi_id:
            _ros_node.publish_trigger(
                f"errand_meetup:{req.meet_poi_id}"
            )
        return {"ok": True}

    @bridge_app.post("/bridge/errand/stop")
    async def errand_stop():
        if _ros_node:
            _ros_node.publish_trigger("idle")
        return {"ok": True}

    # ── MJPEG 스트리밍 ──────────────────────────────────────────────────────

    def _make_placeholder(robot_id: int) -> bytes:
        if not HAS_CV2:
            return b""
        img = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), dtype=np.uint8)
        cv2.putText(
            img, f"No camera (robot {robot_id})",
            (CAMERA_WIDTH // 2 - 120, CAMERA_HEIGHT // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2,
        )
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 50])
        return buf.tobytes()

    async def _mjpeg_gen(robot_id: int):
        min_interval = 1.0 / STREAM_MAX_FPS
        loop = asyncio.get_event_loop()

        while True:
            t0 = loop.time()
            frame = camera_buffer.get()

            if frame is None:
                ph = _make_placeholder(robot_id)
                if ph:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + ph + b"\r\n"
                await asyncio.sleep(1.0)
                continue

            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

            wait = min_interval - (loop.time() - t0)
            if wait > 0:
                await asyncio.sleep(wait)

    @bridge_app.get("/camera/{robot_id}/stream")
    async def camera_stream(robot_id: int):
        return StreamingResponse(
            _mjpeg_gen(robot_id),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @bridge_app.get("/camera/{robot_id}/snapshot")
    async def camera_snapshot(robot_id: int):
        frame = camera_buffer.get() or _make_placeholder(robot_id)
        if not frame:
            return {"error": "No frame"}
        return StreamingResponse(iter([frame]), media_type="image/jpeg")


# ─────────────────────────────────────────────────────────────
# ROS2 Node
# ─────────────────────────────────────────────────────────────

if HAS_ROS2:
    from sensor_msgs.msg import Image as RosImage
    from malle_controller.msg import TaskCommand as TaskCommandMsg

    class BridgeNode(Node):
        def __init__(self):
            super().__init__(f"malle_bridge_{ROBOT_NAMESPACE}")
            self.get_logger().info(
                f"Bridge starting — robot_id={ROBOT_ID}, namespace='{ROBOT_NAMESPACE}'"
            )

            self._http_client = httpx.Client(timeout=2.0)
            self._teleop_active = False
            self._state = {
                "x_m": 0.0, "y_m": 0.0, "theta_rad": 0.0,
                "speed_mps": 0.0, "battery_pct": 100,
            }

            self.create_subscription(Odometry, TOPIC_ODOM, self._odom_cb, 10)
            self.create_subscription(Float32, TOPIC_BATTERY, self._battery_cb, 10)
            self.create_subscription(RosImage, '/camera/image_raw', self._image_cb, 1)
            self.get_logger().info(f"  odom:    {TOPIC_ODOM}")
            self.get_logger().info(f"  battery: {TOPIC_BATTERY}")

            self._cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)
            self._preempt_pub = self.create_publisher(Empty, TOPIC_PREEMPT_TELEOP, 10)
            self._task_command_pub = self.create_publisher(String, TOPIC_TASK_COMMAND, 10)
            self._mission_trigger_pub = self.create_publisher(String, '/malle/mission_trigger', 10)
            self._malle_command_pub = self.create_publisher(TaskCommandMsg, '/malle/command', 10)
            self._guide_advance_pub = self.create_publisher(String, '/malle/guide_advance', 10)
            self._nav2_client = ActionClient(self, NavigateToPose, '/navigate_to_pose')

            self.create_timer(STATE_UPDATE_INTERVAL, self._push_state)
            self.get_logger().info("Bridge ready.")

        def _odom_cb(self, msg: Odometry):
            self._state["x_m"] = round(msg.pose.pose.position.x, 3)
            self._state["y_m"] = round(msg.pose.pose.position.y, 3)

            q = msg.pose.pose.orientation
            self._state["theta_rad"] = round(
                math.atan2(
                    2.0 * (q.w * q.z + q.x * q.y),
                    1.0 - 2.0 * (q.y * q.y + q.z * q.z),
                ), 5
            )

            vx = msg.twist.twist.linear.x
            vy = msg.twist.twist.linear.y
            self._state["speed_mps"] = round(math.sqrt(vx * vx + vy * vy), 3)

        def _battery_cb(self, msg: Float32):
            self._state["battery_pct"] = int(msg.data)

        def _image_cb(self, msg: RosImage):
            if not HAS_CV2:
                return
            frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            camera_buffer.put(buf.tobytes())

        def _push_state(self):
            motion = "MOVING" if self._state["speed_mps"] > 0.01 else "STOPPED"
            payload = {
                "x_m":          self._state["x_m"],
                "y_m":          self._state["y_m"],
                "theta_rad":    self._state["theta_rad"],
                "speed_mps":    self._state["speed_mps"],
                "battery_pct":  self._state["battery_pct"],
                "motion_state": motion,
            }
            if BRIDGE_SELF_URL:
                payload["bridge_url"] = BRIDGE_SELF_URL
            try:
                self._http_client.patch(
                    f"{MALLE_SERVICE_URL}/robots/{ROBOT_ID}/state",
                    json=payload,
                )
            except httpx.ConnectError:
                pass
            except Exception as e:
                self.get_logger().warning(f"State push failed: {e}")

        def publish_cmd_vel(self, linear_x: float, angular_z: float):
            msg = Twist()
            msg.linear.x  = float(linear_x)
            msg.angular.z = float(angular_z)
            self._cmd_vel_pub.publish(msg)
            if self._teleop_active and (linear_x != 0.0 or angular_z != 0.0):
                self._preempt_pub.publish(Empty())

        def set_teleop_mode(self, active: bool):
            self._teleop_active = active
            if active:
                self._preempt_pub.publish(Empty())
            else:
                self._cmd_vel_pub.publish(Twist())
            self.get_logger().info(f"Teleop {'ON' if active else 'OFF'}")

        def publish_command(self, command: str):
            msg = String()
            msg.data = command
            self._task_command_pub.publish(msg)

        def publish_trigger(self, command: str):
            """mission_follow.py 등 /malle/mission_trigger 구독자에게 명령 발행."""
            msg = String()
            msg.data = command
            self._mission_trigger_pub.publish(msg)

        def publish_task_command(self, task_type: str, task_id: str, poi_ids: str):
            """mission_executor에게 TaskCommand 발행."""
            msg = TaskCommandMsg()
            msg.task_type = task_type
            msg.task_id = task_id
            msg.poi_ids = poi_ids
            self._malle_command_pub.publish(msg)

        def publish_guide_advance(self):
            """/malle/guide_advance 발행 — mission_executor가 GuideExecutor.advance() 호출."""
            msg = String()
            msg.data = "advance"
            self._guide_advance_pub.publish(msg)

        def send_nav_goal(self, x: float, y: float, theta: float):
            """Nav2 NavigateToPose 액션으로 직접 이동 명령."""
            import math as _math
            if not self._nav2_client.wait_for_server(timeout_sec=3.0):
                self.get_logger().error('[bridge] Nav2 액션 서버 없음')
                return

            goal = NavigateToPose.Goal()
            goal.pose = PoseStamped()
            goal.pose.header.frame_id = 'map'
            goal.pose.header.stamp = self.get_clock().now().to_msg()
            goal.pose.pose.position.x = float(x)
            goal.pose.pose.position.y = float(y)
            goal.pose.pose.orientation.z = _math.sin(theta / 2.0)
            goal.pose.pose.orientation.w = _math.cos(theta / 2.0)

            self._nav2_client.send_goal_async(goal)
            self.get_logger().info(f"[bridge] Nav2 goal 전송: ({x:.3f}, {y:.3f})")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def run_http_server():
    if HAS_FASTAPI:
        uvicorn.run(bridge_app, host="0.0.0.0", port=BRIDGE_HTTP_PORT, log_level="warning")


def main():
    global _ros_node

    # HTTP 서버 스레드
    threading.Thread(target=run_http_server, daemon=True).start()

    print(f"[bridge_node] robot_id={ROBOT_ID}  namespace='{ROBOT_NAMESPACE}'")
    print(f"[bridge_node] HTTP:   http://0.0.0.0:{BRIDGE_HTTP_PORT}/health")
    print(f"[bridge_node] Camera: http://<ip>:{BRIDGE_HTTP_PORT}/camera/{ROBOT_ID}/stream")

    if HAS_ROS2:
        rclpy.init()

        bridge = BridgeNode()
        _ros_node = bridge

        from rclpy.executors import MultiThreadedExecutor
        ros_executor = MultiThreadedExecutor()
        ros_executor.add_node(bridge)

        try:
            ros_executor.spin()
        except KeyboardInterrupt:
            pass
        finally:
            bridge._http_client.close()
            ros_executor.shutdown()
            rclpy.shutdown()
    else:
        print("[bridge_node] HTTP-only mode. Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    print("[bridge_node] Shutdown.")


if __name__ == "__main__":
    main()