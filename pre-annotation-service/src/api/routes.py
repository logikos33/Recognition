"""API routes do Pre-Annotation Service."""
import logging

from flask import Blueprint, request, jsonify

from src.services.pre_annotator import pre_annotate_frame, pre_annotate_batch
from src.services.active_learning import prioritize_frames

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.route("/pre-annotate/<frame_id>", methods=["POST"])
def pre_annotate_single(frame_id: str):
    """Pré-anota um frame específico via DINO + SAM."""
    try:
        result = pre_annotate_frame(frame_id)
        return jsonify({"success": True, "data": result})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        logger.error("pre_annotate_error: frame=%s err=%s", frame_id, exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@api_bp.route("/pre-annotate/batch", methods=["POST"])
def pre_annotate_batch_endpoint():
    """Pré-anota múltiplos frames (máx 50)."""
    data = request.get_json() or {}
    frame_ids = data.get("frame_ids", [])

    if not frame_ids:
        return jsonify({"success": False, "error": "frame_ids required"}), 400
    if len(frame_ids) > 50:
        return jsonify({"success": False, "error": "max 50 frames per batch"}), 400

    try:
        result = pre_annotate_batch(frame_ids)
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        logger.error("batch_error: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@api_bp.route("/frames/prioritize", methods=["POST"])
def prioritize_frames_endpoint():
    """Prioriza frames para anotação via Active Learning."""
    data = request.get_json() or {}
    tenant_id = data.get("tenant_id")
    module_code = data.get("module_code", "epi")

    if not tenant_id:
        return jsonify({"success": False, "error": "tenant_id required"}), 400

    try:
        result = prioritize_frames(tenant_id, module_code)
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        logger.error("prioritize_error: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500
