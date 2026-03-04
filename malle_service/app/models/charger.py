from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChargerStatus(str, PyEnum):
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"


class ChargerCurrent(Base):
    __tablename__ = "charger_current"

    charger_poi_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pois.id"), primary_key=True
    )
    status: Mapped[ChargerStatus] = mapped_column(
        Enum(ChargerStatus), nullable=False, default=ChargerStatus.FREE
    )
    robot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("robots.id"), nullable=True
    )
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sessions.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
