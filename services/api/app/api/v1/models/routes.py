"""
Model Rollout Routes — API v1.

GET  /api/v1/models/active?module=<code>  → manifesto do modelo ativo
POST /api/v1/models/<id>/pin              → pin de versão (admin; suporta canary)
"""
from flask import Blueprint

from .handlers import get_active_manifest, pin_model_version

models_rollout_bp = Blueprint("models_rollout", __name__, url_prefix="/api/v1/models")

models_rollout_bp.add_url_rule("/active", view_func=get_active_manifest, methods=["GET"])
models_rollout_bp.add_url_rule(
    "/<model_id>/pin", view_func=pin_model_version, methods=["POST"]
)
