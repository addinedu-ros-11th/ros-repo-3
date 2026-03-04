from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, String, DateTime, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PoiType(str, PyEnum):
    STORE = "STORE"
    FACILITY = "FACILITY"
    STATION = "STATION"
    CHARGER = "CHARGER"
    LOUNGE = "LOUNGE"
    OTHER = "OTHER"


class PoiArrivalConfirm(str, PyEnum):
    NAV2 = "NAV2"
    TAG = "TAG"


class Poi(Base):
    __tablename__ = "pois"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    type: Mapped[PoiType] = mapped_column(Enum(PoiType), nullable=False, default=PoiType.OTHER)
    x_m: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    y_m: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    wait_x_m: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    wait_y_m: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    arrival_confirm: Mapped[PoiArrivalConfirm] = mapped_column(
        Enum(PoiArrivalConfirm), nullable=False, default=PoiArrivalConfirm.NAV2
    )
    approach_x_m: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    approach_y_m: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # relationships
    store = relationship("Store", back_populates="poi", uselist=False, foreign_keys="[Store.poi_id]")
    guide_queue_items = relationship("GuideQueueItem", back_populates="poi")
