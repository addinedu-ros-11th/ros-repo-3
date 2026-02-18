"""Teleop endpoints (dashboard)."""

from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.robot import Robot, RobotStateCurrent, RobotNavState
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()

# bridge_node exposes a REST API for receiving commands from malle_service
BRIDGE_NODE_URL = "http://localhost:9100"


class TeleopCmdRequest(BaseModel):
    linear_x: float = 0.0
    angular_z: float = 0.0


async def _notify_bridge(robot_id: int, endpoint: str, payload: dict) -> bool:
    """Send command to bridge_node. Returns True on success."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(
                f"{BRIDGE_NODE_URL}/bridge/{endpoint}",
                json={"robot_id": robot_id, **payload},
            )
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


@router.post("/robots/{robot_id}/teleop/start")
async def start_teleop(robot_id: int, db: AsyncSession = Depends(get_db)):
    """Start teleoperation for a robot."""
    robot = await db.get(Robot, robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    state = await db.get(RobotStateCurrent, robot_id)
    if state:
        state.nav_state = RobotNavState.TELEOP
        state.updated_at = datetime.utcnow()
        await db.flush()

    bridge_ok = await _notify_bridge(robot_id, "teleop/start", {})

    await manager.send_to_dashboard(WsEvent.ROBOT_STATE_UPDATED, {
        "robot_id": robot_id,
        "nav_state": "TELEOP",
        "teleop": "started",
    })
    await manager.send_to_robot(robot_id, WsEvent.ROBOT_STATE_UPDATED, {
        "nav_state": "TELEOP",
    })

    return {"ok": True, "robot_id": robot_id, "teleop": "started", "bridge_connected": bridge_ok}


@router.post("/robots/{robot_id}/teleop/stop")
async def stop_teleop(robot_id: int, db: AsyncSession = Depends(get_db)):
    """Stop teleoperation."""
    robot = await db.get(Robot, robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    state = await db.get(RobotStateCurrent, robot_id)
    if state:
        state.nav_state = RobotNavState.IDLE
        state.updated_at = datetime.utcnow()
        await db.flush()

    bridge_ok = await _notify_bridge(robot_id, "teleop/stop", {})

    await manager.send_to_dashboard(WsEvent.ROBOT_STATE_UPDATED, {
        "robot_id": robot_id,
        "nav_state": "IDLE",
        "teleop": "stopped",
    })

    return {"ok": True, "robot_id": robot_id, "teleop": "stopped", "bridge_connected": bridge_ok}


@router.post("/robots/{robot_id}/teleop/cmd")
async def teleop_command(robot_id: int, req: TeleopCmdRequest, db: AsyncSession = Depends(get_db)):
    """Send teleop movement command."""
    robot = await db.get(Robot, robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    bridge_ok = await _notify_bridge(robot_id, "teleop/cmd", {
        "linear_x": req.linear_x,
        "angular_z": req.angular_z,
    })

    return {"ok": True, "linear_x": req.linear_x, "angular_z": req.angular_z, "bridge_connected": bridge_ok}
