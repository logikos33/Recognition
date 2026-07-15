"""
Recognition — Storage health and test routes.

GET /api/v1/storage/health — Check R2/local storage connectivity
POST /api/v1/storage/test-upload — Test upload (dev only)
"""
import logging
import os
from uuid import uuid4

from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

storage_bp = Blueprint("storage", __name__, url_prefix="/api/v1/storage")


@storage_bp.route("/health", methods=["GET"])
def storage_health():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - storage
    summary: Health check do armazenamento (config apenas, sem I/O real)
    description: |
      Endpoint público (sem JWT). Verifica só se o backend de storage resolve
      configuração/credenciais — NÃO faz upload/delete real. Antes fazia um
      ciclo write/exists/delete real a cada chamada, o que expunha uma
      superfície pública sem auth capaz de gerar custo/latência real de R2 a
      qualquer taxa permitida pelo rate limit (task-085/achado de segurança).
      Para testar upload real, usar POST /api/v1/storage/test-upload (JWT).
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

        return success({
            "storage_type": storage_type,
            "connected": True,
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
    summary: Upload de teste (qualquer usuário autenticado)
    description: |
      Faz upload/exists real de um arquivo de teste no storage configurado.
      Requer JWT válido — não há checagem adicional de role/admin apesar do
      nome sugerir uso administrativo (achado de doc-vs-código, task-085).
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
