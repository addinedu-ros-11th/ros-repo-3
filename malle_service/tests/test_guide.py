from base import ok, get, post, patch, delete, health

USER_ID = 1
POI_IDS = [1, 2, 3]  # Zara, Nike, Apple (seed 기준)


def create_session() -> dict:
    data = post("/sessions", {"user_id": USER_ID, "session_type": "TASK"}).json()
    print(f"  (세션 생성: id={data.get('id')} status={data.get('status')})")
    return data


def test_add_queue_items(session_id: int) -> list:
    print(f"\n[guide] POI 추가 (session={session_id})")
    items = []
    for poi_id in POI_IDS:
        data = ok(f"  POST guide-queue (poi={poi_id})", post(f"/sessions/{session_id}/guide-queue", {
            "poi_id": poi_id
        }))
        if data.get("id"):
            items.append(data)
            print(f"           → item_id={data['id']} poi={data.get('poi_name')}")
    return items


def test_list_queue(session_id: int):
    print(f"\n[guide] 큐 목록 조회 (session={session_id})")
    data = ok("GET guide-queue", get(f"/sessions/{session_id}/guide-queue"))
    if isinstance(data, list):
        print(f"         → {len(data)}개 항목")
        for item in data:
            print(f"           order={item.get('order')} poi={item.get('poi_name')} status={item.get('status')}")
    return data


def test_update_item_status(session_id: int, item_id: int):
    print(f"\n[guide] 항목 상태 변경 → DONE (item={item_id})")
    ok(f"PATCH guide-queue/{item_id}", patch(
        f"/sessions/{session_id}/guide-queue/{item_id}",
        {"status": "DONE"}
    ))


def test_delete_item(session_id: int, item_id: int):
    print(f"\n[guide] 항목 삭제 (item={item_id})")
    ok(f"DELETE guide-queue/{item_id}", delete(f"/sessions/{session_id}/guide-queue/{item_id}"))


def test_execute_queue(session_id: int):
    print(f"\n[guide] 큐 실행 (session={session_id})")
    ok("POST guide-queue/execute", post(f"/sessions/{session_id}/guide-queue/execute"))


def test_clear_queue(session_id: int):
    print(f"\n[guide] 큐 전체 삭제 (session={session_id})")
    ok("DELETE guide-queue (전체)", delete(f"/sessions/{session_id}/guide-queue"))


if __name__ == "__main__":
    health()

    session = create_session()
    sid = session.get("id")
    if not sid:
        print("[ERROR] 세션 생성 실패. 종료.")
        raise SystemExit(1)

    items = test_add_queue_items(sid)
    test_list_queue(sid)

    if len(items) >= 2:
        test_update_item_status(sid, items[0]["id"])
        test_delete_item(sid, items[1]["id"])

    test_execute_queue(sid)
    test_list_queue(sid)
    test_clear_queue(sid)
    test_list_queue(sid)

    post(f"/sessions/{sid}/end")
    print(f"\n  (세션 {sid} 종료)")
    print("\n완료.")
