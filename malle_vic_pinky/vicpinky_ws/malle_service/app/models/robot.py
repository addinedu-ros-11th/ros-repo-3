from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, String, Boolean, Integer, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class RobotMode(str, PyEnum):
    IDLE = "IDLE"
    GUIDE = "GUIDE"
    FOLLOW = "FOLLOW"
    PICKUP = "PICKUP"


class RobotMotionState(str, PyEnum):
    MOVING = "MOVING"
    WAITING = "WAITING"
    STOPPED = "STOPPED"


class RobotNavState(str, PyEnum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    MOVING = "MOVING"
    REPLANNING = "REPLANNING"
    BLOCKED = "BLOCKED"
    ARRIVED = "ARRIVED"
    RECOVERY = "RECOVERY"
    TELEOP = "TELEOP"


class RobotStopState(str, PyEnum):
    NONE = "NONE"
    ESTOP = "ESTOP"
    AUTO_STOP = "AUTO_STOP"


class EStopSource(str, PyEnum):
    ROBOT = "ROBOT"
    DASHBOARD = "DASHBOARD"


class Robot(Base):
    __tablename__ = "robots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    model: Mapped[str] = mapped_column(String(30), nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    battery_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    current_mode: Mapped[RobotMode] = mapped_column(
        Enum(RobotMode), nullable=False, default=RobotMode.IDLE
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    home_poi_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pois.id"), nullable=True
    )

    # relationships
    state = relationship("RobotStateCurrent", back_populates="robot", uselist=False)
    sessions = relationship("Session", back_populates="assigned_robot")
    missions = relationship("Mission", back_populates="robot")
    lockbox_slots = relationship("LockboxSlot", back_populates="robot")
    events = relationship("RobotEvent", back_populates="robot")


class RobotStateCurrent(Base):
    __tablename__ = "robot_state_current"

    robot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("robots.id"), primary_key=True
    )
    x_m: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False, default=0)
    y_m: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False, default=0)
    theta_rad: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False, default=0)
    motion_state: Mapped[RobotMotionState] = mapped_column(
        Enum(RobotMotionState), nullable=False, default=RobotMotionState.STOPPED
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # E-Stop
    stop_state: Mapped[RobotStopState] = mapped_column(
        Enum(RobotStopState), nullable=False, default=RobotStopState.NONE
    )
    stop_source: Mapped[EStopSource | None] = mapped_column(Enum(EStopSource), nullable=True)
    stop_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Navigation context
    target_poi_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pois.id"), nullable=True
    )
    nav_state: Mapped[RobotNavState] = mapped_column(
        Enum(RobotNavState), nullable=False, default=RobotNavState.IDLE
    )
    remaining_distance_m: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False, default=0)
    eta_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    speed_mps: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False, default=0)

    # relationships
    robot = relationship("Robot", back_populates="state")
