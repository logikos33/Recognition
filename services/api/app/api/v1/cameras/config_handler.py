"""
Recognition — Camera config handler.

PATCH /api/cameras/<camera_id>/config — atualiza fps_target e/ou quality_preset.
PATCH parcial: pelo menos um dos campos é obrigatório.
Validações: fps_target in {1,5,10,15,30}, quality_preset in {low,medium,high}.

Permissão escopada pelo tenant do JWT (get_tenant_id) — não pelo user_id
(fix da mesma classe do commit f6df666). Override para admin/superadmin via
role do JWT.

Propagação cloud→edge: após update OK, se a câmera tem site_id, enfileira
edge_command 'update_camera_config' (best-effort — nunca falha o PATCH).
"""
import logging
import time
from uuid import UUID

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_role, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success

from .helpers import _get_camera_service

logger = logging.getLogger(__name__)

_ADMIN_ROLES = {"admin", "superadmin"}


def _get_edge_command_repo():  # type: ignore[no-untyped-def]
    """Factory isolada para facilitar mock em testes."""
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    from app.infrastructure.database.repositories.edge_command_repository import (  # noqa: PLC0415
        EdgeCommandRepository,
    )
    return EdgeCommandRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


def _queue_edge_propagation(camera: dict, user_id) -> dict:  # type: ignore[no-untyped-def]
    """Enfileira edge_command com a config efetiva da câmera (best-effort).

    Retorna {'queued': bool, 'reason': 'no_site'|'error'|None}.
    NUNCA levanta exceção — falha na fila não pode falhar o PATCH.
    """
    site_id = camera.get("site_id")
    if not site_id:
        return {"queued": False, "reason": "no_site"}
    try:
        command_id = f"camcfg:{camera['id']}:{int(time.time() * 1000)}"
        _get_edge_command_repo().create(
            tenant_id=str(camera["tenant_id"]),
            site_id=str(site_id),
            command_type="update_camera_config",
            payload={
                "camera_id": str(camera["id"]),
                "fps_target": camera.get("fps_target"),
                "quality_preset": camera.get("quality_preset"),
            },
            command_id=command_id,
            created_by=str(user_id),
        )
        return {"queued": True, "reason": None}
    except Exception:
        logger.warning(
            "edge_config_propagation_failed camera=%s", camera.get("id"), exc_info=True
        )
        return {"queued": False, "reason": "error"}


@jwt_required()
def patch_camera_config(camera_id: str):  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Atualizar FPS alvo e/ou qualidade da câmera (PATCH parcial)
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: camera_id, type: string, required: true}
      - in: body
        name: body
        required: true
        schema:
          description: "Pelo menos um dos campos é obrigatório"
          properties:
            fps_target:
              type: integer
              enum: [1, 5, 10, 15, 30]
              description: "FPS alvo para inferência YOLO (opcional)"
            quality_preset:
              type: string
              enum: [low, medium, high]
              description: "Preset de qualidade do stream (opcional)"
    responses:
      200: {description: Configuração atualizada (inclui campo aditivo 'propagation')}
      400: {description: Valores inválidos ou nenhum campo informado}
      403: {description: Sem permissão}
      404: {description: Câmera não encontrada}
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        is_admin = get_role() in _ADMIN_ROLES
        data = request.get_json() or {}

        fps_target = data.get("fps_target")
        quality_preset = data.get("quality_preset")

        if fps_target is None and quality_preset is None:
            return error("Informe fps_target e/ou quality_preset", 400)

        if fps_target is not None and (
            isinstance(fps_target, bool) or not isinstance(fps_target, int)
        ):
            return error("fps_target deve ser um inteiro", 400)

        service = _get_camera_service()
        updated = service.patch_config(
            UUID(camera_id),
            UUID(str(tenant_id)),
            fps_target,
            str(quality_preset) if quality_preset is not None else None,
            is_admin,
        )

        propagation = _queue_edge_propagation(updated, user_id)
        return success({**updated, "propagation": propagation})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("patch_camera_config_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
