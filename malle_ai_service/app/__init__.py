"""
malle_ai_service - AI service for voice intent parsing.
Port: 5000
LLM model: TBD
"""

from flask import Flask


def create_app():
    app = Flask(__name__)

    from app.routes.voice import voice_bp
    app.register_blueprint(voice_bp)

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "malle_ai_service"}

    return app