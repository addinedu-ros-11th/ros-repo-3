from base import ok, get, post, patch, delete, health

ROBOT_ID = 1  # seed 데이터 기준


def test_list_robots():
    print("\n[robots] 전체 목록 조회")
    data = ok("GET /robots", get("/robots"))
    robots = data.get("robots", [])
    print(f"         → 로봇 수: {len(robots)}")
    for r in robots:
        print(f"           id={r['id']} name={r['name']} mode={r['current_mode']} battery={r['battery_pct']}%")
    return robots


def test_get_robot():
    print(f"\n[robots] 단건 조회 (id={ROBOT_ID})")
    data = ok(f"GET /robots/{ROBOT_ID}", get(f"/robots/{ROBOT_ID}"))
    if data:
        print(f"         → {data.get('name')} | online={data.get('is_online')}")


def test_update_state():
    print(f"\n[robots] 상태 업데이트 (id={ROBOT_ID})")
    ok(f"PATCH /robots/{ROBOT_ID}/state", patch(f"/robots/{ROBOT_ID}/state", {
        "x_m": 150.0,
        "y_m": 100.0,
        "theta_rad": 1.57,
        "battery_pct": 75,
    }))


def test_estop():
    print(f"\n[robots] E-Stop 발동/해제 (id={ROBOT_ID})")
    ok(f"POST /robots/{ROBOT_ID}/estop", post(f"/robots/{ROBOT_ID}/estop", {
        "source": "DASHBOARD"
    }))
    ok(f"DELETE /robots/{ROBOT_ID}/estop", delete(f"/robots/{ROBOT_ID}/estop"))


def test_teleop():
    print(f"\n[robots] 텔레옵 (id={ROBOT_ID})")
    ok("POST teleop/start", post(f"/robots/{ROBOT_ID}/teleop/start"))
    ok("POST teleop/cmd (전진)", post(f"/robots/{ROBOT_ID}/teleop/cmd", {
        "linear_x": 0.3,
        "angular_z": 0.0,
    }))
    ok("POST teleop/cmd (좌회전)", post(f"/robots/{ROBOT_ID}/teleop/cmd", {
        "linear_x": 0.0,
        "angular_z": 0.5,
    }))
    ok("POST teleop/stop", post(f"/robots/{ROBOT_ID}/teleop/stop"))


def test_command():
    print(f"\n[robots] 명령 전송 (id={ROBOT_ID})")
    ok("POST /robots/{id}/command (return_station)", post(f"/robots/{ROBOT_ID}/command", {
        "command": "return_station"
    }))


if __name__ == "__main__":
    health()
    test_list_robots()
    test_get_robot()
    test_update_state()
    test_estop()
    test_teleop()
    test_command()
    print("\n완료.")
