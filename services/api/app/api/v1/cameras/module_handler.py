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

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.core.responses import error, success
from app.core.tenant import require_permission
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


def _fetch_tenant_modules() -> list[str]:
    """Consulta tenants.modules_enabled no banco (fallback p/ token antigo)."""
    try:
        from app.core.auth import get_tenant_id

        tenant_id = get_tenant_id()
        pool = DatabasePool.get_instance()
        if pool is None:
            return []
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT modules_enabled FROM public.tenants WHERE id = %s",
                (str(tenant_id),),
            )
            row = cur.fetchone()
        raw = row["modules_enabled"] if row else None
        if isinstance(raw, str):
            import json

            raw = json.loads(raw)
        return raw if isinstance(raw, list) else []
    except Exception as exc:
        logger.warning("tenant_modules_lookup_failed: %s", exc)
        return []


def _is_module_allowed(module: str) -> bool:
    """Gate de módulo do tenant — fail-closed (fix WS7 P2).

    Antes: claim 'modules' vazia deixava passar QUALQUER módulo (fail-open).
    Agora:
      - 'none' sempre permitido (pausa a câmera)
      - claim presente (lista) → a lista é a fonte: vazia nega tudo != none
      - claim AUSENTE (token antigo) → consulta tenants.modules_enabled no
        banco antes de negar (não derruba sessões ativas); erro nega.
    """
    if module == "none":
        return True

    from flask_jwt_extended import get_jwt

    modules = get_jwt().get("modules")
    if isinstance(modules, list):
        return module in modules
    return module in _fetch_tenant_modules()


@jwt_required()
@require_permission("cameras:configure")
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

        # Verificar que módulo está habilitado para o tenant (fail-closed)
        if not _is_module_allowed(module):
            raise AuthorizationError(
                f"Módulo '{module}' não habilitado para este tenant."
            )

        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        repo = _get_camera_repo()

        # Verificar que câmera pertence ao tenant (C-01) — 404 em vez de 403
        # para não vazar existência de câmeras de outros tenants.
        camera = repo.get_by_id_and_tenant(camera_id, tenant_id)
        if not camera:
            raise NotFoundError("Câmera", camera_id)

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
@require_permission("cameras:configure")
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

        tenant_id = get_tenant_id()
        repo = _get_camera_repo()
        camera = repo.get_by_id_and_tenant(camera_id, tenant_id)
        if not camera:
            raise NotFoundError("Câmera", camera_id)

        repo.update_schedule(camera_id, rules)

        logger.info("camera_schedule_updated: camera=%s rules_count=%d", camera_id, len(rules))
        return success({"camera_id": camera_id, "schedule_rules": rules})

    except (NotFoundError, ValidationError):
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
        tenant_id = get_tenant_id()
        repo = _get_camera_repo()
        camera = repo.get_by_id_and_tenant(camera_id, tenant_id)
        if not camera:
            raise NotFoundError("Câmera", camera_id)

        current_module = resolve_active_module(camera)

        return success({
            "camera_id": camera_id,
            "current_module": current_module,
            "paused": current_module is None,
            "default_module": camera.get("active_module"),
        })

    except NotFoundError:
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
