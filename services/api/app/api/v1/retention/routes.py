"""
Retention endpoints — tiers de retenção por tenant (task-047).

Endpoints:
  GET /api/v1/tenant/retention  — retenção padrão efetiva do tenant (plano + override)
  PUT /api/v1/tenant/retention  — admin; define default_retention_days no tenant

Tiers permitidos: 1, 7, 30, 90 dias.
Isolamento: tenant_id sempre extraído do JWT — nunca aceito do cliente.
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_role, get_tenant_id
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

retention_bp = Blueprint("retention", __name__, url_prefix="/api/v1")

ALLOWED_TIERS: frozenset[int] = frozenset({1, 7, 30, 90})
_DEFAULT_RETENTION = 7


def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


@retention_bp.route("/tenant/retention", methods=["GET"])
@jwt_required()
def get_tenant_retention():  # type: ignore[no-untyped-def]
    """Retenção padrão efetiva do tenant: override próprio → plano → fallback 7d."""
    try:
        tenant_id = get_tenant_id()
        with _pool().get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT t.default_retention_days, "
                "       COALESCE(p.video_retention_days, %s) AS plan_days "
                "FROM public.tenants t "
                "LEFT JOIN public.plans p ON p.slug = t.plan "
                "WHERE t.id = %s",
                (_DEFAULT_RETENTION, str(tenant_id)),
            )
            row = cur.fetchone()
        if not row:
            return error("Tenant não encontrado", 404)
        plan_days = int(row["plan_days"])
        override_days = int(row["default_retention_days"]) if row["default_retention_days"] is not None else None
        effective = override_days if override_days is not None else plan_days
        return success({
            "tenant_id": str(tenant_id),
            "default_retention_days": override_days,
            "plan_retention_days": plan_days,
            "effective_retention_days": effective,
            "allowed_tiers": sorted(ALLOWED_TIERS),
        })
    except Exception as exc:
        logger.error("get_tenant_retention_error: %s", exc, exc_info=True)
        return error("Erro ao buscar retenção do tenant", 500)


@retention_bp.route("/tenant/retention", methods=["PUT"])
@jwt_required()
def put_tenant_retention():  # type: ignore[no-untyped-def]
    """Define retenção padrão do tenant (admin only). Persiste em tenants.default_retention_days."""
    role = get_role()
    if role not in ("admin", "superadmin"):
        return error("Apenas administradores podem alterar retenção do tenant", 403)

    body = request.get_json(silent=True) or {}
    default_days = body.get("default_retention_days")

    if not isinstance(default_days, int) or default_days not in ALLOWED_TIERS:
        return error(
            f"default_retention_days deve ser um dos tiers permitidos: {sorted(ALLOWED_TIERS)}",
            422,
        )

    try:
        tenant_id = get_tenant_id()
        with _pool().get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE public.tenants SET default_retention_days = %s "
                "WHERE id = %s RETURNING id",
                (default_days, str(tenant_id)),
            )
            if not cur.fetchone():
                return error("Tenant não encontrado", 404)
        logger.info(
            "tenant_retention_updated: tenant=%s days=%s role=%s",
            tenant_id, default_days, role,
        )
        return success({
            "tenant_id": str(tenant_id),
            "default_retention_days": default_days,
        })
    except Exception as exc:
        logger.error("put_tenant_retention_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar retenção do tenant", 500)
