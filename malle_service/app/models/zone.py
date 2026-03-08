"""Zone model — unified single table replacing restricted_zones + nav_rule_zones."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, String, Boolean, DateTime, Enum, Numeric, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ZoneType(str, PyEnum):
    RESTRICTED = "RESTRICTED"
    MAINTENANCE = "MAINTENANCE"
    CAUTION = "CAUTION"
    CONGESTED = "CONGESTED"


class ZonePriority(str, PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    zone_type: Mapped[ZoneType] = mapped_column(Enum(ZoneType), nullable=False)

    # MySQL POLYGON stored as raw bytes (SRID 0 local coordinate)
    # Always write via ST_GeomFromText(), read via ST_AsText()
    polygon: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[ZonePriority] = mapped_column(
        Enum(ZonePriority), nullable=False, default=ZonePriority.MEDIUM
    )

    # CAUTION / CONGESTED
    speed_limit_mps: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)

    # CAUTION only
    one_way: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)

    # CONGESTED only
    enhanced_avoidance: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)

    updated_by_source: Mapped[str] = mapped_column(String(30), nullable=False, default="dashboard")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)