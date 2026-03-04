"""
malle_service/app/ws/handlers.py

WebSocket inbound message handlers.
클라이언트(mobile/robot/dashboard)가 WS로 보내는 메시지 처리.

대부분의 클라이언트→서버 통신은 REST API로 하지만,
일부 실시간 명령(teleop, PING)은 WS로 처리.
"""

import logging
import time

import httpx

from app.config import AI_SERVICE_URL
from app.utils.bridge import send_to_bridge
from app.utils.latency_log import log as _log
from app.ws.manager import manager

logger = logging.getLogger(__name__)


async def handle_dashboard_teleop(payload: dict):
    """
    대시보드 WS TELEOP_CMD 처리.
    기존: self(:8000) 재호출 → 수정: bridge_node 직접 호출
    """
    robot_id = payload.get("robot_id")
    linear_x  = float(payload.get("linear_x", 0.0))
    angular_z = float(payload.get("angular_z", 0.0))

    if robot_id is None:
        logger.debug("[teleop] TELEOP_CMD missing robot_id — ignored")
        return

    await send_to_bridge("teleop/cmd", {
        "robot_id": robot_id,
        "linear_x": linear_x,
        "angular_z": angular_z,
    })


async def handle_voice_command(session_id: int, text: str, client_type: str = "mobile"):
    """
    음성 명령을 AI 서비스로 포워딩하고 결과를 WS로 반환.
    """
    t0 = time.perf_counter()
    _log("L2", "ai_call_start", session_id=session_id, client_type=client_type)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{AI_SERVICE_URL}/ai/voice-parse",
                json={
                    "text": text,
                    "client_type": client_type,
                    "session_id": session_id,
                },
            )
            result = resp.json()
    except httpx.ConnectError:
        result = {"intent": "UNKNOWN", "error": "AI service unreachable"}
    except Exception as e:
        result = {"intent": "UNKNOWN", "error": str(e)}

    elapsed_ms = (time.perf_counter() - t0) * 1000
    _log("L2", "ai_call_done", session_id=session_id,
         intent=result.get("intent"), ms=round(elapsed_ms, 2))

    await manager.send_to_mobile(session_id, "VOICE_RESULT", result)
    return result