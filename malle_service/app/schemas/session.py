"""Session request/response schemas."""

from datetime import datetime
from pydantic import BaseModel

from app.models.session import SessionType, SessionStatus


# --- Request ---

class SessionCreateRequest(BaseModel):
    user_id: int
    session_type: SessionType
    requested_minutes: int | None = None  # TIME only


class SessionStatusUpdateRequest(BaseModel):
    status: SessionStatus


class PinVerifyRequest(BaseModel):
    pin: str


class FollowTagRequest(BaseModel):
    tag_code: int
    tag_family: str = "tag36h11"


# --- Response ---

class SessionResponse(BaseModel):
    id: int
    user_id: int
    session_type: SessionType
    requested_minutes: int | None
    status: SessionStatus
    assigned_robot_id: int | None
    match_pin: str | None
    pin_expires_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    follow_tag_code: int | None
    follow_tag_family: str | None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


class SessionAssignedPayload(SessionResponse):
    """SESSION_ASSIGNED WS 이벤트 payload — SessionResponse + 로봇/고객 부가 정보."""
    robot_name: str | None = None
    battery_pct: int | None = None
    x_m: float | None = None
    y_m: float | None = None
    customer_phone_masked: str | None = None
    eta_sec: int | None = None