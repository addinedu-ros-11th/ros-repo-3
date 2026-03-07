"""Zone management endpoints (dashboard).

단일 zones 테이블 기반 CRUD.
변경 발생 시 WS ZONE_UPDATED 이벤트를 모든 로봇 + 대시보드에 broadcast.

WS payload 포맷:
  {
    "type": "ZONE_UPDATED",
    "payload": {
      "action": "created" | "updated" | "deleted",
      "zone": { ...zone fields... }   # deleted 시에는 {"id": <id>}
    }
  }

로봇 zone_manager.py 의 _apply_patch() 가 이 payload 를 수신해 처리.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.zone import Zone, ZoneType, ZonePriority
from app.ws.events import WsEvent
from app.ws.manager import manager

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ZoneCreateRequest(BaseModel):
    name: str
    zone_type: ZoneType
    polygon_wkt: str                         # "POLYGON((x1 y1, x2 y2, ...))"
    is_active: bool = True
    priority: ZonePriority = ZonePriority.MEDIUM
    speed_limit_mps: float | None = None     # CAUTION / CONGESTED
    one_way: bool | None = None              # CAUTION
    enhanced_avoidance: bool | None = None   # CONGESTED


class ZoneUpdateRequest(BaseModel):
    name: str | None = None
    zone_type: ZoneType | None = None
    polygon_wkt: str | None = None
    is_active: bool | None = None
    priority: ZonePriority | None = None
    speed_limit_mps: float | None = None
    one_way: bool | None = None
    enhanced_avoidance: bool | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _zone_to_dict(zone_id: int, name: str, zone_type, polygon_wkt: str,
                  is_active: bool, priority, speed_limit_mps,
                  one_way, enhanced_avoidance) -> dict:
    return {
        "id": zone_id,
        "name": name,
        "zone_type": zone_type.value if hasattr(zone_type, "value") else zone_type,
        "polygon_wkt": polygon_wkt,
        "is_active": is_active,
        "priority": priority.value if hasattr(priority, "value") else priority,
        "speed_limit_mps": float(speed_limit_mps) if speed_limit_mps is not None else None,
        "one_way": one_way,
        "enhanced_avoidance": enhanced_avoidance,
    }


async def _broadcast_zone_event(action: str, zone_dict: dict):
    """Send ZONE_UPDATED to all robots and dashboards."""
    payload = {"action": action, "zone": zone_dict}
    # All robots
    for robot_id in list(manager.robot_connections.keys()):
        await manager.send_to_robot(robot_id, WsEvent.ZONE_UPDATED, payload)
    # All dashboards
    await manager.send_to_dashboard(WsEvent.ZONE_UPDATED, payload)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/zones")
async def list_zones(db: AsyncSession = Depends(get_db)):
    """List all zones."""
    rows = await db.execute(
        select(
            Zone.id,
            Zone.name,
            Zone.zone_type,
            func.ST_AsText(Zone.polygon).label("polygon_wkt"),
            Zone.is_active,
            Zone.priority,
            Zone.speed_limit_mps,
            Zone.one_way,
            Zone.enhanced_avoidance,
        ).order_by(Zone.id)
    )

    return [
        _zone_to_dict(
            r["id"], r["name"], r["zone_type"], r["polygon_wkt"],
            r["is_active"], r["priority"], r["speed_limit_mps"],
            r["one_way"], r["enhanced_avoidance"],
        )
        for r in rows.mappings().all()
    ]


@router.post("/zones")
async def create_zone(req: ZoneCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create a new zone and notify robots."""
    now = datetime.utcnow()

    zone = Zone(
        name=req.name,
        zone_type=req.zone_type,
        polygon=func.ST_GeomFromText(req.polygon_wkt),
        is_active=req.is_active,
        priority=req.priority,
        speed_limit_mps=req.speed_limit_mps,
        one_way=req.one_way,
        enhanced_avoidance=req.enhanced_avoidance,
        updated_at=now,
        created_at=now,
    )
    db.add(zone)
    await db.flush()

    # Re-read polygon_wkt for broadcast
    wkt_row = await db.execute(
        select(func.ST_AsText(Zone.polygon)).where(Zone.id == zone.id)
    )
    polygon_wkt = wkt_row.scalar() or req.polygon_wkt

    zone_dict = _zone_to_dict(
        zone.id, zone.name, zone.zone_type, polygon_wkt,
        zone.is_active, zone.priority, zone.speed_limit_mps,
        zone.one_way, zone.enhanced_avoidance,
    )
    await _broadcast_zone_event("created", zone_dict)

    return {"ok": True, "id": zone.id}


@router.patch("/zones/{zone_id}")
async def update_zone(zone_id: int, req: ZoneUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Update zone fields and notify robots."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    if req.name is not None:
        zone.name = req.name
    if req.zone_type is not None:
        zone.zone_type = req.zone_type
    if req.is_active is not None:
        zone.is_active = req.is_active
    if req.priority is not None:
        zone.priority = req.priority
    if req.speed_limit_mps is not None:
        zone.speed_limit_mps = req.speed_limit_mps
    if req.one_way is not None:
        zone.one_way = req.one_way
    if req.enhanced_avoidance is not None:
        zone.enhanced_avoidance = req.enhanced_avoidance
    zone.updated_at = datetime.utcnow()

    await db.flush()

    # Polygon update requires ST_GeomFromText (geometry function)
    if req.polygon_wkt is not None:
        await db.execute(
            update(Zone)
            .where(Zone.id == zone_id)
            .values(polygon=func.ST_GeomFromText(req.polygon_wkt))
        )

    # Re-read polygon_wkt for broadcast
    wkt_row = await db.execute(
        select(func.ST_AsText(Zone.polygon)).where(Zone.id == zone_id)
    )
    polygon_wkt = wkt_row.scalar() or ""

    zone_dict = _zone_to_dict(
        zone.id, zone.name, zone.zone_type, polygon_wkt,
        zone.is_active, zone.priority, zone.speed_limit_mps,
        zone.one_way, zone.enhanced_avoidance,
    )
    await _broadcast_zone_event("updated", zone_dict)

    return {"ok": True, "id": zone_id}


@router.patch("/zones/{zone_id}/toggle")
async def toggle_zone(zone_id: int, db: AsyncSession = Depends(get_db)):
    """Toggle zone active state."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    zone.is_active = not zone.is_active
    zone.updated_at = datetime.utcnow()
    await db.flush()

    wkt_row = await db.execute(
        select(func.ST_AsText(Zone.polygon)).where(Zone.id == zone_id)
    )
    polygon_wkt = wkt_row.scalar() or ""

    zone_dict = _zone_to_dict(
        zone.id, zone.name, zone.zone_type, polygon_wkt,
        zone.is_active, zone.priority, zone.speed_limit_mps,
        zone.one_way, zone.enhanced_avoidance,
    )
    await _broadcast_zone_event("updated", zone_dict)

    return {"ok": True, "id": zone_id, "is_active": zone.is_active}


@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a zone and notify robots."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    await db.delete(zone)
    await db.flush()

    await _broadcast_zone_event("deleted", {"id": zone_id})

    return {"ok": True}