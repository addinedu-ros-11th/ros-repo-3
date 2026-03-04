"""OCCUPIED 해제 시 대기 세션 자동 재실행 서비스."""
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guide import GuideQueueItem, GuideItemStatus
from app.models.mission import Mission, MissionType, MissionStatus
from app.models.poi import Poi
from app.models.robot import RobotStateCurrent
from app.models.session import Session
from app.utils.bridge import send_to_bridge
from app.ws.events import WsEvent
from app.ws.manager import manager


async def execute_guide_for_session(db: AsyncSession, session: Session) -> bool:
    """
    대기 중인 세션의 첫 PENDING 항목으로 로봇을 이동시킴.
    409 체크 없음 — 호출자(auto-retry)가 POI 해제를 확인한 후 호출.
    성공 시 True, 펜딩 항목 없으면 False.
    """
    session_id = session.id
    robot_id = session.assigned_robot_id

    # 펜딩 항목 조회
    result = await db.execute(
        select(GuideQueueItem)
        .where(
            GuideQueueItem.session_id == session_id,
            GuideQueueItem.is_active == True,
            GuideQueueItem.status == GuideItemStatus.PENDING,
        )
        .order_by(GuideQueueItem.seq)
    )
    pending = result.scalars().all()
    if not pending:
        return False

    # 미션 생성 또는 기존 RUNNING 미션 조회
    mission_result = await db.execute(
        select(Mission).where(
            Mission.session_id == session_id,
            Mission.type == MissionType.GUIDE,
            Mission.status.in_([MissionStatus.QUEUED, MissionStatus.RUNNING]),
        )
    )
    mission = mission_result.scalar_one_or_none()
    if not mission:
        mission = Mission(
            session_id=session_id,
            robot_id=robot_id,
            type=MissionType.GUIDE,
            status=MissionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(mission)
        await db.flush()
        await manager.send_to_dashboard(WsEvent.MISSION_CREATED, {
            "mission_id": mission.id,
            "session_id": session_id,
            "robot_id": robot_id,
            "type": "GUIDE",
        })

    # 배치 ID 마킹
    for item in pending:
        item.execution_batch_id = mission.id
    await db.flush()

    first_item = pending[0]
    poi = await db.get(Poi, first_item.poi_id)

    # target_poi_id 기록
    state_result = await db.execute(
        select(RobotStateCurrent).where(RobotStateCurrent.robot_id == robot_id)
    )
    robot_state = state_result.scalar_one_or_none()
    if robot_state:
        robot_state.target_poi_id = first_item.poi_id
    await db.flush()

    # WS 이벤트
    await manager.send_to_robot(robot_id, WsEvent.GUIDE_NAVIGATING, {
        "item_id": first_item.id,
        "poi_id": first_item.poi_id,
        "poi_name": poi.name if poi else None,
    })
    await manager.send_to_mobile(session_id, WsEvent.GUIDE_NAVIGATING, {
        "item_id": first_item.id,
        "poi_name": poi.name if poi else None,
    })

    # 내비게이션 명령
    if poi:
        nav_x = float(poi.wait_x_m) if poi.wait_x_m is not None else float(poi.x_m)
        nav_y = float(poi.wait_y_m) if poi.wait_y_m is not None else float(poi.y_m)
        await send_to_bridge("navigate", {
            "robot_id": robot_id,
            "x": nav_x,
            "y": nav_y,
            "theta": 0.0,
        })

    return True


async def find_sessions_blocked_by_poi(
    db: AsyncSession,
    freed_poi_id: int,
    exclude_robot_id: int,
) -> list[Session]:
    """
    특정 POI가 해제됐을 때 대기 중인 세션 목록 반환.
    조건: 첫 번째 PENDING 항목이 freed_poi_id이고 execution_batch_id가 NULL(실행 미완료).
    순차 진입을 위해 최대 1개만 반환.
    """
    # 세션별 첫 번째 PENDING seq 서브쿼리
    first_seq_subq = (
        select(
            GuideQueueItem.session_id,
            func.min(GuideQueueItem.seq).label("first_seq"),
        )
        .where(
            GuideQueueItem.is_active == True,
            GuideQueueItem.status == GuideItemStatus.PENDING,
        )
        .group_by(GuideQueueItem.session_id)
        .subquery()
    )

    result = await db.execute(
        select(Session)
        .join(GuideQueueItem, GuideQueueItem.session_id == Session.id)
        .join(
            first_seq_subq,
            (first_seq_subq.c.session_id == GuideQueueItem.session_id)
            & (first_seq_subq.c.first_seq == GuideQueueItem.seq),
        )
        .where(
            Session.assigned_robot_id.is_not(None),
            Session.assigned_robot_id != exclude_robot_id,
            GuideQueueItem.poi_id == freed_poi_id,
            GuideQueueItem.execution_batch_id.is_(None),
        )
        .limit(1)  # 한 번에 하나씩 해제 (순차 진입 보장)
    )
    return result.scalars().all()
