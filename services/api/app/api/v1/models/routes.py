"""
Model Rollout + Registry Routes — API v1.

Rollout ({schema}.models — manifesto pin/canary, intocado):
  GET  /api/v1/models/active?module=<code>  → manifesto do modelo ativo
  POST /api/v1/models/<id>/pin              → pin de versão (admin; suporta canary)

Registry (public.trained_models — WS-A5, no blueprint EXISTENTE por
decisão do ajuste #6 da revisão arquitetural):
  GET  /api/v1/models                       → lista do tenant (?module=&status=)
  GET  /api/v1/models/<id>                  → detalhe + linhagem + deployments
  POST /api/v1/models/<id>/activate         → ativa (gate de eval; force só admin)
  GET  /api/v1/models/<id>/eval             → última avaliação campeão×desafiante
  POST /api/v1/models/<id>/evaluate         → dispara avaliação campeão×desafiante (WS-C1)
  GET  /api/v1/models/<id>/drift            → janelas de drift

Werkzeug resolve a rota literal /active ANTES da variável /<model_id> —
sem colisão (verificado na revisão arquitetural, defect E-1).
"""
from flask import Blueprint

from .handlers import get_active_manifest, pin_model_version
from .registry_handlers import (
    activate_registry_model,
    evaluate_registry_model,
    get_registry_model,
    get_registry_model_drift,
    get_registry_model_eval,
    list_registry_models,
)

models_rollout_bp = Blueprint("models_rollout", __name__, url_prefix="/api/v1/models")

# --- Rollout (manifesto {schema}.models) ---
models_rollout_bp.add_url_rule("/active", view_func=get_active_manifest, methods=["GET"])
models_rollout_bp.add_url_rule(
    "/<model_id>/pin", view_func=pin_model_version, methods=["POST"]
)

# --- Registry (public.trained_models — WS-A5) ---
models_rollout_bp.add_url_rule("", view_func=list_registry_models, methods=["GET"])
models_rollout_bp.add_url_rule(
    "/<model_id>", view_func=get_registry_model, methods=["GET"]
)
models_rollout_bp.add_url_rule(
    "/<model_id>/activate", view_func=activate_registry_model, methods=["POST"]
)
models_rollout_bp.add_url_rule(
    "/<model_id>/eval", view_func=get_registry_model_eval, methods=["GET"]
)
models_rollout_bp.add_url_rule(
    "/<model_id>/evaluate", view_func=evaluate_registry_model, methods=["POST"]
)
models_rollout_bp.add_url_rule(
    "/<model_id>/drift", view_func=get_registry_model_drift, methods=["GET"]
)
