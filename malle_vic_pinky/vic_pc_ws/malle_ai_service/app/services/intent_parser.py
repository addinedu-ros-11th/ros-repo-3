"""
Intent parser service.
LLM model is TBD — this module provides a pluggable interface.
Currently uses keyword-based fallback for demo.
"""

from typing import Any

# Intents available per client type
MOBILE_INTENTS = {"GUIDE_TO", "FIND_STORE", "OPEN_LOCKBOX", "START_FOLLOW", "CREATE_PICKUP", "ADD_TO_LIST", "CHECK_STATUS"}
ROBOT_INTENTS = {"GUIDE_TO", "FIND_STORE", "OPEN_LOCKBOX", "START_FOLLOW", "CREATE_PICKUP", "CHECK_STATUS", "EMERGENCY_STOP", "RETURN_TO_STATION"}


def parse_intent(text: str, client_type: str, session_id: int | None = None, robot_id: int | None = None) -> dict[str, Any]:
    """
    Parse text into a structured intent.

    TODO: Replace keyword fallback with actual LLM call.
    The LLM integration point is the `_call_llm()` function below.
    """
    # Try LLM first (when configured)
    llm_result = _call_llm(text, client_type)
    if llm_result:
        return llm_result

    # Fallback: keyword-based parsing (demo)
    return _keyword_fallback(text, client_type)


def _call_llm(text: str, client_type: str) -> dict[str, Any] | None:
    """
    Call LLM for intent classification.

    TODO: Implement with chosen LLM (OpenAI / Claude / Gemini).
    Should return:
        { "intent": "GUIDE_TO", "params": { "destination": "Nike" }, "confidence": 0.95 }
    Or None if LLM is not configured.
    """
    # LLM not configured yet — return None to fall through to keyword parser
    return None


def _keyword_fallback(text: str, client_type: str) -> dict[str, Any]:
    """Simple keyword-based intent detection for demo purposes."""
    text_lower = text.lower()

    # Guide
    guide_keywords = ["안내", "가줘", "데려다", "어디", "가이드", "guide", "take me", "go to"]
    if any(kw in text_lower for kw in guide_keywords):
        return {"intent": "GUIDE_TO", "params": {"destination_raw": text}, "confidence": 0.6}

    # Follow
    follow_keywords = ["따라와", "팔로우", "follow"]
    if any(kw in text_lower for kw in follow_keywords):
        return {"intent": "START_FOLLOW", "params": {}, "confidence": 0.6}

    # Lockbox
    lockbox_keywords = ["락박스", "열어", "lockbox", "open"]
    if any(kw in text_lower for kw in lockbox_keywords):
        return {"intent": "OPEN_LOCKBOX", "params": {}, "confidence": 0.6}

    # Pickup
    pickup_keywords = ["픽업", "주문", "pickup", "order"]
    if any(kw in text_lower for kw in pickup_keywords):
        return {"intent": "CREATE_PICKUP", "params": {"store_raw": text}, "confidence": 0.6}

    # Emergency stop (robot only)
    if client_type == "robot" and any(kw in text_lower for kw in ["멈춰", "정지", "stop", "emergency"]):
        return {"intent": "EMERGENCY_STOP", "params": {}, "confidence": 0.8}

    # Shopping list (mobile only)
    if client_type == "mobile" and any(kw in text_lower for kw in ["추가", "리스트", "장바구니", "add to list"]):
        return {"intent": "ADD_TO_LIST", "params": {"item_raw": text}, "confidence": 0.5}

    # Status
    if any(kw in text_lower for kw in ["상태", "status", "어떻게"]):
        return {"intent": "CHECK_STATUS", "params": {}, "confidence": 0.5}

    return {"intent": "UNKNOWN", "params": {"raw_text": text}, "confidence": 0.0}
