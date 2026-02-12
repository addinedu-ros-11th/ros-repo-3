# malle_service/config.py

from pydantic_settings import BaseSettings

class Config(BaseSettings):
    BATTERY_THRESHOLD: int = 20  # 최소 배터리 %
    LAST_SEEN_THRESHOLD_SEC: int = 5  # 마지막 신호 허용 시간
    
    AVG_ROBOT_SPEED_M_PER_SEC: float = 0.5  # 평균 속도 (m/s)
    POI_STOP_TIME_SEC: int = 30  # POI당 정지 시간 (초)
    
    class Config:
        env_file = ".env"