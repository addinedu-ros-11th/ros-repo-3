#!/usr/bin/env python3
"""
test_occupied_mutex.py — PID 구간 Mutex (OCCUPIED) 통합 테스트

시나리오:
  1. 로봇A → nav_state=OCCUPIED, target_poi_id=TARGET_POI 설정
  2. 로봇B 세션 → guide-queue execute → 409 Conflict 확인
  3. HOLD초 후 자동으로 로봇A → nav_state=IDLE 해제 (PID 완료 시뮬레이션)
  4. 로봇B의 guide queue에 execution_batch_id가 채워지면 자동 재실행 성공

사전 조건:
  - malle_service가 실행 중 (기본 localhost:8000)
  - 로봇A, 로봇B가 DB에 존재
  - 로봇B 세션(--session-b)에 TARGET_POI를 가리키는 PENDING 항목이 있어야 함
    없으면 --add-item 플래그로 자동 추가

사용법:
  python3 test_occupied_mutex.py \\
      --robot-a 1 --robot-b 2 --session-b 5 --poi 4

  # 큐 항목 자동 추가 + 점유 시간 3초:
  python3 test_occupied_mutex.py \\
      --robot-a 1 --robot-b 2 --session-b 5 --poi 4 --add-item --hold 3
"""

import argparse
import sys
import time
import threading
import requests

# ── 전역 설정 ──────────────────────────────────────────────────────────────

BASE = "http://localhost:8000/api/v1"

PASS_MARK = "✓"
FAIL_MARK = "✗"
SEP = "─" * 62


# ── API 헬퍼 ───────────────────────────────────────────────────────────────

def api(method: str, path: str, **kwargs) -> requests.Response:
    return getattr(requests, method)(f"{BASE}{path}", timeout=5, **kwargs)


def get_robot(robot_id: int) -> requests.Response:
    return api("get", f"/robots/{robot_id}")


def patch_robot_state(robot_id: int, **fields) -> requests.Response:
    return api("patch", f"/robots/{robot_id}/state", json=fields)


def get_queue(session_id: int) -> requests.Response:
    return api("get", f"/sessions/{session_id}/guide-queue")


def execute_queue(session_id: int) -> requests.Response:
    return api("post", f"/sessions/{session_id}/guide-queue/execute")


def add_queue_item(session_id: int, poi_id: int) -> requests.Response:
    return api("post", f"/sessions/{session_id}/guide-queue", json={"poi_id": poi_id})


# ── 출력 헬퍼 ──────────────────────────────────────────────────────────────

def check(cond: bool, msg: str) -> bool:
    mark = PASS_MARK if cond else FAIL_MARK
    print(f"    {mark} {msg}")
    return cond


def step(n: int, desc: str):
    print(f"\n[STEP {n}] {desc}")
    print(SEP)


# ── 테스트 본체 ────────────────────────────────────────────────────────────

def run_test(args) -> bool:
    robot_a   = args.robot_a
    robot_b   = args.robot_b
    session_b = args.session_b
    poi_id    = args.poi
    hold      = args.hold

    passed = 0
    failed = 0

    print(f"\n{'=' * 62}")
    print("  PID 구간 Mutex (OCCUPIED) 통합 테스트")
    print(f"  로봇A={robot_a}  로봇B={robot_b}  세션B={session_b}  POI={poi_id}")
    print(f"  점유 유지 시간: {hold}초")
    print(f"{'=' * 62}")

    # ── STEP 0: 서버·로봇 연결 확인 ────────────────────────────────────────
    step(0, "서버 및 로봇 접근 확인")

    try:
        r = get_robot(robot_a)
    except requests.ConnectionError:
        print(f"    {FAIL_MARK} 서버에 연결할 수 없습니다: {BASE}")
        print("       malle_service가 실행 중인지 확인하세요.")
        return False

    if not check(r.status_code == 200, f"로봇A (id={robot_a}) 조회"):
        print(f"       응답: {r.text}")
        return False

    r = get_robot(robot_b)
    if not check(r.status_code == 200, f"로봇B (id={robot_b}) 조회"):
        print(f"       응답: {r.text}")
        return False

    # ── STEP 1: 세션B 큐 준비 ──────────────────────────────────────────────
    step(1, f"세션B({session_b}) 가이드 큐 준비 — poi_id={poi_id}")

    r = get_queue(session_b)
    if not check(r.status_code == 200, "큐 조회"):
        print(f"       응답: {r.text}")
        return False

    items = r.json()
    target_pending = [
        i for i in items
        if i["status"] == "PENDING"
        and i["is_active"]
        and i["poi_id"] == poi_id
        and i["execution_batch_id"] is None
    ]

    if target_pending:
        check(True, f"기존 PENDING 항목 확인 (item_id={target_pending[0]['id']})")
    elif args.add_item:
        r = add_queue_item(session_b, poi_id)
        if not check(r.status_code == 200, f"poi_id={poi_id} 항목 추가"):
            print(f"       응답: {r.text}")
            return False
        print(f"       item_id={r.json().get('id')} 추가됨")
    else:
        check(False, f"poi_id={poi_id} PENDING 항목 없음")
        print("       --add-item 플래그를 사용하면 자동으로 추가합니다.")
        return False

    # ── STEP 2: 로봇A OCCUPIED 설정 ────────────────────────────────────────
    step(2, f"로봇A({robot_a}) OCCUPIED 설정 — target_poi_id={poi_id}")

    r = patch_robot_state(robot_a, nav_state="OCCUPIED", target_poi_id=poi_id)
    if not check(r.status_code == 200, "PATCH nav_state=OCCUPIED"):
        print(f"       응답: {r.text}")
        return False

    state = r.json().get("state", {})
    check(state.get("nav_state") == "OCCUPIED", "nav_state=OCCUPIED 반영 확인")
    check(state.get("target_poi_id") == poi_id, f"target_poi_id={poi_id} 반영 확인")

    # ── STEP 3: execute → 409 확인 ─────────────────────────────────────────
    step(3, f"로봇B 세션({session_b}) execute → 409 Conflict 확인")

    r = execute_queue(session_b)
    key_pass = check(r.status_code == 409, f"409 Conflict 수신 (실제 상태코드: {r.status_code})")
    if key_pass:
        passed += 1
        detail = r.json().get("detail", "")
        check("occupied" in detail.lower(), f"오류 메시지 내용 확인: \"{detail}\"")
    else:
        failed += 1
        print(f"       응답 본문: {r.text}")

    # 409 후 batch_id가 None인지 확인 (트랜잭션 롤백 검증)
    q_items = get_queue(session_b).json()
    first_pending = next(
        (i for i in q_items if i["status"] == "PENDING" and i["is_active"]),
        None,
    )
    if first_pending:
        check(
            first_pending["execution_batch_id"] is None,
            "409 후 execution_batch_id=None 유지 (롤백 정상)",
        )

    # ── STEP 4: 자동 해제 타이머 ───────────────────────────────────────────
    step(4, f"자동 해제 타이머 — {hold}초 후 로봇A IDLE 전환")

    released = threading.Event()

    def release_occupied():
        r = patch_robot_state(robot_a, nav_state="IDLE")
        ok = r.status_code == 200
        status_str = "성공" if ok else f"실패 (HTTP {r.status_code})"
        # 타이머 스레드에서 출력 시 줄 정리
        print(f"\n    {PASS_MARK if ok else FAIL_MARK} [AUTO] 로봇A IDLE 해제 → {status_str}")
        released.set()

    timer = threading.Timer(hold, release_occupied)
    timer.start()
    check(True, f"{hold}초 카운트다운 시작")

    for remaining in range(hold, 0, -1):
        print(f"       남은 시간: {remaining:2d}초", end="\r")
        time.sleep(1)
    print(" " * 30, end="\r")  # 카운트다운 줄 지우기

    # ── STEP 5: 자동 재실행 확인 ───────────────────────────────────────────
    step(5, "로봇B 자동 재실행 확인 (최대 5초 폴링)")

    released.wait(timeout=hold + 2)  # 타이머 완료 보장

    auto_executed = False
    batch_id      = None
    deadline      = time.time() + 5

    while time.time() < deadline:
        q_items = get_queue(session_b).json()
        # 가장 seq가 낮은 active 항목 확인
        active = sorted(
            [i for i in q_items if i["is_active"]],
            key=lambda i: i["seq"],
        )
        if active and active[0].get("execution_batch_id") is not None:
            auto_executed = True
            batch_id = active[0]["execution_batch_id"]
            break
        time.sleep(0.3)

    key_pass2 = check(auto_executed, "자동 재실행 — execution_batch_id 채워짐")
    if key_pass2:
        passed += 1
        print(f"       mission_id(batch_id)={batch_id}")
    else:
        failed += 1
        print("       execution_batch_id가 여전히 None")
        print("       → robots.py OCCUPIED→IDLE 자동 재실행 로직을 확인하세요.")

    # ── 결과 요약 ──────────────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{'=' * 62}")
    if failed == 0:
        print(f"  PASS  핵심 검증 {total}/{total} 통과")
    else:
        print(f"  FAIL  핵심 검증 {passed}/{total} 통과 ({failed}개 실패)")
    print(f"{'=' * 62}\n")

    return failed == 0


def cleanup(robot_a: int):
    """테스트 후 로봇A 상태 초기화 (안전망)."""
    try:
        patch_robot_state(robot_a, nav_state="IDLE")
    except Exception:
        pass


# ── 진입점 ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PID 구간 OCCUPIED Mutex 통합 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 (큐 항목이 이미 있어야 함)
  python3 test_occupied_mutex.py --robot-a 1 --robot-b 2 --session-b 5 --poi 4

  # 큐 항목 자동 추가 + 점유 시간 3초
  python3 test_occupied_mutex.py --robot-a 1 --robot-b 2 --session-b 5 --poi 4 --add-item --hold 3

  # 서버 주소 변경
  python3 test_occupied_mutex.py --url http://192.168.1.10:8000 --robot-a 1 --robot-b 2 --session-b 5 --poi 4
        """,
    )
    parser.add_argument("--url",       default="http://localhost:8000",
                        help="malle_service 기본 URL (기본값: http://localhost:8000)")
    parser.add_argument("--robot-a",   type=int, required=True,
                        help="점유 로봇 ID — PID 구간 진입을 시뮬레이션")
    parser.add_argument("--robot-b",   type=int, required=True,
                        help="대기 로봇 ID — execute 차단 후 자동 재실행 대상")
    parser.add_argument("--session-b", type=int, required=True,
                        help="로봇B에 배정된 세션 ID")
    parser.add_argument("--poi",       type=int, required=True,
                        help="충돌 테스트용 목적지 POI ID")
    parser.add_argument("--hold",      type=int, default=5,
                        help="OCCUPIED 유지 시간(초) — 이후 자동 IDLE 해제 (기본값: 5)")
    parser.add_argument("--add-item",  action="store_true",
                        help="세션B 큐에 POI 항목이 없으면 자동 추가")

    args = parser.parse_args()

    global BASE
    BASE = f"{args.url.rstrip('/')}/api/v1"

    try:
        success = run_test(args)
    except KeyboardInterrupt:
        print("\n\n테스트 중단됨")
        success = False
    finally:
        cleanup(args.robot_a)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
