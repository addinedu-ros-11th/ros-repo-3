"""POI endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.poi import Poi, PoiType, PoiArrivalConfirm


class PoiResponse(BaseModel):
    id: int
    name: str
    type: PoiType
    x_m: float
    y_m: float
    wait_x_m: float | None
    wait_y_m: float | None
    arrival_confirm: PoiArrivalConfirm
    approach_x_m: float | None
    approach_y_m: float | None

    model_config = {"from_attributes": True}


router = APIRouter()


@router.get("/pois", response_model=list[PoiResponse])
async def list_pois(
    type: PoiType | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all POIs. Optional filter by type."""
    query = select(Poi).order_by(Poi.id)
    if type:
        query = query.where(Poi.type == type)
    result = await db.execute(query)
    return result.scalars().all()
