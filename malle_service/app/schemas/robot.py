"""Robot request/response schemas."""

from datetime import datetime
from pydantic import BaseModel

from app.models.robot import (
    RobotMode, RobotMotionState, RobotNavState, RobotStopState, EStopSource,
)


# --- Request ---

class RobotStateUpdateRequest(BaseModel):
    """Called by ROS2 to update robot position/state."""
    x_m: float | None = None
    y_m: float | None = None
    theta_rad: float | None = None
    motion_state: RobotMotionState | None = None
    nav_state: RobotNavState | None = None
    target_poi_id: int | None = None
    remaining_distance_m: float | None = None
    eta_sec: int | None = None
    speed_mps: float | None = None
    battery_pct: int | None = None
    bridge_url: str | None = None  # bridge_node 자신의 HTTP URL (자동 등록용)


class RobotCommandRequest(BaseModel):
    """Dashboard command: go_maintenance, return_station, etc."""
    command: str  # go_maintenance | return_station


class EStopRequest(BaseModel):
    source: EStopSource = EStopSource.DASHBOARD


# --- Response ---

class RobotStateResponse(BaseModel):
    x_m: float
    y_m: float
    theta_rad: float
    motion_state: RobotMotionState
    stop_state: RobotStopState
    stop_source: EStopSource | None
    nav_state: RobotNavState
    target_poi_id: int | None
    remaining_distance_m: float
    eta_sec: int
    speed_mps: float
    updated_at: datetime

    model_config = {"from_attributes": True}


class RobotResponse(BaseModel):
    id: int
    name: str
    model: str
    is_online: bool
    battery_pct: int
    current_mode: RobotMode
    last_seen_at: datetime | None
    home_poi_id: int | None
    state: RobotStateResponse | None

    model_config = {"from_attributes": True}


class RobotListResponse(BaseModel):
    robots: list[RobotResponse]
