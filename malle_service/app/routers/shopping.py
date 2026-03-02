"""Shopping list endpoints (mobile only)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.guide import GuideQueueItem, GuideItemStatus
from app.models.poi import Poi
from app.models.robot import RobotStateCurrent
from app.models.session import Session
from app.models.shopping import ShoppingList, ShoppingListItem
from app.services.route_optimizer import optimize_shopping_route, optimize_route_by_stores
from app.ws.events import WsEvent
from app.ws.manager import manager

router = APIRouter()


class ShoppingListCreateRequest(BaseModel):
    name: str


class ShoppingItemAddRequest(BaseModel):
    store_id: int
    product_id: int
    qty: int = 1
    unit_price: float = 0


class ShoppingListResponse(BaseModel):
    id: int
    user_id: int
    name: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ShoppingItemResponse(BaseModel):
    id: int
    list_id: int
    store_id: int
    product_id: int
    qty: int
    unit_price: float
    status: str

    model_config = {"from_attributes": True}


@router.get("/users/{user_id}/shopping-lists", response_model=list[ShoppingListResponse])
async def get_user_shopping_lists(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ShoppingList).where(ShoppingList.user_id == user_id).order_by(ShoppingList.created_at.desc())
    )
    return result.scalars().all()


@router.post("/users/{user_id}/shopping-lists", response_model=ShoppingListResponse)
async def create_shopping_list(user_id: int, req: ShoppingListCreateRequest, db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    sl = ShoppingList(user_id=user_id, name=req.name, created_at=now, updated_at=now)
    db.add(sl)
    await db.flush()
    await db.refresh(sl)
    return sl


@router.post("/shopping-lists/{list_id}/items", response_model=ShoppingItemResponse)
async def add_shopping_item(list_id: int, req: ShoppingItemAddRequest, db: AsyncSession = Depends(get_db)):
    sl = await db.get(ShoppingList, list_id)
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    now = datetime.utcnow()
    item = ShoppingListItem(
        list_id=list_id, store_id=req.store_id, product_id=req.product_id,
        qty=req.qty, unit_price=req.unit_price, created_at=now, updated_at=now,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.patch("/shopping-lists/{list_id}/items/{item_id}", response_model=ShoppingItemResponse)
async def toggle_shopping_item(list_id: int, item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(ShoppingListItem, item_id)
    if not item or item.list_id != list_id:
        raise HTTPException(status_code=404, detail="Item not found")

    item.status = "DONE" if item.status == "TODO" else "TODO"
    item.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(item)
    return item


class OptimizeRouteRequest(BaseModel):
    robot_id: int | None = None   # 로봇 현재 위치를 출발점으로 사용
    start_x: float = 0.0          # robot_id 없을 때 사용할 출발 좌표
    start_y: float = 0.0
    session_id: int | None = None  # 제공 시 가이드 큐 자동 populate


class OptimizedPoiResponse(BaseModel):
    order: int
    store_id: int
    poi_id: int
    poi_name: str
    x: float
    y: float
    queue_item_id: int | None = None  # session_id 제공 시 생성된 큐 아이템 ID


@router.post(
    "/shopping-lists/{list_id}/optimize-route",
    response_model=list[OptimizedPoiResponse],
)
async def optimize_route(
    list_id: int,
    req: OptimizeRouteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    쇼핑 리스트의 TODO 아이템을 최단거리 순으로 정렬해 방문 순서를 반환.

    - robot_id를 주면 로봇 현재 위치를 출발점으로 사용
    - robot_id가 없으면 (start_x, start_y)를 출발점으로 사용
    - 같은 스토어의 아이템은 한 번의 방문으로 합산
    - session_id를 주면 최적화 순서대로 가이드 큐 자동 populate
    """
    sl = await db.get(ShoppingList, list_id)
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    start_x, start_y = req.start_x, req.start_y
    if req.robot_id is not None:
        robot_state = await db.get(RobotStateCurrent, req.robot_id)
        if robot_state:
            start_x = float(robot_state.x_m)
            start_y = float(robot_state.y_m)

    ordered = await optimize_shopping_route(db, list_id, start_x, start_y)

    # session_id 없으면 순서 반환만
    if req.session_id is None:
        return [OptimizedPoiResponse(order=i + 1, **poi) for i, poi in enumerate(ordered)]

    # session_id 있으면 가이드 큐 자동 populate
    session = await db.get(Session, req.session_id, with_for_update=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 현재 max seq 조회
    max_seq_result = await db.execute(
        select(func.coalesce(func.max(GuideQueueItem.seq), 0))
        .where(
            GuideQueueItem.session_id == req.session_id,
            GuideQueueItem.is_active == True,
        )
    )
    next_seq = max_seq_result.scalar() + 1

    # 최적화 순서대로 큐 아이템 생성
    result = []
    for i, poi in enumerate(ordered):
        item = GuideQueueItem(
            session_id=req.session_id,
            poi_id=poi["poi_id"],
            seq=next_seq + i,
            status=GuideItemStatus.PENDING,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        result.append(OptimizedPoiResponse(order=i + 1, queue_item_id=item.id, **poi))

    # WS broadcast (한 번만)
    queue_items = await db.execute(
        select(GuideQueueItem, Poi.name)
        .join(Poi, GuideQueueItem.poi_id == Poi.id)
        .where(GuideQueueItem.session_id == req.session_id, GuideQueueItem.is_active == True)
        .order_by(GuideQueueItem.seq)
    )
    queue = [
        {"id": item.id, "poi_id": item.poi_id, "poi_name": name, "seq": item.seq, "status": item.status}
        for item, name in queue_items.all()
    ]
    await manager.send_to_mobile(req.session_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": queue})
    if session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": queue})
    await manager.send_to_dashboard(WsEvent.MISSION_UPDATED, {"session_id": req.session_id, "queue": queue})

    return result


class OptimizeByStoresRequest(BaseModel):
    store_ids: list[int]
    robot_id: int | None = None
    start_x: float = 0.0
    start_y: float = 0.0
    session_id: int | None = None


@router.post("/shopping/optimize-route", response_model=list[OptimizedPoiResponse])
async def optimize_route_by_store_ids(
    req: OptimizeByStoresRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    store_ids를 직접 받아 최단경로 순서 반환.
    클라이언트 로컬 쇼핑 리스트용 (list_id 불필요).

    - robot_id를 주면 로봇 현재 위치를 출발점으로 사용
    - session_id를 주면 최적화 순서대로 가이드 큐 자동 populate
    """
    if not req.store_ids:
        return []

    start_x, start_y = req.start_x, req.start_y
    if req.robot_id is not None:
        robot_state = await db.get(RobotStateCurrent, req.robot_id)
        if robot_state:
            start_x = float(robot_state.x_m)
            start_y = float(robot_state.y_m)

    ordered = await optimize_route_by_stores(db, req.store_ids, start_x, start_y)

    if req.session_id is None:
        return [OptimizedPoiResponse(order=i + 1, **poi) for i, poi in enumerate(ordered)]

    # session_id 있으면 가이드 큐 자동 populate
    session = await db.get(Session, req.session_id, with_for_update=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    max_seq_result = await db.execute(
        select(func.coalesce(func.max(GuideQueueItem.seq), 0))
        .where(
            GuideQueueItem.session_id == req.session_id,
            GuideQueueItem.is_active == True,
        )
    )
    next_seq = max_seq_result.scalar() + 1

    result = []
    for i, poi in enumerate(ordered):
        item = GuideQueueItem(
            session_id=req.session_id,
            poi_id=poi["poi_id"],
            seq=next_seq + i,
            status=GuideItemStatus.PENDING,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        result.append(OptimizedPoiResponse(order=i + 1, queue_item_id=item.id, **poi))

    queue_items = await db.execute(
        select(GuideQueueItem, Poi.name)
        .join(Poi, GuideQueueItem.poi_id == Poi.id)
        .where(GuideQueueItem.session_id == req.session_id, GuideQueueItem.is_active == True)
        .order_by(GuideQueueItem.seq)
    )
    queue = [
        {"id": item.id, "poi_id": item.poi_id, "poi_name": name, "seq": item.seq, "status": item.status}
        for item, name in queue_items.all()
    ]
    await manager.send_to_mobile(req.session_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": queue})
    if session.assigned_robot_id:
        await manager.send_to_robot(session.assigned_robot_id, WsEvent.GUIDE_QUEUE_UPDATED, {"queue": queue})
    await manager.send_to_dashboard(WsEvent.MISSION_UPDATED, {"session_id": req.session_id, "queue": queue})

    return result


@router.delete("/shopping-lists/{list_id}/items/{item_id}")
async def remove_shopping_item(list_id: int, item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(ShoppingListItem, item_id)
    if not item or item.list_id != list_id:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)
    await db.flush()
    return {"ok": True}
