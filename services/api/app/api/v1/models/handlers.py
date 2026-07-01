"""
Model Rollout Handlers — manifesto de modelo ativo e operação de pin.

GET  /api/v1/models/active?module=<code>  → manifesto do modelo ativo (tenant×módulo)
POST /api/v1/models/<id>/pin              → pin de versão (admin); suporta flag canary
"""
import logging

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_role, get_tenant_schema
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.model_rollout_repository import (
    ModelRolloutRepository,
)

logger = logging.getLogger(__name__)


def _get_repo() -> ModelRolloutRepository:
    pool = DatabasePool.get_instance()
    return ModelRolloutRepository(pool)


@jwt_required()
def get_active_manifest():  # type: ignore[no-untyped-def]
    """Retorna manifesto do modelo ativo para tenant×módulo.

    Query param: module (obrigatório) — ex: epi, quality, counting.
    Resposta: {id, module, version, checksum, git_sha, canary, active, created_at}.
    """
    try:
        module = (request.args.get("module") or "").strip()
        if not module:
            return error("Parâmetro 'module' é obrigatório", 400)

        schema = get_tenant_schema()
        repo = _get_repo()
        manifest = repo.get_active_model(schema, module)
        if manifest is None:
            return error("Nenhum modelo ativo para o módulo informado", 404)
        return success(manifest)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_active_manifest_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def pin_model_version(model_id: str):  # type: ignore[no-untyped-def]
    """Fixa versão de modelo como ativa para tenant×módulo (admin).

    Body (JSON, opcional):
      canary (bool, default false) — se true, marca como canário sem ativar.

    Comportamento:
      - canary=false (padrão): desativa modelo anterior do módulo, ativa este,
        limpa flag canary dos metrics, registra em model_activation_log.
      - canary=true: adiciona {"canary": true} aos metrics, NÃO altera active.
    """
    try:
        role = get_role()
        if role not in ("admin", "superadmin"):
            return error("Acesso restrito a administradores", 403)

        schema = get_tenant_schema()
        user_id = str(get_current_user_id())

        data = request.get_json(silent=True) or {}
        canary = bool(data.get("canary", False))

        repo = _get_repo()

        model = repo.get_model_by_id(schema, model_id)
        if model is None:
            return error("Modelo não encontrado", 404)

        if canary:
            manifest = repo.mark_canary(schema, model_id)
            if manifest is None:
                return error("Falha ao marcar modelo como canário", 500)
            return success({"manifest": manifest, "action": "canary_marked"})

        new_manifest, previous = repo.pin_model(schema, model_id, model["module"])
        if new_manifest is None:
            return error("Falha ao fixar modelo", 500)

        previous_id = previous["id"] if previous else None
        try:
            repo.record_activation_log(model_id, user_id, previous_id)
        except Exception as exc:
            logger.warning("model_activation_log_failed model_id=%s: %s", model_id, exc)

        return success({"manifest": new_manifest, "previous": previous, "action": "pinned"})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("pin_model_version_error model_id=%s: %s", model_id, exc, exc_info=True)
        return error("Erro interno", 500)
