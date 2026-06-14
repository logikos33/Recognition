"""EPI Assistant — endpoint de chat com streaming SSE."""
import json
import logging

from flask import Blueprint, Response, request, stream_with_context
from flask_jwt_extended import jwt_required

from app.core.responses import error
from app.domain.services.assistant_service import build_prompt, retrieve_context
from app.infrastructure.ollama_client import get_ollama_client

logger = logging.getLogger(__name__)
chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@chat_bp.route("", methods=["POST"])
@jwt_required()
def chat() -> Response:
    """
    POST /api/chat
    Body: {"message": "...", "history": [...]}
    Retorna: SSE stream com tokens do assistente.
    """
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return error("message obrigatório", 400)

    ollama = get_ollama_client()

    if not ollama.is_available():
        return error("Assistente indisponível (Ollama offline)", 503)

    from app.infrastructure.database.connection import DatabasePool
    pool = DatabasePool.get_instance()

    context_chunks = retrieve_context(message, pool, ollama) if pool else []
    prompt = build_prompt(message, context_chunks, history)

    def generate():
        try:
            for token in ollama.generate_stream(prompt):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            logger.error("chat_stream_error: %s", exc)
            yield f"data: {json.dumps({'error': 'Erro ao gerar resposta'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@chat_bp.route("/health", methods=["GET"])
def chat_health() -> Response:
    """GET /api/chat/health — verifica disponibilidade do Ollama."""
    ollama = get_ollama_client()
    available = ollama.is_available()
    return Response(
        json.dumps({"available": available, "model": ollama.model}),
        mimetype="application/json",
        status=200 if available else 503,
    )
