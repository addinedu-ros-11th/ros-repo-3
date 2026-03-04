#!/usr/bin/env python3
"""
test/log_latency.py — L1~L5 레이어간 레이턴시 분석 도구.

malle_service(:8000) 와 bridge_node(:9100) 에서 로그를 수집한 뒤
각 이벤트 체인의 소요 시간을 테이블로 출력합니다.

레이어 정의:
  L1  guide_execute         malle_service — execute_guide_queue 진입
  L2  ai_call_done          malle_service — AI 서비스 응답 완료 (voice)
  L3  navigate_received     bridge_node  — /bridge/navigate 수신
  L4  ros2_dispatched       bridge_node  — ROS2 스레드 시작
  L5  state_pushed          bridge_node  — _push_state PATCH 완료

사용:
  python3 test/log_latency.py
  python3 test/log_latency.py --bridge http://<로봇 IP>:9100
  python3 test/log_latency.py --service http://<로컬 PC IP>:8000/api/v1
  python3 test/log_latency.py --clear   # 양쪽 로그 버퍼 초기화 후 종료
"""

import argparse
import sys
from typing import Any

try:
    import httpx
except ImportError:
    print("httpx 필요: pip install httpx")
    sys.exit(1)


DEFAULT_SERVICE = "http://localhost:8000/api/v1"
DEFAULT_BRIDGE  = "http://localhost:9100"


def fetch_logs(service_url: str, bridge_url: str) -> tuple[list[dict], list[dict]]:
    svc_logs: list[dict] = []
    brg_logs: list[dict] = []

    try:
        r = httpx.get(f"{service_url}/debug/logs", timeout=5.0)
        svc_logs = r.json().get("logs", [])
    except Exception as e:
        print(f"[warn] malle_service 로그 수집 실패: {e}")

    try:
        r = httpx.get(f"{bridge_url}/logs", timeout=5.0)
        brg_logs = r.json().get("logs", [])
    except Exception as e:
        print(f"[warn] bridge_node 로그 수집 실패: {e}")

    return svc_logs, brg_logs


def clear_logs(service_url: str, bridge_url: str):
    try:
        httpx.delete(f"{service_url}/debug/logs", timeout=5.0)
        print(f"[ok] malle_service 로그 초기화")
    except Exception as e:
        print(f"[warn] malle_service 초기화 실패: {e}")
    try:
        httpx.delete(f"{bridge_url}/logs", timeout=5.0)
        print(f"[ok] bridge_node 로그 초기화")
    except Exception as e:
        print(f"[warn] bridge_node 초기화 실패: {e}")


def _fmt_ms(val: Any) -> str:
    if val is None:
        return "  —  "
    return f"{val:7.1f} ms"


def analyze(svc_logs: list[dict], brg_logs: list[dict]):
    all_logs = sorted(svc_logs + brg_logs, key=lambda x: x.get("ts", 0))

    if not all_logs:
        print("로그 없음. 먼저 테스트를 실행하세요.")
        return

    # ── Guide 실행 체인 분석 ─────────────────────────────────────────────
    # L1 guide_execute → L3 navigate_received → L4 ros2_dispatched → L5 state_pushed
    guide_chains: list[dict] = []

    l1_events = [e for e in svc_logs if e.get("event") == "guide_execute"]
    l3_events = [e for e in brg_logs if e.get("event") == "navigate_received"]
    l4_events = [e for e in brg_logs if e.get("event") == "ros2_dispatched"]
    l5_events = [e for e in brg_logs if e.get("event") == "state_pushed" and e.get("ok")]

    for l1 in l1_events:
        ts1 = l1["ts"]
        sid = l1.get("session_id")

        # 가장 가까운 후속 이벤트 찾기
        l3 = next((e for e in l3_events
                   if e["ts"] >= ts1 and (sid is None or e.get("session_id") == sid)), None)
        l4 = next((e for e in l4_events
                   if e["ts"] >= ts1 and (sid is None or e.get("session_id") == sid)), None)
        l5 = next((e for e in l5_events if e["ts"] >= (l4["ts"] if l4 else ts1)), None)

        guide_chains.append({
            "session_id": sid,
            "ts_L1": ts1,
            "ts_L3": l3["ts"] if l3 else None,
            "ts_L4": l4["ts"] if l4 else None,
            "ts_L5": l5["ts"] if l5 else None,
            "L5_ms": l5.get("ms") if l5 else None,
        })

    # ── Voice (AI) 분석 ──────────────────────────────────────────────────
    ai_events = [e for e in svc_logs if e.get("event") == "ai_call_done"]

    # ── Bridge call 분석 (L3 side from malle_service) ────────────────────
    bridge_calls = [e for e in svc_logs if e.get("event") == "bridge_call_done"]

    # ── 출력 ─────────────────────────────────────────────────────────────
    print("\n" + "═" * 62)
    print("  레이어별 레이턴시 분석")
    print("═" * 62)

    # Guide 체인
    print(f"\n[Guide 실행 체인]  총 {len(guide_chains)}건")
    if guide_chains:
        print(f"  {'session':>8}  {'L1→L3':>10}  {'L3→L4':>10}  {'L4→L5':>10}  {'L5(PATCH)':>11}  {'L1→L5':>10}")
        print(f"  {'-'*8}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*11}  {'-'*10}")
        for c in guide_chains:
            l1_l3 = (c["ts_L3"] - c["ts_L1"]) * 1000 if c["ts_L3"] else None
            l3_l4 = (c["ts_L4"] - c["ts_L3"]) * 1000 if c["ts_L3"] and c["ts_L4"] else None
            l4_l5 = (c["ts_L5"] - c["ts_L4"]) * 1000 if c["ts_L4"] and c["ts_L5"] else None
            total = (c["ts_L5"] - c["ts_L1"]) * 1000 if c["ts_L5"] else None
            sid_str = str(c["session_id"]) if c["session_id"] is not None else "?"
            print(
                f"  {sid_str:>8}  "
                f"{_fmt_ms(l1_l3)}  "
                f"{_fmt_ms(l3_l4)}  "
                f"{_fmt_ms(l4_l5)}  "
                f"{_fmt_ms(c['L5_ms'])}  "
                f"{_fmt_ms(total)}"
            )
        if len(guide_chains) > 1:
            totals = [(c["ts_L5"] - c["ts_L1"]) * 1000
                      for c in guide_chains if c["ts_L1"] and c["ts_L5"]]
            if totals:
                avg = sum(totals) / len(totals)
                print(f"\n  평균 E2E (L1→L5): {avg:.1f} ms  ({len(totals)}건)")

    # Voice (L2)
    print(f"\n[AI 서비스 (L2)]  총 {len(ai_events)}건")
    if ai_events:
        durations = [e["ms"] for e in ai_events if e.get("ms") is not None]
        if durations:
            avg = sum(durations) / len(durations)
            print(f"  avg={avg:.1f} ms  min={min(durations):.1f}  max={max(durations):.1f}")
        for e in ai_events[-5:]:
            sid = e.get("session_id", "?")
            intent = e.get("intent", "?")
            ms = e.get("ms")
            print(f"  session={sid}  intent={intent}  {_fmt_ms(ms)}")

    # Bridge calls from malle_service (L3 측)
    print(f"\n[Bridge HTTP 호출 (malle_service→bridge)]  총 {len(bridge_calls)}건")
    if bridge_calls:
        durations = [e["ms"] for e in bridge_calls if e.get("ms") is not None]
        if durations:
            avg = sum(durations) / len(durations)
            print(f"  avg={avg:.1f} ms  min={min(durations):.1f}  max={max(durations):.1f}")
        for e in bridge_calls[-5:]:
            print(f"  endpoint={e.get('endpoint','?')}  ok={e.get('ok')}  {_fmt_ms(e.get('ms'))}")

    # L5 state_pushed 통계
    l5_ok = [e for e in brg_logs if e.get("event") == "state_pushed" and e.get("ok")]
    print(f"\n[State Push (L5, 0.5s 주기)]  총 {len(l5_ok)}건")
    if l5_ok:
        durations = [e["ms"] for e in l5_ok if e.get("ms") is not None]
        if durations:
            avg = sum(durations) / len(durations)
            print(f"  avg={avg:.1f} ms  min={min(durations):.1f}  max={max(durations):.1f}")

    print("\n" + "═" * 62 + "\n")

    # ── 원시 로그 요약 ───────────────────────────────────────────────────
    print(f"수집 로그 수: malle_service={len(svc_logs)}, bridge_node={len(brg_logs)}")
    if all_logs:
        import datetime
        oldest = datetime.datetime.fromtimestamp(all_logs[0]["ts"]).strftime("%H:%M:%S")
        newest = datetime.datetime.fromtimestamp(all_logs[-1]["ts"]).strftime("%H:%M:%S")
        print(f"시간 범위: {oldest} ~ {newest}")


def main():
    parser = argparse.ArgumentParser(description="L1~L5 레이턴시 분석")
    parser.add_argument("--service", default=DEFAULT_SERVICE,
                        help=f"malle_service URL (default: {DEFAULT_SERVICE})")
    parser.add_argument("--bridge", default=DEFAULT_BRIDGE,
                        help=f"bridge_node URL (default: {DEFAULT_BRIDGE})")
    parser.add_argument("--clear", action="store_true",
                        help="로그 버퍼 초기화 후 종료")
    args = parser.parse_args()

    if args.clear:
        clear_logs(args.service, args.bridge)
        return

    svc_logs, brg_logs = fetch_logs(args.service, args.bridge)
    analyze(svc_logs, brg_logs)


if __name__ == "__main__":
    main()
