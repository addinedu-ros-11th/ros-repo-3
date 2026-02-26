# malle_service/workflows/session_workflow.py
"""
세션 생성 → 로봇 배정 → 예상 완료시간 산출 → WS 알림 통합 플로우.
"""
import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session, SessionType, SessionStatus
from app.models.robot import Robot, RobotMode, RobotStateCurrent
from app.models.poi import Poi
from app.models.user import User
from app.services.robot_dispatcher import find_nearest_available_robot
from app.services.time_estimator import estimate_travel_time
from app.ws.manager import manager
from app.ws.events import WsEvent
from app.schemas.session import SessionResponse, SessionAssignedPayload


def _generate_pin(length: int = 4) -> str:
    return "".join(random.choices(string.digits, k=length))


async def assign_robot_to_session(
    db: AsyncSession,
    session: Session,
    target_poi_id: int | None = None,
) -> Session:
    """
    기존 세션에 가장 가까운 가용 로봇을 배정하고 WS 알림.

    - REQUESTED / ASSIGNED 상태 모두 허용 (재배정 가능)
    - 가용 로봇 없으면 session 그대로 반환 (status 변경 없음)
    """
    target_x, target_y = 0.0, 0.0
    if target_poi_id:
        poi = await db.get(Poi, target_poi_id)
        if poi:
            target_x = float(poi.x_m)
            target_y = float(poi.y_m)

    # 재배정 시 기존 로봇 제외
    exclude = [session.assigned_robot_id] if session.assigned_robot_id else None
    robot = await find_nearest_available_robot(
        db, target_x=target_x, target_y=target_y, exclude_robot_ids=exclude
    )

    if robot:
        session.assigned_robot_id = robot.id
        session.status = SessionStatus.ASSIGNED
        robot.current_mode = RobotMode.GUIDE

        await db.flush()
        await db.refresh(session)

        eta_sec = await estimate_travel_time(db, robot.id, target_x, target_y)
        robot_state = await db.get(RobotStateCurrent, robot.id)

        user = await db.get(User, session.user_id)
        masked_phone = None
        if user and user.phone:
            p = user.phone.replace("-", "")
            masked_phone = f"{p[:3]}-****-{p[-4:]}" if len(p) >= 8 else user.phone

        payload = SessionAssignedPayload(
            **SessionResponse.model_validate(session).model_dump(),
            robot_name=robot.name,
            battery_pct=robot.battery_pct,
            x_m=float(robot_state.x_m) if robot_state else None,
            y_m=float(robot_state.y_m) if robot_state else None,
            customer_phone_masked=masked_phone,
            eta_sec=eta_sec,
        )
        payload_dict = payload.model_dump(mode="json")

        await manager.send_to_mobile(session.id, WsEvent.SESSION_ASSIGNED, payload_dict)
        await manager.send_to_robot(robot.id, WsEvent.SESSION_ASSIGNED, payload_dict)
        await manager.send_to_dashboard(WsEvent.SESSION_ASSIGNED, payload_dict)

    return session


async def create_session_with_assignment(
    db: AsyncSession,
    user_id: int,
    session_type: SessionType,
    requested_minutes: int | None = None,
    target_poi_id: int | None = None,
) -> Session:
    """세션 생성 후 즉시 로봇 배정."""
    pin = _generate_pin()

    session = Session(
        user_id=user_id,
        session_type=session_type,
        requested_minutes=requested_minutes,
        status=SessionStatus.REQUESTED,
        match_pin=pin,
        pin_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    return await assign_robot_to_session(db, session, target_poi_id=target_poi_id)


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
        session.started_at = datetime.now(timezone.utc)
    elif new_status == SessionStatus.ENDED:
        session.ended_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(session)

    session_data = SessionResponse.model_validate(session).model_dump(mode="json")

    if new_status == SessionStatus.APPROACHING:
        await manager.send_to_mobile(
            session.id, WsEvent.ROBOT_APPROACHING, session_data
        )
        await manager.send_to_dashboard(WsEvent.ROBOT_APPROACHING, session_data)

    elif new_status == SessionStatus.MATCHING:
        pin_payload = {
            "session_id": session.id,
            "pin": session.match_pin,
        }
        # 모바일: PIN 표시용
        await manager.send_to_mobile(session.id, WsEvent.PIN_MATCHING, pin_payload)
        # 로봇: PIN_MATCHING 상태 진입 트리거 (pin 포함)
        if session.assigned_robot_id:
            await manager.send_to_robot(session.assigned_robot_id, WsEvent.PIN_MATCHING, pin_payload)

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
    session.ended_at = datetime.now(timezone.utc)

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