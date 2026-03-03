# Session management endpoints.

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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

class AssignRobotRequest(BaseModel):
    target_poi_id: int | None = None

from app.services.session_workflow import (
    create_session_with_assignment,
    assign_robot_to_session,
    transition_session_status,
    end_session as end_session_workflow,
)
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(req: SessionCreateRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new session with automatic robot assignment.

    Policy:
    - 동일 user_id에 대해 ENDED가 아닌 기존 세션이 있으면 모두 ENDED 처리 후 새 세션 생성.
      (중복 ACTIVE/MATCHING/ASSIGNED 누적 방지)
    """
    # 1) 기존 활성 세션(ENDED 아님) 정리
    existing_result = await db.execute(
        select(Session).where(
            Session.user_id == req.user_id,
            Session.status != SessionStatus.ENDED,
        ).order_by(Session.created_at.desc())
    )
    existing_sessions = existing_result.scalars().all()

    for s in existing_sessions:
        # 이미 ENDED면 제외(쿼리상 없지만 방어)
        if s.status == SessionStatus.ENDED:
            continue
        # 기존 세션 자동 종료
        await end_session_workflow(db, s, reason="superseded_by_new_session")

    # 2) 새 세션 생성 + 자동 배정
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

    follow_payload = {
        "session_id": session_id,
        "tag_code": req.tag_code,
        "tag_family": req.tag_family,
        "robot_id": session.assigned_robot_id,
    }
    if session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.FOLLOW_STARTED, follow_payload)
    await manager.send_to_mobile(session_id, WsEvent.FOLLOW_STARTED, follow_payload)
    # dashboard도 follow 시작 알림
    await manager.send_to_dashboard(WsEvent.FOLLOW_STARTED, follow_payload)

    return session


@router.post("/sessions/{session_id}/assign", response_model=SessionResponse)
async def assign_robot(
    session_id: int,
    req: AssignRobotRequest = AssignRobotRequest(),
    db: AsyncSession = Depends(get_db),
):
    """가용 로봇을 세션에 배정. REQUESTED 상태 또는 재배정 시 사용."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == SessionStatus.ENDED:
        raise HTTPException(status_code=400, detail="Cannot assign robot to ended session")

    session = await assign_robot_to_session(db, session, target_poi_id=req.target_poi_id)
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