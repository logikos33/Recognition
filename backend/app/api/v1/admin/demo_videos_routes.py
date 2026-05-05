"""
Recognition — Admin: Demo Videos Routes (superadmin only).

Endpoints para upload, listagem e exclusão de vídeos MP4 de demonstração.
Todos os endpoints exigem @require_superadmin — clientes nunca acessam.

POST   /api/admin/demo-videos/upload   — upload multipart de vídeo MP4
GET    /api/admin/demo-videos          — lista vídeos demo (?module=&camera_id=)
DELETE /api/admin/demo-videos/<id>     — soft-delete de um vídeo
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity

from app.core.auth import get_role
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.core.tenant import require_superadmin
from app.domain.services import demo_video_service

logger = logging.getLogger(__name__)

demo_videos_bp = Blueprint("demo_videos", __name__, url_prefix="/api/admin/demo-videos")


@demo_videos_bp.route("/upload", methods=["POST"])
@require_superadmin
def upload_demo_video():  # type: ignore[no-untyped-def]
    """
    Upload de vídeo demo (superadmin only).

    Form fields:
      - video: arquivo MP4 (required)
      - module: string — ex. 'fueling', 'epi' (required)
      - camera_id: int (optional)
      - label: string (optional)
    """
    try:
        # Validar presença do arquivo
        if "video" not in request.files:
            return error("Campo 'video' obrigatório", 400)

        file = request.files["video"]
        if not file.filename:
            return error("Arquivo sem nome", 400)

        module = request.form.get("module", "").strip()
        if not module:
            return error("Campo 'module' obrigatório (ex: fueling, epi)", 400)

        camera_id_raw = request.form.get("camera_id")
        camera_id = camera_id_raw or None
        label = request.form.get("label") or None

        # Lê bytes do arquivo para validação de tamanho e upload
        file_data = file.read()
        content_type = file.content_type or "video/mp4"

        # user_id é UUID string — armazenar como string, sem cast para int
        user_id = get_jwt_identity() or None

        record = demo_video_service.upload(
            file_data=file_data,
            content_type=content_type,
            module=module,
            user_role=get_role(),
            user_id=user_id,
            camera_id=camera_id,
            label=label,
        )

        return success({"video": record}, 201)

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("demo_video_upload_error: %s", exc, exc_info=True)
        return error("Erro interno no upload", 500)


@demo_videos_bp.route("", methods=["GET"])
@require_superadmin
def list_demo_videos():  # type: ignore[no-untyped-def]
    """
    Lista vídeos demo ativos.

    Query params opcionais:
      - module: filtrar por módulo
      - camera_id: filtrar por câmera
    """
    try:
        module = request.args.get("module") or None
        camera_id_raw = request.args.get("camera_id")
        camera_id = camera_id_raw or None

        videos = demo_video_service.list_videos(module=module, camera_id=camera_id)
        return success({"videos": videos})

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("demo_video_list_error: %s", exc, exc_info=True)
        return error("Erro ao listar vídeos demo", 500)


@demo_videos_bp.route("/<int:video_id>", methods=["DELETE"])
@require_superadmin
def delete_demo_video(video_id: int):  # type: ignore[no-untyped-def]
    """Soft-delete de um vídeo demo pelo ID."""
    try:
        deleted = demo_video_service.delete(video_id=video_id, user_role=get_role())
        if not deleted:
            return error("Vídeo não encontrado ou já removido", 404)
        return success({"deleted": True})

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("demo_video_delete_error: id=%d %s", video_id, exc, exc_info=True)
        return error("Erro ao deletar vídeo demo", 500)
