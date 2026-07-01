"""
Recognition — Retention handlers for camera routes.

GET /api/cameras/<id>/retention  — lê retention_days da câmera + default do tenant
PUT /api/cameras/<id>/retention  — atualiza retention_days da câmera (admin+)
"""
import logging
from uuid import UUID

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_role, get_tenant_id
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.camera_repository import CameraRepository

logger = logging.getLogger(__name__)

VALID_TIERS = (1, 7, 30, 90)


def _repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraRepository(pool)


def _tenant_default(tenant_id: str) -> int:
    """Retorna video_retention_days do tenant (fallback 30)."""
    pool = DatabasePool.get_instance()
    if pool is None:
        return 30
    with pool.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT video_retention_days FROM public.tenants WHERE id = %s",
            (tenant_id,),
        )
        row = cur.fetchone()
    if row and row.get("video_retention_days") is not None:
        return int(row["video_retention_days"])
    return 30


@jwt_required()
def get_camera_retention(camera_id: str):  # type: ignore[no-untyped-def]
    """
    GET /api/cameras/<id>/retention
    Retorna:
      - retention_days: valor explícito da câmera (ou null)
      - effective_days: valor aplicado (câmera ou tenant default)
      - tenant_default_days: default do tenant
    """
    try:
        tenant_id = get_tenant_id()
        repo = _repo()
        row = repo.get_retention(UUID(camera_id), tenant_id)
        if row is None:
            return error("Câmera não encontrada", 404)

        tenant_default = _tenant_default(tenant_id)
        cam_days = row.get("retention_days")
        effective = cam_days if cam_days is not None else tenant_default

        return success({
            "camera_id": camera_id,
            "retention_days": cam_days,
            "effective_days": effective,
            "tenant_default_days": tenant_default,
            "valid_tiers": list(VALID_TIERS),
        })
    except Exception as exc:
        logger.error("get_camera_retention_error camera=%s: %s", camera_id, exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def put_camera_retention(camera_id: str):  # type: ignore[no-untyped-def]
    """
    PUT /api/cameras/<id>/retention
    Body: {"retention_days": <int|null>}
    null → herda do tenant.
    Requer role admin ou superadmin.
    """
    try:
        role = get_role()
        if role not in ("admin", "superadmin"):
            return error("Sem permissão — requer admin", 403)

        tenant_id = get_tenant_id()
        data = request.get_json() or {}

        # retention_days pode ser null (herdar) ou um tier válido
        retention_days = data.get("retention_days")
        if retention_days is not None:
            try:
                retention_days = int(retention_days)
            except (TypeError, ValueError):
                return error("retention_days deve ser inteiro ou null", 400)
            if retention_days not in VALID_TIERS:
                return error(
                    f"Tier inválido. Use um dos valores: {list(VALID_TIERS)}", 400
                )

        repo = _repo()
        updated = repo.update_retention(UUID(camera_id), tenant_id, retention_days)
        if updated is None:
            return error("Câmera não encontrada", 404)

        tenant_default = _tenant_default(tenant_id)
        effective = retention_days if retention_days is not None else tenant_default

        logger.info(
            "retention_updated camera=%s tenant=%s days=%s",
            camera_id, tenant_id, retention_days,
        )

        return success({
            "camera_id": camera_id,
            "retention_days": retention_days,
            "effective_days": effective,
            "tenant_default_days": tenant_default,
        })
    except Exception as exc:
        logger.error("put_camera_retention_error camera=%s: %s", camera_id, exc, exc_info=True)
        return error("Erro interno", 500)
