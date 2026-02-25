# malle_service/services/time_estimator.py

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guide import GuideQueueItem, GuideItemStatus
from app.models.poi import Poi
from app.models.robot import RobotStateCurrent

from app.config import settings

AVG_ROBOT_SPEED_M_PER_SEC = settings.AVG_ROBOT_SPEED_M_PER_SEC
POI_STOP_TIME_SEC = settings.POI_STOP_TIME_SEC

async def estimate_session_completion(
    db: AsyncSession,
    session_id: int,
    robot_id: int,
) -> datetime:
    """
    가이드큐 기반 세션 예상 완료시간 계산.

    1. 해당 세션의 PENDING 가이드큐 아이템 조회
    2. 로봇 현재 위치 → 첫 POI → ... → 마지막 POI 경로 거리 합산
    3. 거리/속도 + POI수×정지시간 = 예상 소요시간
    """
    # 1. PENDING 가이드큐 아이템 + POI 좌표
    result = await db.execute(
        select(GuideQueueItem, Poi)
        .join(Poi, GuideQueueItem.poi_id == Poi.id)
        .where(
            GuideQueueItem.session_id == session_id,
            GuideQueueItem.is_active == True,
            GuideQueueItem.status == GuideItemStatus.PENDING,
        )
        .order_by(GuideQueueItem.seq)
    )
    queue_with_pois = result.all()

    if not queue_with_pois:
        return datetime.now(timezone.utc)

    # 2. 로봇 현재 위치
    robot_state = await db.get(RobotStateCurrent, robot_id)
    current_x = float(robot_state.x_m) if robot_state else 0.0
    current_y = float(robot_state.y_m) if robot_state else 0.0

    # 3. 경로 거리 계산
    total_distance = 0.0
    prev_x, prev_y = current_x, current_y

    for _item, poi in queue_with_pois:
        poi_x = float(poi.x_m)
        poi_y = float(poi.y_m)
        total_distance += math.sqrt(
            (poi_x - prev_x) ** 2 + (poi_y - prev_y) ** 2
        )
        prev_x, prev_y = poi_x, poi_y

    # 4. 시간 계산
    travel_time_sec = total_distance / AVG_ROBOT_SPEED_M_PER_SEC
    stop_time_sec = len(queue_with_pois) * POI_STOP_TIME_SEC
    total_time_sec = travel_time_sec + stop_time_sec

    return datetime.now(timezone.utc) + timedelta(seconds=total_time_sec)


async def estimate_travel_time(
    db: AsyncSession,
    robot_id: int,
    target_x: float,
    target_y: float,
) -> int:
    """로봇 현재 위치에서 목표까지 예상 이동시간(초)."""
    robot_state = await db.get(RobotStateCurrent, robot_id)
    if not robot_state:
        return 0

    dx = float(robot_state.x_m) - target_x
    dy = float(robot_state.y_m) - target_y
    distance = math.sqrt(dx * dx + dy * dy)

    return int(distance / AVG_ROBOT_SPEED_M_PER_SEC)