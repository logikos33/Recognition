"""
Flask health endpoint para Railway healthcheck.
Sem JWT, sem auth — apenas verifica Redis e estado do modelo.
"""
import logging
import os

import redis as _redis
from flask import Flask, jsonify

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Referência ao engine é injetada pelo main.py após inicialização
_engine_ref = None


def set_engine(engine) -> None:
    global _engine_ref
    _engine_ref = engine


@app.route("/health")
def health():
    redis_ok = _ping_redis()
    model_ok = _engine_ref.is_ready() if _engine_ref else False
    all_ok = redis_ok and model_ok
    status = "healthy" if all_ok else "degraded"
    code = 200 if all_ok else 503
    return jsonify({
        "status": status,
        "service": "inference-service",
        "checks": {
            "redis": redis_ok,
            "model_loaded": model_ok,
        },
    }), code


def _ping_redis() -> bool:
    try:
        _redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            socket_timeout=3,
        ).ping()
        return True
    except Exception:
        return False
