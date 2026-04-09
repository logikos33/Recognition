import logging
import os
import redis as _redis
from flask import Flask, jsonify
from .routes import auth_bp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = Flask(__name__)
app.register_blueprint(auth_bp)


@app.route("/health")
def health():
    redis_ok = db_ok = False
    try:
        _redis.from_url(os.environ.get("REDIS_URL", ""), socket_timeout=3).ping()
        redis_ok = True
    except Exception:
        pass
    try:
        from .db import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass
    ok = redis_ok and db_ok
    return jsonify({"service": "auth-service",
                    "status": "healthy" if ok else "degraded",
                    "checks": {"redis": redis_ok, "database": db_ok}}), 200 if ok else 503
