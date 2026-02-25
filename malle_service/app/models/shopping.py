from datetime import datetime

from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # relationships
    user = relationship("User", back_populates="shopping_lists")
    items = relationship("ShoppingListItem", back_populates="shopping_list")


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    list_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shopping_lists.id"), nullable=False
    )
    store_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stores.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="TODO")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # relationships
    shopping_list = relationship("ShoppingList", back_populates="items")
