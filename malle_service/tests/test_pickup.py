from base import ok, get, post, patch, health

USER_ID = 1
PICKUP_POI_ID = 1   # Zara POI (seed 기준)
PRODUCT_ID = 1      # Linen Blend Shirt


def create_session() -> dict:
    data = post("/sessions", {"user_id": USER_ID, "session_type": "TASK"}).json()
    print(f"  (세션 생성: id={data.get('id')})")
    return data


def test_create_pickup_order(session_id: int) -> dict:
    print(f"\n[pickup] 픽업 주문 생성 (session={session_id})")
    data = ok("POST pickup-orders", post(f"/sessions/{session_id}/pickup-orders", {
        "pickup_poi_id": PICKUP_POI_ID,
        "created_channel": "APP",
        "items": [
            {"product_id": PRODUCT_ID, "qty": 2, "unit_price": 45.90}
        ]
    }))
    if data.get("id"):
        print(f"         → order_id={data['id']} status={data.get('status')}")
    return data


def test_get_order(session_id: int, order_id: int):
    print(f"\n[pickup] 주문 조회 (order={order_id})")
    data = ok(f"GET pickup-orders/{order_id}", get(f"/sessions/{session_id}/pickup-orders/{order_id}"))
    if data:
        print(f"         → status={data.get('status')} items={len(data.get('items', []))}")


def test_status_flow(session_id: int, order_id: int):
    print(f"\n[pickup] 상태 흐름 (order={order_id})")
    for status in ["ROBOT_MOVING", "ARRIVED", "STAFF_PICKING", "LOADED"]:
        ok(f"  → {status}", patch(
            f"/sessions/{session_id}/pickup-orders/{order_id}/status",
            {"status": status}
        ))


def test_staff_pin(session_id: int, order_id: int):
    print(f"\n[pickup] staff-pin 생성 (order={order_id})")
    data = ok("POST staff-pin", post(
        f"/sessions/{session_id}/pickup-orders/{order_id}/staff-pin"
    ))
    if data:
        pin = data.get("staff_pin") or data.get("pin")
        print(f"         → pin={pin}")
    return data


def test_meet(session_id: int, order_id: int):
    print(f"\n[pickup] 만남 확인 (order={order_id})")
    ok("PATCH meet", patch(
        f"/sessions/{session_id}/pickup-orders/{order_id}/meet",
        {"confirmed": True}
    ))


if __name__ == "__main__":
    health()

    session = create_session()
    sid = session.get("id")
    if not sid:
        print("[ERROR] 세션 생성 실패.")
        raise SystemExit(1)

    order = test_create_pickup_order(sid)
    oid = order.get("id")
    if not oid:
        print("[ERROR] 주문 생성 실패.")
        post(f"/sessions/{sid}/end")
        raise SystemExit(1)

    test_get_order(sid, oid)
    test_status_flow(sid, oid)
    test_staff_pin(sid, oid)
    test_meet(sid, oid)

    post(f"/sessions/{sid}/end")
    print(f"\n  (세션 {sid} 종료)")
    print("\n완료.")
