"""Lockbox endpoints."""

import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lockbox import (
    LockboxSlot, LockboxSlotStatus, LockboxOpenLog, LockboxOpenResult,
    LockboxActor, LockboxToken,
)
from app.models.session import Session, SessionStatus
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()


class SlotResponse(BaseModel):
    id: int
    robot_id: int
    slot_no: int
    status: LockboxSlotStatus
    size_label: str | None

    model_config = {"from_attributes": True}


class OpenLogResponse(BaseModel):
    id: int
    robot_id: int
    slot_id: int
    actor: LockboxActor
    result: LockboxOpenResult
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenCreateRequest(BaseModel):
    session_id: int
    slot_id: int | None = None


class TokenVerifyRequest(BaseModel):
    token: str
    session_id: int


class SlotStatusUpdateRequest(BaseModel):
    status: LockboxSlotStatus


async def _get_slots(db: AsyncSession, robot_id: int) -> list[dict]:
    result = await db.execute(
        select(LockboxSlot).where(LockboxSlot.robot_id == robot_id).order_by(LockboxSlot.slot_no)
    )
    return [SlotResponse.model_validate(s).model_dump(mode="json") for s in result.scalars().all()]


async def _get_active_session_id(db: AsyncSession, robot_id: int) -> int | None:
    """활성 세션 id 조회 (mobile WS 브로드캐스트용)."""
    result = await db.execute(
        select(Session.id).where(
            Session.assigned_robot_id == robot_id,
            Session.status != SessionStatus.ENDED,
        ).limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/robots/{robot_id}/lockbox", response_model=list[SlotResponse])
async def get_lockbox_slots(robot_id: int, db: AsyncSession = Depends(get_db)):
    """Get all lockbox slot statuses for a robot."""
    result = await db.execute(
        select(LockboxSlot).where(LockboxSlot.robot_id == robot_id).order_by(LockboxSlot.slot_no)
    )
    return result.scalars().all()


@router.post("/robots/{robot_id}/lockbox/{slot_no}/open")
async def open_slot(
    robot_id: int,
    slot_no: int,
    actor: LockboxActor = LockboxActor.CUSTOMER,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Open a lockbox slot."""
    result = await db.execute(
        select(LockboxSlot).where(
            LockboxSlot.robot_id == robot_id,
            LockboxSlot.slot_no == slot_no,
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    log = LockboxOpenLog(
        robot_id=robot_id,
        slot_id=slot.id,
        actor=actor,
        result=LockboxOpenResult.SUCCESS,
        reason=reason or "MANUAL_OPEN",
    )
    db.add(log)
    await db.flush()

    slots = await _get_slots(db, robot_id)
    session_id = await _get_active_session_id(db, robot_id)

    await manager.send_to_robot(robot_id, WsEvent.LOCKBOX_OPENED, {
        "slot_no": slot_no, "actor": actor.value,
    })
    if session_id:
        await manager.send_to_mobile(session_id, WsEvent.LOCKBOX_OPENED, {
            "slot_no": slot_no, "actor": actor.value,
        })
    await manager.send_to_dashboard(WsEvent.LOCKBOX_OPENED, {
        "robot_id": robot_id, "slot_no": slot_no, "actor": actor.value,
    })
    await manager.send_to_robot(robot_id, WsEvent.LOCKBOX_UPDATED, {"slots": slots})
    if session_id:
        await manager.send_to_mobile(session_id, WsEvent.LOCKBOX_UPDATED, {"slots": slots})
    await manager.send_to_dashboard(WsEvent.LOCKBOX_UPDATED, {"robot_id": robot_id, "slots": slots})

    return {"ok": True, "slot_no": slot_no}


@router.patch("/robots/{robot_id}/lockbox/{slot_no}/status", response_model=SlotResponse)
async def update_slot_status(
    robot_id: int,
    slot_no: int,
    req: SlotStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update lockbox slot status and broadcast to all clients."""
    result = await db.execute(
        select(LockboxSlot).where(
            LockboxSlot.robot_id == robot_id,
            LockboxSlot.slot_no == slot_no,
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    slot.status = req.status
    await db.flush()

    slots = await _get_slots(db, robot_id)
    session_id = await _get_active_session_id(db, robot_id)

    await manager.send_to_robot(robot_id, WsEvent.LOCKBOX_UPDATED, {"slots": slots})
    await manager.send_to_dashboard(WsEvent.LOCKBOX_UPDATED, {"robot_id": robot_id, "slots": slots})
    if session_id:
        await manager.send_to_mobile(session_id, WsEvent.LOCKBOX_UPDATED, {"slots": slots})
        if req.status == LockboxSlotStatus.FULL:
            await manager.send_to_mobile(session_id, WsEvent.LOCKBOX_STORED, {
                "slot_no": slot_no, "robot_id": robot_id,
            })

    return slot


@router.get("/robots/{robot_id}/lockbox/logs", response_model=list[OpenLogResponse])
async def get_lockbox_logs(robot_id: int, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get lockbox open logs."""
    result = await db.execute(
        select(LockboxOpenLog)
        .where(LockboxOpenLog.robot_id == robot_id)
        .order_by(LockboxOpenLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/robots/{robot_id}/lockbox/tokens")
async def create_lockbox_token(
    robot_id: int,
    req: TokenCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a lockbox token for app-based opening."""
    token_str = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    token = LockboxToken(
        session_id=req.session_id,
        slot_id=req.slot_id,
        token=token_str,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.add(token)
    await db.flush()

    return {"token": token_str, "expires_at": token.expires_at.isoformat()}


@router.post("/robots/{robot_id}/lockbox/verify-token")
async def verify_lockbox_token(
    robot_id: int,
    req: TokenVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify token and open slot."""
    result = await db.execute(
        select(LockboxToken).where(
            LockboxToken.session_id == req.session_id,
            LockboxToken.token == req.token,
            LockboxToken.used_at == None,
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or used token")

    if datetime.now(timezone.utc) > token.expires_at:
        raise HTTPException(status_code=400, detail="Token expired")

    token.used_at = datetime.now(timezone.utc)
    await db.flush()

    if token.slot_id:
        slot = await db.get(LockboxSlot, token.slot_id)
        if slot:
            slot.status = LockboxSlotStatus.PICKEDUP

            log = LockboxOpenLog(
                robot_id=robot_id,
                slot_id=slot.id,
                session_id=req.session_id,
                actor=LockboxActor.CUSTOMER,
                result=LockboxOpenResult.SUCCESS,
                reason="TOKEN_OPEN",
            )
            db.add(log)
            await db.flush()

            slots = await _get_slots(db, robot_id)
            await manager.send_to_robot(robot_id, WsEvent.LOCKBOX_OPENED, {
                "slot_no": slot.slot_no, "actor": LockboxActor.CUSTOMER.value,
            })
            await manager.send_to_mobile(req.session_id, WsEvent.LOCKBOX_OPENED, {
                "slot_no": slot.slot_no, "actor": LockboxActor.CUSTOMER.value,
            })
            await manager.send_to_dashboard(WsEvent.LOCKBOX_OPENED, {
                "robot_id": robot_id, "slot_no": slot.slot_no, "actor": LockboxActor.CUSTOMER.value,
            })
            await manager.send_to_robot(robot_id, WsEvent.LOCKBOX_UPDATED, {"slots": slots})
            await manager.send_to_mobile(req.session_id, WsEvent.LOCKBOX_UPDATED, {"slots": slots})
            await manager.send_to_dashboard(WsEvent.LOCKBOX_UPDATED, {"robot_id": robot_id, "slots": slots})

    return {"ok": True, "verified": True}
