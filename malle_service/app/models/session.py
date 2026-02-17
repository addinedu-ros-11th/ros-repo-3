from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SessionType(str, PyEnum):
    TASK = "TASK"
    TIME = "TIME"


class SessionStatus(str, PyEnum):
    REQUESTED = "REQUESTED"
    ASSIGNED = "ASSIGNED"
    APPROACHING = "APPROACHING"
    MATCHING = "MATCHING"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    session_type: Mapped[SessionType] = mapped_column(Enum(SessionType), nullable=False)
    requested_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.REQUESTED
    )
    assigned_robot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("robots.id"), nullable=True
    )
    match_pin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pin_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Follow (AprilTag)
    follow_tag_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follow_tag_family: Mapped[str | None] = mapped_column(String(20), nullable=True, default="tag36h11")
    follow_tag_set_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # relationships
    user = relationship("User", back_populates="sessions")
    assigned_robot = relationship("Robot", back_populates="sessions")
    missions = relationship("Mission", back_populates="session")
    guide_queue_items = relationship("GuideQueueItem", back_populates="session")
    pickup_orders = relationship("PickupOrder", back_populates="session")
