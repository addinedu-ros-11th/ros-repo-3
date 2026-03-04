# malle_service/services/robot_dispatcher.py
"""
핵심 로직:
1. 온라인 + 배터리 충분한 로봇 필터링
2. (중요) 해당 로봇에 '활성 세션(ENDED 아님)'이 없는지 확인하여 busy 로봇 제외
3. 목표 좌표까지 유클리드 거리 기준 가장 가까운 로봇 선택

왜 바꿈?
- current_mode == IDLE 조건은 더미/스테일/외부 덮어쓰기(malle_bot state push) 등으로 쉽게 깨짐
- 세션/배정은 '현재 활성 세션이 있느냐'로 판단하는 게 더 안정적
"""

import math

from sqlalchemy import select, exists, and_, not_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.robot import Robot, RobotMode
from app.models.session import Session, SessionStatus
from app.config import settings

# "활성(바쁜) 세션"으로 간주할 상태들
BUSY_SESSION_STATUSES = (
    SessionStatus.ASSIGNED,
    SessionStatus.APPROACHING,
    SessionStatus.MATCHING,
    SessionStatus.ACTIVE,
)


async def find_nearest_available_robot(
    db: AsyncSession,
    target_x: float = 0.0,
    target_y: float = 0.0,
    exclude_robot_ids: list[int] | None = None,
    include_robot_ids: list[int] | None = None,
) -> Robot | None:
    """
    가용 로봇 중 목표 좌표에 가장 가까운 로봇을 반환.

    가용 조건:
    - is_online = True
    - battery_pct >= BATTERY_THRESHOLD
    - (중요) 이 로봇에 대해 활성 세션이 없음
    """
    # Robot row를 바깥 쿼리에서 쓰기 위해 exists를 상관 서브쿼리 형태로 작성
    busy_session_exists = exists(
        select(1).where(
            and_(
                Session.assigned_robot_id == Robot.id,
                Session.status.in_(BUSY_SESSION_STATUSES),
            )
        )
    )

    query = (
        select(Robot)
        .options(selectinload(Robot.state))
        .where(
            Robot.is_online == True,
            Robot.battery_pct >= settings.BATTERY_THRESHOLD,
            not_(busy_session_exists),
        )
    )

    if include_robot_ids:
        query = query.where(Robot.id.in_(include_robot_ids))

    if exclude_robot_ids:
        query = query.where(Robot.id.not_in(exclude_robot_ids))

    result = await db.execute(query)
    candidates = result.scalars().all()

    if not candidates:
        return None

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
    busy_session_exists = exists(
        select(1).where(
            and_(
                Session.assigned_robot_id == Robot.id,
                Session.status.in_(BUSY_SESSION_STATUSES),
            )
        )
    )

    result = await db.execute(
        select(Robot).where(
            Robot.is_online == True,
            Robot.battery_pct >= settings.BATTERY_THRESHOLD,
            not_(busy_session_exists),
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

    # busy 세션을 가진 로봇을 빠르게 판단하기 위해, 로봇별 활성 세션 존재 여부를 한번에 조회
    busy_robot_ids_result = await db.execute(
        select(Session.assigned_robot_id).where(
            Session.assigned_robot_id.is_not(None),
            Session.status.in_(BUSY_SESSION_STATUSES),
        )
    )
    busy_robot_ids = set(busy_robot_ids_result.scalars().all())

    for r in robots:
        is_available = (
            r.is_online
            and r.battery_pct >= settings.BATTERY_THRESHOLD
            and (r.id not in busy_robot_ids)
        )
        if is_available:
            available_count += 1

        robot_list.append({
            "id": r.id,
            "name": r.name,
            "mode": r.current_mode.value,  # mode는 참고용(디스패치 판단에는 사용 안 함)
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
