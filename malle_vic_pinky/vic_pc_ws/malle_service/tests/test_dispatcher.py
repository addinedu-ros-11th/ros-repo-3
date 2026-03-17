"""
robot_dispatcher 테스트.

GET  /robots/dispatch/status      → get_dispatch_status()
GET  /robots/dispatch/count       → get_available_robot_count()
POST /sessions                    → 세션 생성 + 즉시 배정 (coupled)
POST /sessions/{id}/assign        → 배정만 단독 호출 (decoupled)

시나리오:
1. 현재 배정 현황 조회
2. 가용 로봇 수 조회
3. POST /sessions → 즉시 배정 확인
4. POST /sessions/{id}/assign → 단독 배정 확인
5. 배터리 낮은 로봇 제외 확인
6. 오프라인 로봇 제외 확인
7. IDLE 아닌 로봇 제외 확인
"""

import random
from base import ok, get, post, patch, health

USER_ID = 1
BATTERY_THRESHOLD = 20  # config의 BATTERY_THRESHOLD와 맞춰야 함


def get_robots() -> list:
    return get("/robots/dispatch/status").json().get("robots", [])


def test_dispatch_status():
    print("\n[dispatcher] 배정 현황 조회")
    data = ok("GET /robots/dispatch/status", get("/robots/dispatch/status"))
    print(f"             total={data.get('total_robots')} available={data.get('available_robots')}")
    for r in data.get("robots", []):
        mark = "O" if r["is_available"] else "X"
        pos = r.get("position", {})
        print(f"             [{mark}] id={r['id']} {r['name']} mode={r['mode']} battery={r['battery']}% pos=({pos.get('x')},{pos.get('y')})")
    return data


def test_dispatch_count():
    print("\n[dispatcher] 가용 로봇 수 조회")
    data = ok("GET /robots/dispatch/count", get("/robots/dispatch/count"))
    print(f"             available_count={data.get('available_count')}")
    return data.get("available_count", 0)


def _randomize_robot_positions(available: list):
    """가용 로봇들 위치를 랜덤으로 설정."""
    for r in available:
        x = round(random.uniform(0, 400), 1)
        y = round(random.uniform(0, 300), 1)
        patch(f"/robots/{r['id']}/state", {"x_m": x, "y_m": y})
        print(f"             robot_id={r['id']} 위치 랜덤 설정 → ({x}, {y})")


def test_coupled_assignment():
    """POST /sessions → 세션 생성과 동시에 즉시 배정."""
    print("\n[dispatcher] 세션 생성 + 즉시 배정 (POST /sessions)")

    available = [r for r in get_robots() if r["is_available"]]
    print(f"             배정 전 가용 로봇: {[r['id'] for r in available]}")

    if not available:
        print("             [SKIP] 가용 로봇 없음")
        return None

    _randomize_robot_positions(available)

    session = ok("POST /sessions", post("/sessions", {
        "user_id": USER_ID,
        "session_type": "TASK",
    }))
    assigned_robot_id = session.get("assigned_robot_id")
    print(f"             배정된 robot_id={assigned_robot_id}")

    if assigned_robot_id:
        print("  [PASS] 즉시 배정 성공")
    else:
        print("  [FAIL] 배정 안 됨")

    after_count = get("/robots/dispatch/count").json().get("available_count", 0)
    print(f"             배정 후 가용 수: {after_count} (전: {len(available)})")

    return session


def test_decoupled_assignment():
    """POST /sessions/{id}/assign → 배정만 단독 호출."""
    print("\n[dispatcher] 단독 배정 (POST /sessions/{id}/assign)")

    available = [r for r in get_robots() if r["is_available"]]
    if not available:
        print("             [SKIP] 가용 로봇 없음")
        return None

    _randomize_robot_positions(available)

    # 세션만 생성 (즉시 배정도 시도하지만, assign 엔드포인트를 별도로 검증)
    session = post("/sessions", {"user_id": USER_ID, "session_type": "TASK"}).json()
    sid = session.get("id")
    if not sid:
        print("             [SKIP] 세션 생성 실패")
        return None

    print(f"             세션 생성: id={sid} 현재 robot={session.get('assigned_robot_id')}")

    # 단독 배정 엔드포인트 호출
    data = ok("POST /sessions/{id}/assign", post(f"/sessions/{sid}/assign"))
    assigned_robot_id = data.get("assigned_robot_id")
    print(f"             assign 후 robot_id={assigned_robot_id} status={data.get('status')}")

    if assigned_robot_id:
        print("  [PASS] 단독 배정 성공")
    else:
        print("  [WARN] 가용 로봇 없어 배정 안 됨")

    return data


def test_low_battery_excluded():
    """배터리 부족 로봇은 배정되지 않아야 함."""
    print("\n[dispatcher] 배터리 낮은 로봇 제외 확인")

    # 가용 로봇 중 랜덤 1대 선택
    robots = get_robots()
    available = [r for r in robots if r["is_available"]]
    if not available:
        print("             [SKIP] 가용 로봇 없음")
        return

    target = random.choice(available)
    rid = target["id"]
    original_battery = target["battery"]

    # BATTERY_THRESHOLD 미만으로 랜덤 설정
    low_battery = random.randint(1, BATTERY_THRESHOLD - 1)
    patch(f"/robots/{rid}/state", {"battery_pct": low_battery})
    print(f"             robot_id={rid} 배터리 {original_battery}% → {low_battery}%")

    status = get("/robots/dispatch/status").json()
    robot = next((r for r in status.get("robots", []) if r["id"] == rid), None)
    if robot and not robot["is_available"]:
        print(f"  [PASS] 배터리 {low_battery}% 로봇 제외됨")
    else:
        print(f"  [FAIL] 배터리 {low_battery}% 로봇이 가용으로 표시됨")

    # 원래 배터리로 복구
    patch(f"/robots/{rid}/state", {"battery_pct": original_battery})
    print(f"             robot_id={rid} 배터리 복구 → {original_battery}%")


def test_offline_excluded():
    """오프라인 로봇은 배정되지 않아야 함."""
    print("\n[dispatcher] 오프라인 로봇 제외 확인")

    robots = get_robots()
    offline = [r for r in robots if not r["is_online"]]
    if offline:
        for r in offline:
            if not r["is_available"]:
                print(f"  [PASS] robot_id={r['id']} (offline) 제외됨")
            else:
                print(f"  [FAIL] robot_id={r['id']} (offline) 가용으로 표시됨")
    else:
        print("             [SKIP] 오프라인 로봇 없음")


def test_non_idle_excluded():
    """IDLE 아닌 로봇은 배정되지 않아야 함."""
    print("\n[dispatcher] IDLE 아닌 로봇 제외 확인")

    session = post("/sessions", {"user_id": USER_ID, "session_type": "TASK"}).json()
    assigned_id = session.get("assigned_robot_id")
    sid = session.get("id")

    if assigned_id:
        status = get("/robots/dispatch/status").json()
        assigned_robot = next((r for r in status.get("robots", []) if r["id"] == assigned_id), None)
        if assigned_robot and not assigned_robot["is_available"]:
            print(f"  [PASS] 배정된 robot_id={assigned_id} (mode={assigned_robot['mode']}) 제외됨")
        else:
            print(f"  [FAIL] 배정된 로봇이 여전히 가용으로 표시됨")
    else:
        print("             [SKIP] 배정된 로봇 없음")

    if sid:
        post(f"/sessions/{sid}/end")


def cleanup(session: dict | None):
    if session and session.get("id"):
        post(f"/sessions/{session['id']}/end")
        print(f"  (세션 {session['id']} 종료)")


if __name__ == "__main__":
    health()

    test_dispatch_status()
    test_dispatch_count()

    s1 = test_coupled_assignment()
    cleanup(s1)

    s2 = test_decoupled_assignment()
    cleanup(s2)

    test_low_battery_excluded()
    test_offline_excluded()
    test_non_idle_excluded()

    print("\n완료.")
