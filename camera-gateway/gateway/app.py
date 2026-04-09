"""
Flask health endpoint para Railway healthcheck.
Sem JWT, sem auth — apenas verifica Redis.
"""
import logging
import os

import redis as _redis
from flask import Flask, jsonify

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/health")
def health():
    redis_ok = _ping_redis()
    status = "healthy" if redis_ok else "degraded"
    code = 200 if redis_ok else 503
    return jsonify({
        "status": status,
        "service": "camera-gateway",
        "checks": {"redis": redis_ok},
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
