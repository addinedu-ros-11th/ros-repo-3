from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from .enums import RobotMode


@dataclass
class Robot:
    id: str
    name: str
    mode: RobotMode = RobotMode.IDLE
    battery_pct: int = 100
    position_x: float = 0.0
    position_y: float = 0.0
    is_online: bool = False
    last_seen_at: Optional[datetime] = None
    next_available_time: Optional[datetime] = None
    current_task_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
