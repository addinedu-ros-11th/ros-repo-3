# malle_service/services/robot_dispatcher.py
"""
핵심 로직:
1. IDLE + 온라인 + 배터리 충분한 로봇 필터링
2. 목표 좌표까지 유클리드 거리 기준 가장 가까운 로봇 선택
3. next_available_time이 지난 로봇도 후보에 포함
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.robot import Robot, RobotStateCurrent, RobotMode

from app.config import BATTERY_THRESHOLD  # noqa: E402

async def find_nearest_available_robot(
    db: AsyncSession,
    target_x: float = 0.0,
    target_y: float = 0.0,
    exclude_robot_ids: list[int] | None = None,
) -> Robot | None:
    """
    가용 로봇 중 목표 좌표에 가장 가까운 로봇을 반환.

    가용 조건:
    - is_online = True
    - battery_pct >= BATTERY_THRESHOLD
    - current_mode = IDLE
    """
    query = (
        select(Robot)
        .options(selectinload(Robot.state))
        .where(
            Robot.is_online == True,
            Robot.battery_pct >= BATTERY_THRESHOLD,
            Robot.current_mode == RobotMode.IDLE,
        )
    )

    if exclude_robot_ids:
        query = query.where(Robot.id.not_in(exclude_robot_ids))

    result = await db.execute(query)
    candidates = result.scalars().all()

    if not candidates:
        return None

    # 거리 기반 정렬
    def distance(robot: Robot) -> float:
        if not robot.state:
            return float("inf")
        dx = float(robot.state.x_m) - target_x
        dy = float(robot.state.y_m) - target_y
        return math.sqrt(dx * dx + dy * dy)

    candidates.sort(key=distance)
    return candidates[0]


async def get_available_robot_count(db: AsyncSession) -> int:
    """현재 배정 가능한 로봇 수."""
    result = await db.execute(
        select(Robot).where(
            Robot.is_online == True,
            Robot.battery_pct >= BATTERY_THRESHOLD,
            Robot.current_mode == RobotMode.IDLE,
        )
    )
    return len(result.scalars().all())


async def get_dispatch_status(db: AsyncSession) -> dict:
    """대시보드용 배정 현황."""
    result = await db.execute(
        select(Robot).options(selectinload(Robot.state)).order_by(Robot.id)
    )
    robots = result.scalars().all()

    robot_list = []
    available_count = 0
    for r in robots:
        is_available = (
            r.is_online
            and r.battery_pct >= BATTERY_THRESHOLD
            and r.current_mode == RobotMode.IDLE
        )
        if is_available:
            available_count += 1

        robot_list.append({
            "id": r.id,
            "name": r.name,
            "mode": r.current_mode.value,
            "battery": r.battery_pct,
            "is_online": r.is_online,
            "is_available": is_available,
            "position": {
                "x": float(r.state.x_m) if r.state else 0,
                "y": float(r.state.y_m) if r.state else 0,
            },
        })

    return {
        "total_robots": len(robots),
        "available_robots": available_count,
        "robots": robot_list,
    }