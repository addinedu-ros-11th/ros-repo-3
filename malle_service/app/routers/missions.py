"""Mission endpoints (dashboard)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.mission import Mission, MissionType, MissionStatus
from app.models.guide import GuideQueueItem
from app.models.poi import Poi
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()


class MissionResponse(BaseModel):
    id: int
    session_id: int
    robot_id: int
    type: MissionType
    status: MissionStatus
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class MissionStatusUpdateRequest(BaseModel):
    status: MissionStatus


@router.get("/missions", response_model=list[MissionResponse])
async def list_missions(
    status: MissionStatus | None = None,
    robot_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List missions with optional filters."""
    query = select(Mission).order_by(Mission.created_at.desc())
    if status:
        query = query.where(Mission.status == status)
    if robot_id:
        query = query.where(Mission.robot_id == robot_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/missions/{mission_id}")
async def get_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    """Get mission detail with guide queue if applicable."""
    mission = await db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    data = MissionResponse.model_validate(mission).model_dump(mode="json")

    # Include guide queue if GUIDE mission
    if mission.type == MissionType.GUIDE:
        result = await db.execute(
            select(GuideQueueItem, Poi.name)
            .join(Poi, GuideQueueItem.poi_id == Poi.id)
            .where(
                GuideQueueItem.session_id == mission.session_id,
                GuideQueueItem.is_active == True,
            )
            .order_by(GuideQueueItem.seq)
        )
        guide_queue = []
        for item, poi_name in result.all():
            guide_queue.append({
                "id": item.id,
                "poi_name": poi_name,
                "status": item.status.value,
                "seq": item.seq,
            })
        data["guide_queue"] = guide_queue

    return data


@router.patch("/missions/{mission_id}/status", response_model=MissionResponse)
async def update_mission_status(
    mission_id: int,
    req: MissionStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Pause/resume/cancel a mission."""
    mission = await db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    mission.status = req.status
    if req.status == MissionStatus.COMPLETED:
        mission.ended_at = datetime.utcnow()
    elif req.status == MissionStatus.CANCELED:
        mission.ended_at = datetime.utcnow()
    elif req.status == MissionStatus.RUNNING and not mission.started_at:
        mission.started_at = datetime.utcnow()

    await db.flush()
    await db.refresh(mission)

    data = MissionResponse.model_validate(mission).model_dump(mode="json")
    await manager.send_to_dashboard(WsEvent.MISSION_UPDATED, data)

    return mission
