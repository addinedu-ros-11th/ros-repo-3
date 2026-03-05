from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, String, Integer, Boolean, DateTime, Enum, Numeric, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NavRuleType(str, PyEnum):
    NARROW_CORRIDOR = "NARROW_CORRIDOR"
    NARROW_CORNER = "NARROW_CORNER"


class RestrictedZone(Base):
    __tablename__ = "restricted_zones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    polygon: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    srid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_source: Mapped[str] = mapped_column(String(30), nullable=False, default="dashboard")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class NavRuleZone(Base):
    __tablename__ = "nav_rule_zones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    polygon: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    srid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rule_type: Mapped[NavRuleType] = mapped_column(Enum(NavRuleType), nullable=False)
    speed_limit_mps: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    corner_stop_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by_source: Mapped[str] = mapped_column(String(30), nullable=False, default="dashboard")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
