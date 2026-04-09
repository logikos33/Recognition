"""
Flask app + SocketIO.

Namespaces:
  /monitor  — detecções em tempo real e alertas
  /training — progresso de treinos
"""
import logging
import os

import jwt
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room

from .redis_client import make_redis
from . import config

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(32).hex())

socketio = SocketIO(
    app,
    cors_allowed_origins=config.CORS_ORIGINS,
    async_mode="eventlet",
    logger=False,
    engineio_logger=False,
)


def _validate_token(token: str) -> dict | None:
    if not config.JWT_SECRET_KEY:
        return {"sub": "anonymous"}
    try:
        return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


@app.route("/health")
def health():
    redis_ok = False
    try:
        make_redis().ping()
        redis_ok = True
    except Exception:
        pass
    status = "healthy" if redis_ok else "degraded"
    return jsonify({
        "service": "ws-gateway",
        "status": status,
        "checks": {"redis": redis_ok},
    }), 200 if redis_ok else 503


@socketio.on("connect", namespace="/monitor")
def monitor_connect():
    token = request.args.get("token", "")
    payload = _validate_token(token)
    if payload is None:
        logger.warning("ws_connect_rejected: invalid token")
        return False
    user_id = payload.get("sub", "")
    join_room(f"user:{user_id}")
    logger.info("ws_connected: user=%s", user_id)


@socketio.on("subscribe_camera", namespace="/monitor")
def monitor_subscribe(data: dict):
    camera_id = data.get("camera_id", "")
    if camera_id:
        join_room(f"camera:{camera_id}")
        emit("subscribed", {"camera_id": camera_id})


@socketio.on("unsubscribe_camera", namespace="/monitor")
def monitor_unsubscribe(data: dict):
    camera_id = data.get("camera_id", "")
    if camera_id:
        leave_room(f"camera:{camera_id}")
        emit("unsubscribed", {"camera_id": camera_id})


@socketio.on("disconnect", namespace="/monitor")
def monitor_disconnect():
    logger.info("ws_disconnected")


@socketio.on("connect", namespace="/training")
def training_connect():
    token = request.args.get("token", "")
    payload = _validate_token(token)
    if payload is None:
        return False


@socketio.on("subscribe_job", namespace="/training")
def training_subscribe(data: dict):
    job_id = data.get("job_id", "")
    if job_id:
        join_room(f"job:{job_id}")
        emit("subscribed", {"job_id": job_id})


@socketio.on("disconnect", namespace="/training")
def training_disconnect():
    pass
