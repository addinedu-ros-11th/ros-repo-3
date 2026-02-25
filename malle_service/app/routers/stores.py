"""Store endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.store import Store
from app.models.product import Product
from app.models.poi import Poi


class StoreResponse(BaseModel):
    id: int
    poi_id: int
    category: str | None
    charger_poi_id: int | None
    # joined from poi
    name: str | None = None
    x_m: float | None = None
    y_m: float | None = None

    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    id: int
    store_id: int
    name: str
    price: float
    sku: str | None

    model_config = {"from_attributes": True}


router = APIRouter()


@router.get("/stores", response_model=list[StoreResponse])
async def list_stores(db: AsyncSession = Depends(get_db)):
    """List all stores with POI info."""
    result = await db.execute(
        select(Store).options(selectinload(Store.poi)).order_by(Store.id)
    )
    stores = result.scalars().all()

    response = []
    for s in stores:
        data = StoreResponse.model_validate(s)
        if s.poi:
            data.name = s.poi.name
            data.x_m = float(s.poi.x_m)
            data.y_m = float(s.poi.y_m)
        response.append(data)

    return response


@router.get("/stores/{store_id}/products", response_model=list[ProductResponse])
async def list_store_products(store_id: int, db: AsyncSession = Depends(get_db)):
    """List products for a store."""
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    result = await db.execute(
        select(Product).where(Product.store_id == store_id).order_by(Product.id)
    )
    return result.scalars().all()
