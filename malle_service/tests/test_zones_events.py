from base import ok, get, post, patch, delete, health

ROBOT_ID = 1


# ── Zones ──────────────────────────────────────────────

def test_list_zones():
    print("\n[zones] 목록 조회")
    data = ok("GET /zones", get("/zones"))
    zones = data if isinstance(data, list) else data.get("zones", [])
    print(f"        → {len(zones)}개")
    for z in zones:
        print(f"          id={z['id']} name={z['name']} active={z.get('is_active')}")
    return zones


def test_create_zone() -> dict:
    print("\n[zones] 구역 생성")
    data = ok("POST /zones", post("/zones", {
        "name": "테스트 제한 구역",
        "polygon_wkt": "POLYGON((10 10, 50 10, 50 50, 10 50, 10 10))",
        "zone_kind": "restricted",
        "is_active": True,
    }))
    if data.get("id"):
        print(f"        → zone_id={data['id']}")
    return data


def test_update_zone(zone_id: int):
    print(f"\n[zones] 구역 수정 (id={zone_id})")
    ok("PATCH /zones/{id}", patch(f"/zones/{zone_id}", {
        "is_active": False,
        "name": "테스트 구역 (비활성)",
    }))


def test_delete_zone(zone_id: int):
    print(f"\n[zones] 구역 삭제 (id={zone_id})")
    ok("DELETE /zones/{id}", delete(f"/zones/{zone_id}"))


# ── Events ─────────────────────────────────────────────

def test_list_events():
    print("\n[events] 목록 조회")
    data = ok("GET /events", get("/events"))
    events = data if isinstance(data, list) else data.get("events", [])
    print(f"         → {len(events)}개")
    for e in events[:3]:
        print(f"           id={e['id']} type={e.get('type')} severity={e.get('severity')}")


def test_create_event():
    print("\n[events] 이벤트 생성")
    data = ok("POST /events", post("/events", {
        "robot_id": ROBOT_ID,
        "type": "LOW_BATTERY",
        "severity": "WARN",
        "payload_json": {"battery_pct": 15},
    }))
    if data.get("id"):
        print(f"         → event_id={data['id']}")


# ── Missions ───────────────────────────────────────────

def test_list_missions():
    print("\n[missions] 목록 조회")
    data = ok("GET /missions", get("/missions"))
    missions = data if isinstance(data, list) else data.get("missions", [])
    print(f"           → {len(missions)}개")
    for m in missions[:3]:
        print(f"             id={m['id']} type={m.get('type')} status={m.get('status')}")
    return missions


def test_get_mission(mission_id: int):
    print(f"\n[missions] 단건 조회 (id={mission_id})")
    data = ok(f"GET /missions/{mission_id}", get(f"/missions/{mission_id}"))
    if data:
        print(f"           → type={data.get('type')} status={data.get('status')}")


def test_update_mission_status(mission_id: int):
    print(f"\n[missions] 상태 변경 → IN_PROGRESS (id={mission_id})")
    ok("PATCH mission status", patch(f"/missions/{mission_id}/status", {
        "status": "IN_PROGRESS"
    }))


if __name__ == "__main__":
    health()

    # Zones
    existing = test_list_zones()
    zone = test_create_zone()
    if zone.get("id"):
        test_update_zone(zone["id"])
        test_delete_zone(zone["id"])

    # Events
    test_list_events()
    test_create_event()
    test_list_events()

    # Missions
    missions = test_list_missions()
    if missions:
        mid = missions[0]["id"]
        test_get_mission(mid)
        test_update_mission_status(mid)

    print("\n완료.")
