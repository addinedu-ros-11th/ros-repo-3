from datetime import datetime

from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stores.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # relationships
    store = relationship("Store", back_populates="products")


class InventoryCurrent(Base):
    __tablename__ = "inventory_current"

    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), primary_key=True
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
