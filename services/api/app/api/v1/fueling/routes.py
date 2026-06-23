"""
Recognition — Fueling Module Routes.

KPIs e eventos recentes do módulo de controle de carregamento (carga e descarga).
"""
import logging
import os
from datetime import datetime, timedelta
from uuid import UUID

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.core.tenant import get_role
from app.domain.services import fueling_mock_service
from app.domain.services.counting_service import CountingService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.counting_repository import (
    CountingRepository,
)
from app.infrastructure.database.repositories.tenant_settings_repository import (
    TenantSettingsRepository,
)

logger = logging.getLogger(__name__)

fueling_bp = Blueprint("fueling", __name__, url_prefix="/api/fueling")

FUELING_CLASSES = ("truck", "plate", "forklift", "product_box", "pallet")

# ── Feature flag CD-03: mock vs dados reais ────────────────────────────────────
# Resolução em duas camadas:
#   1. tenants.feature_flags['fueling_use_mock'] (JSONB, migration 030) —
#      controle por tenant via painel admin (PUT /admin/tenants/<id>/feature-flags)
#   2. env FUELING_USE_MOCK (default "true") — fallback global; default true
#      preserva a demo comercial do superadmin enquanto nenhum tenant tem a
#      flag explícita.
# Tenant com flag desligada vê APENAS dados reais de counting_sessions.
FUELING_MOCK_FLAG = "fueling_use_mock"


def _get_pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _get_counting_service() -> CountingService:
    return CountingService(CountingRepository(_get_pool()))


def _env_mock_default() -> bool:
    """Fallback global: env FUELING_USE_MOCK (default true — não quebra a demo)."""
    return os.getenv("FUELING_USE_MOCK", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _use_mock_data(tenant_id) -> bool:
    """Decide mock vs real para o tenant (ver comentário FUELING_MOCK_FLAG)."""
    try:
        repo = TenantSettingsRepository(_get_pool())
        flags = repo.get_feature_flags(UUID(str(tenant_id)))
        if FUELING_MOCK_FLAG in flags:
            return bool(flags[FUELING_MOCK_FLAG])
    except Exception as exc:
        logger.warning("fueling_flag_read_error: %s", exc)
    return _env_mock_default()


def _period_start(period: str) -> datetime:
    """Início da janela do dashboard: today | week | month."""
    days = {"today": 1, "week": 7, "month": 30}.get(period, 1)
    now = datetime.now()
    return datetime.combine(
        (now - timedelta(days=days - 1)).date(), datetime.min.time()
    )


@fueling_bp.route("/stats", methods=["GET"])
@jwt_required()
def fueling_stats():  # type: ignore[no-untyped-def]
    """Retorna KPIs do dia para o tenant no módulo fueling."""
    try:
        tenant_id = get_tenant_id()
        pool = _get_pool()

        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (
                            WHERE class_name IN %s
                            AND created_at::date = CURRENT_DATE
                        ) AS events_today,
                        COUNT(DISTINCT camera_id) FILTER (
                            WHERE class_name IN ('truck', 'plate', 'forklift')
                            AND created_at::date = CURRENT_DATE
                        ) AS active_cameras
                    FROM alerts
                    WHERE tenant_id = %s AND module_code = 'fueling'
                    """,
                    (FUELING_CLASSES, str(tenant_id)),
                )
                row = cur.fetchone()
                events_today = int(row["events_today"]) if row else 0
                active_cameras = int(row["active_cameras"]) if row else 0

        return success({
            "events_today": events_today,
            "active_cameras": active_cameras,
            "module_status": "configuring",
        })
    except Exception as exc:
        logger.error("fueling_stats_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@fueling_bp.route("/events", methods=["GET"])
@jwt_required()
def fueling_events():  # type: ignore[no-untyped-def]
    """Retorna eventos recentes do módulo fueling para o tenant."""
    try:
        tenant_id = get_tenant_id()
        pool = _get_pool()

        try:
            limit = max(1, min(int(request.args.get("limit", 20)), 100))
        except (ValueError, TypeError):
            limit = 20

        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, camera_id, class_name, confidence, created_at
                    FROM alerts
                    WHERE tenant_id = %s AND module_code = 'fueling'
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (str(tenant_id), limit),
                )
                rows = cur.fetchall()

                cur.execute(
                    "SELECT COUNT(*) AS total FROM alerts"
                    " WHERE tenant_id = %s AND module_code = 'fueling'",
                    (str(tenant_id),),
                )
                total_row = cur.fetchone()
                total = int(total_row["total"]) if total_row else 0

        events = [
            {
                "id": str(r["id"]),
                "camera_id": str(r["camera_id"]),
                "class_name": r["class_name"],
                "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

        return success({"events": events, "total": total})
    except Exception as exc:
        logger.error("fueling_events_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@fueling_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def fueling_dashboard():  # type: ignore[no-untyped-def]
    """
    Dashboard de KPIs + séries gráficas do módulo de carga e descarga.

    Flag fueling_use_mock LIGADA (default — demo): superadmin recebe dados
    de demonstração determinísticos; clientes recebem estado vazio.
    Flag DESLIGADA: todos recebem APENAS dados reais de counting_sessions.

    Query param: period = 'today' | 'week' | 'month' (default: 'today').
    """
    try:
        period = request.args.get("period", "today")
        if period not in ("today", "week", "month"):
            period = "today"

        role = get_role()
        tenant_id = get_tenant_id()

        if _use_mock_data(tenant_id):
            # Modo demo (CD-03: comportamento legado preservado pela flag)
            if role == "superadmin":
                data = fueling_mock_service.generate_dashboard(period)
                return success(data)
            return success({
                "no_data": True,
                "message": "Nenhum dado de carregamento disponível para o período.",
            })

        # Flag desligada → dados reais de counting_sessions
        svc = _get_counting_service()
        data = svc.get_loading_dashboard(
            tenant_id=UUID(str(tenant_id)),
            start=_period_start(period),
        )
        return success(data)

    except Exception as exc:
        logger.error("fueling_dashboard_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@fueling_bp.route("/bays", methods=["GET"])
@jwt_required()
def fueling_bays():  # type: ignore[no-untyped-def]
    """
    Lista as baias de carregamento com status atual.

    Flag fueling_use_mock LIGADA: superadmin recebe mock dinâmico; clientes
    recebem estado vazio.
    Flag DESLIGADA: sessões de carga em andamento (counting_sessions reais)
    mapeadas para cards de baia.
    """
    try:
        role = get_role()
        tenant_id = get_tenant_id()

        if _use_mock_data(tenant_id):
            if role == "superadmin":
                bays = fueling_mock_service.generate_bays()
                return success({"bays": bays})
            return success({"bays": [], "no_data": True})

        svc = _get_counting_service()
        bays = svc.list_loading_bays(tenant_id=UUID(str(tenant_id)))
        return success({"bays": bays, "no_data": len(bays) == 0})

    except Exception as exc:
        logger.error("fueling_bays_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@fueling_bp.route("/bays/<int:bay_id>", methods=["GET"])
@jwt_required()
def fueling_bay_detail(bay_id: int):  # type: ignore[no-untyped-def]
    """Retorna detalhes de uma baia específica pelo id (1-6 no mock).

    Endpoint mock-only (ids inteiros 1-6 só existem no mock). Com a flag
    fueling_use_mock desligada retorna 404 — o caminho real usa as sessões
    de /api/counting/sessions (bay_id UUID).
    """
    try:
        role = get_role()
        tenant_id = get_tenant_id()

        if _use_mock_data(tenant_id) and role == "superadmin":
            bay = fueling_mock_service.get_bay(bay_id)
            if bay is None:
                return error("Baia não encontrada", 404)
            return success({"bay": bay})

        return error("Baia não encontrada", 404)

    except Exception as exc:
        logger.error("fueling_bay_detail_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
