"""
Model Registry Handlers — registry canônico em public.trained_models (WS-A5).

GET  /api/v1/models                → lista do tenant (?module=&status=ativo|inativo)
GET  /api/v1/models/<id>           → detalhe + linhagem expandida
                                     (dataset_version→job→model + deployments ativos)
POST /api/v1/models/<id>/activate  → ativa modelo (gate de eval: verdict=reject → 409;
                                     override force=true só admin); desativa irmãos do
                                     mesmo tenant+módulo; sincroniza {schema}.models
                                     via pin_model best-effort (ajuste #7 / ADR-0037)
GET  /api/v1/models/<id>/eval      → última avaliação campeão×desafiante
POST /api/v1/models/<id>/evaluate  → dispara avaliação campeão×desafiante
                                     (WS-C1) sem re-treinar; assíncrono
GET  /api/v1/models/<id>/drift     → janelas de drift do modelo (?limit=)

Pin/canary do manifesto {schema}.models permanece em handlers.py
(models_rollout) — intocado, decisão do plano/ADR-0037.
"""
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from flask import request
from flask_jwt_extended import jwt_required

from app.constants import DeploymentStatus, EvalVerdict
from app.core.auth import (
    get_role,
    get_tenant_id,
    get_tenant_schema,
    require_training_role,
)
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.dataset_repository import (
    DatasetRepository,
)
from app.infrastructure.database.repositories.drift_metrics_repository import (
    DriftMetricsRepository,
)
from app.infrastructure.database.repositories.model_deployment_repository import (
    ModelDeploymentRepository,
)
from app.infrastructure.database.repositories.model_evaluation_repository import (
    ModelEvaluationRepository,
)
from app.infrastructure.database.repositories.model_registry_repository import (
    ModelRegistryRepository,
)
from app.infrastructure.database.repositories.model_rollout_repository import (
    ModelRolloutRepository,
)
from app.infrastructure.database.repositories.training_repository import (
    TrainingRepository,
)

logger = logging.getLogger(__name__)

_DEFAULT_DRIFT_LIMIT = 30
_MAX_DRIFT_LIMIT = 365

# Campos sensíveis que NUNCA saem na API (token de callback da GPU — ajuste #5)
_JOB_SENSITIVE_FIELDS = ("callback_token",)


# ---------------------------------------------------------------------------
# Factories (padrão do repo — monkeypatch-áveis nos testes)
# ---------------------------------------------------------------------------

def _get_registry_repo() -> ModelRegistryRepository:
    return ModelRegistryRepository(DatabasePool.get_instance())


def _get_deployment_repo() -> ModelDeploymentRepository:
    return ModelDeploymentRepository(DatabasePool.get_instance())


def _get_eval_repo() -> ModelEvaluationRepository:
    return ModelEvaluationRepository(DatabasePool.get_instance())


def _get_drift_repo() -> DriftMetricsRepository:
    return DriftMetricsRepository(DatabasePool.get_instance())


def _get_dataset_repo() -> DatasetRepository:
    return DatasetRepository(DatabasePool.get_instance())


def _get_training_repo() -> TrainingRepository:
    return TrainingRepository(DatabasePool.get_instance())


def _get_rollout_repo() -> ModelRolloutRepository:
    return ModelRolloutRepository(DatabasePool.get_instance())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_uuid(value: str) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _serialize(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Converte tipos não-JSON (UUID/datetime/Decimal) para o envelope."""
    if row is None:
        return None
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            out[key] = str(value)
        elif isinstance(value, (datetime, date)):
            out[key] = value.isoformat()
        elif isinstance(value, Decimal):
            out[key] = float(value)
        else:
            out[key] = value
    return out


def _same_tenant_or_legacy(row: Optional[dict[str, Any]], tenant_id: str) -> bool:
    """True se a linha pertence ao tenant OU é legada (tenant_id NULL)."""
    if row is None:
        return False
    row_tenant = row.get("tenant_id")
    return row_tenant is None or str(row_tenant) == str(tenant_id)


# ---------------------------------------------------------------------------
# GET /api/v1/models
# ---------------------------------------------------------------------------

@jwt_required()
def list_registry_models():  # type: ignore[no-untyped-def]
    """Lista modelos do registry do tenant.

    Query params:
      module (opcional) — filtra por module_code (ex: epi, quality).
      status (opcional) — ativo|inativo (aceita active|inactive).
    """
    try:
        tenant_id = get_tenant_id()

        module = (request.args.get("module") or "").strip() or None
        status = (request.args.get("status") or "").strip().lower()
        is_active: Optional[bool] = None
        if status in ("ativo", "active"):
            is_active = True
        elif status in ("inativo", "inactive"):
            is_active = False
        elif status:
            return error("Parâmetro 'status' inválido (use ativo|inativo)", 400)

        repo = _get_registry_repo()
        rows = repo.list_for_tenant(tenant_id, module_code=module, is_active=is_active)
        return success({"models": [_serialize(r) for r in rows], "total": len(rows)})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_registry_models_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/models/<model_id>
# ---------------------------------------------------------------------------

@jwt_required()
def get_registry_model(model_id: str):  # type: ignore[no-untyped-def]
    """Detalhe do modelo com linhagem expandida (ADR-0031).

    Resposta: model + lineage {dataset_version, job} + active_deployments.
    callback_token do job NUNCA é exposto (ajuste #5).
    """
    try:
        model_uuid = _parse_uuid(model_id)
        if model_uuid is None:
            return error("ID de modelo inválido", 400)

        tenant_id = get_tenant_id()
        model = _get_registry_repo().get_for_tenant(model_uuid, tenant_id)
        if model is None:
            return error("Modelo não encontrado", 404)

        # Linhagem: job (training_jobs)
        job: Optional[dict[str, Any]] = None
        if model.get("job_id"):
            job = _get_training_repo().get_job_by_id(model["job_id"])
            if not _same_tenant_or_legacy(job, tenant_id):
                job = None
            if job:
                job = dict(job)
                for field in _JOB_SENSITIVE_FIELDS:
                    job.pop(field, None)

        # Linhagem: dataset_version (do modelo; fallback via job)
        dataset_version: Optional[dict[str, Any]] = None
        dsv_id = model.get("dataset_version_id") or (
            job.get("dataset_version_id") if job else None
        )
        if dsv_id:
            dataset_version = _get_dataset_repo().get_by_id(dsv_id)
            if not _same_tenant_or_legacy(dataset_version, tenant_id):
                dataset_version = None

        # Deployments ativos do modelo (registry-level, migration 100)
        deployments = _get_deployment_repo().list_by_model(model_uuid, tenant_id)
        active_deployments = [
            _serialize(d) for d in deployments
            if d.get("status") == DeploymentStatus.ACTIVE
        ]

        return success({
            "model": _serialize(model),
            "lineage": {
                "dataset_version": _serialize(dataset_version),
                "job": _serialize(job),
            },
            "active_deployments": active_deployments,
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error(
            "get_registry_model_error model_id=%s: %s", model_id, exc, exc_info=True
        )
        return error("Erro interno", 500)


# ---------------------------------------------------------------------------
# POST /api/v1/models/<model_id>/activate
# ---------------------------------------------------------------------------

@jwt_required()
@require_training_role("approve")
def activate_registry_model(model_id: str):  # type: ignore[no-untyped-def]
    """Ativa modelo do registry (gate de avaliação — WS-C1/ADR-0031).

    Body (JSON, opcional):
      force (bool, default false) — override do gate de eval; SÓ admin+.

    Comportamento:
      - Última avaliação com verdict='reject' → 409 (a menos que force=true
        E role admin/superadmin).
      - Desativa is_active dos irmãos do mesmo tenant+module e ativa o alvo.
      - Sincroniza manifesto {schema}.models via ModelRolloutRepository.
        pin_model best-effort — schema/linha ausente → log warning, segue
        (ajuste #7, documentado no ADR-0037).
    """
    try:
        model_uuid = _parse_uuid(model_id)
        if model_uuid is None:
            return error("ID de modelo inválido", 400)

        tenant_id = get_tenant_id()
        data = request.get_json(silent=True) or {}
        force = bool(data.get("force", False))

        repo = _get_registry_repo()
        model = repo.get_for_tenant(model_uuid, tenant_id)
        if model is None:
            return error("Modelo não encontrado", 404)

        # Gate de avaliação campeão×desafiante
        evaluation = _get_eval_repo().get_latest_for_model(model_uuid, tenant_id)
        if evaluation and evaluation.get("verdict") == EvalVerdict.REJECT:
            if not force:
                return error(
                    "Modelo reprovado na avaliação campeão×desafiante — "
                    "reenvie com force=true (somente administradores)",
                    409,
                    error_code="eval_rejected",
                )
            if get_role() not in ("admin", "superadmin"):
                return error(
                    "Override force=true restrito a administradores", 403
                )

        module_code = model.get("module_code") or "epi"
        updated = repo.activate_for_tenant_module(model_uuid, tenant_id, module_code)
        if updated is None:
            return error("Falha ao ativar modelo", 500)

        # Sincronização best-effort do manifesto {schema}.models (ajuste #7)
        rollout_synced = False
        try:
            schema = get_tenant_schema()
            manifest, _previous = _get_rollout_repo().pin_model(
                schema, str(model_uuid), module_code
            )
            rollout_synced = manifest is not None
            if manifest is None:
                logger.warning(
                    "registry_activate_rollout_sync_miss: model=%s schema=%s "
                    "(sem linha correspondente em {schema}.models)",
                    model_id, schema,
                )
        except Exception as sync_exc:
            logger.warning(
                "registry_activate_rollout_sync_failed: model=%s err=%s",
                model_id, sync_exc,
            )

        return success({
            "model": _serialize(updated),
            "rollout_synced": rollout_synced,
            "forced": force,
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error(
            "activate_registry_model_error model_id=%s: %s",
            model_id, exc, exc_info=True,
        )
        return error("Erro interno", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/models/<model_id>/eval
# ---------------------------------------------------------------------------

@jwt_required()
def get_registry_model_eval(model_id: str):  # type: ignore[no-untyped-def]
    """Última avaliação campeão×desafiante do modelo (model_evaluations)."""
    try:
        model_uuid = _parse_uuid(model_id)
        if model_uuid is None:
            return error("ID de modelo inválido", 400)

        tenant_id = get_tenant_id()
        if _get_registry_repo().get_for_tenant(model_uuid, tenant_id) is None:
            return error("Modelo não encontrado", 404)

        evaluation = _get_eval_repo().get_latest_for_model(model_uuid, tenant_id)
        if evaluation is None:
            return error("Nenhuma avaliação para este modelo", 404)
        return success({"evaluation": _serialize(evaluation)})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error(
            "get_registry_model_eval_error model_id=%s: %s",
            model_id, exc, exc_info=True,
        )
        return error("Erro interno", 500)


# ---------------------------------------------------------------------------
# POST /api/v1/models/<model_id>/evaluate
# ---------------------------------------------------------------------------

@jwt_required()
@require_training_role("approve")
def evaluate_registry_model(model_id: str):  # type: ignore[no-untyped-def]
    """Dispara avaliação campeão×desafiante (WS-C1) sob demanda.

    Body (JSON, opcional): {"dataset_version_id": "<uuid>"} — sobrescreve
    a dataset_version de origem do modelo (útil pra reavaliar contra outro
    split sem re-treinar).

    Assíncrono (queue=training) — mesmo padrão de extract-frames/versions.
    """
    try:
        model_uuid = _parse_uuid(model_id)
        if model_uuid is None:
            return error("ID de modelo inválido", 400)

        tenant_id = get_tenant_id()
        if _get_registry_repo().get_for_tenant(model_uuid, tenant_id) is None:
            return error("Modelo não encontrado", 404)

        data = request.get_json(silent=True) or {}
        dataset_version_id = data.get("dataset_version_id")

        from app.infrastructure.queue.tasks.model_evaluation import (  # noqa: PLC0415
            evaluate_challenger_model,
        )
        task = evaluate_challenger_model.delay(str(model_uuid), dataset_version_id)

        return success(
            {"task_id": task.id, "status": "queued", "model_id": model_id},
            "Avaliação campeão×desafiante iniciada", 202,
        )
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error(
            "evaluate_registry_model_error model_id=%s: %s",
            model_id, exc, exc_info=True,
        )
        return error("Erro interno", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/models/<model_id>/drift
# ---------------------------------------------------------------------------

@jwt_required()
def get_registry_model_drift(model_id: str):  # type: ignore[no-untyped-def]
    """Janelas de drift do modelo (model_drift_metrics), mais recentes primeiro.

    Query param: limit (opcional, default 30, máx 365).
    """
    try:
        model_uuid = _parse_uuid(model_id)
        if model_uuid is None:
            return error("ID de modelo inválido", 400)

        raw_limit = request.args.get("limit", str(_DEFAULT_DRIFT_LIMIT))
        try:
            limit = max(1, min(int(raw_limit), _MAX_DRIFT_LIMIT))
        except (ValueError, TypeError):
            return error("Parâmetro 'limit' inválido", 400)

        tenant_id = get_tenant_id()
        if _get_registry_repo().get_for_tenant(model_uuid, tenant_id) is None:
            return error("Modelo não encontrado", 404)

        windows = _get_drift_repo().list_by_model(model_uuid, tenant_id, limit=limit)
        return success({
            "windows": [_serialize(w) for w in windows],
            "total": len(windows),
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error(
            "get_registry_model_drift_error model_id=%s: %s",
            model_id, exc, exc_info=True,
        )
        return error("Erro interno", 500)
