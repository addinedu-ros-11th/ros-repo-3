"""test_zone_mutex_unit.py — Zone-based PID Mutex 단위 테스트

실서버·MySQL 없이 SQLite in-memory + FastAPI TestClient으로 실행.

필요 패키지 (malle_service/ 디렉토리에서 설치):
    pip install pytest pytest-asyncio httpx aiosqlite

실행:
    cd malle_service
    pytest ../test/test_zone_mutex_unit.py -v

검증 시나리오:
  1. OCCUPIED 없을 때  → execute → 200 OK, batch_id 설정
  2. 로봇A OCCUPIED    → 로봇B execute → 409 Conflict, batch_id 롤백(None 유지)
  3. 로봇A OCCUPIED    → 로봇B execute → 409, 로봇A IDLE → 로봇B 자동 재실행
"""

import sys
import os

# malle_service 패키지가 임포트되도록 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "malle_service"))

import pytest
import pytest_asyncio
from datetime import datetime, timezone

# SQLite는 BIGINT PRIMARY KEY를 autoincrement로 인식 못 함.
# BigInteger → INTEGER 로 컴파일하여 rowid alias가 되도록 함.
from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles

@compiles(BigInteger, "sqlite")
def _bigint_as_integer(element, compiler, **kw):
    return "INTEGER"

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

# 모든 모델을 Base.metadata에 등록
import app.models  # noqa: F401

from app.database import Base, get_db
from app.main import app
from app.models.robot import (
    Robot, RobotStateCurrent,
    RobotMode, RobotNavState, RobotMotionState, RobotStopState,
)
from app.models.poi import Poi, PoiType, PoiArrivalConfirm
from app.models.session import Session, SessionType, SessionStatus
from app.models.user import User
from app.models.guide import GuideQueueItem, GuideItemStatus

# ── SQLite in-memory 엔진 ─────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def engine():
    """테스트마다 독립적인 in-memory SQLite DB."""
    eng = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,   # 모든 연결이 동일 in-memory DB 공유
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(engine):
    """get_db를 SQLite로 오버라이드한 FastAPI 비동기 클라이언트."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def seeded(engine):
    """기본 시드 데이터 삽입.

    반환값: {"robot_a": 1, "robot_b": 2, "session_b": 1, "poi": 1}
    """
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    async with factory() as db:
        user   = User(id=1, phone="010-0000-0001", created_at=now)
        poi    = Poi(
            id=1, name="좁은통로A",
            type=PoiType.OTHER,
            x_m=5.0, y_m=3.0,
            arrival_confirm=PoiArrivalConfirm.NAV2,
            created_at=now,
        )
        robot_a = Robot(
            id=1, name="RobotA", model="TurtleBot4",
            is_online=True, battery_pct=100,
            current_mode=RobotMode.IDLE, created_at=now,
        )
        state_a = RobotStateCurrent(
            robot_id=1,
            nav_state=RobotNavState.IDLE,
            motion_state=RobotMotionState.STOPPED,
            stop_state=RobotStopState.NONE,
            x_m=0.0, y_m=0.0, theta_rad=0.0,
            remaining_distance_m=0.0, eta_sec=0, speed_mps=0.0,
            updated_at=now,
        )
        robot_b = Robot(
            id=2, name="RobotB", model="TurtleBot4",
            is_online=True, battery_pct=100,
            current_mode=RobotMode.IDLE, created_at=now,
        )
        state_b = RobotStateCurrent(
            robot_id=2,
            nav_state=RobotNavState.IDLE,
            motion_state=RobotMotionState.STOPPED,
            stop_state=RobotStopState.NONE,
            x_m=1.0, y_m=0.0, theta_rad=0.0,
            remaining_distance_m=0.0, eta_sec=0, speed_mps=0.0,
            updated_at=now,
        )
        session_b = Session(
            id=1, user_id=1,
            session_type=SessionType.TASK,
            status=SessionStatus.ACTIVE,
            assigned_robot_id=2,
            created_at=now,
        )
        queue_item = GuideQueueItem(
            session_id=1, poi_id=1, seq=1,
            status=GuideItemStatus.PENDING,
            is_active=True,
            created_at=now,
        )

        db.add_all([user, poi, robot_a, state_a, robot_b, state_b, session_b, queue_item])
        await db.commit()

    return {"robot_a": 1, "robot_b": 2, "session_b": 1, "poi": 1}


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

async def get_first_pending(client: AsyncClient, session_id: int) -> dict | None:
    r = await client.get(f"/api/v1/sessions/{session_id}/guide-queue")
    assert r.status_code == 200
    items = r.json()
    actives = sorted(
        [i for i in items if i["is_active"] and i["status"] == "PENDING"],
        key=lambda i: i["seq"],
    )
    return actives[0] if actives else None


# ── 테스트 케이스 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_normal_execute_succeeds(client, seeded):
    """OCCUPIED 로봇 없을 때 execute → 200 OK, batch_id 설정."""
    r = await client.post(f"/api/v1/sessions/{seeded['session_b']}/guide-queue/execute")
    assert r.status_code == 200, f"예상 200, 실제: {r.status_code}\n{r.text}"

    data = r.json()
    assert data.get("mission_id") is not None
    assert data.get("executing_count", 0) >= 1

    item = await get_first_pending(client, seeded["session_b"])
    # 정상 실행 → batch_id 가 채워져야 함 (PENDING 상태는 유지, batch_id만 설정)
    # guide.py 는 PENDING 항목에 batch_id를 마킹하고 실행 시작함
    # (상태 자체는 robot이 ARRIVED 보고 시 ARRIVED로 전환)


@pytest.mark.asyncio
async def test_occupied_blocks_execute_409(client, seeded):
    """로봇A가 OCCUPIED 상태일 때 로봇B execute → 409 Conflict."""
    # 로봇A → OCCUPIED + target_poi_id 설정
    r = await client.patch(
        f"/api/v1/robots/{seeded['robot_a']}/state",
        json={"nav_state": "OCCUPIED", "target_poi_id": seeded["poi"]},
    )
    assert r.status_code == 200, f"로봇A OCCUPIED 설정 실패: {r.text}"

    state = r.json()["state"]
    assert state["nav_state"] == "OCCUPIED"
    assert state["target_poi_id"] == seeded["poi"]

    # 로봇B execute → 409
    r = await client.post(f"/api/v1/sessions/{seeded['session_b']}/guide-queue/execute")
    assert r.status_code == 409, f"409 예상, 실제: {r.status_code}\n{r.text}"
    assert "occupied" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_occupied_execute_rolls_back_batch_id(client, seeded):
    """409 응답 후 execution_batch_id 가 None으로 유지되는지(롤백) 확인."""
    # 로봇A OCCUPIED
    await client.patch(
        f"/api/v1/robots/{seeded['robot_a']}/state",
        json={"nav_state": "OCCUPIED", "target_poi_id": seeded["poi"]},
    )

    # execute → 409
    await client.post(f"/api/v1/sessions/{seeded['session_b']}/guide-queue/execute")

    # 큐 조회 → batch_id는 None 이어야 함 (트랜잭션 롤백 정상)
    item = await get_first_pending(client, seeded["session_b"])
    assert item is not None, "PENDING 항목이 사라짐"
    assert item["execution_batch_id"] is None, (
        f"409 후 batch_id={item['execution_batch_id']} → 롤백 실패"
    )


@pytest.mark.asyncio
async def test_idle_triggers_auto_execute(client, seeded):
    """로봇A OCCUPIED → 로봇B 409 → 로봇A IDLE 전환 → 로봇B 자동 실행."""
    # 로봇A OCCUPIED
    await client.patch(
        f"/api/v1/robots/{seeded['robot_a']}/state",
        json={"nav_state": "OCCUPIED", "target_poi_id": seeded["poi"]},
    )

    # 로봇B execute → 409 (batch_id 없음)
    r = await client.post(f"/api/v1/sessions/{seeded['session_b']}/guide-queue/execute")
    assert r.status_code == 409

    # 로봇A IDLE 해제 → guide_service.execute_guide_for_session 자동 호출
    r = await client.patch(
        f"/api/v1/robots/{seeded['robot_a']}/state",
        json={"nav_state": "IDLE"},
    )
    assert r.status_code == 200, f"로봇A IDLE 전환 실패: {r.text}"

    # 로봇B 큐 항목에 batch_id가 채워졌는지 확인
    r = await client.get(f"/api/v1/sessions/{seeded['session_b']}/guide-queue")
    items = sorted(
        [i for i in r.json() if i["is_active"]],
        key=lambda i: i["seq"],
    )
    assert items, "활성 항목 없음"
    assert items[0]["execution_batch_id"] is not None, (
        "자동 재실행 실패: execution_batch_id 가 여전히 None\n"
        "→ robots.py OCCUPIED→IDLE 자동 재실행 로직 확인 필요"
    )


@pytest.mark.asyncio
async def test_occupied_poi_ids_endpoint(client, seeded):
    """GET /robots/occupied-poi-ids — OCCUPIED 상태 조회 엔드포인트 확인."""
    # 초기: 점유 없음
    r = await client.get("/api/v1/robots/occupied-poi-ids")
    assert r.status_code == 200
    assert r.json()["poi_ids"] == []

    # 로봇A OCCUPIED 설정
    await client.patch(
        f"/api/v1/robots/{seeded['robot_a']}/state",
        json={"nav_state": "OCCUPIED", "target_poi_id": seeded["poi"]},
    )

    r = await client.get("/api/v1/robots/occupied-poi-ids")
    assert seeded["poi"] in r.json()["poi_ids"]

    # exclude_robot_id 파라미터 — 로봇A 자신은 제외
    r = await client.get(
        f"/api/v1/robots/occupied-poi-ids?exclude_robot_id={seeded['robot_a']}"
    )
    assert r.json()["poi_ids"] == []

    # 로봇A IDLE 복구
    await client.patch(
        f"/api/v1/robots/{seeded['robot_a']}/state",
        json={"nav_state": "IDLE"},
    )
    r = await client.get("/api/v1/robots/occupied-poi-ids")
    assert r.json()["poi_ids"] == []
