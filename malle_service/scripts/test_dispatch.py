#!/usr/bin/env python3
"""
Dispatch 테스트 스크립트 — 위치 기반 로봇 배정 + 이동 모니터링.

Usage:
    cd malle_service
    python scripts/test_dispatch.py
"""

import httpx
import sys
import time

BASE = "http://localhost:8000/api/v1"
USER_ID = 1
SESSION_TYPE = "TASK"
POLL_INTERVAL = 0.5  # 위치 갱신 주기 (초)
TARGET_Y = 1.44
TARGET_X = 1.91

# robot_id → bridge_node URL
BRIDGE_URLS = {
    2: "http://192.168.1.50:9100",  # malle_17
}


def step(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


def check_robots():
    step("Step 1. 로봇 상태 확인")
    r = httpx.get(f"{BASE}/robots")
    robots = r.json()["robots"]
    for robot in robots:
        state = robot.get("state") or {}
        print(
            f"  id={robot['id']} {robot['name']}"
            f"  online={robot['is_online']}  battery={robot['battery_pct']}%"
            f"  pos=({state.get('x_m', '?')}, {state.get('y_m', '?')})"
        )


def check_dispatch():
    step("Step 2. Dispatch 가능 여부 확인")
    r = httpx.get(f"{BASE}/robots/dispatch/status")
    data = r.json()
    print(f"  available: {data['available_robots']} / {data['total_robots']}")
    for robot in data["robots"]:
        print(
            f"  id={robot['id']} {robot['name']}"
            f"  available={robot['is_available']}"
            f"  pos=({robot['position']['x']}, {robot['position']['y']})"
        )
    return data["available_robots"] > 0


def create_session():
    step("Step 3. 세션 생성 → dispatch")
    print(f"  [dispatch 기준 위치] target=({TARGET_X}, {TARGET_Y})")
    r = httpx.post(f"{BASE}/sessions", json={
        "user_id": USER_ID,
        "session_type": SESSION_TYPE,
        "target_x": TARGET_X,
        "target_y": TARGET_Y,
    })
    if r.status_code != 200:
        print(f"  [!] HTTP {r.status_code}: {r.text}")
        return None
    session = r.json()
    if "id" not in session:
        print(f"  [!] 응답 오류: {session}")
        return None
    print(f"  session_id       : {session['id']}")
    print(f"  status           : {session['status']}")
    print(f"  assigned_robot_id: {session['assigned_robot_id']}")
    print(f"  match_pin        : {session['match_pin']}")
    return session


def send_navigate(robot_id: int, x: float, y: float):
    bridge_url = BRIDGE_URLS.get(robot_id)
    if not bridge_url:
        print(f"  [!] robot_id={robot_id} bridge URL 미등록 — 이동 명령 스킵")
        return
    print(f"  → {bridge_url}/bridge/navigate  target=({x}, {y})")
    try:
        r = httpx.post(f"{bridge_url}/bridge/navigate", json={"x": x, "y": y, "theta": 0.0}, timeout=3.0)
        print(f"  응답: {r.json()}")
    except Exception as e:
        print(f"  [!] bridge 호출 실패: {e}")


def monitor_robot(robot_id: int):
    """nav_state가 IDLE로 복귀하면 도착으로 판단하고 종료."""
    step(f"Step 4. 로봇 id={robot_id} 이동 모니터링 (도착 시 자동 종료, Ctrl+C로 중단)")
    print(f"  {'time':>6}  {'x_m':>8}  {'y_m':>8}  {'nav_state':>12}  {'speed':>7}")
    print(f"  {'-'*6}  {'-'*8}  {'-'*8}  {'-'*12}  {'-'*7}")

    start = time.time()
    navigating = False  # 한 번이라도 MOVING/OCCUPIED 상태를 봤는지
    try:
        while True:
            r = httpx.get(f"{BASE}/robots/{robot_id}")
            if r.status_code == 200:
                robot = r.json()
                state = robot.get("state") or {}
                nav_state = state.get('nav_state', 'IDLE')
                elapsed = time.time() - start
                print(
                    f"  {elapsed:>6.1f}s"
                    f"  {state.get('x_m', 0):>8.3f}"
                    f"  {state.get('y_m', 0):>8.3f}"
                    f"  {nav_state:>12}"
                    f"  {state.get('speed_mps', 0):>6.3f}m/s",
                    flush=True,
                )
                if nav_state in ('MOVING', 'OCCUPIED'):
                    navigating = True
                elif navigating and nav_state == 'IDLE':
                    print("\n  [✓] 도착 확인 — 점유 해제합니다.")
                    return
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\n  모니터링 중단.")


def end_session(session_id: int):
    step("Step 5. 세션 종료")
    r = httpx.post(f"{BASE}/sessions/{session_id}/end")
    session = r.json()
    print(f"  status: {session['status']}")


def main():
    check_robots()

    if not check_dispatch():
        print("\n  [!] 가용 로봇 없음.")
        sys.exit(1)

    session = create_session()
    if not session:
        sys.exit(1)

    session_id = session["id"]
    robot_id = session.get("assigned_robot_id")

    if not robot_id:
        print("\n  [!] 로봇 배정 실패.")
        end_session(session_id)
        sys.exit(1)

    step(f"Step 4. bridge_node navigate → target=({TARGET_X}, {TARGET_Y})")
    send_navigate(robot_id, TARGET_X, TARGET_Y)

    monitor_robot(robot_id)

    end_session(session_id)
    print("\n  Done.")


if __name__ == "__main__":
    main()
