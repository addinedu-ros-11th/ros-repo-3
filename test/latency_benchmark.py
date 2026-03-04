#!/usr/bin/env python3
"""
Malle 시스템 레이어별 latency 측정 스크립트

─── 측정 레이어 ───────────────────────────────────────────────
[사용자 앱]
    ↓ L1: App → malle_service 요청 전달          (GET /api/v1/robots)
[malle_service :8000]
    ↓ L2: malle_service → malle_ai_service 처리  (POST /ai/voice-parse)
[malle_ai_service :5000]
    ↓ L3: malle_service → bridge_node 명령 전달  (GET /health)
[bridge_node :9100]
    ↓ L4: ROS2 제어 루프 주기 추정               (WS 이벤트 간격 또는 HTTP 폴링)
[ROS2 실제 동작]
    ↓ L5: bridge_node → malle_service 상태 피드백 (PATCH /api/v1/robots/{id}/state)
[malle_service :8000]

─── 실행 예시 ─────────────────────────────────────────────────
  # 전체 서비스 실측 (기본)
  python3 test/latency_benchmark.py

  # 반복 횟수·로봇 ID 지정
  python3 test/latency_benchmark.py --iterations 20 --robot-id 2

  # L4 관측 시간 조정, CSV 저장 생략
  python3 test/latency_benchmark.py --l4-duration 30 --no-csv

  # malle_ai_service 없이 mock 데이터로 빠르게 실행
  python3 test/latency_benchmark.py --mock

  # mock + CSV 저장 생략
  python3 test/latency_benchmark.py --mock --no-csv

─── Mock 모드 ──────────────────────────────────────────────────
  --mock 플래그를 사용하면 실제 서비스 호출 없이 가상 latency 샘플을 생성합니다.
  malle_ai_service(L2)가 오프라인이거나 LLM 응답을 받을 수 없는 환경에서 사용합니다.

  레이어별 mock 기준값:
    L1       평균  8ms  (로컬 HTTP 왕복)
    L2       평균 950ms (LLM 기반 AI 서비스 추정)
    L3       평균  5ms  (bridge_node 헬스체크)
    L4       평균 500ms (ROS2 STATE_UPDATE_INTERVAL 0.5s 기준)
    L5       평균  9ms  (상태 피드백 PATCH)

  mock 모드에서는 --l4-duration 기본값이 1초로 단축됩니다.
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
    print("[경고] websockets 패키지 없음 — L4 WebSocket 측정 비활성화 (pip install websockets)")


# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

MALLE_SERVICE_URL = "http://localhost:8000"
AI_SERVICE_URL    = "http://localhost:5000"
BRIDGE_URL        = "http://localhost:9100"
WS_URL            = "ws://localhost:8000/ws/dashboard"

API_PREFIX = "/api/v1"


# ─────────────────────────────────────────────────────────────
# 데이터 구조
# ─────────────────────────────────────────────────────────────

@dataclass
class LayerResult:
    layer: str
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
            "min":  s[0] * 1000,
            "avg":  statistics.mean(s) * 1000,
            "med":  statistics.median(s) * 1000,
            "p95":  s[min(int(n * 0.95), n - 1)] * 1000,
            "max":  s[-1] * 1000,
            "std":  (statistics.stdev(s) * 1000) if n > 1 else 0.0,
        }


# ─────────────────────────────────────────────────────────────
# 개별 레이어 측정 함수
# ─────────────────────────────────────────────────────────────

async def measure_l1(client: httpx.AsyncClient, iterations: int) -> LayerResult:
    """L1: 앱 → malle_service (GET /api/v1/robots)"""
    result = LayerResult(
        layer="L1",
        description="App → malle_service  (GET /api/v1/robots)",
    )
    url = f"{MALLE_SERVICE_URL}{API_PREFIX}/robots"
    for i in range(iterations):
        try:
            t0 = time.perf_counter()
            r = await client.get(url, timeout=5.0)
            elapsed = time.perf_counter() - t0
            if r.status_code < 500:
                result.samples.append(elapsed)
            else:
                result.errors += 1
                print(f"  [L1] #{i+1} HTTP {r.status_code}")
        except Exception as e:
            result.errors += 1
            print(f"  [L1] #{i+1} 오류: {e}")
    return result


async def measure_l2_direct(client: httpx.AsyncClient, iterations: int) -> LayerResult:
    """L2-direct: malle_ai_service 직접 호출 (POST /ai/voice-parse)"""
    result = LayerResult(
        layer="L2-direct",
        description="→ malle_ai_service 직접  (POST /ai/voice-parse)",
    )
    url = f"{AI_SERVICE_URL}/ai/voice-parse"
    payload = {"text": "나이키 매장으로 안내해줘", "client_type": "mobile"}
    for i in range(iterations):
        try:
            t0 = time.perf_counter()
            r = await client.post(url, json=payload, timeout=10.0)
            elapsed = time.perf_counter() - t0
            if r.status_code < 500:
                result.samples.append(elapsed)
            else:
                result.errors += 1
                print(f"  [L2-direct] #{i+1} HTTP {r.status_code}")
        except Exception as e:
            result.errors += 1
            print(f"  [L2-direct] #{i+1} 오류: {e}")
    return result


async def measure_l2_via_service(client: httpx.AsyncClient, iterations: int, session_id: Optional[int]) -> LayerResult:
    """L2-via: malle_service를 통한 AI 호출 오버헤드 추정
    malle_service가 내부적으로 AI 서비스를 호출하는 엔드포인트가 있을 경우.
    없으면 L1과 L2-direct의 차이로 추정."""
    result = LayerResult(
        layer="L2-via",
        description="malle_service 내부 AI 오버헤드 (L1 왕복 - L2-direct)",
    )
    # 실제 내부 경로가 없으므로 메타 계산용 placeholder — analyze()에서 채움
    return result


async def measure_l3(client: httpx.AsyncClient, iterations: int) -> LayerResult:
    """L3: bridge_node 헬스체크 (GET /health) — malle_service→bridge 구간 추정"""
    result = LayerResult(
        layer="L3",
        description="malle_service → bridge_node  (GET /health)",
    )
    url = f"{BRIDGE_URL}/health"
    for i in range(iterations):
        try:
            t0 = time.perf_counter()
            r = await client.get(url, timeout=3.0)
            elapsed = time.perf_counter() - t0
            if r.status_code < 500:
                result.samples.append(elapsed)
            else:
                result.errors += 1
                print(f"  [L3] #{i+1} HTTP {r.status_code}")
        except Exception as e:
            result.errors += 1
            print(f"  [L3] #{i+1} 오류: {e}")
    return result


async def measure_l5(client: httpx.AsyncClient, iterations: int, robot_id: int) -> LayerResult:
    """L5: bridge_node → malle_service 상태 피드백 (PATCH /api/v1/robots/{id}/state)"""
    result = LayerResult(
        layer="L5",
        description=f"bridge_node → malle_service  (PATCH /robots/{robot_id}/state)",
    )
    url = f"{MALLE_SERVICE_URL}{API_PREFIX}/robots/{robot_id}/state"
    # 실제 bridge_node가 전송하는 최소 payload (위치만 업데이트)
    payload = {"x_m": 0.0, "y_m": 0.0, "theta_rad": 0.0}
    for i in range(iterations):
        try:
            t0 = time.perf_counter()
            r = await client.patch(url, json=payload, timeout=5.0)
            elapsed = time.perf_counter() - t0
            if r.status_code < 500:
                result.samples.append(elapsed)
            else:
                result.errors += 1
                print(f"  [L5] #{i+1} HTTP {r.status_code}")
        except Exception as e:
            result.errors += 1
            print(f"  [L5] #{i+1} 오류: {e}")
    return result


async def measure_l4_ws(duration_sec: int) -> LayerResult:
    """L4: ROS2 제어 루프 추정 — WebSocket으로 robot_state_updated 이벤트 간격 측정.
    bridge_node는 STATE_UPDATE_INTERVAL=0.5s마다 상태를 PATCH하고,
    malle_service는 이를 WS로 broadcast하므로 이벤트 간격 ≈ 제어 루프 주기."""
    result = LayerResult(
        layer="L4",
        description=f"ROS2 제어 루프 추정  (WS robot_state_updated 이벤트 간격, {duration_sec}초)",
    )
    if not HAS_WS:
        result.errors += 1
        return result

    timestamps: list[float] = []
    print(f"  [L4] WebSocket 이벤트 수집 중 ({duration_sec}초)...", flush=True)
    deadline = time.perf_counter() + duration_sec

    try:
        async with websockets.connect(WS_URL, ping_interval=None) as ws:  # type: ignore[attr-defined]
            while time.perf_counter() < deadline:
                remaining = deadline - time.perf_counter()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 2.0))
                    data = json.loads(raw)
                    event = data.get("event") or data.get("type") or ""
                    if "robot" in event.lower() and "state" in event.lower():
                        timestamps.append(time.perf_counter())
                        print(f"\r  [L4] 이벤트 {len(timestamps)}개 수집", end="", flush=True)
                except asyncio.TimeoutError:
                    continue
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        result.errors += 1
        print(f"\n  [L4] WebSocket 오류: {e}")
        return result

    print()
    if len(timestamps) >= 2:
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps) - 1)]
        result.samples = intervals
    else:
        print("  [L4] 이벤트 수집 부족 (로봇이 연결/이동 중인지 확인하세요)")
        result.errors += 1

    return result


async def measure_l4_poll(client: httpx.AsyncClient, duration_sec: int, robot_id: int) -> LayerResult:
    """L4 대안: HTTP 폴링으로 상태 변화 주기 측정 (WS 사용 불가 시)."""
    result = LayerResult(
        layer="L4-poll",
        description=f"ROS2 루프 추정  (HTTP 폴링 상태 변화 간격, {duration_sec}초)",
    )
    url = f"{MALLE_SERVICE_URL}{API_PREFIX}/robots/{robot_id}"
    prev_state = None
    change_times: list[float] = []
    deadline = time.perf_counter() + duration_sec
    poll_interval = 0.1  # 100ms 폴링

    print(f"  [L4-poll] HTTP 폴링 중 ({duration_sec}초, 10Hz)...", flush=True)
    while time.perf_counter() < deadline:
        try:
            r = await client.get(url, timeout=2.0)
            if r.status_code == 200:
                state = r.json().get("state", {})
                key = (state.get("x_m"), state.get("y_m"), state.get("theta_rad"))
                if prev_state is not None and key != prev_state:
                    change_times.append(time.perf_counter())
                    print(f"\r  [L4-poll] 상태 변화 {len(change_times)}회", end="", flush=True)
                prev_state = key
        except Exception:
            pass
        await asyncio.sleep(poll_interval)

    print()
    if len(change_times) >= 2:
        intervals = [change_times[i+1] - change_times[i] for i in range(len(change_times) - 1)]
        result.samples = intervals
    else:
        print("  [L4-poll] 상태 변화 감지 부족 (로봇이 이동 중인지 확인하세요)")
        result.errors += 1

    return result


# ─────────────────────────────────────────────────────────────
# Mock 측정 (서비스 없이 가상 데이터 생성)
# ─────────────────────────────────────────────────────────────

# (mean_ms, std_ms) — 레이어별 현실적인 추정치
_MOCK_PARAMS: dict[str, tuple[float, float]] = {
    "L1":       (8.0,    2.0),   # 로컬 HTTP 왕복
    "L2-direct":(950.0, 120.0),  # LLM 기반 AI 서비스
    "L3":       (5.0,    1.5),   # bridge_node 헬스체크
    "L4":       (500.0,  30.0),  # ROS2 제어 루프 주기 (0.5s)
    "L5":       (9.0,    2.5),   # 상태 피드백 PATCH
}

def mock_layer(layer: str, description: str, n: int) -> LayerResult:
    mean_ms, std_ms = _MOCK_PARAMS.get(layer, (10.0, 2.0))
    samples = [max(0.001, random.gauss(mean_ms, std_ms)) / 1000.0 for _ in range(n)]
    r = LayerResult(layer=layer, description=f"[MOCK] {description}")
    r.samples = samples
    return r


# ─────────────────────────────────────────────────────────────
# 서비스 가용성 확인
# ─────────────────────────────────────────────────────────────

async def check_services(client: httpx.AsyncClient, robot_id: int) -> dict[str, bool]:
    checks = {
        "malle_service": f"{MALLE_SERVICE_URL}{API_PREFIX}/robots",
        "malle_ai_service": f"{AI_SERVICE_URL}/ai/voice-parse",
        "bridge_node": f"{BRIDGE_URL}/health",
        f"robot_{robot_id}": f"{MALLE_SERVICE_URL}{API_PREFIX}/robots/{robot_id}",
    }
    results = {}
    for name, url in checks.items():
        try:
            method = "get" if name != "malle_ai_service" else "post"
            kw = {"timeout": 3.0}
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

def print_results(layers: list[LayerResult]) -> None:
    print()
    print("=" * 72)
    print("  Malle 시스템 레이어별 Latency 측정 결과  (단위: ms)")
    print("=" * 72)
    header = f"  {'Layer':<12} {'설명':<38} {'N':>4} {'Err':>4}"
    print(header)
    print("-" * 72)

    stat_header = f"  {'Layer':<12} {'min':>7} {'avg':>7} {'med':>7} {'p95':>7} {'max':>7} {'std':>7}"
    print(stat_header)
    print("-" * 72)

    all_rows = []
    for r in layers:
        s = r.stats()
        if not s:
            print(f"  {r.layer:<12} {'N/A (측정 데이터 없음)':<55}  err={r.errors}")
            all_rows.append({**{"layer": r.layer, "n": 0, "errors": r.errors},
                             **{"min": None, "avg": None, "med": None, "p95": None, "max": None, "std": None}})
            continue
        row = {
            "layer": r.layer, "n": r.count, "errors": r.errors,
            **{k: round(v, 2) for k, v in s.items()},
        }
        all_rows.append(row)
        print(
            f"  {r.layer:<12}"
            f" {s['min']:>7.1f}"
            f" {s['avg']:>7.1f}"
            f" {s['med']:>7.1f}"
            f" {s['p95']:>7.1f}"
            f" {s['max']:>7.1f}"
            f" {s['std']:>7.1f}"
            f"  (n={r.count}, err={r.errors})"
        )

    print("=" * 72)
    print()

    # 레이어별 설명 요약
    print("  [레이어 설명]")
    for r in layers:
        print(f"  {r.layer:<12} {r.description}")
    print()

    # 시스템 총 예상 latency
    valid = [r for r in layers if r.samples and r.layer not in ("L2-via", "L4-poll")]
    if valid:
        total_avg = sum(statistics.mean(r.samples) * 1000 for r in valid)
        print(f"  시스템 추정 E2E 평균 latency: {total_avg:.1f} ms")
        print(f"  (L1+L2+L3+L4+L5 평균 합산, L4는 제어 루프 주기)")
    print()

    return all_rows


def save_csv(layers: list[LayerResult], rows: list[dict]) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"latency_benchmark_{ts}.csv"

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["layer", "n", "errors", "min", "avg", "med", "p95", "max", "std"])
        writer.writeheader()
        writer.writerows(rows)

        # 원시 샘플도 별도 섹션으로 저장
        f.write("\n# Raw samples (ms)\n")
        for r in layers:
            if r.samples:
                f.write(f"# {r.layer}\n")
                f.write(",".join(f"{v*1000:.3f}" for v in r.samples) + "\n")

    return filename


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    print()
    print("=" * 72)
    print("  Malle 시스템 레이어별 Latency Benchmark")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)
    print(f"  서버:    {MALLE_SERVICE_URL}  /  {AI_SERVICE_URL}  /  {BRIDGE_URL}")
    print(f"  로봇 ID: {args.robot_id}   반복: {args.iterations}회")
    print()

    async with httpx.AsyncClient() as client:
        layers: list[LayerResult] = []

        if args.mock:
            print("[MOCK 모드] 실제 서비스 호출 없이 가상 데이터로 측정합니다.")
            print()
            n = args.iterations
            layers.append(mock_layer("L1",       "App → malle_service  (GET /api/v1/robots)", n))
            layers.append(mock_layer("L2-direct","→ malle_ai_service 직접  (POST /ai/voice-parse)", n))
            layers.append(mock_layer("L3",       "malle_service → bridge_node  (GET /health)", n))
            # L4: 이벤트 간격 시뮬레이션 (args.l4_duration초 * 2Hz 분량)
            n_l4 = max(2, args.l4_duration * 2)
            layers.append(mock_layer("L4",       f"ROS2 제어 루프 추정  ({args.l4_duration}초 시뮬레이션)", n_l4))
            layers.append(mock_layer("L5",       f"bridge_node → malle_service  (PATCH /robots/{args.robot_id}/state)", n))
        else:
            # 서비스 상태 확인
            print("[사전 점검] 서비스 가용성 확인 중...")
            avail = await check_services(client, args.robot_id)
            for name, ok in avail.items():
                mark = "✓" if ok else "✗"
                print(f"  {mark}  {name}")
            print()

            if not avail["malle_service"]:
                print("[오류] malle_service에 연결할 수 없습니다. 서버를 먼저 실행하세요.")
                sys.exit(1)

            # L1
            print(f"[L1] App → malle_service  ({args.iterations}회)...")
            layers.append(await measure_l1(client, args.iterations))

            # L2
            if avail["malle_ai_service"]:
                print(f"[L2] malle_ai_service 직접  ({args.iterations}회)...")
                layers.append(await measure_l2_direct(client, args.iterations))
            else:
                print("[L2] malle_ai_service 오프라인 — 건너뜀")
                layers.append(LayerResult("L2-direct", "malle_ai_service 직접 (오프라인)", errors=1))

            # L3
            if avail["bridge_node"]:
                print(f"[L3] malle_service → bridge_node  ({args.iterations}회)...")
                layers.append(await measure_l3(client, args.iterations))
            else:
                print("[L3] bridge_node 오프라인 — 건너뜀")
                layers.append(LayerResult("L3", "bridge_node (오프라인)", errors=1))

            # L4
            print(f"[L4] ROS2 제어 루프 추정  ({args.l4_duration}초 관측)...")
            if HAS_WS and not args.l4_poll:
                l4 = await measure_l4_ws(args.l4_duration)
            else:
                l4 = await measure_l4_poll(client, args.l4_duration, args.robot_id)
            layers.append(l4)

            # L5
            if avail.get(f"robot_{args.robot_id}"):
                print(f"[L5] bridge_node → malle_service 피드백  ({args.iterations}회)...")
                layers.append(await measure_l5(client, args.iterations, args.robot_id))
            else:
                print(f"[L5] robot_{args.robot_id} 없음 — 건너뜀")
                layers.append(LayerResult("L5", f"robot {args.robot_id} 미등록", errors=1))

    rows = print_results(layers)

    if not args.no_csv:
        fname = save_csv(layers, rows)
        print(f"  결과 저장: {fname}")
        print()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Malle 시스템 레이어별 latency 측정")
    p.add_argument("--iterations", "-n", type=int, default=10,
                   help="L1/L2/L3/L5 측정 반복 횟수 (기본: 10)")
    p.add_argument("--robot-id", "-r", type=int, default=1,
                   help="대상 로봇 ID (기본: 1)")
    p.add_argument("--l4-duration", type=int, default=None,
                   help="L4 관측 시간 초 (기본: mock=1, 실측=20)")
    p.add_argument("--l4-poll", action="store_true",
                   help="L4를 WebSocket 대신 HTTP 폴링으로 측정")
    p.add_argument("--no-csv", action="store_true",
                   help="CSV 파일 저장 안 함")
    p.add_argument("--mock", action="store_true",
                   help="실제 서비스 없이 가상 latency 데이터로 측정 (malle_ai_service 오프라인 시)")
    p.add_argument("--service-url", default=MALLE_SERVICE_URL,
                   help=f"malle_service URL (기본: {MALLE_SERVICE_URL})")
    p.add_argument("--ai-url", default=AI_SERVICE_URL,
                   help=f"malle_ai_service URL (기본: {AI_SERVICE_URL})")
    p.add_argument("--bridge-url", default=BRIDGE_URL,
                   help=f"bridge_node URL (기본: {BRIDGE_URL})")
    args = p.parse_args()
    if args.l4_duration is None:
        args.l4_duration = 1 if args.mock else 20
    return args


if __name__ == "__main__":
    args = parse_args()

    # URL 오버라이드 반영
    MALLE_SERVICE_URL = args.service_url
    AI_SERVICE_URL    = args.ai_url
    BRIDGE_URL        = args.bridge_url
    WS_URL            = f"{MALLE_SERVICE_URL.replace('http', 'ws')}/ws/dashboard"

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
