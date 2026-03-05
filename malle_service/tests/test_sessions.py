from base import ok, get, post, patch, health

USER_ID = 1  # seed 데이터 기준


def test_create_session():
    print("\n[sessions] 세션 생성 (TASK)")
    data = ok("POST /sessions", post("/sessions", {
        "user_id": USER_ID,
        "session_type": "TASK",
    }))
    if data.get("id"):
        sid = data["id"]
        print(f"           → session_id={sid} status={data.get('status')} robot={data.get('assigned_robot_id')} pin={data.get('match_pin')}")
    return data


def test_create_time_session():
    print("\n[sessions] 세션 생성 (TIME, 30분)")
    data = ok("POST /sessions (TIME)", post("/sessions", {
        "user_id": USER_ID,
        "session_type": "TIME",
        "requested_minutes": 30,
    }))
    if data.get("id"):
        print(f"           → session_id={data['id']} status={data.get('status')}")
    return data


def test_list_active():
    print("\n[sessions] 활성 세션 목록")
    data = ok("GET /sessions/active", get("/sessions/active"))
    sessions = data.get("sessions", [])
    print(f"           → 활성 세션 수: {len(sessions)}")
    for s in sessions:
        print(f"             id={s['id']} type={s['session_type']} status={s['status']} robot={s.get('assigned_robot_id')}")
    return sessions


def test_get_session(session_id: int):
    print(f"\n[sessions] 단건 조회 (id={session_id})")
    data = ok(f"GET /sessions/{session_id}", get(f"/sessions/{session_id}"))
    if data:
        print(f"           → status={data.get('status')}")
    return data


def test_status_flow(session_id: int, pin: str):
    print(f"\n[sessions] 상태 흐름 테스트 (id={session_id})")

    ok("→ APPROACHING", patch(f"/sessions/{session_id}/status", {"status": "APPROACHING"}))
    ok("→ MATCHING",    patch(f"/sessions/{session_id}/status", {"status": "MATCHING"}))

    print(f"\n[sessions] PIN 검증 (pin={pin})")
    ok("POST verify-pin (정답)", post(f"/sessions/{session_id}/verify-pin", {"pin": pin}))

    ok("→ ENDED", post(f"/sessions/{session_id}/end"))


def test_wrong_pin(session_id: int):
    print(f"\n[sessions] PIN 검증 실패 케이스 (id={session_id})")
    # MATCHING 상태여야 함
    patch(f"/sessions/{session_id}/status", {"status": "MATCHING"})
    resp = post(f"/sessions/{session_id}/verify-pin", {"pin": "0000"})
    if resp.status_code == 400:
        print("  [PASS] 잘못된 PIN 거부 (400)")
    else:
        print(f"  [FAIL] 예상 400, 실제 {resp.status_code}")


def test_assign_robot(session_id: int):
    print(f"\n[sessions] 로봇 배정 단독 호출 (id={session_id})")
    before = get(f"/sessions/{session_id}").json()
    print(f"           배정 전 robot={before.get('assigned_robot_id')} status={before.get('status')}")

    data = ok("POST /sessions/{id}/assign", post(f"/sessions/{session_id}/assign"))
    print(f"           배정 후 robot={data.get('assigned_robot_id')} status={data.get('status')}")

    if data.get("assigned_robot_id"):
        print("  [PASS] 로봇 배정 성공")
    else:
        print("  [WARN] 가용 로봇 없어 배정 안 됨")
    return data


def test_reassign_robot(session_id: int):
    print(f"\n[sessions] 로봇 재배정 (id={session_id})")
    before = get(f"/sessions/{session_id}").json()
    prev_robot = before.get("assigned_robot_id")
    print(f"           재배정 전 robot={prev_robot}")

    data = ok("POST /sessions/{id}/assign (재배정)", post(f"/sessions/{session_id}/assign"))
    new_robot = data.get("assigned_robot_id")
    print(f"           재배정 후 robot={new_robot}")

    if new_robot and new_robot != prev_robot:
        print("  [PASS] 다른 로봇으로 재배정됨")
    elif new_robot == prev_robot:
        print("  [WARN] 같은 로봇 재배정 (다른 가용 로봇 없음)")
    else:
        print("  [WARN] 가용 로봇 없어 배정 안 됨")


def test_assign_ended_session():
    print("\n[sessions] 종료된 세션에 배정 시도 (400 기대)")
    s = post("/sessions", {"user_id": USER_ID, "session_type": "TASK"}).json()
    sid = s.get("id")
    if not sid:
        print("  [SKIP] 세션 생성 실패")
        return
    post(f"/sessions/{sid}/end")
    resp = post(f"/sessions/{sid}/assign")
    if resp.status_code == 400:
        print("  [PASS] ENDED 세션 배정 거부 (400)")
    else:
        print(f"  [FAIL] 예상 400, 실제 {resp.status_code}")


def test_follow_tag(session_id: int):
    print(f"\n[sessions] follow-tag 설정 (id={session_id})")
    ok("PATCH follow-tag", patch(f"/sessions/{session_id}/follow-tag", {
        "tag_code": 42,
        "tag_family": "tag36h11",
    }))


if __name__ == "__main__":
    health()

    s1 = test_create_session()
    s2 = test_create_time_session()

    test_list_active()

    if s1.get("id"):
        sid = s1["id"]
        pin = s1.get("match_pin", "0000")
        test_get_session(sid)
        test_status_flow(sid, pin)

    if s2.get("id"):
        sid2 = s2["id"]
        test_assign_robot(sid2)
        test_reassign_robot(sid2)
        test_wrong_pin(sid2)
        test_follow_tag(sid2)
        post(f"/sessions/{sid2}/end")
        print(f"  (세션 {sid2} 종료)")

    test_assign_ended_session()

    print("\n완료.")
