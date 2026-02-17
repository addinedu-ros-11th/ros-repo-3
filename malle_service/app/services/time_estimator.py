# malle_service/services/time_estimator.py

from sqlalchemy.orm import Session as DBSession
from datetime import datetime, timedelta
import math

from models import Robot, Session, GuideQueue, GuideQueueItem, POI
from config import Config

class TimeEstimatorService:
    
    def __init__(self, config: Config):
        self.avg_speed = config.AVG_ROBOT_SPEED_M_PER_SEC
        self.poi_stop_time = config.POI_STOP_TIME_SEC
    
    def calculate_session_completion_time(
        self,
        db: DBSession,
        session: Session
    ) -> datetime:
        
        # 1. 가이드 큐 조회
        guide_queue = db.query(GuideQueue).filter(
            GuideQueue.session_id == session.id
        ).first()
        
        if not guide_queue:
            return datetime.now()
        
        queue_items = db.query(GuideQueueItem).filter(
            GuideQueueItem.queue_id == guide_queue.id
        ).order_by(GuideQueueItem.seq).all()
        
        if not queue_items:
            return datetime.now()
        
        # 2. POI 좌표 가져오기
        poi_ids = [item.poi_id for item in queue_items]
        pois = db.query(POI).filter(POI.id.in_(poi_ids)).all()
        poi_map = {poi.id: poi for poi in pois}
        
        # 3. 로봇 현재 위치
        robot = session.assigned_robot
        if not robot:
            return datetime.now()
        
        current_x = robot.last_x
        current_y = robot.last_y
        
        # 4. 경로 거리 계산
        total_distance = self._calculate_route_distance(
            start_x=current_x,
            start_y=current_y,
            queue_items=queue_items,
            poi_map=poi_map
        )
        
        # 5. 시간 계산
        travel_time_sec = total_distance / self.avg_speed
        stop_time_sec = len(queue_items) * self.poi_stop_time
        total_time_sec = travel_time_sec + stop_time_sec
        
        completion_time = datetime.now() + timedelta(
            seconds=total_time_sec
        )
        
        return completion_time
    
    def _calculate_route_distance(
        self,
        start_x: float,
        start_y: float,
        queue_items: list,
        poi_map: dict
    ) -> float:
        total_distance = 0.0
        prev_x, prev_y = start_x, start_y
        
        for item in queue_items:
            poi = poi_map.get(item.poi_id)
            if not poi:
                continue
            
            distance = math.sqrt(
                (poi.x_m - prev_x)**2 + 
                (poi.y_m - prev_y)**2
            )
            total_distance += distance
            
            # 다음 구간을 위해 업데이트
            prev_x = poi.x_m
            prev_y = poi.y_m
        
        return total_distance
    
    def update_robot_availability(
        self,
        db: DBSession,
        robot: Robot,
        session: Session
    ):
        completion_time = self.calculate_session_completion_time(
            db, session
        )
        
        robot.next_available_time = completion_time
        db.commit()