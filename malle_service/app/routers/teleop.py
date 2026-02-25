"""
malle_service/app/routers/teleop.py

Teleop endpoints (dashboard).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.robot import Robot, RobotStateCurrent, RobotNavState
from app.utils.bridge import send_to_bridge
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()


class TeleopCmdRequest(BaseModel):
    linear_x: float = 0.0
    angular_z: float = 0.0


@router.post("/robots/{robot_id}/teleop/start")
async def start_teleop(robot_id: int, db: AsyncSession = Depends(get_db)):
    """Start teleoperation for a robot."""
    robot = await db.get(Robot, robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    state = await db.get(RobotStateCurrent, robot_id)
    if state:
        state.nav_state = RobotNavState.TELEOP
        state.updated_at = datetime.now(timezone.utc)
        await db.flush()

    bridge_ok = await send_to_bridge("teleop/start", {"robot_id": robot_id})

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
        state.updated_at = datetime.now(timezone.utc)
        await db.flush()

    bridge_ok = await send_to_bridge("teleop/stop", {"robot_id": robot_id})

    await manager.send_to_dashboard(WsEvent.ROBOT_STATE_UPDATED, {
        "robot_id": robot_id,
        "nav_state": "IDLE",
        "teleop": "stopped",
    })

    return {"ok": True, "robot_id": robot_id, "teleop": "stopped", "bridge_connected": bridge_ok}


@router.post("/robots/{robot_id}/teleop/cmd")
async def teleop_command(robot_id: int, req: TeleopCmdRequest, db: AsyncSession = Depends(get_db)):
    """Send teleop movement command (low-frequency REST fallback; prefer WS TELEOP_CMD)."""
    robot = await db.get(Robot, robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    bridge_ok = await send_to_bridge("teleop/cmd", {
        "robot_id": robot_id,
        "linear_x": req.linear_x,
        "angular_z": req.angular_z,
    })

    return {"ok": True, "linear_x": req.linear_x, "angular_z": req.angular_z, "bridge_connected": bridge_ok}