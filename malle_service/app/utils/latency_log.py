"""
malle_service 레이어별 latency 로그 버퍼.

bridge_node의 /logs 엔드포인트와 함께 test/log_latency.py로 수집·분석합니다.

로그 형식:
  {"ts": 1234567890.123, "layer": "L1", "event": "guide_execute", "session_id": 5, "ms": 12.3}
"""

import time
from collections import deque
from typing import Any

_buf: deque = deque(maxlen=500)


def log(layer: str, event: str, **extra: Any) -> float:
    """타임스탬프와 함께 레이어 이벤트를 버퍼에 기록. 현재 타임스탬프(float) 반환."""
    ts = time.time()
    _buf.append({"ts": ts, "layer": layer, "event": event, **extra})
    return ts


def get_logs() -> list[dict]:
    return list(_buf)


def clear():
    _buf.clear()
