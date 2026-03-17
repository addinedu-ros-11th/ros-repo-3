"""Voice intent parsing endpoint."""

from flask import Blueprint, request, jsonify
from app.services.intent_parser import parse_intent

voice_bp = Blueprint("voice", __name__)


@voice_bp.route("/ai/voice-parse", methods=["POST"])
def voice_parse():
    """
    Parse text into an intent.

    Request:
        {
            "text": "나이키 매장으로 안내해줘",
            "client_type": "mobile" | "robot",
            "session_id": 123,
            "robot_id": null
        }

    Response:
        {
            "intent": "GUIDE_TO",
            "params": { "destination": "Nike", "poi_id": 2 },
            "confidence": 0.95
        }
    """
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "text is required"}), 400

    result = parse_intent(
        text=data["text"],
        client_type=data.get("client_type", "mobile"),
        session_id=data.get("session_id"),
        robot_id=data.get("robot_id"),
    )

    return jsonify(result)