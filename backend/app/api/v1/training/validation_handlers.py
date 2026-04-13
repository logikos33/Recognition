"""
EPI Monitor V2 — Frame Validation Handler.

Endpoint para marcar frame como validado por humano.
AI_NOTE: Validação é separada de anotação — 'annotated' = tem boxes salvas,
'validated' = humano revisou e confirmou que as boxes estão corretas.
AI_NOTE: Todos os métodos de repositório usados aqui verificam posse via
JOIN em training_videos.user_id para prevenir IDOR.
"""
import logging
from uuid import UUID

from flask import jsonify

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError, NotFoundError
from app.core.responses import error
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.frame_repository import FrameRepository

logger = logging.getLogger(__name__)


def validate_frame_handler(frame_id: str):
    """Marca um frame como validado pelo usuário atual.

    Frame deve estar anotado (is_annotated=TRUE) para ser validado.
    Pode ser re-validado (idempotente).
    Apenas frames do próprio usuário podem ser validados.
    """
    try:
        user_id = get_current_user_id()
        pool = DatabasePool.get_instance()
        frame_repo = FrameRepository(pool)

        # AI_NOTE: get_by_id_and_user verifica posse via JOIN em training_videos
        # Previne IDOR — retorna None se frame não pertencer ao usuário
        frame = frame_repo.get_by_id_and_user(UUID(frame_id), UUID(str(user_id)))
        if not frame:
            raise NotFoundError("Frame", frame_id)

        if not frame.get("is_annotated"):
            return error("Frame não está anotado. Anote o frame antes de validar.", 400)

        # AI_NOTE: mark_validated usa UPDATE com JOIN — garante posse no próprio UPDATE
        updated = frame_repo.mark_validated(UUID(frame_id), UUID(str(user_id)))
        logger.info("frame_validated: frame_id=%s, user=%s", frame_id, user_id)

        return jsonify({
            "success": True,
            "frame_id": frame_id,
            "validated_at": (
                updated["validated_at"].isoformat()
                if updated and updated.get("validated_at")
                else None
            ),
        }), 200

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("validate_frame_error: frame=%s, err=%s", frame_id, exc, exc_info=True)
        return error("Erro interno", 500)


def get_frame_validation_stats_handler(video_id: str):
    """Retorna contagem de frames anotados e validados de um vídeo.

    AI_NOTE: count_validated filtra por user_id (via JOIN) para garantir
    que o usuário só vê stats dos seus próprios vídeos.
    """
    try:
        user_id = get_current_user_id()
        pool = DatabasePool.get_instance()
        frame_repo = FrameRepository(pool)
        stats = frame_repo.count_validated(UUID(video_id), UUID(str(user_id)))
        return jsonify({"success": True, "stats": stats}), 200
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("validation_stats_error: video=%s, err=%s", video_id, exc, exc_info=True)
        return error("Erro interno", 500)
