"""Session management endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.session import Session, SessionStatus
from app.schemas.session import (
    SessionCreateRequest,
    SessionStatusUpdateRequest,
    SessionResponse,
    SessionListResponse,
    PinVerifyRequest,
    FollowTagRequest,
)
from app.services.session_workflow import (
    create_session_with_assignment,
    transition_session_status,
    end_session as end_session_workflow,
)
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(req: SessionCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create a new session with automatic robot assignment."""
    session = await create_session_with_assignment(
        db,
        user_id=req.user_id,
        session_type=req.session_type,
        requested_minutes=req.requested_minutes,
    )
    return session


@router.get("/sessions/active", response_model=SessionListResponse)
async def list_active_sessions(db: AsyncSession = Depends(get_db)):
    """List all active sessions (for dashboard)."""
    result = await db.execute(
        select(Session).where(
            Session.status != SessionStatus.ENDED,
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
    """Update session status (ASSIGNED→APPROACHING→MATCHING→ACTIVE→ENDED).

    APPROACHING is triggered by bridge_node when the robot starts moving toward the customer.
    In demo/dev, call this endpoint manually:
      PATCH /api/v1/sessions/{id}/status  { "status": "APPROACHING" }
    """
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session = await transition_session_status(db, session, req.status)
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
        raise HTTPException(
            status_code=400,
            detail=f"Session not in MATCHING state (current: {session.status})",
        )

    if session.pin_expires_at and datetime.utcnow() > session.pin_expires_at.replace(tzinfo=None):
        raise HTTPException(status_code=400, detail="PIN expired")

    if session.match_pin != req.pin:
        raise HTTPException(status_code=400, detail="Invalid PIN")

    # PIN matched → ACTIVE
    session = await transition_session_status(db, session, SessionStatus.ACTIVE)
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
    session.follow_tag_set_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(session)

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

    session = await end_session_workflow(db, session, reason="user_ended")
    return session