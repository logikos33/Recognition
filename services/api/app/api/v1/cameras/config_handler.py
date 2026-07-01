"""
Recognition — Camera config handler.

PATCH /api/cameras/<camera_id>/config — atualiza fps_target e quality_preset.
Validações: fps_target in {1,5,10,15,30}, quality_preset in {low,medium,high}.
"""
import logging
from uuid import UUID

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error

from .helpers import _get_camera_service, _is_admin

logger = logging.getLogger(__name__)


@jwt_required()
def patch_camera_config(camera_id: str):  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Atualizar FPS alvo e qualidade da câmera
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: camera_id, type: string, required: true}
      - in: body
        name: body
        required: true
        schema:
          required: [fps_target, quality_preset]
          properties:
            fps_target:
              type: integer
              enum: [1, 5, 10, 15, 30]
              description: "FPS alvo para inferência YOLO"
            quality_preset:
              type: string
              enum: [low, medium, high]
              description: "Preset de qualidade do stream"
    responses:
      200: {description: Configuração atualizada}
      400: {description: Valores inválidos}
      403: {description: Sem permissão}
      404: {description: Câmera não encontrada}
    """
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}

        fps_target = data.get("fps_target")
        quality_preset = data.get("quality_preset")

        if fps_target is None or quality_preset is None:
            return error("fps_target e quality_preset são obrigatórios", 400)

        if not isinstance(fps_target, int):
            return error("fps_target deve ser um inteiro", 400)

        service = _get_camera_service()
        updated = service.patch_config(
            UUID(camera_id),
            UUID(str(user_id)),
            fps_target,
            str(quality_preset),
            _is_admin(user_id),
        )
        return success(updated)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("patch_camera_config_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
