#!/usr/bin/env python3
"""
Malle 시스템 E2E Latency 측정 스크립트

기존의 컴포넌트 독립 측정(health check 등)과 달리,
실제 서비스 플로우를 통해 latency를 측정합니다.

─── 측정 항목 ────────────────────────────────────────────────────────
E1  State loop latency
      PATCH /robots/{id}/state → WS ROBOT_STATE_UPDATED 수신까지.
      malle_service 내부 DB 갱신 + WS 브로드캐스트 시간을 측정합니다.
      필요: malle_service(:8000), websockets 패키지

E2  Voice command E2E
      WS VOICE_CMD 전송 → malle_service → ai_service → WS VOICE_RESULT 수신까지.
      실제 음성 명령 파이프라인 전체 latency를 측정합니다.
      필요: malle_service, malle_ai_service(:5000), 활성 세션, websockets

E3  Bridge command latency
      POST /bridge/teleop/cmd (zero-velocity) 응답 시간.
      bridge_node의 실제 명령 처리 시간을 측정합니다.
      필요: bridge_node(:9100)

─── 실행 모드 ────────────────────────────────────────────────────────
  # 서비스 실행 중일 때 — active E2E 측정
  python3 test/latency_benchmark.py

  # 팀 테스트 중 passive 자동 수집 (아무 조작 없이 WS 이벤트 측정)
  python3 test/latency_benchmark.py --watch [--watch-duration 120]

  # 서비스 없이 mock 데이터로 빠른 확인
  python3 test/latency_benchmark.py --mock --no-csv

─── 현재 상태 ────────────────────────────────────────────────────────
  malle_ai_service는 현재 LLM 미구현 (keyword fallback).
  E2 mock 기준값 950ms는 LLM 통합 후 예정 수치입니다.
"""

import argparse
import asyncio
import csv
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

try:
    import httpx
except ImportError:
    print("httpx 패키지가 필요합니다: pip install httpx")
    sys.exit(1)

try:
    import websockets
    HAS_WS = True
except ImportError:
    HAS_WS = False
    print("[경고] websockets 패키지 없음 — WS 기반 측정 비활성화 (pip install websockets)")


# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

MALLE_SERVICE_URL = "http://localhost:8000"
AI_SERVICE_URL    = "http://localhost:5000"
BRIDGE_URL        = "http://localhost:9100"
API_PREFIX        = "/api/v1"


# ─────────────────────────────────────────────────────────────
# 데이터 구조
# ─────────────────────────────────────────────────────────────

@dataclass
class MeasurementResult:
    key: str
    description: str
    samples: list[float] = field(default_factory=list)
    errors: int = 0

    @property
    def count(self) -> int:
        return len(self.samples)

    def stats(self) -> dict:
        if not self.samples:
            return {}
        s = sorted(self.samples)
        n = len(s)
        return {
            "min": s[0] * 1000,
            "avg": statistics.mean(s) * 1000,
            "med": statistics.median(s) * 1000,
            "p95": s[min(int(n * 0.95), n - 1)] * 1000,
            "max": s[-1] * 1000,
            "std": (statistics.stdev(s) * 1000) if n > 1 else 0.0,
        }


def _ws_url() -> str:
    return f"{MALLE_SERVICE_URL.replace('http', 'ws')}/ws/dashboard"


def _ws_mobile_url(session_id: int) -> str:
    return f"{MALLE_SERVICE_URL.replace('http', 'ws')}/ws/mobile/{session_id}"


def _extract_type(raw: str) -> str:
    """WS 메시지에서 type 추출. 포맷: {"type": "...", "payload": {...}}"""
    try:
        return json.loads(raw).get("type", "")
    except json.JSONDecodeError:
        return ""


# ─────────────────────────────────────────────────────────────
# E1: State PATCH → WS ROBOT_STATE_UPDATED
# ─────────────────────────────────────────────────────────────

async def measure_e1(client: httpx.AsyncClient, iterations: int, robot_id: int) -> MeasurementResult:
    """E1: PATCH /robots/{id}/state → WS ROBOT_STATE_UPDATED 수신까지"""
    result = MeasurementResult(
        key="E1",
        description="State PATCH → WS ROBOT_STATE_UPDATED  (malle_service 내부 처리 + WS 전송)",
    )

    if not HAS_WS:
        print("  [E1] websockets 패키지 없음 — 건너뜀")
        result.errors = iterations
        return result

    url = f"{MALLE_SERVICE_URL}{API_PREFIX}/robots/{robot_id}/state"

    try:
        async with websockets.connect(_ws_url(), ping_interval=None) as ws:  # type: ignore[attr-defined]
            msg_queue: asyncio.Queue = asyncio.Queue()

            async def _reader():
                try:
                    async for raw in ws:
                        await msg_queue.put((time.perf_counter(), raw))
                except Exception:
                    pass

            reader = asyncio.create_task(_reader())

            for i in range(iterations):
                # 이전 이터레이션 잔여 메시지 비우기
                while not msg_queue.empty():
                    try:
                        msg_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                payload = {"x_m": float(i % 10), "y_m": 0.0, "theta_rad": 0.0}
                t0 = time.perf_counter()
                try:
                    r = await client.patch(url, json=payload, timeout=5.0)
                    if r.status_code >= 500:
                        result.errors += 1
                        continue
                except Exception as e:
                    result.errors += 1
                    print(f"  [E1] #{i+1} PATCH 오류: {e}")
                    continue

                # WS ROBOT_STATE_UPDATED 대기
                deadline = time.perf_counter() + 3.0
                found = False
                while time.perf_counter() < deadline:
                    remaining = deadline - time.perf_counter()
                    try:
                        ts, raw = await asyncio.wait_for(msg_queue.get(), timeout=remaining)
                        if _extract_type(raw) == "ROBOT_STATE_UPDATED":
                            result.samples.append(ts - t0)
                            found = True
                            break
                    except asyncio.TimeoutError:
                        break

                if not found:
                    print(f"  [E1] #{i+1} WS 이벤트 수신 타임아웃")
                    result.errors += 1

                await asyncio.sleep(0.15)

            reader.cancel()

    except Exception as e:
        print(f"  [E1] WS 연결 오류: {e}")
        result.errors = iterations

    return result


# ─────────────────────────────────────────────────────────────
# E2: Voice command E2E (WS VOICE_CMD → WS VOICE_RESULT)
# ─────────────────────────────────────────────────────────────

async def _find_active_session(client: httpx.AsyncClient) -> Optional[int]:
    try:
        r = await client.get(f"{MALLE_SERVICE_URL}{API_PREFIX}/sessions/active", timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            sessions = data if isinstance(data, list) else data.get("sessions", [])
            if sessions:
                return sessions[0].get("id") or sessions[0].get("session_id")
    except Exception:
        pass
    return None


async def measure_e2(client: httpx.AsyncClient, iterations: int) -> MeasurementResult:
    """E2: WS VOICE_CMD → malle_service → ai_service → WS VOICE_RESULT"""
    result = MeasurementResult(
        key="E2",
        description="Voice command E2E  (WS VOICE_CMD → ai_service → WS VOICE_RESULT)",
    )

    if not HAS_WS:
        print("  [E2] websockets 패키지 없음 — 건너뜀")
        result.errors = iterations
        return result

    session_id = await _find_active_session(client)
    if session_id is None:
        print("  [E2] 활성 세션 없음 — 건너뜀 (세션 생성 후 재시도)")
        result.errors = iterations
        return result

    print(f"  [E2] session_id={session_id} 사용")

    texts = ["카페로 안내해줘", "나이키 매장 어디야", "로봇 상태 알려줘", "따라와줘"]

    try:
        async with websockets.connect(_ws_mobile_url(session_id), ping_interval=None) as ws:  # type: ignore[attr-defined]
            msg_queue: asyncio.Queue = asyncio.Queue()

            async def _reader():
                try:
                    async for raw in ws:
                        await msg_queue.put((time.perf_counter(), raw))
                except Exception:
                    pass

            reader = asyncio.create_task(_reader())

            for i in range(iterations):
                while not msg_queue.empty():
                    try:
                        msg_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                cmd = json.dumps({"type": "VOICE_CMD", "text": texts[i % len(texts)]})
                t0 = time.perf_counter()
                try:
                    await ws.send(cmd)
                except Exception as e:
                    result.errors += 1
                    print(f"  [E2] #{i+1} WS 전송 오류: {e}")
                    continue

                # WS VOICE_RESULT 대기 (ai_service 호출 포함 — 최대 15초)
                deadline = time.perf_counter() + 15.0
                found = False
                while time.perf_counter() < deadline:
                    remaining = deadline - time.perf_counter()
                    try:
                        ts, raw = await asyncio.wait_for(msg_queue.get(), timeout=remaining)
                        if _extract_type(raw) == "VOICE_RESULT":
                            result.samples.append(ts - t0)
                            found = True
                            break
                    except asyncio.TimeoutError:
                        break

                if not found:
                    print(f"  [E2] #{i+1} VOICE_RESULT 타임아웃")
                    result.errors += 1

                await asyncio.sleep(0.5)

            reader.cancel()

    except Exception as e:
        print(f"  [E2] WS 연결 오류 (session={session_id}): {e}")
        result.errors = iterations

    return result


# ─────────────────────────────────────────────────────────────
# E3: bridge_node 명령 처리 latency
# ─────────────────────────────────────────────────────────────

async def measure_e3(client: httpx.AsyncClient, iterations: int, robot_id: int) -> MeasurementResult:
    """E3: POST /bridge/teleop/cmd (zero-velocity) — bridge_node 명령 처리 시간"""
    result = MeasurementResult(
        key="E3",
        description="bridge_node 명령 처리  (POST /bridge/teleop/cmd, zero-vel)",
    )
    url = f"{BRIDGE_URL}/bridge/teleop/cmd"
    payload = {"robot_id": robot_id, "linear_x": 0.0, "angular_z": 0.0}

    for i in range(iterations):
        try:
            t0 = time.perf_counter()
            r = await client.post(url, json=payload, timeout=5.0)
            elapsed = time.perf_counter() - t0
            if r.status_code < 500:
                result.samples.append(elapsed)
            else:
                result.errors += 1
                print(f"  [E3] #{i+1} HTTP {r.status_code}")
        except Exception as e:
            result.errors += 1
            print(f"  [E3] #{i+1} 오류: {e}")

    return result


# ─────────────────────────────────────────────────────────────
# Watch 모드 (passive — 팀 테스트 중 자동 수집)
# ─────────────────────────────────────────────────────────────

async def run_watch(duration_sec: int, no_csv: bool) -> None:
    """
    WS /ws/dashboard를 수신하며 실제 운영 중 latency를 자동 수집합니다.
    팀이 정상적으로 테스트하는 동안 백그라운드에서 실행하면 됩니다.

    측정 항목:
      - ROBOT_STATE_UPDATED 이벤트 간격 (bridge_node → malle_service → WS 루프)
      - GUIDE_NAVIGATING → GUIDE_ARRIVED 소요시간 (실제 가이드 미션 시간)
    """
    if not HAS_WS:
        print("[오류] --watch 모드는 websockets 패키지가 필요합니다.")
        return

    print(f"[Watch 모드] WS 이벤트 수집 중 (최대 {duration_sec}초, Ctrl+C로 조기 종료)")
    print(f"  → {_ws_url()}")
    print()

    state_intervals: list[float] = []   # ROBOT_STATE_UPDATED 이벤트 간격
    guide_times: list[float] = []       # GUIDE_NAVIGATING → GUIDE_ARRIVED

    last_state_ts: Optional[float] = None
    guide_start: dict[str, float] = {}  # session_id → 시작 시각
    total_events = 0
    deadline = time.perf_counter() + duration_sec

    try:
        async with websockets.connect(_ws_url(), ping_interval=None) as ws:  # type: ignore[attr-defined]
            while time.perf_counter() < deadline:
                remaining = deadline - time.perf_counter()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 2.0))
                    ts = time.perf_counter()
                    ev = _extract_type(raw)
                    total_events += 1

                    if ev == "ROBOT_STATE_UPDATED":
                        if last_state_ts is not None:
                            state_intervals.append(ts - last_state_ts)
                        last_state_ts = ts
                        print(f"\r  state={len(state_intervals)}간격  guide={len(guide_times)}건  events={total_events}", end="", flush=True)

                    elif ev == "GUIDE_NAVIGATING":
                        try:
                            payload = json.loads(raw).get("payload", {})
                            sid = str(payload.get("session_id", ""))
                        except Exception:
                            sid = "unknown"
                        guide_start[sid] = ts

                    elif ev == "GUIDE_ARRIVED":
                        try:
                            payload = json.loads(raw).get("payload", {})
                            sid = str(payload.get("session_id", ""))
                        except Exception:
                            sid = "unknown"
                        if sid in guide_start:
                            guide_times.append(ts - guide_start.pop(sid))
                            print(f"\r  state={len(state_intervals)}간격  guide={len(guide_times)}건  events={total_events}", end="", flush=True)

                except asyncio.TimeoutError:
                    continue

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n[Watch] WS 오류: {e}")

    print(f"\n\n[Watch 모드 결과]  (총 이벤트: {total_events})")
    print("=" * 60)

    if state_intervals:
        s = sorted(state_intervals)
        print(f"  ROBOT_STATE_UPDATED 간격  (n={len(s)})")
        print(f"    avg={statistics.mean(s)*1000:.1f}ms  "
              f"med={statistics.median(s)*1000:.1f}ms  "
              f"std={(statistics.stdev(s)*1000 if len(s)>1 else 0.0):.1f}ms")
        print(f"    → bridge STATE_UPDATE_INTERVAL 기댓값: 500ms")
    else:
        print("  ROBOT_STATE_UPDATED: 이벤트 없음 (로봇이 연결되어 있나요?)")

    print()

    if guide_times:
        s = sorted(guide_times)
        print(f"  Guide 미션 소요시간  NAVIGATING → ARRIVED  (n={len(s)})")
        print(f"    avg={statistics.mean(s):.1f}s  "
              f"med={statistics.median(s):.1f}s  "
              f"min={s[0]:.1f}s  max={s[-1]:.1f}s")
    else:
        print("  Guide 미션: 감지 없음 (가이드 미션 실행 중에 사용하세요)")

    print("=" * 60)
    print()

    if not no_csv and (state_intervals or guide_times):
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"latency_watch_{ts_str}.csv"
        with open(filename, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["type", "value_ms"])
            for v in state_intervals:
                w.writerow(["state_interval", round(v * 1000, 2)])
            for v in guide_times:
                w.writerow(["guide_mission_sec", round(v, 3)])
        print(f"  결과 저장: {filename}")
        print()


# ─────────────────────────────────────────────────────────────
# Mock 측정 (서비스 없이 가상 데이터 생성)
# ─────────────────────────────────────────────────────────────

# (mean_ms, std_ms) — 레이어별 현실적인 추정치
_MOCK_PARAMS: dict[str, tuple[float, float]] = {
    "E1": (12.0,   3.0),    # PATCH → WS broadcast
    "E2": (950.0, 120.0),   # Voice E2E — LLM 통합 후 기준 (현재 keyword: ~10ms)
    "E3": (5.0,    1.5),    # bridge_node 명령 처리
}

def _mock_result(key: str, description: str, n: int) -> MeasurementResult:
    mean_ms, std_ms = _MOCK_PARAMS.get(key, (10.0, 2.0))
    samples = [max(0.001, random.gauss(mean_ms, std_ms)) / 1000.0 for _ in range(n)]
    r = MeasurementResult(key=key, description=f"[MOCK] {description}")
    r.samples = samples
    return r


# ─────────────────────────────────────────────────────────────
# 서비스 가용성 확인
# ─────────────────────────────────────────────────────────────

async def check_services(client: httpx.AsyncClient) -> dict[str, bool]:
    checks = {
        "malle_service":    f"{MALLE_SERVICE_URL}{API_PREFIX}/robots",
        "malle_ai_service": f"{AI_SERVICE_URL}/ai/voice-parse",
        "bridge_node":      f"{BRIDGE_URL}/health",
    }
    results = {}
    for name, url in checks.items():
        try:
            method = "post" if name == "malle_ai_service" else "get"
            kw: dict = {"timeout": 3.0}
            if method == "post":
                kw["json"] = {"text": "test", "client_type": "mobile"}
            r = await getattr(client, method)(url, **kw)
            results[name] = r.status_code < 500
        except Exception:
            results[name] = False
    return results


# ─────────────────────────────────────────────────────────────
# 출력 및 저장
# ─────────────────────────────────────────────────────────────

def print_results(measurements: list[MeasurementResult]) -> list[dict]:
    print()
    print("=" * 72)
    print("  Malle 시스템 E2E Latency 측정 결과  (단위: ms)")
    print("=" * 72)
    print(f"  {'항목':<8} {'min':>7} {'avg':>7} {'med':>7} {'p95':>7} {'max':>7} {'std':>7}")
    print("-" * 72)

    rows = []
    for m in measurements:
        s = m.stats()
        if not s:
            print(f"  {m.key:<8} {'N/A':<51}  err={m.errors}")
            rows.append({"key": m.key, "n": 0, "errors": m.errors,
                         "min": None, "avg": None, "med": None,
                         "p95": None, "max": None, "std": None})
            continue
        rows.append({"key": m.key, "n": m.count, "errors": m.errors,
                     **{k: round(v, 2) for k, v in s.items()}})
        print(
            f"  {m.key:<8}"
            f" {s['min']:>7.1f}"
            f" {s['avg']:>7.1f}"
            f" {s['med']:>7.1f}"
            f" {s['p95']:>7.1f}"
            f" {s['max']:>7.1f}"
            f" {s['std']:>7.1f}"
            f"  (n={m.count}, err={m.errors})"
        )

    print("=" * 72)
    print()
    print("  [측정 항목 설명]")
    for m in measurements:
        print(f"  {m.key:<8} {m.description}")
    print()

    return rows


def save_csv(measurements: list[MeasurementResult], rows: list[dict]) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"latency_e2e_{ts}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["key", "n", "errors", "min", "avg", "med", "p95", "max", "std"]
        )
        writer.writeheader()
        writer.writerows(rows)
        f.write("\n# Raw samples (ms)\n")
        for m in measurements:
            if m.samples:
                f.write(f"# {m.key}\n")
                f.write(",".join(f"{v*1000:.3f}" for v in m.samples) + "\n")
    return filename


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    print()
    print("=" * 72)
    print("  Malle 시스템 E2E Latency Benchmark")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)
    print(f"  malle_service: {MALLE_SERVICE_URL}")
    print(f"  ai_service:    {AI_SERVICE_URL}")
    print(f"  bridge_node:   {BRIDGE_URL}")
    print(f"  로봇 ID: {args.robot_id}   반복: {args.iterations}회")
    print()

    if args.watch:
        await run_watch(args.watch_duration, args.no_csv)
        return

    async with httpx.AsyncClient() as client:
        measurements: list[MeasurementResult] = []

        if args.mock:
            print("[MOCK 모드] 가상 데이터로 측정합니다.")
            print()
            n = args.iterations
            measurements.append(_mock_result(
                "E1", "State PATCH → WS ROBOT_STATE_UPDATED", n))
            measurements.append(_mock_result(
                "E2", "Voice command E2E (WS → ai_service → WS)", n))
            measurements.append(_mock_result(
                "E3", "bridge_node 명령 처리 (POST /bridge/teleop/cmd)", n))

        else:
            print("[사전 점검] 서비스 가용성 확인 중...")
            avail = await check_services(client)
            for name, ok in avail.items():
                mark = "✓" if ok else "✗"
                print(f"  {mark}  {name}")
            print()

            if not avail["malle_service"]:
                print("[오류] malle_service에 연결할 수 없습니다.")
                sys.exit(1)

            # E1
            if HAS_WS:
                print(f"[E1] State PATCH → WS broadcast  ({args.iterations}회)...")
                measurements.append(
                    await measure_e1(client, args.iterations, args.robot_id))
            else:
                print("[E1] websockets 없음 — 건너뜀")
                measurements.append(MeasurementResult(
                    "E1", "State PATCH → WS (websockets 없음)", errors=args.iterations))

            # E2
            if avail["malle_ai_service"] and HAS_WS:
                print(f"[E2] Voice command E2E  ({args.iterations}회)...")
                measurements.append(await measure_e2(client, args.iterations))
            else:
                reason = "ai_service 오프라인" if not avail["malle_ai_service"] else "websockets 없음"
                print(f"[E2] {reason} — 건너뜀")
                measurements.append(MeasurementResult(
                    "E2", f"Voice command E2E ({reason})", errors=args.iterations))

            # E3
            if avail["bridge_node"]:
                print(f"[E3] bridge_node 명령 처리  ({args.iterations}회)...")
                measurements.append(
                    await measure_e3(client, args.iterations, args.robot_id))
            else:
                print("[E3] bridge_node 오프라인 — 건너뜀")
                measurements.append(MeasurementResult(
                    "E3", "bridge_node (오프라인)", errors=args.iterations))

        rows = print_results(measurements)

        if not args.no_csv:
            fname = save_csv(measurements, rows)
            print(f"  결과 저장: {fname}")
            print()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Malle 시스템 E2E latency 측정")
    p.add_argument("--iterations", "-n", type=int, default=10,
                   help="측정 반복 횟수 (기본: 10)")
    p.add_argument("--robot-id", "-r", type=int, default=1,
                   help="대상 로봇 ID (기본: 1)")
    p.add_argument("--mock", action="store_true",
                   help="서비스 없이 가상 데이터로 측정")
    p.add_argument("--watch", action="store_true",
                   help="팀 테스트 중 WS 이벤트를 passive하게 자동 수집")
    p.add_argument("--watch-duration", type=int, default=120,
                   help="Watch 모드 수집 시간 초 (기본: 120)")
    p.add_argument("--no-csv", action="store_true",
                   help="CSV 파일 저장 안 함")
    p.add_argument("--service-url", default=MALLE_SERVICE_URL,
                   help=f"malle_service URL (기본: {MALLE_SERVICE_URL})")
    p.add_argument("--ai-url", default=AI_SERVICE_URL,
                   help=f"malle_ai_service URL (기본: {AI_SERVICE_URL})")
    p.add_argument("--bridge-url", default=BRIDGE_URL,
                   help=f"bridge_node URL (기본: {BRIDGE_URL})")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # URL 오버라이드
    MALLE_SERVICE_URL = args.service_url
    AI_SERVICE_URL    = args.ai_url
    BRIDGE_URL        = args.bridge_url

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
