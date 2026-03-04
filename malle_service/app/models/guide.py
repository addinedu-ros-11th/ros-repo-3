from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, Integer, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GuideItemStatus(str, PyEnum):
    PENDING = "PENDING"
    ARRIVED = "ARRIVED"
    DONE = "DONE"
    SKIPPED = "SKIPPED"


class GuideQueueItem(Base):
    __tablename__ = "guide_queue_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sessions.id"), nullable=False)
    poi_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pois.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[GuideItemStatus] = mapped_column(
        Enum(GuideItemStatus), nullable=False, default=GuideItemStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # relationships
    session = relationship("Session", back_populates="guide_queue_items")
    poi = relationship("Poi", back_populates="guide_queue_items")
