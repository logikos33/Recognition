"""
EPI Monitor V2 — Fueling Module Routes.

KPIs e eventos recentes do módulo de controle de abastecimento.
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

fueling_bp = Blueprint("fueling", __name__, url_prefix="/api/fueling")

FUELING_CLASSES = ("truck", "plate", "fuel_nozzle", "product_box", "pallet")


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
                                WHERE class_name IN ('truck', 'plate', 'fuel_nozzle')
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
