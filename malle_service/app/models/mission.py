from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MissionType(str, PyEnum):
    GUIDE = "GUIDE"
    FOLLOW = "FOLLOW"
    PICKUP = "PICKUP"


class MissionStatus(str, PyEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELED = "CANCELED"
    COMPLETED = "COMPLETED"


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sessions.id"), nullable=False)
    robot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("robots.id"), nullable=False)
    type: Mapped[MissionType] = mapped_column(Enum(MissionType), nullable=False)
    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus), nullable=False, default=MissionStatus.QUEUED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # relationships
    session = relationship("Session", back_populates="missions")
    robot = relationship("Robot", back_populates="missions")
