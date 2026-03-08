"""WebSocket connection manager and endpoint routes."""

import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
WS_DEBUG_LOGS = os.getenv("WS_DEBUG_LOGS", "0") == "1"

ws_router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for mobile, robot, and dashboard clients."""

    def __init__(self):
        # mobile: session_id → WebSocket
        self.mobile_connections: dict[int, WebSocket] = {}
        # robot: robot_id → WebSocket
        self.robot_connections: dict[int, WebSocket] = {}
        # dashboard: list of WebSocket
        self.dashboard_connections: list[WebSocket] = []

    # --- Connect / Disconnect ---

    async def connect_mobile(self, session_id: int, ws: WebSocket):
        await ws.accept()
        self.mobile_connections[session_id] = ws
        logger.info(f"[WS] Mobile connected: session={session_id}")

    async def connect_robot(self, robot_id: int, ws: WebSocket):
        await ws.accept()
        self.robot_connections[robot_id] = ws
        logger.info(f"[WS] Robot connected: robot={robot_id}")

    async def connect_dashboard(self, ws: WebSocket):
        await ws.accept()
        self.dashboard_connections.append(ws)
        logger.info(f"[WS] Dashboard connected (total={len(self.dashboard_connections)})")

    def disconnect_mobile(self, session_id: int):
        self.mobile_connections.pop(session_id, None)
        logger.info(f"[WS] Mobile disconnected: session={session_id}")

    def disconnect_robot(self, robot_id: int):
        self.robot_connections.pop(robot_id, None)
        logger.info(f"[WS] Robot disconnected: robot={robot_id}")

    def disconnect_dashboard(self, ws: WebSocket):
        if ws in self.dashboard_connections:
            self.dashboard_connections.remove(ws)
        logger.info(f"[WS] Dashboard disconnected")

    # --- Send helpers ---

    @staticmethod
    def _make_message(event_type: str, payload: dict) -> str:
        return json.dumps({
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    async def send_to_mobile(self, session_id: int, event_type: str, payload: dict):
        ws = self.mobile_connections.get(session_id)
        if ws:
            try:
                await ws.send_text(self._make_message(event_type, payload))
            except Exception:
                self.disconnect_mobile(session_id)
        elif WS_DEBUG_LOGS:
            logger.warning(
                "[WS] drop mobile event=%s session=%s (no connection)",
                event_type,
                session_id,
            )

    async def send_to_robot(self, robot_id: int, event_type: str, payload: dict):
        ws = self.robot_connections.get(robot_id)
        if ws:
            try:
                await ws.send_text(self._make_message(event_type, payload))
            except Exception:
                self.disconnect_robot(robot_id)
        elif WS_DEBUG_LOGS:
            logger.warning(
                "[WS] drop robot event=%s robot=%s (no connection, connected=%s)",
                event_type,
                robot_id,
                list(self.robot_connections.keys()),
            )

    async def send_to_dashboard(self, event_type: str, payload: dict):
        msg = self._make_message(event_type, payload)
        dead = []
        for ws in self.dashboard_connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_dashboard(ws)

    async def broadcast_to_session(self, session_id: int, robot_id: int | None, event_type: str, payload: dict):
        """Send to mobile + assigned robot + all dashboards."""
        await self.send_to_mobile(session_id, event_type, payload)
        if robot_id:
            await self.send_to_robot(robot_id, event_type, payload)
        await self.send_to_dashboard(event_type, payload)


# Singleton
manager = ConnectionManager()


# --- WebSocket endpoints ---

@ws_router.websocket("/ws/mobile/{session_id}")
async def ws_mobile(ws: WebSocket, session_id: int):
    await manager.connect_mobile(session_id, ws)
    try:
        while True:
            data = await ws.receive_text()
            # Handle client→server messages (PING, etc.)
            try:
                msg = json.loads(data)
                if msg.get("type") == "PING":
                    await ws.send_text(manager._make_message("PONG", {}))
                elif msg.get("type") == "VOICE_CMD":
                    from app.ws.handlers import handle_voice_command
                    await handle_voice_command(
                        session_id=session_id,
                        text=msg.get("text", ""),
                        client_type="mobile",
                    )
            except json.JSONDecodeError:
                if data == "PING":
                    await ws.send_text(manager._make_message("PONG", {}))
    except WebSocketDisconnect:
        manager.disconnect_mobile(session_id)


@ws_router.websocket("/ws/robot/{robot_id}")
async def ws_robot(ws: WebSocket, robot_id: int):
    await manager.connect_robot(robot_id, ws)
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "PING":
                    await ws.send_text(manager._make_message("PONG", {}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect_robot(robot_id)


@ws_router.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await manager.connect_dashboard(ws)
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")
                if msg_type == "PING":
                    await ws.send_text(manager._make_message("PONG", {}))
                elif msg_type == "TELEOP_CMD":
                    from app.ws.handlers import handle_dashboard_teleop
                    await handle_dashboard_teleop(msg.get("payload", {}))
                elif msg_type == "VOICE_CMD":
                    from app.ws.handlers import handle_voice_command
                    await handle_voice_command(
                        session_id=msg.get("session_id", 0),
                        text=msg.get("text", ""),
                        client_type="dashboard",
                    )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect_dashboard(ws)
