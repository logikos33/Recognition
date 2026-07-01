"""
Recognition — Retention handlers for camera routes (task-047).

Handlers: get_camera_retention, put_camera_retention.

Tiers permitidos: 1, 7, 30, 90 dias.
NULL = herdar default do tenant.
Apenas admin/superadmin pode alterar.
"""
import logging

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_role, get_tenant_id
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.camera_repository import CameraRepository

logger = logging.getLogger(__name__)

ALLOWED_TIERS: frozenset[int] = frozenset({1, 7, 30, 90})
_DEFAULT_RETENTION = 7


def _get_repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraRepository(pool)


def _get_tenant_default(tenant_id: str) -> int:
    """Retorna retenção efetiva do tenant: override próprio ou plano."""
    pool = DatabasePool.get_instance()
    if pool is None:
        return _DEFAULT_RETENTION
    with pool.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(t.default_retention_days, p.video_retention_days, %s) AS days "
            "FROM public.tenants t "
            "LEFT JOIN public.plans p ON p.slug = t.plan "
            "WHERE t.id = %s",
            (_DEFAULT_RETENTION, str(tenant_id)),
        )
        row = cur.fetchone()
    return int(row["days"]) if row else _DEFAULT_RETENTION


@jwt_required()
def get_camera_retention(camera_id: str):  # type: ignore[no-untyped-def]
    """GET /api/cameras/<id>/retention — retenção efetiva da câmera."""
    try:
        tenant_id = get_tenant_id()
        repo = _get_repo()
        camera = repo.get_by_id_and_tenant(camera_id, str(tenant_id))
        if not camera:
            return error("Câmera não encontrada", 404)
        tenant_default = _get_tenant_default(str(tenant_id))
        camera_days = camera.get("retention_days")
        effective = int(camera_days) if camera_days is not None else tenant_default
        return success({
            "camera_id": camera_id,
            "retention_days": camera_days,
            "tenant_default_days": tenant_default,
            "effective_days": effective,
            "allowed_tiers": sorted(ALLOWED_TIERS),
        })
    except Exception as exc:
        logger.error("get_camera_retention_error: %s", exc, exc_info=True)
        return error("Erro ao buscar retenção", 500)


@jwt_required()
def put_camera_retention(camera_id: str):  # type: ignore[no-untyped-def]
    """PUT /api/cameras/<id>/retention — define tier de retenção (admin only)."""
    role = get_role()
    if role not in ("admin", "superadmin"):
        return error("Apenas administradores podem alterar retenção", 403)

    body = request.get_json(silent=True) or {}
    retention_days = body.get("retention_days")

    if retention_days is not None:
        if not isinstance(retention_days, int) or retention_days not in ALLOWED_TIERS:
            return error(
                f"retention_days deve ser um dos tiers permitidos: {sorted(ALLOWED_TIERS)}",
                422,
            )

    try:
        tenant_id = get_tenant_id()
        repo = _get_repo()
        camera = repo.get_by_id_and_tenant(camera_id, str(tenant_id))
        if not camera:
            return error("Câmera não encontrada", 404)

        updated = repo.update_retention_days(camera_id, str(tenant_id), retention_days)
        if not updated:
            return error("Câmera não encontrada", 404)

        logger.info(
            "camera_retention_updated: camera=%s tenant=%s days=%s role=%s",
            camera_id, tenant_id, retention_days, role,
        )
        return success({
            "camera_id": camera_id,
            "retention_days": retention_days,
        })
    except Exception as exc:
        logger.error("put_camera_retention_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar retenção", 500)
