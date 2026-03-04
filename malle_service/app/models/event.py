from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EventType(str, PyEnum):
    COLLISION_RISK = "COLLISION_RISK"
    PATH_DEVIATION = "PATH_DEVIATION"
    LOW_BATTERY = "LOW_BATTERY"
    SENSOR_FAULT = "SENSOR_FAULT"
    COMMS_LOSS = "COMMS_LOSS"
    ESTOP = "ESTOP"


class EventSeverity(str, PyEnum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class RobotEvent(Base):
    __tablename__ = "robot_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    robot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("robots.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sessions.id"), nullable=True
    )
    type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    severity: Mapped[EventSeverity] = mapped_column(
        Enum(EventSeverity), nullable=False, default=EventSeverity.INFO
    )
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # relationships
    robot = relationship("Robot", back_populates="events")
