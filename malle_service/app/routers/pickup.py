"""Pickup mode endpoints."""

import random
import string
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pickup import PickupOrder, PickupOrderItem, PickupStatus, PickupCreatedChannel, MeetType
from app.models.session import Session
from app.models.mission import Mission, MissionType, MissionStatus
from app.models.lockbox import LockboxSlot, LockboxSlotStatus
from app.ws.manager import manager
from app.ws.events import WsEvent

router = APIRouter()


class PickupItemRequest(BaseModel):
    product_id: int
    qty: int = 1
    unit_price: float = 0


class PickupCreateRequest(BaseModel):
    pickup_poi_id: int
    created_channel: PickupCreatedChannel = PickupCreatedChannel.APP
    items: list[PickupItemRequest] = []


class PickupStatusUpdateRequest(BaseModel):
    status: PickupStatus


class PickupMeetRequest(BaseModel):
    meet_type: MeetType
    meet_poi_id: int | None = None
    meet_x_m: float | None = None
    meet_y_m: float | None = None


class StaffPinVerifyRequest(BaseModel):
    pin: str


class PickupOrderResponse(BaseModel):
    id: int
    session_id: int
    created_channel: PickupCreatedChannel
    pickup_poi_id: int
    status: PickupStatus
    assigned_slot_id: int | None
    meet_type: MeetType | None
    meet_poi_id: int | None
    created_at: datetime
    loaded_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


@router.post("/sessions/{session_id}/pickup-orders", response_model=PickupOrderResponse)
async def create_pickup_order(
    session_id: int,
    req: PickupCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a pickup order."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Generate staff PIN
    staff_pin = "".join(random.choices(string.digits, k=4))

    order = PickupOrder(
        session_id=session_id,
        created_channel=req.created_channel,
        pickup_poi_id=req.pickup_poi_id,
        status=PickupStatus.CREATED,
        staff_pin=staff_pin,
    )
    db.add(order)
    await db.flush()

    # Add items
    for item_req in req.items:
        item = PickupOrderItem(
            pickup_order_id=order.id,
            product_id=item_req.product_id,
            qty=item_req.qty,
            unit_price=item_req.unit_price,
        )
        db.add(item)

    # Reserve lockbox slot if robot assigned
    if session.assigned_robot_id:
        slot_result = await db.execute(
            select(LockboxSlot).where(
                LockboxSlot.robot_id == session.assigned_robot_id,
                LockboxSlot.status == LockboxSlotStatus.EMPTY,
            ).limit(1)
        )
        slot = slot_result.scalar_one_or_none()
        if slot:
            slot.status = LockboxSlotStatus.RESERVED
            order.assigned_slot_id = slot.id

        # Create mission
        mission = Mission(
            session_id=session_id,
            robot_id=session.assigned_robot_id,
            type=MissionType.PICKUP,
            status=MissionStatus.QUEUED,
        )
        db.add(mission)

    await db.flush()
    await db.refresh(order)

    data = PickupOrderResponse.model_validate(order).model_dump(mode="json")

    # WS
    await manager.send_to_mobile(session_id, WsEvent.PICKUP_STATUS_CHANGED, data)
    if session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.PICKUP_STATUS_CHANGED, data)
    await manager.send_to_dashboard(WsEvent.MISSION_CREATED, {
        "session_id": session_id,
        "type": "PICKUP",
        "order": data,
    })

    return order


@router.get("/sessions/{session_id}/pickup-orders/{order_id}", response_model=PickupOrderResponse)
async def get_pickup_order(session_id: int, order_id: int, db: AsyncSession = Depends(get_db)):
    """Get pickup order status."""
    order = await db.get(PickupOrder, order_id)
    if not order or order.session_id != session_id:
        raise HTTPException(status_code=404, detail="Pickup order not found")
    return order


@router.patch("/sessions/{session_id}/pickup-orders/{order_id}/status", response_model=PickupOrderResponse)
async def update_pickup_status(
    session_id: int,
    order_id: int,
    req: PickupStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update pickup order status."""
    order = await db.get(PickupOrder, order_id)
    if not order or order.session_id != session_id:
        raise HTTPException(status_code=404, detail="Pickup order not found")

    order.status = req.status
    if req.status == PickupStatus.LOADED:
        order.loaded_at = datetime.utcnow()
    elif req.status == PickupStatus.COMPLETED:
        order.completed_at = datetime.utcnow()
        # Release slot
        if order.assigned_slot_id:
            slot = await db.get(LockboxSlot, order.assigned_slot_id)
            if slot:
                slot.status = LockboxSlotStatus.EMPTY

    await db.flush()
    await db.refresh(order)

    session = await db.get(Session, session_id)
    data = PickupOrderResponse.model_validate(order).model_dump(mode="json")

    await manager.send_to_mobile(session_id, WsEvent.PICKUP_STATUS_CHANGED, data)
    if session and session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.PICKUP_STATUS_CHANGED, data)
    await manager.send_to_dashboard(WsEvent.PICKUP_STATUS_CHANGED, data)

    return order


@router.post("/sessions/{session_id}/pickup-orders/{order_id}/staff-pin")
async def verify_staff_pin(
    session_id: int,
    order_id: int,
    req: StaffPinVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify staff PIN at store."""
    order = await db.get(PickupOrder, order_id)
    if not order or order.session_id != session_id:
        raise HTTPException(status_code=404, detail="Pickup order not found")

    if order.staff_pin != req.pin:
        raise HTTPException(status_code=400, detail="Invalid staff PIN")

    return {"ok": True, "verified": True}


@router.patch("/sessions/{session_id}/pickup-orders/{order_id}/meet", response_model=PickupOrderResponse)
async def set_meetup(
    session_id: int,
    order_id: int,
    req: PickupMeetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set meetup location."""
    order = await db.get(PickupOrder, order_id)
    if not order or order.session_id != session_id:
        raise HTTPException(status_code=404, detail="Pickup order not found")

    order.meet_type = req.meet_type
    order.meet_poi_id = req.meet_poi_id
    order.meet_x_m = req.meet_x_m
    order.meet_y_m = req.meet_y_m
    order.status = PickupStatus.MEET_SET

    await db.flush()
    await db.refresh(order)

    session = await db.get(Session, session_id)
    data = PickupOrderResponse.model_validate(order).model_dump(mode="json")

    if session and session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.PICKUP_MEET_SET, data)

    return order
