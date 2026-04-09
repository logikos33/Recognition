"""
EPI Monitor V2 — Camera Routes.

Thin router: all logic lives in handler modules.
Senhas SEMPRE criptografadas — NUNCA retornadas na API.
"""
from flask import Blueprint

from .crud_handlers import list_cameras, create_camera, get_camera, update_camera, delete_camera
from .stream_handlers import start_stream, stop_stream, stream_status, serve_hls
from .test_handler import test_camera
from .model_handlers import get_camera_model, set_camera_model

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
cameras_bp.add_url_rule("/<camera_id>/stream/<path:filename>", view_func=serve_hls, methods=["GET"])

# Test
cameras_bp.add_url_rule("/<camera_id>/test", view_func=test_camera, methods=["POST"])

# Model
cameras_bp.add_url_rule("/<camera_id>/model", view_func=get_camera_model, methods=["GET"])
cameras_bp.add_url_rule("/<camera_id>/model", view_func=set_camera_model, methods=["PUT"])
