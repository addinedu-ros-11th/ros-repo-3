from pydantic import BaseModel
from typing import Optional


class RobotStatusUpdate(BaseModel):
    robot_id: str
    mode: str
    battery: int
    position_x: float
    position_y: float


class RobotCommandRequest(BaseModel):
    robot_id: str
    task_type: str
    target_x: float
    target_y: float
    task_id: str


class TaskRequest(BaseModel):
    task_type: str  # "GUIDE", "ERRAND", "BROWSE"
    target_x: float
    target_y: float
    start_poi_id: Optional[int] = None
