"""
Recognition — Training Image handlers.

GET  /api/training/images  → galeria paginada de frames (imagens de treino) do tenant
"""
import logging
from uuid import UUID

from flask import request

from app.core.auth import get_current_user_id
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.frame_repository import FrameRepository

logger = logging.getLogger(__name__)


def _get_frame_repo() -> FrameRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return FrameRepository(pool)


def list_training_images_handler():
    """Lista imagens de treino do usuário com paginação e filtros.

    Query params:
      page          int  (default 1)
      page_size     int  (default 24, max 100)
      is_annotated  'true' | 'false' | omitido → todos
      order         'desc' | 'asc'  (default desc por created_at)
    """
    try:
        user_id = get_current_user_id()

        page = max(1, request.args.get("page", 1, type=int))
        page_size = min(100, max(1, request.args.get("page_size", 24, type=int)))
        order = request.args.get("order", "desc")
        if order not in ("asc", "desc"):
            order = "desc"

        is_annotated_param = request.args.get("is_annotated")
        is_annotated: bool | None = None
        if is_annotated_param == "true":
            is_annotated = True
        elif is_annotated_param == "false":
            is_annotated = False

        repo = _get_frame_repo()
        result = repo.get_by_user_paginated(
            user_id=UUID(str(user_id)),
            page=page,
            page_size=page_size,
            is_annotated=is_annotated,
            order=order,
        )

        # Serialise UUIDs
        for frame in result.get("frames", []):
            frame["id"] = str(frame["id"])
            frame["video_id"] = str(frame["video_id"])

        return success(result)

    except Exception as exc:
        logger.error("list_training_images_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
