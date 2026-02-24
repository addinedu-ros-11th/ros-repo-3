# malle_service/services/robot_dispatcher.py

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import math

from models import Robot, RobotMode, Session, SessionStatus, SessionType

class RobotDispatcherService:
    def __init__(self, battery_threshold: int = 20):
        self.robots: Dict[str, Robot] = {}
        self.sessions: Dict[str, Session] = {}
        self.battery_threshold = battery_threshold
    
    def update_robot_state(
        self,
        robot_id: str,
        mode: str,
        battery: int,
        pos_x: float,
        pos_y: float
    ):
        if robot_id not in self.robots:
            self.robots[robot_id] = Robot(
                id=robot_id,
                name=robot_id,
                mode=RobotMode[mode],
                battery_pct=battery,
                position_x=pos_x,
                position_y=pos_y,
                is_online=True,
                last_seen_at=datetime.now()
            )
        else:
            robot = self.robots[robot_id]
            robot.mode = RobotMode[mode]
            robot.battery_pct = battery
            robot.position_x = pos_x
            robot.position_y = pos_y
            robot.is_online = True
            robot.last_seen_at = datetime.now()
            robot.updated_at = datetime.now()
    
    def find_available_robots(self, request_time: datetime) -> List[str]:
        available = []
        
        for robot_id, robot in self.robots.items():
            if robot.mode in [RobotMode.CHARGING, RobotMode.EXCEPTION]:
                continue
            
            if robot.battery_pct < self.battery_threshold:
                continue
            
            if robot.mode == RobotMode.IDLE:
                available.append(robot_id)
                continue
            
            if robot.next_available_time and robot.next_available_time <= request_time:
                available.append(robot_id)
        
        return available
    
    def calculate_distance(self, robot_id: str, target_x: float, target_y: float) -> float:
        robot = self.robots[robot_id]
        return math.sqrt(
            (robot.position_x - target_x)**2 + 
            (robot.position_y - target_y)**2
        )
    
    def dispatch_task(
        self,
        session_id: str,
        task_type: str,
        target_x: float,
        target_y: float,
        request_time: Optional[datetime] = None
    ) -> Tuple[Optional[str], str]:
        if request_time is None:
            request_time = datetime.now()
        
        # 세션 생성
        session = Session(
            id=session_id,
            session_type=SessionType[task_type],
            target_x=target_x,
            target_y=target_y,
            status=SessionStatus.PENDING
        )
        self.sessions[session_id] = session
        
        # 사용 가능한 로봇 찾기
        available = self.find_available_robots(request_time)
        
        if not available:
            return None, "queued"
        
        # 가장 가까운 로봇 선택
        best_robot_id = min(
            available,
            key=lambda rid: self.calculate_distance(rid, target_x, target_y)
        )
        
        # 로봇 상태 업데이트
        robot = self.robots[best_robot_id]
        robot.mode = self._session_type_to_mode(SessionType[task_type])
        robot.current_task_id = session_id
        robot.updated_at = datetime.now()
        
        # 세션 업데이트
        session.assigned_robot_id = best_robot_id
        session.status = SessionStatus.ASSIGNED
        session.updated_at = datetime.now()
        
        return best_robot_id, "assigned"
    
    def _session_type_to_mode(self, session_type: SessionType) -> RobotMode:
        mapping = {
            SessionType.GUIDE: RobotMode.GUIDE,
            SessionType.ERRAND: RobotMode.ERRAND,
            SessionType.BROWSE: RobotMode.BROWSE,
        }
        return mapping.get(session_type, RobotMode.IDLE)
    
    def set_task_completion_time(self, robot_id: str, completion_time: datetime):
        if robot_id in self.robots:
            self.robots[robot_id].next_available_time = completion_time
            self.robots[robot_id].updated_at = datetime.now()
    
    def get_status(self) -> dict:
        return {
            "robots": {
                rid: {
                    "name": r.name,
                    "mode": r.mode.value,
                    "battery": r.battery_pct,
                    "position": {"x": r.position_x, "y": r.position_y},
                    "is_online": r.is_online,
                    "last_seen": r.last_seen_at.isoformat() if r.last_seen_at else None,
                    "available_at": r.next_available_time.isoformat() 
                        if r.next_available_time else None,
                    "current_task": r.current_task_id
                }
                for rid, r in self.robots.items()
            },
            "sessions": {
                sid: {
                    "type": s.session_type.value,
                    "status": s.status.value,
                    "assigned_robot": s.assigned_robot_id,
                    "target": {"x": s.target_x, "y": s.target_y} if s.target_x else None,
                    "started_at": s.started_at.isoformat()
                }
                for sid, s in self.sessions.items()
            },
            "total_robots": len(self.robots),
            "available_robots": len([r for r in self.robots.values() if r.mode == RobotMode.IDLE])
        }