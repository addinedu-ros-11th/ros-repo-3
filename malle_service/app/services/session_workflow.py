# malle_service/workflows/session_workflow.py
"""
세션 생성 → 로봇 배정 → 예상 완료시간 산출 → WS 알림 통합 플로우.
"""
import random
import string
from datetime import datetime, timedelta, timezone
import logging

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
from sqlalchemy import select, update
from app.models.lockbox import LockboxSlot, LockboxSlotStatus
from app.models.pickup import PickupOrder, PickupStatus

logger = logging.getLogger(__name__)


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
    # 우선: 현재 WS로 연결된 로봇 중에서 배정 시도 (PIN/세션 이벤트 유실 방지)
    connected_robot_ids = list(manager.robot_connections.keys())
    robot = None
    if connected_robot_ids:
        robot = await find_nearest_available_robot(
            db,
            target_x=target_x,
            target_y=target_y,
            exclude_robot_ids=exclude,
            include_robot_ids=connected_robot_ids,
        )

    # 폴백: 연결 로봇이 없거나 모두 가용 아님이면 전체 가용 로봇 대상
    if not robot:
        robot = await find_nearest_available_robot(
            db, target_x=target_x, target_y=target_y, exclude_robot_ids=exclude
        )

    if robot:
        session.assigned_robot_id = robot.id
        session.status = SessionStatus.ASSIGNED
        # NOTE: 배정 시점에 robot.current_mode를 변경하지 않는다.
        # 실제 로봇 미션 실행 시점에서만 mode를 바꾸는 것이 정합성이 좋다.
        # robot.current_mode = RobotMode.GUIDE

        # ---- 핵심: 동일 로봇에 걸려 있던 "ENDED 아님" 세션들을 강제 종료하여 중복 ACTIVE 누적 방지 ----
        stale_session_result = await db.execute(
            select(Session).where(
                Session.assigned_robot_id == robot.id,
                Session.status != SessionStatus.ENDED,
                Session.id != session.id,
            ).order_by(Session.created_at.desc())
        )
        stale_sessions = stale_session_result.scalars().all()

        for s in stale_sessions:
            # end_session()가 픽업/락박스/WS까지 정리하므로 일관성이 유지됨
            await end_session(db, s, reason="superseded_by_new_assignment")

        # 슬롯은 항상 초기화 (스테일 데이터 유무와 무관하게)
        await db.execute(
            update(LockboxSlot)
            .where(LockboxSlot.robot_id == robot.id)
            .values(status=LockboxSlotStatus.EMPTY)
        )

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
        logger.info(
            "[SESSION_ASSIGN] session=%s robot=%s connected_robot_ids=%s",
            session.id,
            robot.id,
            connected_robot_ids,
        )

        # 슬롯 초기화 상태 동기화 (스테일 데이터 정리 후 EMPTY 상태 전파)
        slot_result = await db.execute(
            select(LockboxSlot.slot_no)
            .where(LockboxSlot.robot_id == robot.id)
            .order_by(LockboxSlot.slot_no)
        )
        slot_nos = list(slot_result.scalars().all())
        empty_slots = [{"slot_no": sno, "status": "EMPTY"} for sno in (slot_nos or range(1, 6))]
        lockbox_payload = {"robot_id": robot.id, "slots": empty_slots}
        await manager.send_to_mobile(session.id, WsEvent.LOCKBOX_UPDATED, lockbox_payload)
        await manager.send_to_robot(robot.id, WsEvent.LOCKBOX_UPDATED, lockbox_payload)
        await manager.send_to_dashboard(WsEvent.LOCKBOX_UPDATED, lockbox_payload)

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
    # ✅ ENDED는 반드시 end_session()로 통일 처리
    if new_status == SessionStatus.ENDED:
        return await end_session(db, session, reason="status_update")

    old_status = session.status
    session.status = new_status

    if new_status == SessionStatus.ACTIVE:
        session.started_at = datetime.now(timezone.utc)

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
        else:
            logger.warning("[PIN_MATCHING] session=%s has no assigned_robot_id", session.id)

    elif new_status == SessionStatus.ACTIVE:
        await manager.broadcast_to_session(
            session.id, session.assigned_robot_id,
            WsEvent.SESSION_ACTIVE, session_data,
        )

    return session


async def end_session(db: AsyncSession, session: Session, reason: str = "user_ended") -> Session:
    """세션 종료 + 로봇 해제 + 락박스 초기화 + WS 알림."""
    session.status = SessionStatus.ENDED
    session.ended_at = datetime.now(timezone.utc)

    # 미완료 픽업 주문 CANCELED 처리
    await db.execute(
        update(PickupOrder)
        .where(
            PickupOrder.session_id == session.id,
            PickupOrder.status.not_in([PickupStatus.COMPLETED, PickupStatus.CANCELED])
        )
        .values(status=PickupStatus.CANCELED)
    )

    robot_id = session.assigned_robot_id
    if robot_id:
        robot = await db.get(Robot, robot_id)
        if robot:
            robot.current_mode = RobotMode.IDLE

        await db.execute(
            update(LockboxSlot)
            .where(LockboxSlot.robot_id == robot_id)
            .values(status=LockboxSlotStatus.EMPTY)
        )

    await db.flush()
    await db.refresh(session)

    await manager.broadcast_to_session(
        session.id, robot_id,
        WsEvent.SESSION_ENDED, {"session_id": session.id, "reason": reason},
    )

    if robot_id:
        # 실제 DB 슬롯 번호 조회 (bulk UPDATE 후 slot_no는 변경 없으므로 안전)
        slot_result = await db.execute(
            select(LockboxSlot.slot_no)
            .where(LockboxSlot.robot_id == robot_id)
            .order_by(LockboxSlot.slot_no)
        )
        slot_nos = list(slot_result.scalars().all())
        empty_slots = [{"slot_no": sno, "status": "EMPTY"} for sno in (slot_nos or range(1, 6))]
        lockbox_payload = {"robot_id": robot_id, "slots": empty_slots}
        # mobile + robot에 전송
        await manager.broadcast_to_session(
            session.id, robot_id,
            WsEvent.LOCKBOX_UPDATED, lockbox_payload,
        )
        # dashboard에도 전송 (broadcast_to_session은 dashboard 미포함)
        await manager.send_to_dashboard(WsEvent.LOCKBOX_UPDATED, lockbox_payload)

    return session
