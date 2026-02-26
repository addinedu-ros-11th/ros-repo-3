#!/usr/bin/env python3
import math
import os
import threading
import time
from typing import Optional

import httpx

try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from std_msgs.msg import String, Float32, Int32
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False
    print("[bridge_node] WARNING: ROS2 not available. Running in HTTP-only mode.")

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    print("[bridge_node] WARNING: FastAPI not available. Install with: pip install fastapi uvicorn")

# --- Configuration ---
MALLE_SERVICE_URL = os.getenv("MALLE_SERVICE_URL", "http://localhost:8000")
BRIDGE_HTTP_PORT = int(os.getenv("BRIDGE_HTTP_PORT", "9100"))
STATE_UPDATE_INTERVAL = 0.5  # seconds between state pushes

# Robot ID mapping: ROS2 namespace → DB robot_id
# 환경변수 ROBOT_NS_MAP 으로 주입 (형식: "robot1:1,robot2:2")
# 미설정 시 robot1:1 단일 로봇으로 동작
def _parse_robot_ns_map(env: str) -> dict:
    result = {}
    for entry in env.split(","):
        entry = entry.strip()
        if ":" not in entry:
            continue
        ns, rid = entry.split(":", 1)
        result[ns.strip()] = int(rid.strip())
    return result

ROBOT_NS_TO_ID = _parse_robot_ns_map(os.getenv("ROBOT_NS_MAP", "robot1:1"))
ROBOT_ID_TO_NS = {v: k for k, v in ROBOT_NS_TO_ID.items()}


# ============================================================
# Part 1: HTTP API server (receives commands from malle_service)
# ============================================================

if HAS_FASTAPI:
    bridge_app = FastAPI(title="Mall-E Bridge Node", version="0.1.0")

    class CommandRequest(BaseModel):
        robot_id: int
        command: str = ""

    class TeleopStartRequest(BaseModel):
        robot_id: int

    class TeleopStopRequest(BaseModel):
        robot_id: int

    class TeleopCmdRequest(BaseModel):
        robot_id: int
        linear_x: float = 0.0
        angular_z: float = 0.0

    # Reference to the ROS2 node (set after initialization)
    _ros_node: Optional["BridgeNode"] = None

    @bridge_app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "bridge_node",
            "ros2": HAS_ROS2,
            "node_active": _ros_node is not None,
        }

    @bridge_app.post("/bridge/command")
    async def receive_command(req: CommandRequest):
        """Receive robot command from malle_service → publish to ROS2."""
        if _ros_node and HAS_ROS2:
            _ros_node.publish_command(req.robot_id, req.command)
        return {"ok": True, "robot_id": req.robot_id, "command": req.command}

    @bridge_app.post("/bridge/teleop/start")
    async def teleop_start(req: TeleopStartRequest):
        if _ros_node and HAS_ROS2:
            _ros_node.set_teleop_mode(req.robot_id, True)
        return {"ok": True}

    @bridge_app.post("/bridge/teleop/stop")
    async def teleop_stop(req: TeleopStopRequest):
        if _ros_node and HAS_ROS2:
            _ros_node.set_teleop_mode(req.robot_id, False)
        return {"ok": True}

    @bridge_app.post("/bridge/teleop/cmd")
    async def teleop_cmd(req: TeleopCmdRequest):
        if _ros_node and HAS_ROS2:
            _ros_node.publish_cmd_vel(req.robot_id, req.linear_x, req.angular_z)
        return {"ok": True}

    @bridge_app.post("/bridge/navigate")
    async def navigate_to(req: dict):
        """Start Nav2 goal for robot."""
        robot_id = req.get("robot_id")
        x = req.get("x", 0.0)
        y = req.get("y", 0.0)
        theta = req.get("theta", 0.0)
        if _ros_node and HAS_ROS2:
            _ros_node.send_nav_goal(robot_id, x, y, theta)
        return {"ok": True}


# ============================================================
# Part 2: ROS2 Node (subscribes to topics, publishes commands)
# ============================================================

if HAS_ROS2:
    class BridgeNode(Node):
        def __init__(self):
            super().__init__("malle_bridge_node")
            self.get_logger().info("Mall-E Bridge Node starting...")

            self._http_client = httpx.Client(timeout=2.0)
            self._robot_states: dict[int, dict] = {}
            self._robot_modes: dict[int, str] = {}
            self._teleop_active: dict[int, bool] = {}
            self._cmd_vel_pubs: dict[int, object] = {}
            self._command_pubs: dict[int, object] = {}

            # Subscribe to each robot's topics
            for ns, robot_id in ROBOT_NS_TO_ID.items():
                # Odometry
                self.create_subscription(
                    Odometry,
                    f"/{ns}/odom",
                    lambda msg, rid=robot_id: self._odom_callback(rid, msg),
                    10,
                )
                # Battery (Float32: 0-100%)
                self.create_subscription(
                    Float32,
                    f"/{ns}/battery",
                    lambda msg, rid=robot_id: self._battery_callback(rid, msg),
                    10,
                )

                # Publishers
                self._cmd_vel_pubs[robot_id] = self.create_publisher(
                    Twist, f"/{ns}/cmd_vel", 10
                )
                self._command_pubs[robot_id] = self.create_publisher(
                    String, f"/{ns}/task_command", 10
                )

                self._robot_states[robot_id] = {
                    "x_m": 0.0, "y_m": 0.0, "theta_rad": 0.0,
                    "speed_mps": 0.0, "battery_pct": 100,
                }
                self._robot_modes[robot_id] = "IDLE"

            # Timer: push state to malle_service periodically
            self.create_timer(STATE_UPDATE_INTERVAL, self._push_states)
            self.get_logger().info(
                f"Subscribed to {len(ROBOT_NS_TO_ID)} robots. "
                f"HTTP server on :{BRIDGE_HTTP_PORT}"
            )

        def _odom_callback(self, robot_id: int, msg: Odometry):
            """Extract position and speed from odometry."""
            state = self._robot_states.get(robot_id)
            if not state:
                return
            state["x_m"] = round(msg.pose.pose.position.x, 3)
            state["y_m"] = round(msg.pose.pose.position.y, 3)

            # Quaternion → yaw
            q = msg.pose.pose.orientation
            siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            state["theta_rad"] = round(math.atan2(siny_cosp, cosy_cosp), 5)

            # Linear speed
            vx = msg.twist.twist.linear.x
            vy = msg.twist.twist.linear.y
            state["speed_mps"] = round(math.sqrt(vx * vx + vy * vy), 3)

        def _battery_callback(self, robot_id: int, msg: Float32):
            state = self._robot_states.get(robot_id)
            if state:
                state["battery_pct"] = int(msg.data)

        def _push_states(self):
            """Push all robot states to malle_service via POST /api/robots/state/update."""
            for robot_id, state in self._robot_states.items():
                ns = ROBOT_ID_TO_NS.get(robot_id, f"robot{robot_id}")
                payload = {
                    "robot_id": ns,
                    "mode": self._robot_modes.get(robot_id, "IDLE"),
                    "battery": state["battery_pct"],
                    "position_x": state["x_m"],
                    "position_y": state["y_m"],
                }
                try:
                    self._http_client.post(
                        f"{MALLE_SERVICE_URL}/api/robots/state/update",
                        json=payload,
                    )
                except httpx.ConnectError:
                    pass  # malle_service offline
                except Exception as e:
                    self.get_logger().warning(f"State push failed for robot {robot_id}: {e}")

        def publish_command(self, robot_id: int, command: str):
            """Publish task command to ROS2."""
            pub = self._command_pubs.get(robot_id)
            if pub:
                msg = String()
                msg.data = command
                pub.publish(msg)
                self.get_logger().info(f"Published command '{command}' to robot {robot_id}")

        def publish_cmd_vel(self, robot_id: int, linear_x: float, angular_z: float):
            """Publish velocity command for teleop."""
            pub = self._cmd_vel_pubs.get(robot_id)
            if pub:
                msg = Twist()
                msg.linear.x = linear_x
                msg.angular.z = angular_z
                pub.publish(msg)

        def set_teleop_mode(self, robot_id: int, active: bool):
            self._teleop_active[robot_id] = active
            self.get_logger().info(f"Teleop {'started' if active else 'stopped'} for robot {robot_id}")

        def send_nav_goal(self, robot_id: int, x: float, y: float, theta: float):
            """Send Nav2 goal. Uses task_command topic with JSON payload."""
            pub = self._command_pubs.get(robot_id)
            if pub:
                import json
                msg = String()
                msg.data = json.dumps({
                    "action": "navigate_to_pose",
                    "x": x, "y": y, "theta": theta,
                })
                pub.publish(msg)
                self.get_logger().info(f"Nav goal sent to robot {robot_id}: ({x}, {y}, {theta})")


# ============================================================
# Part 3: Main entry point
# ============================================================

def run_http_server():
    """Run bridge HTTP server in a separate thread."""
    if HAS_FASTAPI:
        uvicorn.run(bridge_app, host="0.0.0.0", port=BRIDGE_HTTP_PORT, log_level="warning")


def main():
    global _ros_node

    # Start HTTP server thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    print(f"[bridge_node] HTTP server started on :{BRIDGE_HTTP_PORT}")

    if HAS_ROS2:
        rclpy.init()
        node = BridgeNode()
        _ros_node = node
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node._http_client.close()
            node.destroy_node()
            rclpy.shutdown()
    else:
        # No ROS2: just keep HTTP server alive
        print("[bridge_node] Running in HTTP-only mode (no ROS2). Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    print("[bridge_node] Shutdown complete.")


if __name__ == "__main__":
    main()