"""
Recognition — Video and Frame handlers.

Handles: list_videos, create_video, get_video_frames, get_frame_image
"""
import logging
import os
from uuid import UUID

from botocore.exceptions import ClientError
from flask import jsonify, make_response, request, send_file

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError, NotFoundError, StorageError
from app.core.responses import error, success
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.storage.local_storage import get_storage
from app.infrastructure.storage.r2_storage import R2Storage

from .helpers import _get_pool, get_video_service

logger = logging.getLogger(__name__)

# Códigos do R2/S3 que significam "objeto realmente não existe". Qualquer
# outro ClientError (403 credencial, 500, timeout de conexão) é falha de
# INFRAESTRUTURA — não pode virar 404 de "frame não encontrado" (a máscara
# escondia credencial R2 quebrada atrás de um 404 indistinguível de posse).
_R2_MISSING_OBJECT_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


def list_videos_handler():
    """Lista vídeos de treinamento do usuário.
    ---
    tags:
      - training
    summary: Listar vídeos de treinamento
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de vídeos
    """
    try:
        user_id = get_current_user_id()
        videos = get_video_service().list_videos(user_id)
        return success(videos)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_videos_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def create_video_handler():
    """Registra upload de vídeo."""
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        video = get_video_service().create_video(
            user_id=user_id,
            filename=data.get("filename", ""),
            original_filename=data.get("original_filename"),
            file_size=data.get("file_size"),
        )
        return success(video, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_video_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_video_frames_handler(video_id: str):
    """Lista frames de um vídeo. Usado pelo AnnotationInterface.jsx.
    ---
    tags:
      - training
    summary: Listar frames aprovados de um vídeo
    security:
      - Bearer: []
    parameters:
      - in: path
        name: video_id
        type: string
        required: true
    responses:
      200:
        description: Lista de frames com status de anotação e presigned URL
      404:
        description: Vídeo não encontrado
    """
    try:
        user_id = get_current_user_id()
        service = get_video_service()
        video = service.get_video(UUID(video_id))
        if str(video.get("user_id")) != str(user_id):
            # C-01: mesmo NotFoundError de vídeo inexistente — corpo idêntico, sem oráculo
            raise NotFoundError("Vídeo", str(UUID(video_id)))
        frames = service.get_video_frames(UUID(video_id))

        # Enriquecer com presigned URL para que o browser carregue direto do R2
        storage = get_storage()
        if isinstance(storage, R2Storage):
            for frame in frames:
                try:
                    frame["url"] = storage.generate_presigned_download_url(
                        frame["filename"], ttl=3600, response_content_type="image/jpeg"
                    )
                except Exception as url_exc:  # noqa: BLE001
                    logger.warning("presigned_url_failed frame=%s: %s", frame.get("id"), url_exc)
                    frame["url"] = None

        return jsonify({"success": True, "frames": frames}), 200
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_frames_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_frame_image_handler(frame_id: str):
    """Serve imagem de um frame.

    Proxia bytes pelo backend para evitar CORB com redirect cross-origin.
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        pool = _get_pool()
        frame_repo = FrameRepository(pool)
        frame = frame_repo.get_by_id_and_user(UUID(frame_id), UUID(str(user_id)), tenant_id)
        if not frame:
            raise NotFoundError("Frame", frame_id)

        storage = get_storage()

        # R2: proxiar bytes pelo backend (evita CORB no browser com redirect cross-origin)
        if isinstance(storage, R2Storage):
            try:
                data = storage.download_bytes(frame["filename"])
            except StorageError as exc:
                cause = exc.__cause__
                code = (
                    cause.response.get("Error", {}).get("Code", "")
                    if isinstance(cause, ClientError)
                    else ""
                )
                if code in _R2_MISSING_OBJECT_CODES:
                    # Objeto de fato ausente no R2 — 404 real (posse
                    # cross-tenant também cai aqui via frame_repo acima,
                    # C-01 intacto).
                    raise NotFoundError("Frame", frame_id) from exc
                # Erro de infraestrutura (403 credencial, timeout, conexão)
                # NÃO é "frame não existe" — mascarar como 404 esconde
                # credencial R2 quebrada atrás de um erro indistinguível de
                # posse. Log ERROR com a exceção original preservada.
                logger.error(
                    "get_frame_image_storage_error: frame=%s key=%s code=%s err=%s",
                    frame_id, frame["filename"], code, exc, exc_info=True,
                )
                raise StorageError(
                    "Falha ao acessar armazenamento de imagens"
                ) from exc
            resp = make_response(data)
            resp.headers["Content-Type"] = "image/jpeg"
            resp.headers["Cache-Control"] = "public, max-age=3600"
            return resp

        # LocalStorage: servir arquivo direto (fallback dev)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )))
        storage_dir = os.path.realpath(os.path.join(base_dir, "storage"))
        frame_path = os.path.realpath(os.path.join(storage_dir, frame["filename"]))

        # SEC: path traversal guard
        if not frame_path.startswith(storage_dir + os.sep):
            raise NotFoundError("Arquivo de frame", "path traversal blocked")

        if not os.path.exists(frame_path):
            raise NotFoundError("Arquivo de frame", frame["filename"])

        return send_file(frame_path, mimetype="image/jpeg")

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_frame_image_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


