"""
EPI Monitor V2 — Storage health and test routes.

GET /api/v1/storage/health — Check R2/local storage connectivity
POST /api/v1/storage/test-upload — Test upload (dev only)
"""
import logging
import os
from uuid import uuid4

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
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
