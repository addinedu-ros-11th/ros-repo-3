"""Event endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import RobotEvent, EventType, EventSeverity
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()


class EventCreateRequest(BaseModel):
    robot_id: int
    session_id: int | None = None
    type: EventType
    severity: EventSeverity = EventSeverity.INFO
    payload_json: dict | None = None


class EventResponse(BaseModel):
    id: int
    robot_id: int
    session_id: int | None
    type: EventType
    severity: EventSeverity
    payload_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    severity: EventSeverity | None = None,
    robot_id: int | None = None,
    type: EventType | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List events with filters."""
    query = select(RobotEvent).order_by(RobotEvent.created_at.desc()).limit(limit)
    if severity:
        query = query.where(RobotEvent.severity == severity)
    if robot_id:
        query = query.where(RobotEvent.robot_id == robot_id)
    if type:
        query = query.where(RobotEvent.type == type)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/events", response_model=EventResponse)
async def create_event(req: EventCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create an event (from ROS2 or internal)."""
    event = RobotEvent(
        robot_id=req.robot_id,
        session_id=req.session_id,
        type=req.type,
        severity=req.severity,
        payload_json=req.payload_json,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)

    data = EventResponse.model_validate(event).model_dump(mode="json")
    await manager.send_to_dashboard(WsEvent.ROBOT_EVENT, data)

    return event
