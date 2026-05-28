"""
Recognition — Fueling Module Routes.

KPIs e eventos recentes do módulo de controle de carregamento (carga e descarga).
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.core.tenant import get_role
from app.domain.services import fueling_mock_service
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

fueling_bp = Blueprint("fueling", __name__, url_prefix="/api/fueling")

FUELING_CLASSES = ("truck", "plate", "forklift", "product_box", "pallet")


def _get_pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


@fueling_bp.route("/stats", methods=["GET"])
@jwt_required()
def fueling_stats():  # type: ignore[no-untyped-def]
    """Retorna KPIs do dia para o tenant no módulo fueling."""
    try:
        tenant_id = get_tenant_id()
        pool = _get_pool()

        with pool.getconn() as conn:
            try:
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
                    events_today = int(row[0]) if row else 0
                    active_cameras = int(row[1]) if row else 0
            finally:
                pool.putconn(conn)

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

        with pool.getconn() as conn:
            try:
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
                        "SELECT COUNT(*) FROM alerts"
                        " WHERE tenant_id = %s AND module_code = 'fueling'",
                        (str(tenant_id),),
                    )
                    total_row = cur.fetchone()
                    total = int(total_row[0]) if total_row else 0
            finally:
                pool.putconn(conn)

        events = [
            {
                "id": str(r[0]),
                "camera_id": str(r[1]),
                "class_name": r[2],
                "confidence": float(r[3]) if r[3] is not None else None,
                "created_at": r[4].isoformat() if r[4] else None,
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

    Superadmin recebe dados de demonstração gerados deterministicamente.
    Outros roles recebem dados reais do tenant (ou estado vazio se não houver dados).

    Query param: period = 'today' | 'week' | 'month' (default: 'today').
    """
    try:
        period = request.args.get("period", "today")
        if period not in ("today", "week", "month"):
            period = "today"

        role = get_role()

        # Superadmin → dados mock para demonstração comercial
        if role == "superadmin":
            data = fueling_mock_service.generate_dashboard(period)
            return success(data)

        # Clientes → dados reais (placeholder: retorna estado vazio enquanto não há dados)
        return success({
            "no_data": True,
            "message": "Nenhum dado de carregamento disponível para o período.",
        })

    except Exception as exc:
        logger.error("fueling_dashboard_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@fueling_bp.route("/bays", methods=["GET"])
@jwt_required()
def fueling_bays():  # type: ignore[no-untyped-def]
    """
    Lista as baias de carregamento com status atual.

    Superadmin recebe dados mock dinâmicos (status muda a cada 5 min).
    Clientes recebem estado vazio até que câmeras de carregamento estejam configuradas.
    """
    try:
        role = get_role()

        if role == "superadmin":
            bays = fueling_mock_service.generate_bays()
            return success({"bays": bays})

        return success({"bays": [], "no_data": True})

    except Exception as exc:
        logger.error("fueling_bays_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@fueling_bp.route("/bays/<int:bay_id>", methods=["GET"])
@jwt_required()
def fueling_bay_detail(bay_id: int):  # type: ignore[no-untyped-def]
    """Retorna detalhes de uma baia específica pelo id (1-6 no mock)."""
    try:
        role = get_role()

        if role == "superadmin":
            bay = fueling_mock_service.get_bay(bay_id)
            if bay is None:
                return error("Baia não encontrada", 404)
            return success({"bay": bay})

        return error("Baia não encontrada", 404)

    except Exception as exc:
        logger.error("fueling_bay_detail_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
