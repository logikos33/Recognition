"""
EPI Monitor V2 — Frames Routes.

Endpoints para pré-anotação e Active Learning (proxy para pre-annotation-service).
"""
import logging
import os

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success

logger = logging.getLogger(__name__)

frames_bp = Blueprint("frames", __name__, url_prefix="/api/frames")

_PRE_ANNOT_URL = os.environ.get(
    "PRE_ANNOTATION_URL",
    os.environ.get("PRE_ANNOTATION_SERVICE_URL", "http://pre-annotation-service.railway.internal:8080"),
)


def _proxy_post(path: str, payload: dict) -> tuple:
    """Encaminha POST para o pre-annotation-service."""
    try:
        import requests as req_lib
        resp = req_lib.post(
            f"{_PRE_ANNOT_URL}{path}",
            json=payload,
            timeout=300,
        )
        data = resp.json()
        if resp.ok:
            return success(data.get("data", data))
        return error(data.get("error", "Pre-annotation service error"), resp.status_code)
    except Exception as exc:
        logger.error("pre_annot_proxy_error: path=%s err=%s", path, exc)
        return error("Pre-annotation service indisponível", 503)


@frames_bp.route("/<frame_id>/pre-annotate", methods=["POST"])
@jwt_required()
def trigger_pre_annotate(frame_id: str):  # type: ignore[no-untyped-def]
    """Dispara pré-anotação DINO+SAM para um frame."""
    return _proxy_post(f"/api/v1/pre-annotate/{frame_id}", {})


@frames_bp.route("/prioritize", methods=["POST"])
@jwt_required()
def prioritize_frames():  # type: ignore[no-untyped-def]
    """Prioriza frames para anotação via Active Learning."""
    tenant_id = get_tenant_id()
    body = request.get_json() or {}
    module_code = body.get("module_code", "epi")
    return _proxy_post(
        "/api/v1/frames/prioritize", {"tenant_id": tenant_id, "module_code": module_code}
    )
