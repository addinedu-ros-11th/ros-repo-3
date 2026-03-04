"""Configuration loaded from environment variables."""

from pydantic_settings import BaseSettings

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from config/ directory
_env_file = Path(__file__).parent.parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

# --- Database ---
DB_URL: str = os.getenv(
    "DB_URL",
    "mysql+aiomysql://root:password@localhost:3306/malle",
)

# --- CORS ---
CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:8001",
).split(",")

# --- Internal services ---
AI_SERVICE_URL: str = os.getenv("AI_SERVICE_URL", "http://localhost:5000")
BRIDGE_BASE_URL: str = os.getenv("BRIDGE_BASE_URL", "http://localhost:9100")

# --- Server ---
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

class Config(BaseSettings):
    BATTERY_THRESHOLD: int = 20  # 최소 배터리 %
    LAST_SEEN_THRESHOLD_SEC: int = 5  # 마지막 신호 허용 시간
    
    AVG_ROBOT_SPEED_M_PER_SEC: float = 0.5  # 평균 속도 (m/s)
    POI_STOP_TIME_SEC: int = 30  # POI당 정지 시간 (초)
    
    class Config:
        env_file = ".env"

settings = Config()