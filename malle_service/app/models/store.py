from sqlalchemy import BigInteger, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    poi_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pois.id"), nullable=False, unique=True
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    charger_poi_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pois.id"), nullable=True
    )

    # relationships
    poi = relationship("Poi", back_populates="store", foreign_keys=[poi_id])
    products = relationship("Product", back_populates="store")
