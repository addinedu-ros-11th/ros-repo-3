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

MALLE_SERVICE_URL     = os.getenv("MALLE_SERVICE_URL", "http://localhost:8000")
BRIDGE_HTTP_PORT      = int(os.getenv("BRIDGE_HTTP_PORT", "9100"))
STATE_UPDATE_INTERVAL = 0.5


def _topic(name: str) -> str:
    return f"/{ROBOT_NAMESPACE}/{name.lstrip('/')}"


TOPIC_ODOM           = _topic("odom")
TOPIC_BATTERY        = _topic("battery/present")
TOPIC_CMD_VEL_TELEOP = _topic("cmd_vel_teleop")
TOPIC_PREEMPT_TELEOP = _topic("preempt_teleop")
TOPIC_TASK_COMMAND   = _topic("task_command")

JPEG_QUALITY   = 70
STREAM_MAX_FPS = 15
CAMERA_WIDTH   = 640
CAMERA_HEIGHT  = 480

# ─────────────────────────────────────────────────────────────
# ROS2 import
# ─────────────────────────────────────────────────────────────
try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from std_msgs.msg import String, Float32, Empty
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False
    print("[bridge_node] WARNING: ROS2 not available. HTTP-only mode.")

# ─────────────────────────────────────────────────────────────
# Camera import
# ─────────────────────────────────────────────────────────────
try:
    import cv2
    import numpy as np
    from malle_bot.src.malle_controller.malle_controller.camera import Camera as PinkyCamera
    HAS_CAMERA = True
    print("[bridge_node] Camera: camera.py loaded")
except ImportError as e:
    HAS_CAMERA = False
    print(f"[bridge_node] Camera disabled: {e}")

# ─────────────────────────────────────────────────────────────
# FastAPI import
# ─────────────────────────────────────────────────────────────
try:
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

    print("[bridge_node] WARNING: FastAPI not available.")


# ─────────────────────────────────────────────────────────────
# Camera frame buffer
# ─────────────────────────────────────────────────────────────

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


def _camera_loop():
    if not HAS_CAMERA:
        return

    cam = None
    while True:
        try:
            cam = PinkyCamera()
            cam.start(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
            print(f"[camera] Picamera2 started ({CAMERA_WIDTH}x{CAMERA_HEIGHT})")

            while True:
                frame = cam.get_frame()
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                _, buf = cv2.imencode(
                    ".jpg", frame_bgr,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
                camera_buffer.put(buf.tobytes())
                time.sleep(1.0 / STREAM_MAX_FPS)

        except RuntimeError as e:
            print(f"[camera] Error: {e}. Retrying in 3s...")
            if cam:
                try: cam.close()
                except Exception: pass
            time.sleep(3.0)
        except Exception as e:
            print(f"[camera] Unexpected error: {e}. Retrying in 5s...")
            if cam:
                try: cam.close()
                except Exception: pass
            time.sleep(5.0)


# ─────────────────────────────────────────────────────────────
# HTTP API server (:9100)
# ─────────────────────────────────────────────────────────────

if HAS_FASTAPI:
    bridge_app = FastAPI(title="Mall-E Bridge Node", version="0.4.0")

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

    # 전역 참조 (main()에서 주입)
    _ros_node: Optional["BridgeNode"] = None
    _mission_executor = None

    @bridge_app.get("/health")
    async def health():
        return {
            "status": "ok",
            "robot_id": ROBOT_ID,
            "namespace": ROBOT_NAMESPACE,
            "camera": HAS_CAMERA,
            "mission_executor": _mission_executor is not None,
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
        session_id 있으면 MissionExecutor.dispatch_guide() 사용,
        없으면 단순 좌표 이동.
        """
        if not _mission_executor:
            if _ros_node:
                _ros_node.send_nav_goal(req.x, req.y, req.theta)
            return {"ok": True, "mode": "fallback_nav"}

        if req.session_id:
            def _dispatch():
                _mission_executor.dispatch_guide(req.session_id)
            threading.Thread(target=_dispatch, daemon=True).start()
            return {"ok": True, "mode": "guide", "session_id": req.session_id}
        else:
            def _nav():
                from malle_controller.nav_core import NavCore
                if hasattr(_mission_executor, 'navigate_to_pose'):
                    _mission_executor.navigate_to_pose(req.x, req.y, req.theta)
            threading.Thread(target=_nav, daemon=True).start()
            return {"ok": True, "mode": "direct_nav"}

    @bridge_app.post("/bridge/stop")
    async def stop_mission():
        """E-Stop 또는 세션 종료 시 모든 미션 중지."""
        if _mission_executor:
            _mission_executor.stop_all()
        elif _ros_node:
            _ros_node.publish_cmd_vel(0.0, 0.0)
        return {"ok": True}

    # ── MJPEG 스트리밍 ──────────────────────────────────────────────────────

    def _make_placeholder(robot_id: int) -> bytes:
        if not HAS_CAMERA:
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
            self.get_logger().info(f"  odom:    {TOPIC_ODOM}")
            self.get_logger().info(f"  battery: {TOPIC_BATTERY}")

            self._cmd_vel_pub      = self.create_publisher(Twist, TOPIC_CMD_VEL_TELEOP, 10)
            self._preempt_pub      = self.create_publisher(Empty, TOPIC_PREEMPT_TELEOP, 10)
            self._task_command_pub = self.create_publisher(String, TOPIC_TASK_COMMAND, 10)

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

        def _push_state(self):
            motion = "MOVING" if self._state["speed_mps"] > 0.01 else "STOPPED"
            try:
                self._http_client.patch(
                    f"{MALLE_SERVICE_URL}/robots/{ROBOT_ID}/state",
                    json={
                        "x_m":          self._state["x_m"],
                        "y_m":          self._state["y_m"],
                        "theta_rad":    self._state["theta_rad"],
                        "speed_mps":    self._state["speed_mps"],
                        "battery_pct":  self._state["battery_pct"],
                        "motion_state": motion,
                    },
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

        def send_nav_goal(self, x: float, y: float, theta: float):
            """폴백용 — MissionExecutor 없을 때만 사용."""
            import json as _j
            msg = String()
            msg.data = _j.dumps({"action": "navigate_to_pose", "x": x, "y": y, "theta": theta})
            self._task_command_pub.publish(msg)
            self.get_logger().info(f"[fallback] Nav goal: ({x:.3f}, {y:.3f})")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def run_http_server():
    if HAS_FASTAPI:
        uvicorn.run(bridge_app, host="0.0.0.0", port=BRIDGE_HTTP_PORT, log_level="warning")


def main():
    global _ros_node, _mission_executor

    # 카메라 스레드
    threading.Thread(target=_camera_loop, daemon=True).start()

    # HTTP 서버 스레드
    threading.Thread(target=run_http_server, daemon=True).start()

    print(f"[bridge_node] robot_id={ROBOT_ID}  namespace='{ROBOT_NAMESPACE}'")
    print(f"[bridge_node] HTTP:   http://0.0.0.0:{BRIDGE_HTTP_PORT}/health")
    print(f"[bridge_node] Camera: http://<ip>:{BRIDGE_HTTP_PORT}/camera/{ROBOT_ID}/stream")

    if HAS_ROS2:
        rclpy.init()

        bridge = BridgeNode()
        _ros_node = bridge

        try:
            from malle_controller.mission_executor import MissionExecutor
            executor = MissionExecutor(api_base_url=MALLE_SERVICE_URL)
            _mission_executor = executor
            print("[bridge_node] MissionExecutor 로드 완료")
        except Exception as e:
            print(f"[bridge_node] MissionExecutor 로드 실패: {e} — 폴백 모드")

        from rclpy.executors import MultiThreadedExecutor
        ros_executor = MultiThreadedExecutor()
        ros_executor.add_node(bridge)
        if _mission_executor:
            ros_executor.add_node(_mission_executor)

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