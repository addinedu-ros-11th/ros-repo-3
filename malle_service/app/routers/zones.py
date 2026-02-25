"""Zone management endpoints (dashboard)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.zone import RestrictedZone, NavRuleZone, NavRuleType

router = APIRouter()


class ZoneCreateRequest(BaseModel):
    name: str
    polygon_wkt: str
    zone_kind: str = "restricted"  # "restricted" or "nav_rule"
    is_active: bool = True
    rule_type: NavRuleType | None = None
    speed_limit_mps: float | None = None
    corner_stop_ms: int | None = None


class ZoneUpdateRequest(BaseModel):
    name: str | None = None
    polygon_wkt: str | None = None
    is_active: bool | None = None
    speed_limit_mps: float | None = None
    corner_stop_ms: int | None = None


class ZoneResponse(BaseModel):
    id: int
    name: str
    polygon_wkt: str
    is_active: bool
    zone_kind: str = "restricted"

    model_config = {"from_attributes": True}


@router.get("/zones")
async def list_zones(db: AsyncSession = Depends(get_db)):
    """List all zones (restricted + nav_rule)."""
    restricted = await db.execute(select(RestrictedZone).order_by(RestrictedZone.id))
    nav_rules = await db.execute(select(NavRuleZone).order_by(NavRuleZone.id))

    result = []
    for z in restricted.scalars().all():
        result.append({
            "id": z.id, "name": z.name, "polygon_wkt": z.polygon_wkt,
            "is_active": z.is_active, "zone_kind": "restricted",
        })
    for z in nav_rules.scalars().all():
        result.append({
            "id": z.id, "name": z.name, "polygon_wkt": z.polygon_wkt,
            "is_active": z.is_active, "zone_kind": "nav_rule",
            "rule_type": z.rule_type.value, "speed_limit_mps": float(z.speed_limit_mps) if z.speed_limit_mps else None,
        })

    return result


@router.post("/zones")
async def create_zone(req: ZoneCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create a new zone."""
    now = datetime.utcnow()

    if req.zone_kind == "nav_rule":
        if not req.rule_type:
            raise HTTPException(status_code=400, detail="rule_type required for nav_rule zones")
        zone = NavRuleZone(
            name=req.name, polygon_wkt=req.polygon_wkt, is_active=req.is_active,
            rule_type=req.rule_type, speed_limit_mps=req.speed_limit_mps,
            corner_stop_ms=req.corner_stop_ms, updated_at=now,
        )
    else:
        zone = RestrictedZone(
            name=req.name, polygon_wkt=req.polygon_wkt,
            is_active=req.is_active, updated_at=now,
        )

    db.add(zone)
    await db.flush()
    await db.refresh(zone)

    return {"ok": True, "id": zone.id, "zone_kind": req.zone_kind}


@router.patch("/zones/{zone_id}")
async def update_zone(zone_id: int, req: ZoneUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Update zone."""
    zone = await db.get(RestrictedZone, zone_id)
    if not zone:
        zone = await db.get(NavRuleZone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    if req.name is not None:
        zone.name = req.name
    if req.polygon_wkt is not None:
        zone.polygon_wkt = req.polygon_wkt
    if req.is_active is not None:
        zone.is_active = req.is_active
    zone.updated_at = datetime.utcnow()

    if isinstance(zone, NavRuleZone):
        if req.speed_limit_mps is not None:
            zone.speed_limit_mps = req.speed_limit_mps
        if req.corner_stop_ms is not None:
            zone.corner_stop_ms = req.corner_stop_ms

    await db.flush()
    return {"ok": True, "id": zone_id}


@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a zone."""
    zone = await db.get(RestrictedZone, zone_id)
    if zone:
        await db.delete(zone)
        await db.flush()
        return {"ok": True}

    zone = await db.get(NavRuleZone, zone_id)
    if zone:
        await db.delete(zone)
        await db.flush()
        return {"ok": True}

    raise HTTPException(status_code=404, detail="Zone not found")
