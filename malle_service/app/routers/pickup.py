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


async def _get_lockbox_slots(db: AsyncSession, robot_id: int) -> list[dict]:
    """락박스 슬롯 목록 조회 (LOCKBOX_UPDATED 브로드캐스트용).

    pickup_poi_id는 항상 pois.id를 참조 (FK 정의).
    store 이름은 pois → stores (stores.poi_id == pois.id) 경로로 조회하되,
    store가 없는 POI(시설 등)면 poi.name을 그대로 사용.
    """
    from sqlalchemy import select as _select, and_
    from app.models.poi import Poi
    from app.models.store import Store

    result = await db.execute(
        _select(LockboxSlot, PickupOrder, Poi, Store)
        .outerjoin(
            PickupOrder,
            and_(
                PickupOrder.assigned_slot_id == LockboxSlot.id,
                PickupOrder.status.in_([
                    PickupStatus.CREATED,
                    PickupStatus.LOADED,
                    PickupStatus.MEET_SET,
                    PickupStatus.RETURNING,
                    PickupStatus.COMPLETED,
                ]),
            ),
        )
        # pickup_poi_id → pois.id (정방향 FK)
        .outerjoin(Poi, Poi.id == PickupOrder.pickup_poi_id)
        # pois.id → stores.poi_id (역방향: store가 있으면 매칭)
        .outerjoin(Store, Store.poi_id == Poi.id)
        .where(LockboxSlot.robot_id == robot_id)
        .order_by(LockboxSlot.slot_no)
    )
    rows = result.all()
    return [
        {
            "slot_no": slot.slot_no,
            "status": slot.status.value,
            "order_id": order.id if order else None,
            "pickup_poi_id": order.pickup_poi_id if order else None,
            "store_name": poi.name if poi else None,
        }
        for slot, order, poi, store in rows
    ]


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
            select(LockboxSlot)
            .where(
                LockboxSlot.robot_id == session.assigned_robot_id,
                LockboxSlot.status == LockboxSlotStatus.EMPTY,
            )
            .order_by(LockboxSlot.slot_no)
            .with_for_update(skip_locked=True)
            .limit(1)
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

    # 슬롯 RESERVED 상태를 모든 클라이언트에 동기화
    if session.assigned_robot_id:
        slots = await _get_lockbox_slots(db, session.assigned_robot_id)
        lockbox_payload = {"robot_id": session.assigned_robot_id, "slots": slots}
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.LOCKBOX_UPDATED, lockbox_payload)
        await manager.send_to_mobile(session_id, WsEvent.LOCKBOX_UPDATED, lockbox_payload)
        await manager.send_to_dashboard(WsEvent.LOCKBOX_UPDATED, lockbox_payload)

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
        # 물건이 락박스에 적재됨 → PICKEDUP 상태 (고객이 아직 수령 전)
        if order.assigned_slot_id:
            slot = await db.get(LockboxSlot, order.assigned_slot_id)
            if slot:
                slot.status = LockboxSlotStatus.PICKEDUP
    elif req.status == PickupStatus.COMPLETED:
        order.completed_at = datetime.utcnow()
        # Release slot
        # if order.assigned_slot_id:
        #     slot = await db.get(LockboxSlot, order.assigned_slot_id)
        #     if slot:
        #         slot.status = LockboxSlotStatus.EMPTY

    await db.flush()
    await db.refresh(order)

    session = await db.get(Session, session_id)
    data = PickupOrderResponse.model_validate(order).model_dump(mode="json")

    await manager.send_to_mobile(session_id, WsEvent.PICKUP_STATUS_CHANGED, data)
    if session and session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.PICKUP_STATUS_CHANGED, data)
    await manager.send_to_dashboard(WsEvent.PICKUP_STATUS_CHANGED, data)

    # 슬롯 상태 변경(PICKEDUP / EMPTY) 시 LOCKBOX_UPDATED 동기화
    if req.status in (PickupStatus.LOADED, PickupStatus.COMPLETED) and session and session.assigned_robot_id:
        slots = await _get_lockbox_slots(db, session.assigned_robot_id)
        lockbox_payload = {"robot_id": session.assigned_robot_id, "slots": slots}
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.LOCKBOX_UPDATED, lockbox_payload)
        await manager.send_to_mobile(session_id, WsEvent.LOCKBOX_UPDATED, lockbox_payload)
        await manager.send_to_dashboard(WsEvent.LOCKBOX_UPDATED, lockbox_payload)

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

    # meet_poi_name 추가 — Robot UI에서 meetupLocation 표시용
    if order.meet_poi_id:
        from app.models.poi import Poi as _Poi
        _poi = await db.get(_Poi, order.meet_poi_id)
        data["meet_poi_name"] = _poi.name if _poi else None
    else:
        data["meet_poi_name"] = None

    if session and session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.PICKUP_MEET_SET, data)

    return order