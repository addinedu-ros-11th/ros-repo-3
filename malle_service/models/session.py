from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from .enums import SessionStatus, SessionType

@dataclass
class Session:
    id: str
    session_type: SessionType
    status: SessionStatus = SessionStatus.PENDING
    assigned_robot_id: Optional[str] = None
    
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # 목표 위치
    target_x: Optional[float] = None
    target_y: Optional[float] = None
    
    # POI 정보
    start_poi_id: Optional[int] = None
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)