"""
Recognition — Alert Rules Routes.

CRUD de regras de alerta com condições de duração/ocorrência.
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

rules_bp = Blueprint("rules", __name__, url_prefix="/api/rules")


def _get_pool():  # type: ignore[no-untyped-def]
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _list_rules(pool, tenant_id: str) -> list:
    from psycopg2.extras import RealDictCursor
    with pool.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM alert_rules WHERE tenant_id = %s ORDER BY created_at DESC",
                (tenant_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def _get_rule(pool, rule_id: str, tenant_id: str):  # type: ignore[no-untyped-def]
    from psycopg2.extras import RealDictCursor
    with pool.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM alert_rules WHERE id = %s AND tenant_id = %s",
                (rule_id, tenant_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None


@rules_bp.route("", methods=["GET"])
@jwt_required()
def list_rules():  # type: ignore[no-untyped-def]
    try:
        from app.core.auth import get_tenant_id
        tenant_id = get_tenant_id()
        pool = _get_pool()
        rules = _list_rules(pool, tenant_id)
        return success({"rules": rules})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_rules_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@rules_bp.route("", methods=["POST"])
@jwt_required()
def create_rule():  # type: ignore[no-untyped-def]
    try:
        from app.core.auth import get_tenant_id
        from psycopg2.extras import RealDictCursor
        tenant_id = get_tenant_id()
        data = request.get_json() or {}

        if not data.get("violation_type"):
            return error("violation_type é obrigatório", 400)
        if not data.get("min_duration_seconds") and not data.get("min_occurrences"):
            return error("Defina min_duration_seconds ou min_occurrences", 400)

        pool = _get_pool()
        with pool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO alert_rules
                       (tenant_id, camera_id, violation_type, min_duration_seconds,
                        min_occurrences, time_window_seconds, create_alert, enabled)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (
                        tenant_id,
                        data.get("camera_id"),
                        data["violation_type"],
                        data.get("min_duration_seconds", 3),
                        data.get("min_occurrences"),
                        data.get("time_window_seconds"),
                        data.get("create_alert", True),
                        data.get("enabled", True),
                    ),
                )
                rule = dict(cur.fetchone())
                conn.commit()
        return success({"rule": rule}), 201
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_rule_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@rules_bp.route("/<rule_id>", methods=["GET"])
@jwt_required()
def get_rule(rule_id: str):  # type: ignore[no-untyped-def]
    try:
        from app.core.auth import get_tenant_id
        tenant_id = get_tenant_id()
        rule = _get_rule(_get_pool(), rule_id, tenant_id)
        if not rule:
            return error("Regra não encontrada", 404)
        return success({"rule": rule})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_rule_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@rules_bp.route("/<rule_id>", methods=["PUT"])
@jwt_required()
def update_rule(rule_id: str):  # type: ignore[no-untyped-def]
    try:
        from app.core.auth import get_tenant_id
        from psycopg2.extras import RealDictCursor
        tenant_id = get_tenant_id()
        data = request.get_json() or {}
        pool = _get_pool()
        if not _get_rule(pool, rule_id, tenant_id):
            return error("Regra não encontrada", 404)
        with pool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """UPDATE alert_rules SET
                       violation_type = COALESCE(%s, violation_type),
                       min_duration_seconds = COALESCE(%s, min_duration_seconds),
                       min_occurrences = COALESCE(%s, min_occurrences),
                       time_window_seconds = COALESCE(%s, time_window_seconds),
                       create_alert = COALESCE(%s, create_alert),
                       enabled = COALESCE(%s, enabled),
                       updated_at = NOW()
                       WHERE id = %s AND tenant_id = %s
                       RETURNING *""",
                    (
                        data.get("violation_type"),
                        data.get("min_duration_seconds"),
                        data.get("min_occurrences"),
                        data.get("time_window_seconds"),
                        data.get("create_alert"),
                        data.get("enabled"),
                        rule_id,
                        tenant_id,
                    ),
                )
                rule = dict(cur.fetchone())
                conn.commit()
        return success({"rule": rule})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("update_rule_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@rules_bp.route("/<rule_id>", methods=["DELETE"])
@jwt_required()
def delete_rule(rule_id: str):  # type: ignore[no-untyped-def]
    try:
        from app.core.auth import get_tenant_id
        tenant_id = get_tenant_id()
        pool = _get_pool()
        if not _get_rule(pool, rule_id, tenant_id):
            return error("Regra não encontrada", 404)
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM alert_rules WHERE id = %s AND tenant_id = %s",
                    (rule_id, tenant_id),
                )
                conn.commit()
        return success({"deleted": True})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("delete_rule_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@rules_bp.route("/<rule_id>/toggle", methods=["POST"])
@jwt_required()
def toggle_rule(rule_id: str):  # type: ignore[no-untyped-def]
    try:
        from app.core.auth import get_tenant_id
        from psycopg2.extras import RealDictCursor
        tenant_id = get_tenant_id()
        pool = _get_pool()
        with pool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "UPDATE alert_rules SET enabled = NOT enabled, updated_at = NOW() "
                    "WHERE id = %s AND tenant_id = %s RETURNING *",
                    (rule_id, tenant_id),
                )
                row = cur.fetchone()
                conn.commit()
        if not row:
            return error("Regra não encontrada", 404)
        return success({"rule": dict(row)})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("toggle_rule_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
