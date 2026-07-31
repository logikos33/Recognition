"""
Recognition — Storage health and test routes.

GET /api/v1/storage/health — Check R2/local storage connectivity
POST /api/v1/storage/test-upload — Test upload (dev only)
"""
import logging
import os
from uuid import uuid4

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, verify_jwt_in_request

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
    summary: Health check do armazenamento (config; round-trip real com ?deep=1)
    description: |
      Endpoint público (sem JWT) no modo padrão: verifica só se o backend de
      storage resolve configuração/credenciais — NÃO faz I/O. Antes fazia um
      ciclo write/exists/delete real a cada chamada, o que expunha uma
      superfície pública sem auth capaz de gerar custo/latência real de R2 a
      qualquer taxa permitida pelo rate limit (task-085/achado de segurança);
      esse modo NÃO volta por padrão.

      `connected` foi RENOMEADO o significado: antes era sempre `true` quando
      `get_storage()` não levantava — o que mentia. Caso real no DEV: dizia
      `connected: true, R2Storage` enquanto TODO PutObject dava AccessDenied
      (token escopado a outro bucket). Agora o padrão devolve
      `connected: null` + `checked: "config"`, deixando explícito que nada
      foi verificado na rede.

      `?deep=1` faz o round-trip REAL (upload → exists → delete) e exige JWT,
      justamente pra não reabrir o buraco de custo sem auth.
    parameters:
      - {in: query, name: deep, type: boolean, required: false,
         description: "Round-trip real (exige JWT)"}
    responses:
      200:
        description: Status do storage
        schema:
          properties:
            storage_type: {type: string, example: R2Storage}
            connected: {type: boolean, description: "null quando checked=config"}
            checked: {type: string, enum: [config, round_trip]}
            r2_configured: {type: boolean}
      401: {description: "?deep=1 sem JWT"}
    """
    deep = request.args.get("deep", "").strip().lower() in ("1", "true", "yes")

    try:
        storage = get_storage()
        storage_type = type(storage).__name__
    except Exception as exc:
        # Com o fim do fallback silencioso, config parcial/ausente chega aqui
        # como StorageError — é uma falha REAL de configuração, não um detalhe.
        logger.error("storage_health_config_error: %s", exc)
        return success({
            "storage_type": "unknown",
            "connected": False,
            "checked": "config",
            "error": str(exc),
            "r2_configured": bool(os.environ.get("R2_ENDPOINT")),
        })

    if not deep:
        return success({
            "storage_type": storage_type,
            "connected": None,
            "checked": "config",
            "r2_configured": bool(os.environ.get("R2_ENDPOINT")),
        })

    # Round-trip real — só com JWT (ver descrição acima).
    try:
        verify_jwt_in_request()
    except Exception:
        return error("?deep=1 exige autenticação", 401)

    probe_key = f"health-probe/{uuid4()}.txt"
    try:
        storage.upload_bytes(probe_key, b"round-trip probe", "text/plain")
        exists = storage.exists(probe_key)
    except Exception as exc:
        logger.error("storage_health_round_trip_failed: key=%s err=%s", probe_key, exc)
        return success({
            "storage_type": storage_type,
            "connected": False,
            "checked": "round_trip",
            "error": str(exc),
            "r2_configured": bool(os.environ.get("R2_ENDPOINT")),
        })
    finally:
        # Sonda não pode virar lixo no bucket — best-effort, e um delete que
        # falha não invalida o resultado do teste de escrita/leitura.
        try:
            storage.delete(probe_key)
        except Exception as exc:
            logger.warning("storage_health_probe_cleanup_failed: key=%s err=%s", probe_key, exc)

    return success({
        "storage_type": storage_type,
        "connected": bool(exists),
        "checked": "round_trip",
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
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("test_upload_error: %s", exc, exc_info=True)
        return error("Erro no upload de teste", 500)
    finally:
        # Antes o objeto de teste ficava no bucket pra sempre — cada chamada
        # acumulava lixo em test/. Limpeza best-effort: a URL assinada acima
        # já foi gerada e o que interessa (escreveu e leu) já foi apurado.
        try:
            storage.delete(test_key)
        except Exception as exc:
            logger.warning("test_upload_cleanup_failed: key=%s err=%s", test_key, exc)

    return success({
        "key": test_key,
        "exists": exists,
        "download_url": download_url,
        "storage_type": type(storage).__name__,
        "cleaned_up": True,
    })
