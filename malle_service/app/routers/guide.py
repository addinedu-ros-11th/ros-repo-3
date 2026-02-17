"""Guide mode endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.guide import GuideQueueItem, GuideItemStatus
from app.models.session import Session
from app.models.mission import Mission, MissionType, MissionStatus
from app.models.poi import Poi
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()


class GuideQueueAddRequest(BaseModel):
    poi_id: int


class GuideQueueItemResponse(BaseModel):
    id: int
    session_id: int
    poi_id: int
    poi_name: str | None = None
    seq: int
    status: GuideItemStatus
    is_active: bool
    execution_batch_id: int | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class GuideItemStatusUpdateRequest(BaseModel):
    status: GuideItemStatus


async def _get_queue(db: AsyncSession, session_id: int) -> list[dict]:
    """Get full queue with POI names for WS broadcast."""
    result = await db.execute(
        select(GuideQueueItem, Poi.name)
        .join(Poi, GuideQueueItem.poi_id == Poi.id)
        .where(GuideQueueItem.session_id == session_id, GuideQueueItem.is_active == True)
        .order_by(GuideQueueItem.seq)
    )
    items = []
    for item, poi_name in result.all():
        d = GuideQueueItemResponse.model_validate(item).model_dump(mode="json")
        d["poi_name"] = poi_name
        items.append(d)
    return items


@router.get("/sessions/{session_id}/guide-queue", response_model=list[GuideQueueItemResponse])
async def get_guide_queue(session_id: int, db: AsyncSession = Depends(get_db)):
    """Get current guide queue for a session."""
    return await _get_queue(db, session_id)


@router.post("/sessions/{session_id}/guide-queue", response_model=GuideQueueItemResponse)
async def add_to_guide_queue(
    session_id: int,
    req: GuideQueueAddRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add POI to guide queue."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    poi = await db.get(Poi, req.poi_id)
    if not poi:
        raise HTTPException(status_code=404, detail="POI not found")

    # Get next seq number
    max_seq_result = await db.execute(
        select(func.coalesce(func.max(GuideQueueItem.seq), 0))
        .where(GuideQueueItem.session_id == session_id)
    )
    next_seq = max_seq_result.scalar() + 1

    item = GuideQueueItem(
        session_id=session_id,
        poi_id=req.poi_id,
        seq=next_seq,
        status=GuideItemStatus.PENDING,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    # WS broadcast
    queue = await _get_queue(db, session_id)
    await manager.send_to_mobile(session_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": queue})
    if session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": queue})
    await manager.send_to_dashboard(WsEvent.MISSION_UPDATED, {
        "session_id": session_id,
        "queue": queue,
    })

    resp = GuideQueueItemResponse.model_validate(item)
    resp.poi_name = poi.name
    return resp


@router.delete("/sessions/{session_id}/guide-queue/{item_id}")
async def remove_from_guide_queue(
    session_id: int, item_id: int, db: AsyncSession = Depends(get_db),
):
    """Remove item from guide queue (soft delete)."""
    item = await db.get(GuideQueueItem, item_id)
    if not item or item.session_id != session_id:
        raise HTTPException(status_code=404, detail="Guide queue item not found")

    item.is_active = False
    await db.flush()

    session = await db.get(Session, session_id)
    queue = await _get_queue(db, session_id)
    await manager.send_to_mobile(session_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": queue})
    if session and session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": queue})

    return {"ok": True}


@router.patch("/sessions/{session_id}/guide-queue/{item_id}", response_model=GuideQueueItemResponse)
async def update_guide_item_status(
    session_id: int,
    item_id: int,
    req: GuideItemStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update guide item status (PENDING→ARRIVED→DONE)."""
    item = await db.get(GuideQueueItem, item_id)
    if not item or item.session_id != session_id:
        raise HTTPException(status_code=404, detail="Guide queue item not found")

    item.status = req.status
    if req.status in (GuideItemStatus.DONE, GuideItemStatus.SKIPPED):
        item.completed_at = datetime.utcnow()

    await db.flush()
    await db.refresh(item)

    poi = await db.get(Poi, item.poi_id)
    session = await db.get(Session, session_id)

    # WS based on status
    if req.status == GuideItemStatus.ARRIVED:
        await manager.send_to_mobile(session_id, WsEvent.GUIDE_ARRIVED, {
            "item_id": item_id,
            "poi_name": poi.name if poi else None,
        })
        await manager.send_to_dashboard(WsEvent.GUIDE_ARRIVED, {
            "session_id": session_id,
            "item_id": item_id,
            "poi_name": poi.name if poi else None,
        })

    # Always send updated queue
    queue = await _get_queue(db, session_id)
    if session and session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": queue})

    resp = GuideQueueItemResponse.model_validate(item)
    resp.poi_name = poi.name if poi else None
    return resp


@router.post("/sessions/{session_id}/guide-queue/execute")
async def execute_guide_queue(session_id: int, db: AsyncSession = Depends(get_db)):
    """Start executing pending guide queue items. Creates/updates mission."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.assigned_robot_id:
        raise HTTPException(status_code=400, detail="No robot assigned")

    # Get pending items
    result = await db.execute(
        select(GuideQueueItem).where(
            GuideQueueItem.session_id == session_id,
            GuideQueueItem.is_active == True,
            GuideQueueItem.status == GuideItemStatus.PENDING,
        ).order_by(GuideQueueItem.seq)
    )
    pending = result.scalars().all()
    if not pending:
        raise HTTPException(status_code=400, detail="No pending items in queue")

    # Create or get mission
    mission_result = await db.execute(
        select(Mission).where(
            Mission.session_id == session_id,
            Mission.type == MissionType.GUIDE,
            Mission.status.in_([MissionStatus.QUEUED, MissionStatus.RUNNING]),
        )
    )
    mission = mission_result.scalar_one_or_none()

    if not mission:
        mission = Mission(
            session_id=session_id,
            robot_id=session.assigned_robot_id,
            type=MissionType.GUIDE,
            status=MissionStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        db.add(mission)
        await db.flush()
        await manager.send_to_dashboard(WsEvent.MISSION_CREATED, {
            "mission_id": mission.id,
            "session_id": session_id,
            "robot_id": session.assigned_robot_id,
            "type": "GUIDE",
        })

    # Mark batch
    batch_id = mission.id
    for item in pending:
        item.execution_batch_id = batch_id

    await db.flush()

    # Notify robot to start navigation
    queue = await _get_queue(db, session_id)
    first_item = pending[0]
    poi = await db.get(Poi, first_item.poi_id)

    await manager.send_to_robot(session.assigned_robot_id, WsEvent.GUIDE_NAVIGATING, {
        "item_id": first_item.id,
        "poi_id": first_item.poi_id,
        "poi_name": poi.name if poi else None,
        "queue": queue,
    })
    await manager.send_to_mobile(session_id, WsEvent.GUIDE_NAVIGATING, {
        "item_id": first_item.id,
        "poi_name": poi.name if poi else None,
    })

    return {"ok": True, "mission_id": mission.id, "executing_count": len(pending)}


@router.delete("/sessions/{session_id}/guide-queue")
async def clear_guide_queue(session_id: int, db: AsyncSession = Depends(get_db)):
    """Clear entire guide queue (soft delete all)."""
    result = await db.execute(
        select(GuideQueueItem).where(
            GuideQueueItem.session_id == session_id,
            GuideQueueItem.is_active == True,
        )
    )
    items = result.scalars().all()
    for item in items:
        item.is_active = False

    await db.flush()

    session = await db.get(Session, session_id)
    await manager.send_to_mobile(session_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": []})
    if session and session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": []})

    return {"ok": True, "cleared": len(items)}
