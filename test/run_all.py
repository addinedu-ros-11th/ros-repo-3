#!/usr/bin/env python3
"""
run_all.py — FT-104 Zone-based Mutex 전체 테스트 실행기

실행:
    cd malle_service
    python ../test/run_all.py

    # 통합 테스트도 함께 (서버 필요):
    python ../test/run_all.py --integration --robot-a 1 --robot-b 2 --session-b 5 --poi 4

필요 패키지:
    pip install pytest pytest-asyncio httpx aiosqlite requests
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

HERE     = os.path.dirname(os.path.abspath(__file__))
SVC_DIR  = os.path.join(HERE, "..", "malle_service")
SVC_TEST = os.path.join(SVC_DIR, "tests", "run_all.py")

SEP  = "=" * 62
SEP2 = "─" * 62

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SKIP = "\033[33mSKIP\033[0m"


def server_alive(url: str) -> bool:
    try:
        import requests
        r = requests.get(f"{url}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def run(label: str, cmd: list[str], cwd: str = HERE) -> bool:
    print(f"\n{SEP2}")
    print(f"▶  {label}")
    print(SEP2)
    result = subprocess.run(cmd, cwd=cwd)
    ok = result.returncode == 0
    print(f"\n[{'PASS' if ok else 'FAIL'}] {label}")
    return ok


def main():
    parser = argparse.ArgumentParser(description="전체 테스트 실행기")
    _svc_url = os.getenv("MALLE_SERVICE_URL", "http://localhost:8000/api/v1")
    _svc_base = _svc_url.rsplit("/api/", 1)[0] if "/api/" in _svc_url else _svc_url

    parser.add_argument("--url", default=_svc_base,
                        help="malle_service URL (기본값: MALLE_SERVICE_URL 또는 http://localhost:8000)")
    parser.add_argument("--integration", action="store_true",
                        help="HTTP 통합 테스트 실행 (서버 필요)")
    parser.add_argument("--api-tests", action="store_true",
                        help="malle_service/tests/ 전체 API 테스트 실행 (서버 필요)")
    # test_occupied_mutex.py 인자
    _env_int = lambda k: int(os.getenv(k)) if os.getenv(k) else None
    parser.add_argument("--robot-a",   type=int, default=_env_int("TEST_ROBOT_A"))
    parser.add_argument("--robot-b",   type=int, default=_env_int("TEST_ROBOT_B"))
    parser.add_argument("--session-b", type=int, default=_env_int("TEST_SESSION_B"))
    parser.add_argument("--poi",       type=int, default=_env_int("TEST_POI_ID"))
    parser.add_argument("--hold",      type=int, default=int(os.getenv("TEST_HOLD_SEC", "5")))
    args = parser.parse_args()

    results: list[tuple[str, str]] = []   # (label, "pass"|"fail"|"skip")

    print(SEP)
    print("  FT-104 Zone-based Mutex — 전체 테스트")
    print(SEP)

    # ── 1. 단위 테스트 (서버 불필요) ─────────────────────────────────────────
    ok = run(
        "단위 테스트 (SQLite in-memory)",
        [sys.executable, "-m", "pytest", os.path.join(HERE, "test_zone_mutex_unit.py"), "-v"],
        cwd=SVC_DIR,
    )
    results.append(("단위 테스트", "pass" if ok else "fail"))

    # ── 2. HTTP 통합 테스트 (선택, 서버 필요) ────────────────────────────────
    if args.integration:
        alive = server_alive(args.url)
        if not alive:
            print(f"\n[{SKIP}] HTTP 통합 테스트 — 서버 응답 없음 ({args.url})")
            results.append(("HTTP 통합 테스트 (test_occupied_mutex)", "skip"))
        else:
            required = [args.robot_a, args.robot_b, args.session_b, args.poi]
            if any(v is None for v in required):
                print(f"\n[{SKIP}] HTTP 통합 테스트 — --robot-a/b, --session-b, --poi 필요")
                results.append(("HTTP 통합 테스트 (test_occupied_mutex)", "skip"))
            else:
                mutex_cmd = [
                    sys.executable,
                    os.path.join(HERE, "test_occupied_mutex.py"),
                    "--url",      args.url,
                    "--robot-a",  str(args.robot_a),
                    "--robot-b",  str(args.robot_b),
                    "--session-b",str(args.session_b),
                    "--poi",      str(args.poi),
                    "--hold",     str(args.hold),
                    "--add-item",
                ]
                ok = run("HTTP 통합 테스트 (test_occupied_mutex)", mutex_cmd)
                results.append(("HTTP 통합 테스트 (test_occupied_mutex)", "pass" if ok else "fail"))

    # ── 3. API 전체 테스트 (선택, 서버 필요) ─────────────────────────────────
    if args.api_tests:
        alive = server_alive(args.url)
        if not alive:
            print(f"\n[{SKIP}] API 전체 테스트 — 서버 응답 없음 ({args.url})")
            results.append(("API 전체 테스트 (malle_service/tests)", "skip"))
        else:
            ok = run(
                "API 전체 테스트 (malle_service/tests)",
                [sys.executable, SVC_TEST],
                cwd=SVC_DIR,
            )
            results.append(("API 전체 테스트 (malle_service/tests)", "pass" if ok else "fail"))

    # ── 결과 요약 ─────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  결과 요약")
    print(SEP)
    for label, status in results:
        if status == "pass":
            mark = PASS
        elif status == "fail":
            mark = FAIL
        else:
            mark = SKIP
        print(f"  [{mark}] {label}")
    print(SEP)

    failed = [l for l, s in results if s == "fail"]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
