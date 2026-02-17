"""Teleop endpoints (dashboard)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.robot import Robot, RobotStateCurrent, RobotNavState
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
        state.updated_at = datetime.utcnow()
        await db.flush()

    # TODO: Notify ROS2 via bridge_node (POST callback or polling)

    await manager.send_to_dashboard(WsEvent.ROBOT_STATE_UPDATED, {
        "robot_id": robot_id,
        "nav_state": "TELEOP",
        "teleop": "started",
    })
    await manager.send_to_robot(robot_id, WsEvent.ROBOT_STATE_UPDATED, {
        "nav_state": "TELEOP",
    })

    return {"ok": True, "robot_id": robot_id, "teleop": "started"}


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

    # TODO: Notify ROS2 via bridge_node

    await manager.send_to_dashboard(WsEvent.ROBOT_STATE_UPDATED, {
        "robot_id": robot_id,
        "nav_state": "IDLE",
        "teleop": "stopped",
    })

    return {"ok": True, "robot_id": robot_id, "teleop": "stopped"}


@router.post("/robots/{robot_id}/teleop/cmd")
async def teleop_command(robot_id: int, req: TeleopCmdRequest, db: AsyncSession = Depends(get_db)):
    """Send teleop movement command."""
    robot = await db.get(Robot, robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    # TODO: Forward to ROS2 via bridge_node
    # bridge_node polls this endpoint or receives callback

    return {"ok": True, "linear_x": req.linear_x, "angular_z": req.angular_z}
