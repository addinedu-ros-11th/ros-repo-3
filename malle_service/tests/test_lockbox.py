from base import ok, get, post, health

ROBOT_ID = 1
SESSION_ID_FOR_TOKEN = 1   # 미리 존재하는 세션 ID (또는 테스트용 세션 생성 필요)


def create_session() -> int:
    resp = post("/sessions", {"user_id": 1, "session_type": "TASK"})
    data = resp.json()
    sid = data.get("id")
    print(f"  (세션 생성: id={sid})")
    return sid


def test_get_slots():
    print(f"\n[lockbox] 슬롯 목록 (robot={ROBOT_ID})")
    data = ok(f"GET /robots/{ROBOT_ID}/lockbox", get(f"/robots/{ROBOT_ID}/lockbox"))
    slots = data.get("slots", data) if isinstance(data, dict) else data
    if isinstance(slots, list):
        for s in slots:
            print(f"           slot={s.get('slot_no')} status={s.get('status')} size={s.get('size_label')}")
    return slots


def test_get_logs():
    print(f"\n[lockbox] 이용 로그 (robot={ROBOT_ID})")
    data = ok(f"GET /robots/{ROBOT_ID}/lockbox/logs", get(f"/robots/{ROBOT_ID}/lockbox/logs"))
    logs = data if isinstance(data, list) else data.get("logs", [])
    print(f"           → 로그 수: {len(logs)}")


def test_create_token(session_id: int) -> dict:
    print(f"\n[lockbox] 토큰 생성 (session={session_id})")
    data = ok("POST lockbox/tokens", post(f"/robots/{ROBOT_ID}/lockbox/tokens", {
        "session_id": session_id,
    }))
    if data:
        token = data.get("token")
        slot_id = data.get("slot_id")
        print(f"           → token={token} slot_id={slot_id}")
    return data


def test_verify_token(session_id: int, token: str) -> dict:
    print(f"\n[lockbox] 토큰 검증 (token={token})")
    data = ok("POST lockbox/verify-token", post(f"/robots/{ROBOT_ID}/lockbox/verify-token", {
        "token": token,
        "session_id": session_id,
    }))
    return data


def test_open_slot(slot_no: int = 1):
    print(f"\n[lockbox] 슬롯 열기 (slot={slot_no})")
    ok(f"POST lockbox/{slot_no}/open", post(f"/robots/{ROBOT_ID}/lockbox/{slot_no}/open"))


if __name__ == "__main__":
    health()

    session_id = create_session()

    test_get_slots()
    test_get_logs()

    token_data = test_create_token(session_id)
    token = token_data.get("token") if token_data else None

    if token:
        test_verify_token(session_id, token)

    test_open_slot(slot_no=1)

    post(f"/sessions/{session_id}/end")
    print(f"\n  (세션 {session_id} 종료)")
    print("\n완료.")
