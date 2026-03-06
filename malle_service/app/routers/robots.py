"""Robot management endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.robot import (
    Robot, RobotStateCurrent, RobotMode,
    RobotStopState, EStopSource, RobotMotionState,
)
from app.schemas.robot import (
    RobotResponse, RobotListResponse,
    RobotStateUpdateRequest, RobotCommandRequest, EStopRequest,
)
from app.ws.manager import manager
from app.ws.events import WsEvent
from app.services.robot_dispatcher import get_dispatch_status, get_available_robot_count
from app.utils.bridge import register_bridge_url, send_to_bridge

router = APIRouter()


@router.get("/robots", response_model=RobotListResponse)
async def list_robots(db: AsyncSession = Depends(get_db)):
    """List all robots with current state."""
    result = await db.execute(
        select(Robot).options(selectinload(Robot.state)).order_by(Robot.id)
    )
    robots = result.scalars().all()
    return RobotListResponse(robots=robots)


@router.get("/robots/dispatch/status")
async def dispatch_status(db: AsyncSession = Depends(get_db)):
    """배정 현황: 전체 로봇 목록 + 가용 여부."""
    return await get_dispatch_status(db)


@router.get("/robots/dispatch/count")
async def dispatch_count(db: AsyncSession = Depends(get_db)):
    """현재 배정 가능한 로봇 수."""
    count = await get_available_robot_count(db)
    return {"available_count": count}


@router.get("/robots/{robot_id}", response_model=RobotResponse)
async def get_robot(robot_id: int, db: AsyncSession = Depends(get_db)):
    """Get robot detail including state_current."""
    result = await db.execute(
        select(Robot).options(selectinload(Robot.state)).where(Robot.id == robot_id)
    )
    robot = result.scalar_one_or_none()
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")
    return robot


@router.patch("/robots/{robot_id}/state", response_model=RobotResponse)
async def update_robot_state(
    robot_id: int,
    req: RobotStateUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update robot position/state (called by bridge_node or internal).

    Auto-transition: if a robot has an ASSIGNED session and starts MOVING,
    the session is automatically advanced to APPROACHING.
    """
    result = await db.execute(
        select(Robot).options(selectinload(Robot.state)).where(Robot.id == robot_id)
    )
    robot = result.scalar_one_or_none()
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    state = robot.state
    if not state:
        raise HTTPException(status_code=404, detail="Robot state not initialized")

    now = datetime.now(timezone.utc)

    # Update only provided fields
    if req.x_m is not None:
        state.x_m = req.x_m
    if req.y_m is not None:
        state.y_m = req.y_m
    if req.theta_rad is not None:
        state.theta_rad = req.theta_rad
    if req.motion_state is not None:
        state.motion_state = req.motion_state
    if req.nav_state is not None:
        state.nav_state = req.nav_state
    if req.target_poi_id is not None:
        state.target_poi_id = req.target_poi_id
    if req.remaining_distance_m is not None:
        state.remaining_distance_m = req.remaining_distance_m
    if req.eta_sec is not None:
        state.eta_sec = req.eta_sec
    if req.speed_mps is not None:
        state.speed_mps = req.speed_mps
    if req.battery_pct is not None:
        robot.battery_pct = req.battery_pct

    state.updated_at = now
    robot.last_seen_at = now

    if req.bridge_url:
        register_bridge_url(robot_id, req.bridge_url)

    await db.flush()

    # Auto-transition ASSIGNED → APPROACHING when robot starts moving
    from app.models.session import Session, SessionStatus
    from app.services.session_workflow import transition_session_status
    if req.motion_state == RobotMotionState.MOVING:
        sess_result = await db.execute(
            select(Session).where(
                Session.assigned_robot_id == robot_id,
                Session.status == SessionStatus.ASSIGNED,
            )
        )
        assigned_session = sess_result.scalar_one_or_none()
        if assigned_session:
            await transition_session_status(db, assigned_session, SessionStatus.APPROACHING)

    await db.refresh(robot)
    await db.refresh(state)

    # WS → dashboard
    from app.schemas.robot import RobotStateResponse
    state_data = RobotStateResponse.model_validate(state).model_dump(mode="json")
    await manager.send_to_dashboard(WsEvent.ROBOT_STATE_UPDATED, {
        "robot_id": robot_id,
        "state": state_data,
        "battery_pct": robot.battery_pct,
    })

    return robot


@router.post("/robots/{robot_id}/estop")
async def trigger_estop(
    robot_id: int,
    req: EStopRequest = EStopRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Trigger E-Stop from dashboard."""
    result = await db.execute(
        select(Robot).options(selectinload(Robot.state)).where(Robot.id == robot_id)
    )
    robot = result.scalar_one_or_none()
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    state = robot.state
    if not state:
        raise HTTPException(status_code=404, detail="Robot state not initialized")

    now = datetime.now(timezone.utc)
    state.stop_state = RobotStopState.ESTOP
    state.stop_source = req.source
    state.stop_updated_at = now
    state.motion_state = RobotMotionState.STOPPED
    state.speed_mps = 0
    state.updated_at = now

    await db.flush()

    # WS → dashboard + mobile (if session active)
    payload = {"robot_id": robot_id, "source": req.source.value}
    await manager.send_to_dashboard(WsEvent.ROBOT_ESTOP, payload)

    # Find active session for this robot to notify mobile
    from app.models.session import Session, SessionStatus
    sess_result = await db.execute(
        select(Session).where(
            Session.assigned_robot_id == robot_id,
            Session.status.not_in([SessionStatus.ENDED]),
        )
    )
    active_session = sess_result.scalar_one_or_none()
    if active_session:
        await manager.send_to_mobile(active_session.id, WsEvent.ROBOT_ESTOP, payload)

    return {"ok": True, "robot_id": robot_id, "stop_state": "ESTOP"}


@router.delete("/robots/{robot_id}/estop")
async def release_estop(robot_id: int, db: AsyncSession = Depends(get_db)):
    """Release E-Stop."""
    result = await db.execute(
        select(Robot).options(selectinload(Robot.state)).where(Robot.id == robot_id)
    )
    robot = result.scalar_one_or_none()
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    state = robot.state
    if not state:
        raise HTTPException(status_code=404, detail="Robot state not initialized")

    now = datetime.now(timezone.utc)
    state.stop_state = RobotStopState.NONE
    state.stop_source = None
    state.stop_updated_at = now
    state.updated_at = now

    await db.flush()

    payload = {"robot_id": robot_id}
    await manager.send_to_dashboard(WsEvent.ROBOT_ESTOP_RELEASED, payload)

    from app.models.session import Session, SessionStatus
    sess_result = await db.execute(
        select(Session).where(
            Session.assigned_robot_id == robot_id,
            Session.status.not_in([SessionStatus.ENDED]),
        )
    )
    active_session = sess_result.scalar_one_or_none()
    if active_session:
        await manager.send_to_mobile(active_session.id, WsEvent.ROBOT_ESTOP_RELEASED, payload)

    return {"ok": True, "robot_id": robot_id, "stop_state": "NONE"}


@router.post("/robots/{robot_id}/command")
async def send_command(
    robot_id: int,
    req: RobotCommandRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send command (go_maintenance, return_station)."""
    robot = await db.get(Robot, robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    valid_commands = {"go_maintenance", "return_station"}
    if req.command not in valid_commands:
        raise HTTPException(status_code=400, detail=f"Invalid command. Valid: {valid_commands}")

    # Forward command to ROS2 via bridge_node
    bridge_ok = await send_to_bridge("command", {"robot_id": robot_id, "command": req.command})

    if req.command == "return_station":
        robot.current_mode = RobotMode.IDLE

    await db.flush()

    await manager.send_to_dashboard(WsEvent.ROBOT_STATE_UPDATED, {
        "robot_id": robot_id,
        "command": req.command,
    })

    # Also forward to robot iPad
    await manager.send_to_robot(robot_id, WsEvent.ROBOT_STATE_UPDATED, {
        "command": req.command,
    })

    return {"ok": True, "robot_id": robot_id, "command": req.command, "bridge_connected": bridge_ok}