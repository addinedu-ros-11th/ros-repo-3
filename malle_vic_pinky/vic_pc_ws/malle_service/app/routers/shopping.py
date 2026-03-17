"""Shopping list endpoints (mobile only)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.shopping import ShoppingList, ShoppingListItem

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


@router.delete("/shopping-lists/{list_id}/items/{item_id}")
async def remove_shopping_item(list_id: int, item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(ShoppingListItem, item_id)
    if not item or item.list_id != list_id:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)
    await db.flush()
    return {"ok": True}
