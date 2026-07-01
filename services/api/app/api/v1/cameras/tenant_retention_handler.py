"""
Recognition — Tenant-level retention handlers.

GET /api/tenant/retention  — lê video_retention_days do tenant atual
PUT /api/tenant/retention  — atualiza video_retention_days (admin+)
"""
import logging

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_role, get_tenant_id
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

VALID_TIERS = (1, 7, 30, 90)


def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


@jwt_required()
def get_tenant_retention():  # type: ignore[no-untyped-def]
    """
    GET /api/tenant/retention
    Retorna video_retention_days do tenant extraído do JWT.
    """
    try:
        tenant_id = get_tenant_id()
        with _pool().get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT video_retention_days FROM public.tenants WHERE id = %s",
                (tenant_id,),
            )
            row = cur.fetchone()

        if row is None:
            return error("Tenant não encontrado", 404)

        retention = row.get("video_retention_days") or 30

        return success({
            "tenant_id": tenant_id,
            "retention_days": retention,
            "valid_tiers": list(VALID_TIERS),
        })
    except Exception as exc:
        logger.error("get_tenant_retention_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def put_tenant_retention():  # type: ignore[no-untyped-def]
    """
    PUT /api/tenant/retention
    Body: {"retention_days": <int>}
    Requer role admin ou superadmin.
    """
    try:
        role = get_role()
        if role not in ("admin", "superadmin"):
            return error("Sem permissão — requer admin", 403)

        tenant_id = get_tenant_id()
        data = request.get_json() or {}

        try:
            retention_days = int(data.get("retention_days", 30))
        except (TypeError, ValueError):
            return error("retention_days deve ser inteiro", 400)

        if retention_days not in VALID_TIERS:
            return error(f"Tier inválido. Use um dos valores: {list(VALID_TIERS)}", 400)

        with _pool().get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.tenants SET video_retention_days = %s WHERE id = %s",
                    (retention_days, tenant_id),
                )
            conn.commit()

        logger.info(
            "tenant_retention_updated tenant=%s days=%s",
            tenant_id, retention_days,
        )

        return success({
            "tenant_id": tenant_id,
            "retention_days": retention_days,
        })
    except Exception as exc:
        logger.error("put_tenant_retention_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
