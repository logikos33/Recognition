"""
Branding endpoints — white-label theming por tenant (task-048).

Endpoints:
  GET  /api/v1/tenant/branding                    JWT obrigatório; retorna branding do tenant do token
  GET  /api/v1/admin/branding/tenants             superadmin; lista todos os tenants com branding
  GET  /api/v1/admin/branding/tenant/<tenant_id>  superadmin; branding de um tenant específico
  PUT  /api/v1/admin/branding                     admin; atualiza branding (body: {branding, tenant_id?})
  POST /api/v1/admin/branding/logo                admin; upload de logo/favicon para R2

Restrições:
  - branding JSONB aceita apenas chaves: 'brand', 'colors'
  - logo: MIME image/png, image/jpeg, image/svg+xml, image/webp; máx 2 MB
  - Tenant A nunca acessa branding de Tenant B (admin usa tenant_id do JWT)
  - Superadmin pode passar tenant_id explícito no body para editar outros tenants
"""
import json
import logging

from flask import Blueprint, request
from app.core.auth import get_role, get_tenant_id
from app.core.responses import error, success
from app.core.tenant import require_admin, require_superadmin
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

branding_bp = Blueprint("branding", __name__, url_prefix="/api/v1")

ALLOWED_MIME: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/webp"}
)
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_BRANDING_KEYS: frozenset[str] = frozenset({"brand", "colors"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


# ---------------------------------------------------------------------------
# GET /api/v1/tenant/branding  (JWT opcional — boot do frontend)
# ---------------------------------------------------------------------------

@branding_bp.route("/tenant/branding", methods=["GET"])
def get_tenant_branding():
    """
    Retorna branding do tenant autenticado.
    JWT opcional: sem token → retorna {} silenciosamente.
    Tenant não encontrado ou branding vazio → retorna {}.
    """
    try:
        from flask_jwt_extended import get_jwt, verify_jwt_in_request

        tenant_id = None
        try:
            verify_jwt_in_request(optional=True)
            tenant_id = get_jwt().get("tenant_id")
        except Exception:
            pass

        if not tenant_id:
            return success({})

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT branding FROM public.tenants "
                "WHERE id = %s AND is_active = true",
                (tenant_id,),
            )
            row = cur.fetchone()

        if not row:
            return success({})

        branding = row.get("branding") or {}
        if isinstance(branding, str):
            branding = json.loads(branding)

        return success(branding)

    except Exception as exc:
        logger.warning("get_tenant_branding_error: %s", exc)
        return success({})


# ---------------------------------------------------------------------------
# GET /api/v1/admin/branding/tenants
# ---------------------------------------------------------------------------
@branding_bp.route("/admin/branding/tenants", methods=["GET"])
@require_superadmin
def list_tenants_branding():
    """Lista todos os tenants com seus brandings (superadmin only)."""
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, slug, is_active, branding "
                "FROM public.tenants ORDER BY name"
            )
            rows = cur.fetchall()
        tenants = [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "slug": r["slug"],
                "is_active": r["is_active"],
                "branding": dict(r["branding"] or {}),
            }
            for r in rows
        ]
        return success({"tenants": tenants})
    except Exception as exc:
        logger.error("list_tenants_branding_error: %s", exc, exc_info=True)
        return error("Erro ao listar tenants", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/branding/tenant/<tenant_id>
# ---------------------------------------------------------------------------
@branding_bp.route("/admin/branding/tenant/<tenant_id>", methods=["GET"])
@require_superadmin
def get_branding_by_tenant(tenant_id: str):
    """Retorna branding + metadados de um tenant específico (superadmin only)."""
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, slug, branding "
                "FROM public.tenants WHERE id = %s",
                (tenant_id,),
            )
            row = cur.fetchone()
        if not row:
            return error("Tenant não encontrado", 404)
        return success(
            {
                "tenant_id": str(row["id"]),
                "name": row["name"],
                "slug": row["slug"],
                "branding": dict(row["branding"] or {}),
            }
        )
    except Exception as exc:
        logger.error("get_branding_by_tenant_error: %s", exc, exc_info=True)
        return error("Erro ao buscar branding", 500)


# ---------------------------------------------------------------------------
# PUT /api/v1/admin/branding
# ---------------------------------------------------------------------------
@branding_bp.route("/admin/branding", methods=["PUT"])
@require_admin
def update_branding():
    """
    Atualiza o branding de um tenant.

    Admin: atualiza o próprio tenant (tenant_id extraído do JWT).
    Superadmin: pode passar tenant_id no body para editar qualquer tenant.

    Body: {branding: {brand?: {...}, colors?: {...}}, tenant_id?: UUID}
    """
    try:
        body = request.get_json(silent=True) or {}
        role = get_role()
        if role == "superadmin" and "tenant_id" in body:
            tenant_id = str(body["tenant_id"])
        else:
            tenant_id = get_tenant_id()

        branding = body.get("branding")
        if not isinstance(branding, dict):
            return error("Campo 'branding' deve ser um objeto JSON", 400)

        invalid_keys = set(branding.keys()) - ALLOWED_BRANDING_KEYS
        if invalid_keys:
            return error(
                f"Chaves inválidas em branding: {sorted(invalid_keys)}", 400
            )

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE public.tenants SET branding = %s::jsonb "
                "WHERE id = %s RETURNING id",
                (json.dumps(branding), tenant_id),
            )
            if not cur.fetchone():
                return error("Tenant não encontrado", 404)

        return success({"branding": branding, "tenant_id": tenant_id})
    except Exception as exc:
        logger.error("update_branding_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar branding", 500)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/branding/logo
# ---------------------------------------------------------------------------
@branding_bp.route("/admin/branding/logo", methods=["POST"])
@require_admin
def upload_logo():
    """
    Upload de logo/favicon para storage (R2 em prod, local em dev).
    Valida MIME type (PNG/JPEG/SVG/WebP) e tamanho (máx 2 MB).
    Retorna {url, key}.
    """
    try:
        file = request.files.get("file")
        if not file:
            return error("Nenhum arquivo enviado", 400)

        mime = (file.content_type or "").split(";")[0].strip()
        if mime not in ALLOWED_MIME:
            return error(
                f"Tipo não permitido: '{mime}'. "
                "Permitidos: image/png, image/jpeg, image/webp",
                415,
            )

        data = file.read()
        if len(data) > MAX_LOGO_BYTES:
            return error("Arquivo muito grande — máximo 2 MB", 413)

        tenant_id = get_tenant_id()
        ext = mime.split("/")[-1].replace("svg+xml", "svg")
        key = f"branding/{tenant_id}/logo.{ext}"

        storage = get_storage()
        storage.upload_bytes(key, data, mime)

        # Gera URL presigned para R2; fallback para path local em dev
        try:
            from app.infrastructure.storage.r2_storage import R2Storage  # noqa: PLC0415

            if isinstance(storage, R2Storage):
                url = storage.generate_presigned_download_url(
                    key, ttl=86400 * 365
                )
            else:
                url = f"/local-storage/{key}"
        except ImportError:
            url = f"/local-storage/{key}"

        return success({"url": url, "key": key})
    except Exception as exc:
        logger.error("upload_logo_error: %s", exc, exc_info=True)
        return error("Erro ao fazer upload do logo", 500)
