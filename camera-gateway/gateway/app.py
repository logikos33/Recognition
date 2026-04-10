"""
Flask health + HLS serving endpoint para camera-gateway.
Sem JWT, sem auth — hls.js nao envia headers customizados.
"""
import logging
import os
import re

import redis as _redis
from flask import Flask, jsonify, send_from_directory, abort

logger = logging.getLogger(__name__)

app = Flask(__name__)

_SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_.-]+$')
_HLS_BASE = "/tmp/hls"


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


@app.route("/hls/<camera_id>/<filename>")
def serve_hls(camera_id: str, filename: str):
    """Serve HLS .m3u8 and .ts segments from /tmp/hls/{camera_id}/."""
    if not _SAFE_FILENAME.match(camera_id) or not _SAFE_FILENAME.match(filename):
        abort(400)
    hls_dir = os.path.join(_HLS_BASE, camera_id)
    try:
        return send_from_directory(hls_dir, filename)
    except FileNotFoundError:
        abort(404)


def _ping_redis() -> bool:
    try:
        _redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            socket_timeout=3,
        ).ping()
        return True
    except Exception:
        return False
