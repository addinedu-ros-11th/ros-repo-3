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
from app.utils.bridge import send_to_bridge

router = APIRouter()


async def _get_lockbox_slots(db: AsyncSession, robot_id: int) -> list[dict]:
    """락박스 슬롯 목록 조회 (LOCKBOX_UPDATED 브로드캐스트용).

    각 슬롯당 활성 주문 1개만 매핑 (1:N 중복 방지).
    활성 주문 기준: CREATED / LOADED / MEET_SET / RETURNING / COMPLETED
    """
    from sqlalchemy import select as _select
    from app.models.poi import Poi
    from app.models.store import Store

    # 슬롯 목록 조회
    slot_result = await db.execute(
        _select(LockboxSlot)
        .where(LockboxSlot.robot_id == robot_id)
        .order_by(LockboxSlot.slot_no)
    )
    slots = slot_result.scalars().all()

    # 활성 주문: 슬롯 id → 주문 1개 (가장 최근)
    order_result = await db.execute(
        _select(PickupOrder)
        .where(
            PickupOrder.assigned_slot_id.in_([s.id for s in slots]),
            PickupOrder.status.in_([
                PickupStatus.CREATED,
                PickupStatus.LOADED,
                PickupStatus.MEET_SET,
                PickupStatus.RETURNING,
                PickupStatus.COMPLETED,
            ]),
        )
        .order_by(PickupOrder.id.desc())
    )
    orders = order_result.scalars().all()

    # slot_id → 첫 번째 (최신) 주문만 매핑
    slot_order_map: dict[int, PickupOrder] = {}
    for o in orders:
        if o.assigned_slot_id not in slot_order_map:
            slot_order_map[o.assigned_slot_id] = o

    # poi_id → poi name 조회
    poi_ids = {o.pickup_poi_id for o in slot_order_map.values() if o.pickup_poi_id}
    poi_map: dict[int, str] = {}
    if poi_ids:
        poi_result = await db.execute(
            _select(Poi).where(Poi.id.in_(poi_ids))
        )
        for poi in poi_result.scalars().all():
            poi_map[poi.id] = poi.name

    return [
        {
            "slot_no": slot.slot_no,
            "status": slot.status.value,
            "order_id": slot_order_map[slot.id].id if slot.id in slot_order_map else None,
            "pickup_poi_id": slot_order_map[slot.id].pickup_poi_id if slot.id in slot_order_map else None,
            "store_name": poi_map.get(slot_order_map[slot.id].pickup_poi_id) if slot.id in slot_order_map else None,
        }
        for slot in slots
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

    # bridge → mission_errand.py 트리거 (store_poi_id 전달)
    if session.assigned_robot_id:
        await send_to_bridge("errand/start", {
            "session_id": session_id,
            "order_id": order.id,
            "store_poi_id": req.pickup_poi_id,
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
        # 적재 완료 → slot PICKEDUP (고객 수령 대기)
        if order.assigned_slot_id:
            slot = await db.get(LockboxSlot, order.assigned_slot_id)
            if slot:
                slot.status = LockboxSlotStatus.PICKEDUP

    elif req.status == PickupStatus.COMPLETED:
        order.completed_at = datetime.utcnow()
        # slot 상태는 건드리지 않음 — 고객이 박스 열고 꺼낼 때까지 PICKEDUP 유지

    await db.flush()
    await db.refresh(order)

    session = await db.get(Session, session_id)
    data = PickupOrderResponse.model_validate(order).model_dump(mode="json")

    await manager.send_to_mobile(session_id, WsEvent.PICKUP_STATUS_CHANGED, data)
    if session and session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.PICKUP_STATUS_CHANGED, data)
    await manager.send_to_dashboard(WsEvent.PICKUP_STATUS_CHANGED, data)

    # LOADED 시만 LOCKBOX_UPDATED 발행 (COMPLETED는 slot 변경 없음)
    if req.status == PickupStatus.LOADED and session and session.assigned_robot_id:
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

    if order.meet_poi_id:
        from app.models.poi import Poi as _Poi
        _poi = await db.get(_Poi, order.meet_poi_id)
        data["meet_poi_name"] = _poi.name if _poi else None
    else:
        data["meet_poi_name"] = None

    if session and session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.PICKUP_MEET_SET, data)

    # meetup 위치 확정 → bridge에 meetup poi 좌표로 이동 명령
    if session and session.assigned_robot_id:
        await send_to_bridge("errand/meetup", {
            "session_id": session_id,
            "order_id": order.id,
            "meet_poi_id": order.meet_poi_id,
            "meet_x_m": order.meet_x_m,
            "meet_y_m": order.meet_y_m,
        })

    return order