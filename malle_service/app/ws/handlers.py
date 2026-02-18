"""
WebSocket inbound message handlers.
클라이언트(mobile/robot/dashboard)가 WS로 보내는 메시지 처리.

대부분의 클라이언트→서버 통신은 REST API로 하지만,
일부 실시간 명령(teleop, PING)은 WS로 처리.
"""

import json
import logging

import httpx

from app.config import AI_SERVICE_URL
from app.ws.manager import manager

logger = logging.getLogger(__name__)


async def handle_dashboard_teleop(payload: dict):
    """
    대시보드에서 WS로 보내는 텔레옵 명령 처리.
    REST API POST /robots/{id}/teleop/cmd 로 내부 포워딩.
    """
    robot_id = payload.get("robot_id")
    linear_x = payload.get("linear_x", 0.0)
    angular_z = payload.get("angular_z", 0.0)

    if not robot_id:
        return

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                f"http://localhost:8000/api/v1/robots/{robot_id}/teleop/cmd",
                json={"linear_x": linear_x, "angular_z": angular_z},
            )
    except httpx.ConnectError:
        logger.debug("Teleop forward failed: service unreachable")
    except Exception as e:
        logger.warning(f"Teleop forward error: {e}")


async def handle_voice_command(session_id: int, text: str, client_type: str = "mobile"):
    """
    음성 명령을 AI 서비스로 포워딩하고 결과를 WS로 반환.
    """
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

    await manager.send_to_mobile(session_id, "VOICE_RESULT", result)
    return result
