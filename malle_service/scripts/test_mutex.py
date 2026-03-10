#!/usr/bin/env python3
"""
Mutex 테스트 스크립트 — guide 모드로 두 로봇 동시 이동, zone-based mutex 검증.

시나리오:
  Robot 1 (malle_15, id=1): ABC마트 → 하이마트
  Robot 2 (malle_17, id=2): 하이마트 → ABC마트  (반대 방향 → 충돌 유발)

Usage:
    cd malle_service
    python scripts/test_mutex.py
"""

import httpx
import threading
import time
import sys

BASE        = "http://localhost:8000/api/v1"
POLL_INTERVAL = 0.5
USER_IDS    = {1: 1, 2: 2}   # robot_id → user_id

ROBOT_ROUTES = {
    1: [(21, "노스페이스")],   # malle_15: ABC마트 출발 → 노스페이스
    2: [(19, "ABC마트")],     # malle_17: 하이마트 출발 → ABC마트
}


# ─────────────────────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────────────────────

def post(path, **kwargs):
    return httpx.post(f"{BASE}{path}", timeout=5.0, **kwargs)

def get(path, **kwargs):
    return httpx.get(f"{BASE}{path}", timeout=3.0, **kwargs)

def patch(path, **kwargs):
    return httpx.patch(f"{BASE}{path}", timeout=3.0, **kwargs)


def create_session(robot_id: int) -> int:
    r = post("/sessions", json={
        "user_id": USER_IDS[robot_id],
        "session_type": "TASK",
        "robot_id": robot_id,
    })
    if r.status_code != 200:
        print(f"  [!] 세션 생성 실패 R{robot_id}: {r.text}")
        sys.exit(1)
    session = r.json()
    print(f"  [R{robot_id}] 세션 생성 → session_id={session['id']}  robot={session['assigned_robot_id']}")
    return session["id"]


def add_guide_item(session_id: int, poi_id: int, seq: int):
    r = post(f"/sessions/{session_id}/guide-queue", json={"poi_id": poi_id, "seq": seq})
    if r.status_code != 200:
        print(f"  [!] guide item 추가 실패: {r.text}")


def execute_guide(session_id: int):
    r = post(f"/sessions/{session_id}/guide-queue/execute")
    if r.status_code != 200:
        print(f"  [!] guide execute 실패: {r.text}")


def end_session(session_id: int):
    post(f"/sessions/{session_id}/end")


def fetch_state(robot_id: int) -> dict:
    try:
        r = get(f"/robots/{robot_id}")
        if r.status_code == 200:
            return r.json().get("state") or {}
    except Exception:
        pass
    return {}


def active_pid_zones() -> list[str]:
    try:
        r = get("/zones")
        return [z["name"] for z in r.json()
                if z.get("is_active") and z["name"].startswith("pid_lock_")]
    except Exception:
        return []


def reset_pid_zones():
    """테스트 시작 전 모든 pid_lock zone 비활성화."""
    try:
        r = get("/zones")
        for z in r.json():
            if z["name"].startswith("pid_lock_") and z.get("is_active"):
                patch(f"/zones/{z['id']}", json={"is_active": False})
                print(f"  [reset] zone 비활성화: {z['name']}")
    except Exception as e:
        print(f"  [!] zone reset 실패: {e}")


# ─────────────────────────────────────────────────────────────
# 로봇별 guide 실행 (세션 생성 → 큐 적재 → execute)
# ─────────────────────────────────────────────────────────────

def run_robot(robot_id: int, done_event: threading.Event):
    route = ROBOT_ROUTES[robot_id]
    print(f"\n[R{robot_id}] 출발 — {' → '.join(l for _, l in route)}")

    session_id = create_session(robot_id)

    for seq, (poi_id, label) in enumerate(route, start=1):
        add_guide_item(session_id, poi_id, seq)
        print(f"  [R{robot_id}] guide item 추가: {label} (poi_id={poi_id}, seq={seq})")

    execute_guide(session_id)
    print(f"  [R{robot_id}] guide 시작")

    # 이동 완료 대기 (nav_state IDLE 복귀 반복)
    navigating = False
    while True:
        state = fetch_state(robot_id)
        nav_state = state.get("nav_state", "IDLE")
        if nav_state in ("MOVING", "OCCUPIED"):
            navigating = True
        elif navigating and nav_state == "IDLE":
            print(f"\n  [R{robot_id}] ✓ 전체 경로 완료")
            break
        time.sleep(POLL_INTERVAL)

    end_session(session_id)
    done_event.set()


# ─────────────────────────────────────────────────────────────
# 모니터링
# ─────────────────────────────────────────────────────────────

def monitor(done_events: list[threading.Event]):
    print(f"\n{'─'*70}")
    print(f"  {'time':>6}  "
          f"{'R1 nav':>10}  {'R1 poi':>6}  "
          f"{'R2 nav':>10}  {'R2 poi':>6}  "
          f"active pid zones")
    print(f"{'─'*70}")

    start = time.time()
    while not all(e.is_set() for e in done_events):
        s1 = fetch_state(1)
        s2 = fetch_state(2)
        zones = active_pid_zones()
        elapsed = time.time() - start
        print(
            f"  {elapsed:>6.1f}s  "
            f"{s1.get('nav_state','?'):>10}  {str(s1.get('target_poi_id','-')):>6}  "
            f"{s2.get('nav_state','?'):>10}  {str(s2.get('target_poi_id','-')):>6}  "
            f"{', '.join(zones) or '-'}",
            flush=True,
        )
        time.sleep(POLL_INTERVAL)

    print(f"{'─'*70}")
    print("  [모니터링 종료]")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  Mutex 테스트 시작 (guide 모드)")
    print("=" * 50)

    reset_pid_zones()

    for rid in (1, 2):
        state = fetch_state(rid)
        if not state:
            print(f"[!] robot_id={rid} 상태 조회 실패 — 연결 확인 필요")
            sys.exit(1)
        print(f"  R{rid}: nav={state.get('nav_state')}  "
              f"pos=({state.get('x_m',0):.2f}, {state.get('y_m',0):.2f})")

    input("\n로봇 위치 확인 완료 시 Enter...")

    done1 = threading.Event()
    done2 = threading.Event()

    t1 = threading.Thread(target=run_robot, args=(1, done1), daemon=True)
    t2 = threading.Thread(target=run_robot, args=(2, done2), daemon=True)
    tm = threading.Thread(target=monitor, args=([done1, done2],), daemon=True)

    tm.start()
    t1.start()
    time.sleep(5)  # R1이 먼저 출발해서 경합 POI 점유할 시간 확보
    t2.start()

    t1.join()
    t2.join()
    tm.join(timeout=2)

    print("\n  Done.")


if __name__ == "__main__":
    main()
