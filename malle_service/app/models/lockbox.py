from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LockboxSlotStatus(str, PyEnum):
    EMPTY = "EMPTY"
    FULL = "FULL"
    RESERVED = "RESERVED"
    PICKEDUP = "PICKEDUP"


class LockboxActor(str, PyEnum):
    CUSTOMER = "customer"
    STAFF = "staff"
    ROBOT = "robot"


class LockboxOpenResult(str, PyEnum):
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


class LockboxSlot(Base):
    __tablename__ = "lockbox_slots"
    __table_args__ = (UniqueConstraint("robot_id", "slot_no"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    robot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("robots.id"), nullable=False)
    slot_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[LockboxSlotStatus] = mapped_column(
        Enum(LockboxSlotStatus), nullable=False, default=LockboxSlotStatus.EMPTY
    )
    size_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # relationships
    robot = relationship("Robot", back_populates="lockbox_slots")
    assignments = relationship("LockboxAssignment", back_populates="slot")
    open_logs = relationship("LockboxOpenLog", back_populates="slot")


class LockboxAssignment(Base):
    __tablename__ = "lockbox_assignments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("lockbox_slots.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # SESSION_STORAGE / PICKUP
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sessions.id"), nullable=True
    )
    pickup_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pickup_orders.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # relationships
    slot = relationship("LockboxSlot", back_populates="assignments")


class LockboxToken(Base):
    __tablename__ = "lockbox_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sessions.id"), nullable=False)
    slot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("lockbox_slots.id"), nullable=True
    )
    token: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LockboxOpenLog(Base):
    __tablename__ = "lockbox_open_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    robot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("robots.id"), nullable=False)
    slot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("lockbox_slots.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sessions.id"), nullable=True
    )
    pickup_order_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pickup_orders.id"), nullable=True
    )
    actor: Mapped[LockboxActor] = mapped_column(Enum(LockboxActor), nullable=False)
    result: Mapped[LockboxOpenResult] = mapped_column(Enum(LockboxOpenResult), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # relationships
    slot = relationship("LockboxSlot", back_populates="open_logs")
