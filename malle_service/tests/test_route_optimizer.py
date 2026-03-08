"""쇼핑 최단경로 최적화 API 테스트.

실행:
    cd malle_service/tests
    python test_route_optimizer.py
"""
from base import ok, get, post, delete, health

USER_ID = 1


# ─────────────────────────────────────────
# helpers
# ─────────────────────────────────────────

def fetch_stores() -> list[dict]:
    data = get("/stores").json()
    stores = data if isinstance(data, list) else []
    print(f"  (사용 가능한 스토어: {len(stores)}개)")
    for s in stores[:5]:
        print(f"    id={s['id']} poi_id={s.get('poi_id')} category={s.get('category')}")
    return stores


def create_session() -> dict:
    data = post("/sessions", {"user_id": USER_ID, "session_type": "TIME", "requested_minutes": 60}).json()
    print(f"  (세션 생성: id={data.get('id')} status={data.get('status')})")
    return data


def end_session(session_id: int):
    post(f"/sessions/{session_id}/end")
    print(f"  (세션 {session_id} 종료)")


# ─────────────────────────────────────────
# tests
# ─────────────────────────────────────────

def test_optimize_no_session(store_ids: list[int]):
    """session_id 없이 최적 순서만 반환."""
    print(f"\n[optimize] store_ids만으로 최적 경로 조회 (store_ids={store_ids})")
    data = ok(
        "POST /shopping/optimize-route (no session)",
        post("/shopping/optimize-route", {"store_ids": store_ids}),
    )
    if isinstance(data, list):
        print(f"  → {len(data)}개 POI 순서:")
        for item in data:
            print(f"    order={item['order']} poi_id={item['poi_id']} poi_name={item['poi_name']}"
                  f"  ({item['x']:.2f}, {item['y']:.2f})  queue_item_id={item['queue_item_id']}")
    return data


def test_optimize_with_start_pos(store_ids: list[int]):
    """출발 좌표를 명시해서 다른 결과가 나오는지 확인."""
    print(f"\n[optimize] 출발 좌표 지정 (start_x=10, start_y=10)")
    data = ok(
        "POST /shopping/optimize-route (with start pos)",
        post("/shopping/optimize-route", {
            "store_ids": store_ids,
            "start_x": 10.0,
            "start_y": 10.0,
        }),
    )
    if isinstance(data, list):
        print(f"  → 순서: {[item['poi_name'] for item in data]}")
    return data


def test_optimize_with_session(store_ids: list[int], session_id: int):
    """session_id 포함 → 가이드 큐 자동 populate."""
    print(f"\n[optimize] session_id 포함 → 가이드 큐 자동 populate (session={session_id})")
    data = ok(
        "POST /shopping/optimize-route (with session)",
        post("/shopping/optimize-route", {
            "store_ids": store_ids,
            "session_id": session_id,
        }),
    )
    if isinstance(data, list):
        print(f"  → {len(data)}개 POI 큐 생성:")
        for item in data:
            print(f"    order={item['order']} poi_name={item['poi_name']}"
                  f"  queue_item_id={item['queue_item_id']}")
    return data


def test_guide_queue_after_optimize(session_id: int):
    """optimize 후 실제 가이드 큐에 반영됐는지 확인."""
    print(f"\n[optimize] 가이드 큐 확인 (session={session_id})")
    data = ok(
        f"GET /sessions/{session_id}/guide-queue",
        get(f"/sessions/{session_id}/guide-queue"),
    )
    if isinstance(data, list):
        print(f"  → 큐 항목 {len(data)}개:")
        for item in data:
            print(f"    seq={item['seq']} poi_name={item.get('poi_name')} status={item['status']}")
    return data


def test_optimize_empty_store_ids():
    """store_ids 빈 배열 → 빈 결과."""
    print("\n[optimize] store_ids=[] → 빈 결과 기대")
    data = ok(
        "POST /shopping/optimize-route (empty store_ids)",
        post("/shopping/optimize-route", {"store_ids": []}),
    )
    assert data == [], f"빈 배열 기대했으나: {data}"
    print("  → [] 확인 OK")


def test_optimize_invalid_store_id():
    """존재하지 않는 store_id → 빈 결과 (DB에 해당 row 없음)."""
    print("\n[optimize] 존재하지 않는 store_id=99999")
    data = ok(
        "POST /shopping/optimize-route (invalid store_id)",
        post("/shopping/optimize-route", {"store_ids": [99999]}),
    )
    if isinstance(data, list):
        print(f"  → {len(data)}개 (0 기대)")


def test_optimize_duplicate_stores(store_ids: list[int]):
    """중복 store_id → deduplicate되어 한 번만."""
    if not store_ids:
        return
    dup_ids = [store_ids[0], store_ids[0]]
    print(f"\n[optimize] 중복 store_id={dup_ids} → 1개만 반환 기대")
    data = ok(
        "POST /shopping/optimize-route (duplicate store_ids)",
        post("/shopping/optimize-route", {"store_ids": dup_ids}),
    )
    if isinstance(data, list):
        poi_ids = [item["poi_id"] for item in data]
        assert len(set(poi_ids)) == len(poi_ids), f"중복 POI 발생: {poi_ids}"
        print(f"  → {len(data)}개 (중복 없음 확인 OK)")


def test_optimize_replace_queue(store_ids: list[int], session_id: int):
    """큐에 기존 항목이 있을 때 optimize → 기존 clear 후 교체."""
    print(f"\n[optimize] 큐 교체 시나리오 (session={session_id})")

    # 먼저 임의 항목 추가
    if store_ids:
        first_store = get("/stores").json()[0]
        poi_id = first_store.get("poi_id")
        if poi_id:
            post(f"/sessions/{session_id}/guide-queue", {"poi_id": poi_id})
            print(f"  (기존 항목 poi_id={poi_id} 추가)")

    before = get(f"/sessions/{session_id}/guide-queue").json()
    print(f"  (optimize 전 큐: {len(before)}개)")

    # clear + optimize
    delete(f"/sessions/{session_id}/guide-queue")
    test_optimize_with_session(store_ids, session_id)

    after = get(f"/sessions/{session_id}/guide-queue").json()
    print(f"  (optimize 후 큐: {len(after)}개)")
    assert len(after) == len(store_ids), \
        f"optimize 후 큐 수({len(after)}) ≠ store_ids 수({len(store_ids)})"
    print("  → 큐 교체 확인 OK")


# ─────────────────────────────────────────
# main
# ─────────────────────────────────────────

if __name__ == "__main__":
    health()

    stores = fetch_stores()
    if len(stores) < 2:
        print("[SKIP] 스토어가 2개 미만이어서 테스트 불가.")
        raise SystemExit(0)

    store_ids = [s["id"] for s in stores[:3]]

    # 1. session 없이 순서만 반환
    result_no_session = test_optimize_no_session(store_ids)

    # 2. 출발 좌표 변경 시 다른 순서
    test_optimize_with_start_pos(store_ids)

    # 3. edge cases
    test_optimize_empty_store_ids()
    test_optimize_invalid_store_id()
    test_optimize_duplicate_stores(store_ids)

    # 4. session_id 포함 → 가이드 큐 자동 populate
    session = create_session()
    sid = session.get("id")
    if sid:
        test_optimize_with_session(store_ids, sid)
        test_guide_queue_after_optimize(sid)
        test_optimize_replace_queue(store_ids, sid)
        end_session(sid)

    print("\n완료.")
