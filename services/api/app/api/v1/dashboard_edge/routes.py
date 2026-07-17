"""
Recognition — Dashboard Integrado (task-112, ADR-0053).

Observabilidade de MODELOS (curvas de treino por época) + telemetria do EDGE
ao vivo/histórica, DENTRO da plataforma (envelope success/error, tenant-scoped
via get_tenant_id — C-01/ADR-0017: sem claim de tenant → falha; cross-tenant
filtrado por tenant_id → nunca aparece).

Blueprint `dashboard_edge_bp` (prefixo /api/v1/dashboard) — distinto do
dashboard_bp existente (métricas de negócio EPI).

Routes:
  Ingest (edge/pipeline → plataforma):
    POST /api/v1/dashboard/training-metrics
         body {model_name, framework?, epochs:[{epoch, metrics{...}}]}
    POST /api/v1/dashboard/edge-telemetry
         body {site_id?, samples:[{sampled_at, label?, payload{...}}]}
  Read (dashboard → tenant-scoped):
    GET  /api/v1/dashboard/training-metrics?models=a,b
    GET  /api/v1/dashboard/training-metrics/models
    GET  /api/v1/dashboard/edge-telemetry?site_id=&window=1h
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.domain.services.dashboard_edge_service import (
    DEFAULT_WINDOW,
    WINDOW_SECONDS,
    DashboardEdgeService,
)
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.edge_telemetry_repository import (
    EdgeTelemetryRepository,
)
from app.infrastructure.database.repositories.model_training_metrics_repository import (
    ModelTrainingMetricsRepository,
)

logger = logging.getLogger(__name__)
dashboard_edge_bp = Blueprint("dashboard_edge", __name__)

_MAX_TELEMETRY_SAMPLES = 5000


def _get_service() -> DashboardEdgeService:
    pool = DatabasePool.get_instance()
    return DashboardEdgeService(
        ModelTrainingMetricsRepository(pool),
        EdgeTelemetryRepository(pool),
    )


# --------------------------------------------------------------------------- #
# Ingest                                                                      #
# --------------------------------------------------------------------------- #

@dashboard_edge_bp.route("/api/v1/dashboard/training-metrics", methods=["POST"])
@jwt_required()
def ingest_training_metrics():  # type: ignore[no-untyped-def]
    """Upsert de métricas de treino por época de um modelo (tenant do JWT)."""
    tenant_id = get_tenant_id()
    body = request.get_json(silent=True) or {}
    model_name = body.get("model_name")
    if not model_name or not isinstance(model_name, str):
        return error("model_name é obrigatório", 400)
    epochs = body.get("epochs")
    if not isinstance(epochs, list) or not epochs:
        return error("epochs (lista não vazia) é obrigatório", 400)
    for e in epochs:
        if not isinstance(e, dict) or "epoch" not in e:
            return error("cada item de epochs precisa de 'epoch'", 400)
        try:
            int(e["epoch"])
        except (TypeError, ValueError):
            return error("epoch deve ser inteiro", 400)

    affected = _get_service().ingest_training_metrics(
        tenant_id, model_name, body.get("framework"), epochs
    )
    return success({"model_name": model_name, "upserted": affected})


@dashboard_edge_bp.route("/api/v1/dashboard/edge-telemetry", methods=["POST"])
@jwt_required()
def ingest_edge_telemetry():  # type: ignore[no-untyped-def]
    """Insere amostras de telemetria e publica ao vivo no Redis (tenant do JWT)."""
    tenant_id = get_tenant_id()
    body = request.get_json(silent=True) or {}
    samples = body.get("samples")
    if not isinstance(samples, list) or not samples:
        return error("samples (lista não vazia) é obrigatório", 400)
    if len(samples) > _MAX_TELEMETRY_SAMPLES:
        return error(
            f"máximo de {_MAX_TELEMETRY_SAMPLES} amostras por request", 400
        )
    for s in samples:
        if not isinstance(s, dict) or not s.get("sampled_at"):
            return error("cada amostra precisa de 'sampled_at'", 400)

    inserted = _get_service().ingest_edge_telemetry(
        tenant_id, body.get("site_id"), samples
    )
    return success({"inserted": inserted})


# --------------------------------------------------------------------------- #
# Read                                                                        #
# --------------------------------------------------------------------------- #

@dashboard_edge_bp.route("/api/v1/dashboard/training-metrics", methods=["GET"])
@jwt_required()
def get_training_metrics():  # type: ignore[no-untyped-def]
    """Curvas por época por modelo (comparação). ?models=a,b filtra."""
    tenant_id = get_tenant_id()
    models_param = request.args.get("models", "").strip()
    models = [m.strip() for m in models_param.split(",") if m.strip()] if models_param else []
    curves = _get_service().get_training_curves(tenant_id, models)
    return success({"models": curves})


@dashboard_edge_bp.route(
    "/api/v1/dashboard/training-metrics/models", methods=["GET"]
)
@jwt_required()
def list_training_models():  # type: ignore[no-untyped-def]
    """Lista de modelos disponíveis + resumo (última época, ap5095, ap_small)."""
    tenant_id = get_tenant_id()
    models = _get_service().get_models_summary(tenant_id)
    return success({"models": models})


@dashboard_edge_bp.route("/api/v1/dashboard/edge-telemetry", methods=["GET"])
@jwt_required()
def get_edge_telemetry():  # type: ignore[no-untyped-def]
    """Série temporal recente de telemetria do edge. ?site_id= &window=1h."""
    tenant_id = get_tenant_id()
    window = request.args.get("window", DEFAULT_WINDOW)
    if window not in WINDOW_SECONDS:
        return error(
            f"window inválido (use um de: {', '.join(WINDOW_SECONDS)})", 400
        )
    site_id = request.args.get("site_id") or None
    series = _get_service().get_edge_timeseries(tenant_id, site_id, window)
    return success(series)
