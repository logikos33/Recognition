"""
Recognition — Camera Routes.

Thin router: all logic lives in handler modules.
Senhas SEMPRE criptografadas — NUNCA retornadas na API.
"""
from flask import Blueprint

from .crud_handlers import create_camera, delete_camera, get_camera, list_cameras, update_camera
from .model_handlers import get_camera_model, set_camera_model
from .module_handler import get_camera_module_current, patch_camera_module, put_camera_schedule
from .stream_handlers import serve_hls, start_stream, stop_stream, stream_info, stream_status
from .test_handler import test_camera

cameras_bp = Blueprint("cameras", __name__, url_prefix="/api/cameras")

# CRUD
cameras_bp.add_url_rule("", view_func=list_cameras, methods=["GET"])
cameras_bp.add_url_rule("", view_func=create_camera, methods=["POST"])
cameras_bp.add_url_rule("/<camera_id>", view_func=get_camera, methods=["GET"])
cameras_bp.add_url_rule("/<camera_id>", view_func=update_camera, methods=["PUT"])
cameras_bp.add_url_rule("/<camera_id>", view_func=delete_camera, methods=["DELETE"])

# Stream
cameras_bp.add_url_rule("/<camera_id>/stream/start", view_func=start_stream, methods=["POST"])
cameras_bp.add_url_rule("/<camera_id>/stream/stop", view_func=stop_stream, methods=["POST"])
cameras_bp.add_url_rule("/<camera_id>/stream/status", view_func=stream_status, methods=["GET"])
cameras_bp.add_url_rule("/<camera_id>/stream/info", view_func=stream_info, methods=["GET"])
cameras_bp.add_url_rule("/<camera_id>/stream/<path:filename>", view_func=serve_hls, methods=["GET"])

# Test
cameras_bp.add_url_rule("/<camera_id>/test", view_func=test_camera, methods=["POST"])

# Model
cameras_bp.add_url_rule("/<camera_id>/model", view_func=get_camera_model, methods=["GET"])
cameras_bp.add_url_rule("/<camera_id>/model", view_func=set_camera_model, methods=["PUT"])

# Module + Schedule
cameras_bp.add_url_rule("/<camera_id>/module", view_func=patch_camera_module, methods=["PATCH"])
cameras_bp.add_url_rule("/<camera_id>/schedule", view_func=put_camera_schedule, methods=["PUT"])
cameras_bp.add_url_rule(
    "/<camera_id>/module/current", view_func=get_camera_module_current, methods=["GET"]
)
