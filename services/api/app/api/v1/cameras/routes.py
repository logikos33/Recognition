"""
Recognition — Camera Routes.

Thin router: all logic lives in handler modules.
Senhas SEMPRE criptografadas — NUNCA retornadas na API.
"""
from flask import Blueprint

from .config_handler import patch_camera_config
from .crud_handlers import create_camera, delete_camera, get_camera, list_cameras, update_camera
from .model_handlers import (
    get_available_models,
    get_camera_model,
    get_camera_models,
    get_effective_model,
    put_camera_models,
    set_camera_model,
)
from .module_handler import get_camera_module_current, patch_camera_module, put_camera_schedule
from .probe_handler import probe_camera
from .retention_handler import get_camera_retention, put_camera_retention
from .stream_handlers import serve_hls, start_stream, stop_stream, stream_info, stream_status
from .tenant_retention_handler import get_tenant_retention, put_tenant_retention
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

# Probe (onboarding — antes de salvar câmera)
cameras_bp.add_url_rule("/probe", view_func=probe_camera, methods=["POST"])

# Test
cameras_bp.add_url_rule("/<camera_id>/test", view_func=test_camera, methods=["POST"])

# Model (legacy GET Redis-only + Task 045 PUT persistente)
cameras_bp.add_url_rule("/<camera_id>/model", view_func=get_camera_model, methods=["GET"])
cameras_bp.add_url_rule("/<camera_id>/model", view_func=set_camera_model, methods=["PUT"])

# Model — Task 045: atribuição por módulo explícito
cameras_bp.add_url_rule("/<camera_id>/models", view_func=get_camera_models, methods=["GET"])
cameras_bp.add_url_rule("/<camera_id>/models", view_func=put_camera_models, methods=["PUT"])

# FPS / Quality config (deliverable j)
cameras_bp.add_url_rule("/<camera_id>/config", view_func=patch_camera_config, methods=["PATCH"])

# Model — Task 045: available-models e effective-model
cameras_bp.add_url_rule(
    "/<camera_id>/available-models", view_func=get_available_models, methods=["GET"]
)
cameras_bp.add_url_rule(
    "/<camera_id>/effective-model", view_func=get_effective_model, methods=["GET"]
)

# Module + Schedule
cameras_bp.add_url_rule("/<camera_id>/module", view_func=patch_camera_module, methods=["PATCH"])
cameras_bp.add_url_rule("/<camera_id>/schedule", view_func=put_camera_schedule, methods=["PUT"])
cameras_bp.add_url_rule(
    "/<camera_id>/module/current", view_func=get_camera_module_current, methods=["GET"]
)

# Retention tiers (task-047)
cameras_bp.add_url_rule("/<camera_id>/retention", view_func=get_camera_retention, methods=["GET"])
cameras_bp.add_url_rule("/<camera_id>/retention", view_func=put_camera_retention, methods=["PUT"])

# Tenant-level retention default
cameras_bp.add_url_rule("/tenant/retention", view_func=get_tenant_retention, methods=["GET"])
cameras_bp.add_url_rule("/tenant/retention", view_func=put_tenant_retention, methods=["PUT"])

# ---------------------------------------------------------------------------
# v1-versioned aliases — probe, effective-model, config.
# O Blueprint principal está em /api/cameras (legado). Clientes que usam o
# prefixo /api/v1/cameras eram servidos pelo catch-all → 405/200.
# Estes aliases corrigem as rotas sem alterar o Blueprint existente.
# ---------------------------------------------------------------------------
cameras_v1_bp = Blueprint("cameras_v1", __name__, url_prefix="/api/v1/cameras")
cameras_v1_bp.add_url_rule(
    "/probe",
    endpoint="probe_camera_v1",
    view_func=probe_camera,
    methods=["POST"],
)
cameras_v1_bp.add_url_rule(
    "/<camera_id>/effective-model",
    endpoint="get_effective_model_v1",
    view_func=get_effective_model,
    methods=["GET"],
)
cameras_v1_bp.add_url_rule(
    "/<camera_id>/config",
    endpoint="patch_camera_config_v1",
    view_func=patch_camera_config,
    methods=["PATCH"],
)
