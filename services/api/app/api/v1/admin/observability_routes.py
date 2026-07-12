"""
Recognition — Observability Routes (superadmin only) — WS11/E2-7.

Blueprint /api/v1/admin/observability:
  GET  /summary     — resumo consolidado (DB/Redis/R2/Celery/workers/edge/api/migrations)
  GET  /timeseries  — série bucketizada de platform_metrics (?scope&metric&window[&tenant_id][&queue])
  GET  /edge-fleet  — visão frota cross-tenant (último heartbeat por site + tenant)
  GET  /streams     — status agregado de streams (mata o N+1 da StreamHealthPage)
  POST /collect     — dispara coleta de snapshot in-process ('Coletar agora')

ALIASES/ZERO QUEBRA: /admin/health/platform e /admin/health/metrics permanecem
intocados; /v1/edge/* intocados; /api/streams/status público permanece.
"""
import logging

from flask import Blueprint, request

from app.core.responses import error, success
from app.core.tenant import require_superadmin
from app.domain.services import observability_service

logger = logging.getLogger(__name__)

admin_observability_bp = Blueprint(
    "admin_observability", __name__, url_prefix="/api/v1/admin/observability"
)


@admin_observability_bp.route("/summary", methods=["GET"])
@require_superadmin
def observability_summary():
    """Resumo consolidado da plataforma (aba Visão Geral do dashboard)."""
    try:
        return success(observability_service.get_summary())
    except Exception as exc:
        logger.error("observability_summary_error: %s", exc, exc_info=True)
        return error("Erro ao montar resumo de observability", 500)


@admin_observability_bp.route("/timeseries", methods=["GET"])
@require_superadmin
def observability_timeseries():
    """Série temporal bucketizada.

    Query params:
      scope   — obrigatório (api|db|redis|r2|celery|edge|workers|ws)
      metric  — obrigatório (ex.: queue_depth, http_5xx, conn_active)
      window  — 1h|6h|24h|7d (whitelist; default 24h)
      tenant_id — opcional (métricas escopadas)
      queue   — opcional (filtra labels->>'queue')
    """
    try:
        scope = (request.args.get("scope") or "").strip()
        metric = (request.args.get("metric") or "").strip()
        window = (request.args.get("window") or "24h").strip()
        tenant_id = (request.args.get("tenant_id") or "").strip() or None
        queue = (request.args.get("queue") or "").strip() or None

        if not scope or not metric:
            return error("Parâmetros 'scope' e 'metric' são obrigatórios", 400)
        if window not in observability_service.WINDOW_BUCKETS:
            return error("Janela inválida — use 1h, 6h, 24h ou 7d", 400)

        data = observability_service.get_timeseries(
            scope=scope, metric=metric, window=window,
            tenant_id=tenant_id, queue=queue,
        )
        return success(data)
    except Exception as exc:
        logger.error("observability_timeseries_error: %s", exc, exc_info=True)
        return error("Erro ao buscar série temporal", 500)


@admin_observability_bp.route("/edge-fleet", methods=["GET"])
@require_superadmin
def observability_edge_fleet():
    """Visão FROTA cross-tenant — shape do /v1/edge/sites/health + tenant."""
    try:
        return success({"sites": observability_service.get_edge_fleet()})
    except Exception as exc:
        logger.error("observability_edge_fleet_error: %s", exc, exc_info=True)
        return error("Erro ao buscar frota edge", 500)


@admin_observability_bp.route("/streams", methods=["GET"])
@require_superadmin
def observability_streams():
    """Status agregado de streams de todas as câmeras ativas (uma resposta)."""
    try:
        return success(observability_service.get_streams_aggregate())
    except Exception as exc:
        logger.error("observability_streams_error: %s", exc, exc_info=True)
        return error("Erro ao buscar status de streams", 500)


@admin_observability_bp.route("/collect", methods=["POST"])
@require_superadmin
def observability_collect():
    """Dispara coleta de snapshot in-process (botão 'Coletar agora')."""
    try:
        from app.infrastructure.queue.tasks.observability import (  # noqa: PLC0415
            collect_platform_metrics,
        )
        points = collect_platform_metrics()
        return success({"points_recorded": points})
    except Exception as exc:
        logger.error("observability_collect_error: %s", exc, exc_info=True)
        return error("Erro ao coletar métricas", 500)
