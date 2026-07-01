"""
CAMERA module_handler.py — Handlers de módulo e agendamento de câmeras.

Endpoints:
  PATCH /api/cameras/<id>/module    — alterar módulo ativo
  PUT   /api/cameras/<id>/schedule  — definir regras de agendamento
  GET   /api/cameras/<id>/module/current — módulo ativo agora (resolve schedule)
"""
import logging
import os

import redis as _redis
from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_modules_enabled
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.core.responses import error, success
from app.domain.services.camera_module_service import (
    resolve_active_module,
    validate_schedule_rules,
)
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.camera_repository import CameraRepository

logger = logging.getLogger(__name__)


def _get_camera_repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraRepository(pool)


@jwt_required()
def patch_camera_module(camera_id: str):  # type: ignore[no-untyped-def]
    """
    PATCH /api/cameras/<id>/module

    Body: {"module": "epi" | "quality" | "counting" | "basic" | "none"}

    Valida que módulo está em tenant.modules_enabled antes de salvar.
    Publica evento Redis para worker recarregar modelo se necessário.
    """
    try:
        data = request.get_json() or {}
        module = (data.get("module") or "").strip()

        valid_modules = {"epi", "quality", "counting", "basic", "none"}
        if module not in valid_modules:
            raise ValidationError(f"Módulo inválido. Use: {sorted(valid_modules)}")

        # Verificar que módulo está habilitado para o tenant
        modules_enabled = get_modules_enabled()
        if module != "none" and modules_enabled and module not in modules_enabled:
            raise AuthorizationError(
                f"Módulo '{module}' não habilitado para este tenant. "
                f"Habilitados: {modules_enabled}"
            )

        user_id = get_current_user_id()
        repo = _get_camera_repo()

        camera = repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", camera_id)

        if camera.get("tenant_id") and str(camera["tenant_id"]) != str(user_id):
            raise AuthorizationError("Sem permissão para esta câmera")

        # Atualizar active_module
        repo.update_module(camera_id, module)

        # Notificar worker via Redis (best-effort)
        _notify_module_changed(camera_id, module)

        logger.info(
            "camera_module_updated: camera=%s module=%s user=%s", camera_id, module, user_id
        )
        return success({"camera_id": camera_id, "active_module": module})

    except (NotFoundError, ValidationError, AuthorizationError):
        raise
    except Exception as exc:
        logger.error("patch_camera_module_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar módulo", 500)


@jwt_required()
def put_camera_schedule(camera_id: str):  # type: ignore[no-untyped-def]
    """
    PUT /api/cameras/<id>/schedule

    Body: {"rules": [...]}  — array de regras de agendamento

    Formato de cada regra:
      {"days": [1,2,3,4,5], "start": "08:00", "end": "18:00", "module": "epi"}
    """
    try:
        data = request.get_json() or {}
        rules = data.get("rules", [])

        valid, msg = validate_schedule_rules(rules)
        if not valid:
            raise ValidationError(f"schedule_rules inválido: {msg}")

        user_id = get_current_user_id()
        repo = _get_camera_repo()
        camera = repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", camera_id)

        if camera.get("tenant_id") and str(camera["tenant_id"]) != str(user_id):
            raise AuthorizationError("Sem permissão para esta câmera")

        repo.update_schedule(camera_id, rules)

        logger.info("camera_schedule_updated: camera=%s rules_count=%d", camera_id, len(rules))
        return success({"camera_id": camera_id, "schedule_rules": rules})

    except (NotFoundError, ValidationError, AuthorizationError):
        raise
    except Exception as exc:
        logger.error("put_camera_schedule_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar agendamento", 500)


@jwt_required()
def get_camera_module_current(camera_id: str):  # type: ignore[no-untyped-def]
    """
    GET /api/cameras/<id>/module/current

    Retorna módulo ativo agora baseado no schedule_rules + horário atual.
    Útil para o frontend mostrar qual módulo está rodando sem esperar o worker.
    """
    try:
        user_id = get_current_user_id()
        repo = _get_camera_repo()
        camera = repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", camera_id)

        if camera.get("tenant_id") and str(camera["tenant_id"]) != str(user_id):
            raise AuthorizationError("Sem permissão para esta câmera")

        current_module = resolve_active_module(camera)

        return success({
            "camera_id": camera_id,
            "current_module": current_module,
            "paused": current_module is None,
            "default_module": camera.get("active_module"),
        })

    except (NotFoundError, AuthorizationError):
        raise
    except Exception as exc:
        logger.error("get_camera_module_current_error: %s", exc, exc_info=True)
        return error("Erro ao resolver módulo ativo", 500)


def _notify_module_changed(camera_id: str, module: str) -> None:
    """
    Publica evento Redis para o worker de inferência recarregar o modelo.
    Falha silenciosa — não deve bloquear a response.
    """
    try:
        r = _redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
        r.publish(f"camera_module_changed:{camera_id}", module)
        r.close()
    except Exception as exc:
        logger.warning("notify_module_changed_failed: camera=%s error=%s", camera_id, exc)
