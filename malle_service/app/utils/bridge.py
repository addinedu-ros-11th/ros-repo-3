"""
malle_service/app/utils/bridge.py

bridge_node(:9100) HTTP API 호출 유틸.

malle_service 내부에서 ROS2 명령을 보낼 때 이 모듈만 사용.
bridge_node가 오프라인이어도 예외를 던지지 않고 False 반환.

사용처:
  - app/routers/teleop.py  (teleop start/stop/cmd)
  - app/routers/guide.py   (navigate to POI)
  - app/ws/handlers.py     (WS TELEOP_CMD 실시간 처리)
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

BRIDGE_NODE_URL = os.getenv("BRIDGE_NODE_URL", "http://localhost:9100")


async def send_to_bridge(endpoint: str, payload: dict) -> bool:
    """
    bridge_node HTTP API 호출.

    Args:
        endpoint: bridge_node 엔드포인트 경로 (예: "teleop/cmd", "navigate")
                  앞에 /bridge/ 는 자동으로 붙음.
        payload:  JSON body

    Returns:
        True  — bridge_node 응답 200
        False — 연결 실패 또는 오류 (로그만 남기고 흐름 유지)
    """
    url = f"{BRIDGE_NODE_URL}/bridge/{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        logger.debug(f"[bridge] {endpoint} unreachable — skipped")
        return False
    except Exception as e:
        logger.warning(f"[bridge] {endpoint} error: {e}")
        return False