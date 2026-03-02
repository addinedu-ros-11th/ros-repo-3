"""쇼핑 리스트 최단경로 최적화 (Nearest Neighbor TSP)."""

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shopping import ShoppingListItem
from app.models.store import Store
from app.models.poi import Poi


def _nearest_neighbor(
    start_x: float,
    start_y: float,
    nodes: list[dict],
) -> list[dict]:
    """
    Nearest Neighbor TSP 휴리스틱.

    현재 위치에서 가장 가까운 미방문 노드를 순서대로 선택.
    시간복잡도: O(n²) — 쇼핑몰 규모(< 50개 매장)에 충분.
    """
    unvisited = list(nodes)
    path: list[dict] = []
    cx, cy = start_x, start_y

    while unvisited:
        nearest = min(unvisited, key=lambda n: math.hypot(n["x"] - cx, n["y"] - cy))
        path.append(nearest)
        cx, cy = nearest["x"], nearest["y"]
        unvisited.remove(nearest)

    return path


async def optimize_route_by_stores(
    db: AsyncSession,
    store_ids: list[int],
    start_x: float,
    start_y: float,
) -> list[dict]:
    """
    store_ids 리스트를 직접 받아 최단경로 순서 반환.
    (클라이언트가 list_id 없이 호출할 때 사용)
    """
    if not store_ids:
        return []

    result = await db.execute(
        select(Store, Poi)
        .join(Poi, Store.poi_id == Poi.id)
        .where(Store.id.in_(store_ids))
    )
    nodes = [
        {
            "store_id": store.id,
            "poi_id": poi.id,
            "poi_name": poi.name,
            "x": float(poi.x_m),
            "y": float(poi.y_m),
        }
        for store, poi in result.all()
    ]

    return _nearest_neighbor(start_x, start_y, nodes)


async def optimize_shopping_route(
    db: AsyncSession,
    list_id: int,
    start_x: float,
    start_y: float,
) -> list[dict]:
    """
    쇼핑 리스트의 TODO 아이템을 최단거리 순서로 정렬한 스토어 POI 목록 반환.

    - 같은 스토어의 여러 아이템은 한 번만 방문 (deduplicate)
    - 반환값: [{ store_id, poi_id, poi_name, x, y }, ...]  (방문 순서대로)
    """
    # TODO 아이템의 고유 store_id 수집
    result = await db.execute(
        select(ShoppingListItem.store_id)
        .where(
            ShoppingListItem.list_id == list_id,
            ShoppingListItem.status == "TODO",
        )
        .distinct()
    )
    store_ids = [row[0] for row in result.all()]

    if not store_ids:
        return []

    # store_id → poi 좌표 조회
    result = await db.execute(
        select(Store, Poi)
        .join(Poi, Store.poi_id == Poi.id)
        .where(Store.id.in_(store_ids))
    )
    nodes = [
        {
            "store_id": store.id,
            "poi_id": poi.id,
            "poi_name": poi.name,
            "x": float(poi.x_m),
            "y": float(poi.y_m),
        }
        for store, poi in result.all()
    ]

    return _nearest_neighbor(start_x, start_y, nodes)
