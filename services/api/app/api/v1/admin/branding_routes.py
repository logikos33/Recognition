"""
Recognition — Tenant Branding Routes (task-048).

Endpoints:
  GET  /api/v1/tenant/branding                     — público, boot do frontend
  GET  /api/v1/admin/tenants/<id>/branding         — superadmin
  PUT  /api/v1/admin/tenants/<id>/branding         — superadmin
  POST /api/v1/admin/tenants/<id>/branding/logo    — superadmin, upload logo R2
"""
import json
import logging

from flask import Blueprint, request

from app.core.responses import error, success
from app.core.tenant import require_superadmin
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

branding_bp = Blueprint("tenant_branding", __name__)
admin_branding_bp = Blueprint("admin_branding", __name__, url_prefix="/api/v1/admin")

_DEFAULT_BRANDING: dict = {
    "product_name": "Recognition",
    "color_primary": "#06b6d4",
    "color_secondary": "#ea580c",
    "logo_url": None,
    "favicon_url": None,
}

_ALLOWED_MIME = frozenset({
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
})
_MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


def _pool():
    p = DatabasePool.get_instance()
    if p is None:
        raise RuntimeError("Database pool not initialized")
    return p


def _merge_branding(stored: dict) -> dict:
    """Merge stored JSONB with defaults; stored non-None values override defaults."""
    return {**_DEFAULT_BRANDING, **{k: v for k, v in stored.items() if v is not None}}


# ---------------------------------------------------------------------------
# Admin — GET /api/v1/admin/tenants/<id>/branding
# ---------------------------------------------------------------------------

@admin_branding_bp.route("/tenants/<tenant_id>/branding", methods=["GET"])
@require_superadmin
def get_tenant_branding(tenant_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, branding FROM public.tenants WHERE id = %s",
                (tenant_id,),
            )
            row = cur.fetchone()

        if not row:
            return error("Tenant não encontrado", 404)

        stored = row["branding"] or {}
        if isinstance(stored, str):
            stored = json.loads(stored)

        merged = _merge_branding(stored)
        return success({"branding": merged})

    except Exception as exc:
        logger.error("get_tenant_branding_error: %s", exc, exc_info=True)
        return error("Erro ao buscar branding", 500)


# ---------------------------------------------------------------------------
# Admin — PUT /api/v1/admin/tenants/<id>/branding
# ---------------------------------------------------------------------------

@admin_branding_bp.route("/tenants/<tenant_id>/branding", methods=["PUT"])
@require_superadmin
def update_tenant_branding(tenant_id: str):
    try:
        data = request.get_json() or {}
        allowed = {"product_name", "color_primary", "color_secondary", "logo_url", "favicon_url"}
        branding = {k: v for k, v in data.items() if k in allowed}

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM public.tenants WHERE id = %s",
                    (tenant_id,),
                )
                if not cur.fetchone():
                    return error("Tenant não encontrado", 404)

                cur.execute(
                    "UPDATE public.tenants SET branding = %s::jsonb WHERE id = %s",
                    (json.dumps(branding), tenant_id),
                )
            conn.commit()

        return success({"updated": True, "branding": branding})

    except Exception as exc:
        logger.error("update_tenant_branding_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar branding", 500)


# ---------------------------------------------------------------------------
# Admin — POST /api/v1/admin/tenants/<id>/branding/logo
# ---------------------------------------------------------------------------

@admin_branding_bp.route("/tenants/<tenant_id>/branding/logo", methods=["POST"])
@require_superadmin
def upload_tenant_branding_logo(tenant_id: str):
    try:
        if "file" not in request.files:
            return error("Campo 'file' ausente", 400)

        f = request.files["file"]
        if not f.filename:
            return error("Nome do arquivo inválido", 400)

        content_type = (f.content_type or "").split(";")[0].strip()
        if content_type not in _ALLOWED_MIME:
            return error(
                f"Tipo não permitido: '{content_type}'. Use PNG, JPEG, GIF ou WebP.",
                400,
            )

        data = f.read()
        if len(data) == 0:
            return error("Arquivo vazio", 400)
        if len(data) > _MAX_SIZE_BYTES:
            return error(
                f"Arquivo muito grande: máximo {_MAX_SIZE_BYTES // (1024 * 1024)} MB",
                400,
            )

        _ext_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }
        ext = _ext_map.get(content_type, ".bin")
        key = f"branding/{tenant_id}/logo{ext}"

        from app.infrastructure.storage.local_storage import get_storage
        storage = get_storage()
        storage.upload_bytes(key, data, content_type)
        logo_url = storage.generate_presigned_download_url(key, ttl=315_360_000)  # ~10 years

        # Persist logo_url into tenant branding JSONB
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.tenants
                       SET branding = COALESCE(branding, '{}'::jsonb) || %s::jsonb
                     WHERE id = %s
                    """,
                    (json.dumps({"logo_url": logo_url}), tenant_id),
                )
            conn.commit()

        return success({"logo_url": logo_url, "key": key}, status=201)

    except Exception as exc:
        logger.error("upload_logo_error: %s", exc, exc_info=True)
        return error("Erro no upload do logo", 500)
