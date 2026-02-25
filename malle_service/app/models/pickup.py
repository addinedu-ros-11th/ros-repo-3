from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PickupStatus(str, PyEnum):
    CREATED = "CREATED"
    PAID = "PAID"
    ENROUTE = "ENROUTE"
    LOADING = "LOADING"
    LOADED = "LOADED"
    MEET_SET = "MEET_SET"
    RETURNING = "RETURNING"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class MeetType(str, PyEnum):
    POI = "POI"
    PIN = "PIN"


class PickupCreatedChannel(str, PyEnum):
    APP = "APP"
    ROBOT = "ROBOT"


class PickupOrder(Base):
    __tablename__ = "pickup_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sessions.id"), nullable=False)
    created_channel: Mapped[PickupCreatedChannel] = mapped_column(
        Enum(PickupCreatedChannel), nullable=False
    )
    pickup_poi_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pois.id"), nullable=False)
    status: Mapped[PickupStatus] = mapped_column(
        Enum(PickupStatus), nullable=False, default=PickupStatus.CREATED
    )
    assigned_slot_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("lockbox_slots.id"), nullable=True
    )
    staff_pin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    meet_type: Mapped[MeetType | None] = mapped_column(Enum(MeetType), nullable=True)
    meet_poi_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pois.id"), nullable=True
    )
    meet_x_m: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    meet_y_m: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # relationships
    session = relationship("Session", back_populates="pickup_orders")
    items = relationship("PickupOrderItem", back_populates="order")


class PickupOrderItem(Base):
    __tablename__ = "pickup_order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pickup_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pickup_orders.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    # relationships
    order = relationship("PickupOrder", back_populates="items")
