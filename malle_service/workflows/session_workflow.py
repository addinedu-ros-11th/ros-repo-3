# malle_service/workflows/session_workflow.py

from sqlalchemy.orm import Session as DBSession
from datetime import datetime

from models import Session
from services.robot_dispatcher import RobotDispatcherService
from services.time_estimator import TimeEstimatorService
from config import Config

class SessionWorkflow:
    
    def __init__(self, config: Config):
        self.dispatcher = RobotDispatcherService(config)
        self.estimator = TimeEstimatorService(config)
    
    def create_and_assign_session(
        self,
        db: DBSession,
        session_type: str,
        start_poi_id: int = None
    ) -> tuple[Session, bool]:
        
        # 1. 세션 생성
        new_session = Session(
            session_type=session_type,
            started_at=datetime.now()
        )
        db.add(new_session)
        db.flush()  # ID 생성
        
        # 2. 목표 POI 좌표 가져오기
        target_x, target_y = 0.0, 0.0
        if start_poi_id:
            from models import POI
            poi = db.query(POI).filter(POI.id == start_poi_id).first()
            if poi:
                target_x = poi.x_m
                target_y = poi.y_m
        
        # 3. 로봇 배정 (SELECT FOR UPDATE)
        assigned_robot = self.dispatcher.assign_robot_to_session(
            db, new_session, target_x, target_y
        )
        
        if not assigned_robot:
            db.rollback()
            return new_session, False
        
        # 4. 예상 완료 시간 계산 및 업데이트
        self.estimator.update_robot_availability(
            db, assigned_robot, new_session
        )
        
        db.commit()
        
        return new_session, True