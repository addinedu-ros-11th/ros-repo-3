"""Session management endpoints."""

import random
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.session import Session, SessionStatus, SessionType
from app.models.robot import Robot, RobotMode
from app.schemas.session import (
    SessionCreateRequest,
    SessionStatusUpdateRequest,
    SessionResponse,
    SessionListResponse,
    PinVerifyRequest,
    FollowTagRequest,
)
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()


def _generate_pin(length: int = 4) -> str:
    return "".join(random.choices(string.digits, k=length))


@router.post("/sessions", response_model=SessionResponse)
async def create_session(req: SessionCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create a new session. Generates match_pin."""
    pin = _generate_pin()

    session = Session(
        user_id=req.user_id,
        session_type=req.session_type,
        requested_minutes=req.requested_minutes,
        status=SessionStatus.REQUESTED,
        match_pin=pin,
        pin_expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # TODO: 로봇 자동 배정 — 팀원 알고리즘 연결
    # 현재는 가장 가까운 IDLE 로봇을 단순 배정 (데모용)
    idle_robot = await db.execute(
        select(Robot).where(Robot.current_mode == RobotMode.IDLE, Robot.is_online == True).limit(1)
    )
    robot = idle_robot.scalar_one_or_none()

    if robot:
        session.assigned_robot_id = robot.id
        session.status = SessionStatus.ASSIGNED
        robot.current_mode = RobotMode.GUIDE  # default; will change based on user choice
        await db.flush()
        await db.refresh(session)

        # WS: notify mobile + robot
        session_data = SessionResponse.model_validate(session).model_dump(mode="json")
        await manager.send_to_mobile(session.id, WsEvent.SESSION_ASSIGNED, session_data)
        await manager.send_to_robot(robot.id, WsEvent.SESSION_ASSIGNED, session_data)
        await manager.send_to_dashboard(WsEvent.SESSION_ASSIGNED, session_data)

    return session


@router.get("/sessions/active", response_model=SessionListResponse)
async def list_active_sessions(db: AsyncSession = Depends(get_db)):
    """List all active sessions (for dashboard)."""
    result = await db.execute(
        select(Session).where(
            Session.status.not_in([SessionStatus.ENDED])
        ).order_by(Session.created_at.desc())
    )
    sessions = result.scalars().all()
    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """Get session details."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/sessions/{session_id}/status", response_model=SessionResponse)
async def update_session_status(
    session_id: int,
    req: SessionStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update session status (ASSIGNED→APPROACHING→MATCHING→ACTIVE→ENDED)."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    old_status = session.status
    session.status = req.status

    if req.status == SessionStatus.ACTIVE:
        session.started_at = datetime.utcnow()
    elif req.status == SessionStatus.ENDED:
        session.ended_at = datetime.utcnow()

    await db.flush()
    await db.refresh(session)

    # WS broadcasts based on new status
    session_data = SessionResponse.model_validate(session).model_dump(mode="json")

    if req.status == SessionStatus.APPROACHING:
        await manager.send_to_mobile(session_id, WsEvent.ROBOT_APPROACHING, session_data)

    elif req.status == SessionStatus.MATCHING:
        await manager.send_to_mobile(session_id, WsEvent.PIN_MATCHING, {
            "session_id": session_id,
            "pin": session.match_pin,
        })

    elif req.status == SessionStatus.ACTIVE:
        await manager.broadcast_to_session(
            session_id, session.assigned_robot_id,
            WsEvent.SESSION_ACTIVE, session_data,
        )

    elif req.status == SessionStatus.ENDED:
        await manager.broadcast_to_session(
            session_id, session.assigned_robot_id,
            WsEvent.SESSION_ENDED, {"session_id": session_id, "reason": "status_update"},
        )
        # Release robot
        if session.assigned_robot_id:
            robot = await db.get(Robot, session.assigned_robot_id)
            if robot:
                robot.current_mode = RobotMode.IDLE

    return session


@router.post("/sessions/{session_id}/verify-pin", response_model=SessionResponse)
async def verify_pin(
    session_id: int,
    req: PinVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify PIN matching. On success, session becomes ACTIVE."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != SessionStatus.MATCHING:
        raise HTTPException(status_code=400, detail=f"Session not in MATCHING state (current: {session.status})")

    if session.pin_expires_at and datetime.utcnow() > session.pin_expires_at:
        raise HTTPException(status_code=400, detail="PIN expired")

    if session.match_pin != req.pin:
        raise HTTPException(status_code=400, detail="Invalid PIN")

    # PIN matched → ACTIVE
    session.status = SessionStatus.ACTIVE
    session.started_at = datetime.utcnow()
    await db.flush()
    await db.refresh(session)

    session_data = SessionResponse.model_validate(session).model_dump(mode="json")
    await manager.broadcast_to_session(
        session_id, session.assigned_robot_id,
        WsEvent.SESSION_ACTIVE, session_data,
    )

    return session


@router.patch("/sessions/{session_id}/follow-tag", response_model=SessionResponse)
async def set_follow_tag(
    session_id: int,
    req: FollowTagRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set AprilTag code for follow mode."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.follow_tag_code = req.tag_code
    session.follow_tag_family = req.tag_family
    session.follow_tag_set_at = datetime.utcnow()
    await db.flush()
    await db.refresh(session)

    # Notify robot
    if session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.FOLLOW_STARTED, {
            "session_id": session_id,
            "tag_code": req.tag_code,
            "tag_family": req.tag_family,
        })

    return session


@router.post("/sessions/{session_id}/end", response_model=SessionResponse)
async def end_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """End an active session."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == SessionStatus.ENDED:
        raise HTTPException(status_code=400, detail="Session already ended")

    session.status = SessionStatus.ENDED
    session.ended_at = datetime.utcnow()

    # Release robot
    if session.assigned_robot_id:
        robot = await db.get(Robot, session.assigned_robot_id)
        if robot:
            robot.current_mode = RobotMode.IDLE

    await db.flush()
    await db.refresh(session)

    await manager.broadcast_to_session(
        session_id, session.assigned_robot_id,
        WsEvent.SESSION_ENDED, {"session_id": session_id, "reason": "user_ended"},
    )

    return session
