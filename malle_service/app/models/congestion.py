from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CongestionLevel(str, PyEnum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"


class CongestionCurrent(Base):
    __tablename__ = "congestion_current"

    poi_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pois.id"), primary_key=True)
    level: Mapped[CongestionLevel] = mapped_column(
        Enum(CongestionLevel), nullable=False, default=CongestionLevel.LOW
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
