"""
Recognition — Storage routes.

GET  /api/v1/storage/health            — Check R2/local storage connectivity
POST /api/v1/storage/test-upload       — Test upload (dev only)
POST /api/v1/storage/evidence-upload   — Presigned PUT URL for edge device evidence
GET  /api/v1/storage/evidence/<key>    — Presigned GET URL for operator (JWT)
"""
import logging
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.device_auth import verify_device_token
from app.core.exceptions import AuthenticationError, EpiMonitorError
from app.core.responses import error, success
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

_UPLOAD_TTL = 900    # 15 minutes — presigned PUT
_DOWNLOAD_TTL = 3600  # 1 hour   — presigned GET


def _sanitize_filename(name: str) -> str:
    """Remove path-traversal characters and cap length."""
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"\.{2,}", "__", name)
    return name[:200] or "evidence"


def _sanitize_path_segment(segment: str) -> str:
    """Allow only alphanumeric, hyphens, underscores for path segment (e.g. camera_id)."""
    segment = re.sub(r"[^a-zA-Z0-9_\-]", "_", segment)
    return segment[:64] or "unknown"

storage_bp = Blueprint("storage", __name__, url_prefix="/api/v1/storage")


@storage_bp.route("/health", methods=["GET"])
def storage_health():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - storage
    summary: Health check do armazenamento R2
    description: Testa conectividade com Cloudflare R2 (upload, exists, delete)
    responses:
      200:
        description: Status do storage
        schema:
          properties:
            storage_type: {type: string, example: R2Storage}
            connected: {type: boolean}
            r2_configured: {type: boolean}
    """
    try:
        storage = get_storage()
        storage_type = type(storage).__name__

        # Test write/read/delete cycle
        test_key = f"_health_check/{uuid4()}.txt"
        test_data = b"health-check-ok"
        storage.upload_bytes(test_key, test_data, "text/plain")
        exists = storage.exists(test_key)
        storage.delete(test_key)

        return success({
            "storage_type": storage_type,
            "connected": exists,
            "r2_configured": bool(os.environ.get("R2_ENDPOINT")),
        })
    except Exception as exc:
        logger.error("storage_health_error: %s", exc)
        return success({
            "storage_type": "unknown",
            "connected": False,
            "error": str(exc),
            "r2_configured": bool(os.environ.get("R2_ENDPOINT")),
        })


@storage_bp.route("/test-upload", methods=["POST"])
@jwt_required()
def test_upload():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - storage
    summary: Upload de teste (admin)
    security:
      - Bearer: []
    responses:
      200:
        description: Upload realizado com sucesso
      500:
        description: Erro no upload
    """
    try:
        storage = get_storage()
        test_key = f"test/{uuid4()}.txt"
        storage.upload_bytes(test_key, b"test upload content", "text/plain")

        download_url = storage.generate_presigned_download_url(test_key)
        exists = storage.exists(test_key)

        return success({
            "key": test_key,
            "exists": exists,
            "download_url": download_url,
            "storage_type": type(storage).__name__,
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("test_upload_error: %s", exc, exc_info=True)
        return error("Erro no upload de teste", 500)


# ---------------------------------------------------------------------------
# POST /api/v1/storage/evidence-upload — edge device presigned PUT
# ---------------------------------------------------------------------------

@storage_bp.route("/evidence-upload", methods=["POST"])
def evidence_upload():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - storage
    summary: Gera presigned PUT URL para evidência do dispositivo edge
    description: >
      Auth por X-Device-Token (RS256). Retorna URL de upload direto para R2
      e a evidence_key para posterior recuperação pelo operador.
    parameters:
      - in: header
        name: X-Device-Token
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          required: [filename]
          properties:
            filename:    {type: string, example: "frame_001.jpg"}
            content_type:{type: string, example: "image/jpeg"}
            camera_id:   {type: string, example: "cam-uuid-or-name"}
    responses:
      200:
        description: Presigned upload URL gerada
      400:
        description: filename ausente
      401:
        description: Token ausente ou inválido
      403:
        description: Dispositivo revogado
    """
    # 1. Extract device token from header
    token = request.headers.get("X-Device-Token", "").strip()
    if not token:
        return error("X-Device-Token ausente", 401)

    # 2. Verify enrollment token and extract claims
    try:
        claims = verify_device_token(token)
    except AuthenticationError as exc:
        logger.warning("evidence_upload: token validation failed")
        return error(str(exc), 401)

    # 3. tenant_id from verified claims (enrollment token binds tenant at issue time)
    tenant_id = str(claims["tenant_id"])

    # 7. Parse body
    data = request.get_json(silent=True) or {}
    filename = (data.get("filename") or "").strip()
    content_type = (data.get("content_type") or "application/octet-stream").strip()
    camera_id = (data.get("camera_id") or "unknown").strip()

    if not filename:
        return error("filename é obrigatório", 400)

    # 8. Sanitize to prevent path injection in the key
    filename = _sanitize_filename(filename)
    camera_id = _sanitize_path_segment(camera_id)

    # 9. Build evidence key: tenant/<tid>/evidence/<cam>/<ts>_<file>
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_key = f"tenant/{tenant_id}/evidence/{camera_id}/{timestamp}_{filename}"

    # 10. Generate presigned PUT URL
    try:
        storage = get_storage()
        upload_url = storage.generate_presigned_upload_url(
            evidence_key, content_type, ttl=_UPLOAD_TTL
        )
    except Exception as exc:
        logger.error("evidence_upload: presigned url failed: %s", exc)
        return error("Erro ao gerar URL de upload", 500)

    logger.info(
        "evidence_upload_presigned: tenant=%s camera=%s",
        tenant_id[:8], camera_id,
    )

    return success({
        "upload_url": upload_url,
        "evidence_key": evidence_key,
        "expires_in": _UPLOAD_TTL,
    })


# ---------------------------------------------------------------------------
# GET /api/v1/storage/evidence/<key> — operator presigned GET (JWT)
# ---------------------------------------------------------------------------

@storage_bp.route("/evidence/<path:evidence_key>", methods=["GET"])
@jwt_required()
def evidence_download(evidence_key: str):  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - storage
    summary: Gera presigned GET URL para evidência (operador JWT)
    security:
      - Bearer: []
    parameters:
      - in: path
        name: evidence_key
        required: true
        type: string
        description: Chave da evidência (deve começar com tenant/{tenant_id}/)
    responses:
      200:
        description: Presigned download URL gerada
      400:
        description: evidence_key inválido (path traversal)
      403:
        description: Chave pertence a outro tenant
    """
    # 1. Path traversal guard
    if ".." in evidence_key or evidence_key.startswith("/"):
        return error("evidence_key inválido", 400)

    # 2. Tenant isolation — key MUST start with tenant/<caller's tenant_id>/
    tenant_id = str(get_tenant_id())
    expected_prefix = f"tenant/{tenant_id}/"
    if not evidence_key.startswith(expected_prefix):
        logger.warning(
            "evidence_download: cross-tenant attempt tenant=%s key_prefix=%s",
            tenant_id[:8],
            evidence_key[:32],
        )
        return error("Acesso negado", 403)

    # 3. Generate presigned GET URL
    try:
        storage = get_storage()
        download_url = storage.generate_presigned_download_url(
            evidence_key, ttl=_DOWNLOAD_TTL
        )
    except Exception as exc:
        logger.error("evidence_download: presigned url failed: %s", exc)
        return error("Erro ao gerar URL de download", 500)

    logger.info(
        "evidence_download_presigned: tenant=%s key=%s",
        tenant_id[:8],
        evidence_key[:48],
    )

    return success({
        "download_url": download_url,
        "evidence_key": evidence_key,
        "expires_in": _DOWNLOAD_TTL,
    })
