# malle_service/services/robot_state_service.py

from sqlalchemy.orm import Session as DBSession
from datetime import datetime

from models import Robot, RobotMode

class RobotStateService:

    def update_from_dds(
        self,
        db: DBSession,
        robot_name: str,
        mode: str,
        battery: int,
        position_x: float,
        position_y: float
    ):
        existing_robot = db.query(Robot).filter(
            Robot.name == robot_name
        ).first()

        if not existing_robot:
            new_robot = Robot(
                name=robot_name,
                current_mode=RobotMode[mode],
                battery_pct=battery,
                last_x=position_x,
                last_y=position_y,
                last_seen_at=datetime.now(),
                is_online=True
            )
            db.add(new_robot)

        else:
            existing_robot.current_mode = RobotMode[mode]
            existing_robot.battery_pct = battery
            existing_robot.last_x = position_x
            existing_robot.last_y = position_y
            existing_robot.last_seen_at = datetime.now()
            existing_robot.is_online = True

            if mode == "IDLE":
                existing_robot.next_available_time = None

        db.commit()
        return existing_robot if existing_robot else new_robot

    def mark_robot_offline(
        self,
        db: DBSession,
        robot_name: str
    ):
        existing_robot = db.query(Robot).filter(
            Robot.name == robot_name
        ).first()

        if existing_robot:
            existing_robot.is_online = False
            db.commit()
