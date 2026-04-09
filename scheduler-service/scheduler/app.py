import logging
import os
import redis as _redis
from flask import Flask, jsonify

logger = logging.getLogger(__name__)
app = Flask(__name__)


@app.route("/health")
def health():
    ok = False
    try:
        _redis.from_url(os.environ.get("REDIS_URL", ""), socket_timeout=3).ping()
        ok = True
    except Exception:
        pass
    return jsonify({"service": "scheduler-service",
                    "status": "healthy" if ok else "degraded",
                    "checks": {"redis": ok}}), 200 if ok else 503
