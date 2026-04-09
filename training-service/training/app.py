import logging
import uuid

from flask import Flask, jsonify, request

from .job_manager import JobManager
from .redis_client import make_redis

logger = logging.getLogger(__name__)
app = Flask(__name__)
_mgr = JobManager()


@app.route("/health")
def health():
    ok = False
    try:
        make_redis().ping()
        ok = True
    except Exception:
        pass
    return jsonify({"service": "training-service", "status": "healthy" if ok else "degraded",
                    "checks": {"redis": ok}, "active_jobs": len(_mgr.active_jobs())}), 200 if ok else 503


@app.route("/jobs", methods=["POST"])
def start_job():
    data = request.get_json() or {}
    job_id = data.get("job_id") or str(uuid.uuid4())
    dataset_url = data.get("dataset_url", "")
    if not dataset_url:
        return jsonify({"error": "dataset_url required"}), 400
    try:
        return jsonify(_mgr.start_job(job_id, dataset_url)), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id: str):
    return (jsonify({"job_id": job_id, "status": "cancelled"})
            if _mgr.cancel_job(job_id)
            else (jsonify({"error": "not found"}), 404))


@app.route("/jobs", methods=["GET"])
def list_jobs():
    return jsonify({"active_jobs": _mgr.active_jobs()})
