#!/usr/bin/env python3
"""
nav_state 업데이트 확인 스크립트.
로봇을 Fountain(id=10)으로 보내면서 nav_state가 IDLE 외의 값으로 바뀌는지 모니터링.

Usage:
    python scripts/test_nav_state.py --robot 1   # malle_15
    python scripts/test_nav_state.py --robot 2   # malle_17
"""

import argparse
import httpx
import time

BASE = "http://localhost:8000/api/v1"
POI_ID = 10  # Fountain


def post(path, **kw):
    return httpx.post(f"{BASE}{path}", timeout=5.0, **kw)


def get(path, **kw):
    return httpx.get(f"{BASE}{path}", timeout=3.0, **kw)


def fetch_nav_state(robot_id):
    r = get(f"/robots/{robot_id}")
    if r.status_code == 200:
        return r.json().get("state", {}).get("nav_state", "?")
    return "?"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", type=int, default=1, help="robot_id (1=malle_15, 2=malle_17)")
    args = parser.parse_args()
    robot_id = args.robot
    user_id = robot_id  # user_id == robot_id 가정

    print(f"[test] robot_id={robot_id} → Fountain(poi_id={POI_ID}) 이동 테스트")
    print(f"[test] 현재 nav_state: {fetch_nav_state(robot_id)}")

    # 기존 세션 정리
    result = get("/sessions/active")
    for s in result.json().get("sessions", []):
        if s["assigned_robot_id"] == robot_id:
            post(f"/sessions/{s['id']}/end")
            print(f"[test] 기존 세션 {s['id']} 종료")

    # 세션 생성
    r = post("/sessions", json={"user_id": user_id, "session_type": "TASK", "robot_id": robot_id})
    session_id = r.json()["id"]
    print(f"[test] 세션 생성: session_id={session_id}")

    # guide queue 추가
    post(f"/sessions/{session_id}/guide-queue", json={"poi_id": POI_ID})
    print(f"[test] Fountain(id={POI_ID}) 추가")

    # execute
    r = post(f"/sessions/{session_id}/guide-queue/execute")
    print(f"[test] execute → {r.json()}")

    # 모니터링
    print(f"\n{'─'*40}")
    print(f"  time   nav_state")
    print(f"{'─'*40}")
    start = time.time()
    prev = None
    try:
        while time.time() - start < 60:
            nav = fetch_nav_state(robot_id)
            if nav != prev:
                print(f"  {time.time()-start:5.1f}s  {nav}  ← 변경!")
                prev = nav
            else:
                print(f"  {time.time()-start:5.1f}s  {nav}", end="\r")
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass

    print(f"\n[test] 종료. 세션 {session_id} 정리 중...")
    post(f"/sessions/{session_id}/end")


if __name__ == "__main__":
    main()
