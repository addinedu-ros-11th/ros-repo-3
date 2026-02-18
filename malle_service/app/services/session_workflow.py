# malle_service/workflows/session_workflow.py
"""
세션 생성 → 로봇 배정 → 예상 완료시간 산출 → WS 알림 통합 플로우.
"""
import random
import string
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session, SessionType, SessionStatus
from app.models.robot import Robot, RobotMode
from app.models.poi import Poi
from app.services.robot_dispatcher import find_nearest_available_robot
from app.services.time_estimator import estimate_travel_time
from app.ws.manager import manager
from app.ws.events import WsEvent
from app.schemas.session import SessionResponse


def _generate_pin(length: int = 4) -> str:
    return "".join(random.choices(string.digits, k=length))


async def create_session_with_assignment(
    db: AsyncSession,
    user_id: int,
    session_type: SessionType,
    requested_minutes: int | None = None,
    target_poi_id: int | None = None,
) -> Session:
    """
    세션 생성 + 로봇 자동 배정 + WS 알림.

    Flow:
    1. Session 레코드 생성 (REQUESTED)
    2. target POI가 있으면 좌표 조회
    3. find_nearest_available_robot()으로 가장 가까운 로봇 선택
    4. 배정 성공 → ASSIGNED, 로봇 모드 변경
    5. 예상 도착시간 계산
    6. WS 브로드캐스트 (mobile + robot + dashboard)
    """
    pin = _generate_pin()

    session = Session(
        user_id=user_id,
        session_type=session_type,
        requested_minutes=requested_minutes,
        status=SessionStatus.REQUESTED,
        match_pin=pin,
        pin_expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # 목표 좌표 결정
    target_x, target_y = 0.0, 0.0
    if target_poi_id:
        poi = await db.get(Poi, target_poi_id)
        if poi:
            target_x = float(poi.x_m)
            target_y = float(poi.y_m)

    # 로봇 배정
    robot = await find_nearest_available_robot(
        db, target_x=target_x, target_y=target_y
    )

    if robot:
        session.assigned_robot_id = robot.id
        session.status = SessionStatus.ASSIGNED

        # 세션 타입에 따라 로봇 모드 설정
        mode_map = {
            SessionType.TASK: RobotMode.GUIDE,
            SessionType.TIME: RobotMode.GUIDE,
        }
        robot.current_mode = mode_map.get(session_type, RobotMode.GUIDE)

        await db.flush()
        await db.refresh(session)

        # ETA 계산
        eta_sec = await estimate_travel_time(db, robot.id, target_x, target_y)

        session_data = SessionResponse.model_validate(session).model_dump(mode="json")
        session_data["eta_sec"] = eta_sec

        # WS 알림
        await manager.send_to_mobile(
            session.id, WsEvent.SESSION_ASSIGNED, session_data
        )
        await manager.send_to_robot(
            robot.id, WsEvent.SESSION_ASSIGNED, session_data
        )
        await manager.send_to_dashboard(WsEvent.SESSION_ASSIGNED, session_data)

    return session


async def transition_session_status(
    db: AsyncSession,
    session: Session,
    new_status: SessionStatus,
) -> Session:
    """
    세션 상태 전이 + 부수 효과 처리.

    APPROACHING → PIN_MATCHING → ACTIVE → ENDED
    """
    old_status = session.status
    session.status = new_status

    if new_status == SessionStatus.ACTIVE:
        session.started_at = datetime.utcnow()
    elif new_status == SessionStatus.ENDED:
        session.ended_at = datetime.utcnow()

    await db.flush()
    await db.refresh(session)

    session_data = SessionResponse.model_validate(session).model_dump(mode="json")

    if new_status == SessionStatus.APPROACHING:
        await manager.send_to_mobile(
            session.id, WsEvent.ROBOT_APPROACHING, session_data
        )
        await manager.send_to_dashboard(WsEvent.ROBOT_APPROACHING, session_data)

    elif new_status == SessionStatus.MATCHING:
        await manager.send_to_mobile(session.id, WsEvent.PIN_MATCHING, {
            "session_id": session.id,
            "pin": session.match_pin,
        })

    elif new_status == SessionStatus.ACTIVE:
        await manager.broadcast_to_session(
            session.id, session.assigned_robot_id,
            WsEvent.SESSION_ACTIVE, session_data,
        )

    elif new_status == SessionStatus.ENDED:
        await manager.broadcast_to_session(
            session.id, session.assigned_robot_id,
            WsEvent.SESSION_ENDED, {"session_id": session.id, "reason": "status_update"},
        )
        # 로봇 해제
        if session.assigned_robot_id:
            robot = await db.get(Robot, session.assigned_robot_id)
            if robot:
                robot.current_mode = RobotMode.IDLE

    return session


async def end_session(db: AsyncSession, session: Session, reason: str = "user_ended") -> Session:
    """세션 종료 + 로봇 해제 + WS 알림."""
    session.status = SessionStatus.ENDED
    session.ended_at = datetime.utcnow()

    robot_id = session.assigned_robot_id
    if robot_id:
        robot = await db.get(Robot, robot_id)
        if robot:
            robot.current_mode = RobotMode.IDLE

    await db.flush()
    await db.refresh(session)

    await manager.broadcast_to_session(
        session.id, robot_id,
        WsEvent.SESSION_ENDED, {"session_id": session.id, "reason": reason},
    )

    return session
