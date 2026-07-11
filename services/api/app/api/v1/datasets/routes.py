"""
Recognition — Datasets API (WS-A3).

Datasets pai tenant-scoped + build de versões COCO via Celery
(build_dataset_version_v2, queue versioning) + detalhe de versão com
presigned GET dos _annotations.coco.json por split.

Todas as rotas exigem JWT; mutações exigem @require_training_role('write')
(WS-D). Toda query filtra por tenant_id (C-01).
"""
import logging
from uuid import UUID

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.constants import ExportFormat
from app.core.auth import get_current_user_id, get_tenant_id, require_training_role
from app.core.responses import error, success
from app.domain.services.dataset_service import DatasetService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.dataset_repository import (
    DatasetRepository,
)

logger = logging.getLogger(__name__)

datasets_bp = Blueprint("datasets", __name__, url_prefix="/api/v1")


def _get_service() -> DatasetService:
    return DatasetService(DatasetRepository(DatabasePool.get_instance()))


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Datasets (container pai)
# ---------------------------------------------------------------------------

@datasets_bp.route("/datasets", methods=["GET"])
@jwt_required()
def list_datasets():
    """Lista datasets do tenant. Filtro opcional: ?module=epi."""
    tenant_id = str(get_tenant_id())
    module_code = request.args.get("module") or None
    service = _get_service()
    items = service.list_datasets(tenant_id, module_code)
    return success({"datasets": items, "total": len(items)})


@datasets_bp.route("/datasets", methods=["POST"])
@jwt_required()
@require_training_role("write")
def create_dataset():
    """Cria dataset pai. Body: {name, description?, module_code?}."""
    tenant_id = str(get_tenant_id())
    user_id = str(get_current_user_id())
    body = request.get_json(silent=True) or {}

    service = _get_service()
    try:
        dataset = service.create_dataset(
            tenant_id=tenant_id,
            name=body.get("name", ""),
            description=body.get("description"),
            module_code=body.get("module_code"),
            created_by=user_id,
        )
    except ValueError as exc:
        return error(str(exc), 400)

    logger.info("dataset_created: id=%s tenant=%s", dataset["id"], tenant_id)
    return success({"dataset": dataset}, "Dataset criado", 201)


@datasets_bp.route("/datasets/<dataset_id>", methods=["GET"])
@jwt_required()
def get_dataset(dataset_id: str):
    """Detalhe do dataset pai + suas versões (tenant-scoped)."""
    parsed = _parse_uuid(dataset_id)
    if parsed is None:
        return error("ID de dataset inválido", 400)

    tenant_id = str(get_tenant_id())
    service = _get_service()
    dataset = service.get_dataset(parsed, tenant_id)
    if dataset is None:
        return error("Dataset não encontrado", 404)

    versions = service.list_dataset_versions(parsed, tenant_id)
    return success({"dataset": dataset, "versions": versions})


# ---------------------------------------------------------------------------
# Build de versão (COCO v2)
# ---------------------------------------------------------------------------

@datasets_bp.route("/datasets/<dataset_id>/versions", methods=["POST"])
@jwt_required()
@require_training_role("write")
def create_dataset_version(dataset_id: str):
    """Dispara build assíncrono de uma versão COCO do dataset.

    Body: {name?, split?{train,val,test}, augmentations?, format?}.
    O build roda em Celery (queue versioning) — snapshot de frames rotulados
    do tenant, split por grupo de vídeo (sem leakage), export COCO por split,
    upload R2 e INSERT em dataset_versions (status building→ready|error).
    """
    parsed = _parse_uuid(dataset_id)
    if parsed is None:
        return error("ID de dataset inválido", 400)

    tenant_id = str(get_tenant_id())
    user_id = str(get_current_user_id())
    body = request.get_json(silent=True) or {}

    export_format = str(body.get("format") or ExportFormat.COCO.value).lower()
    if export_format != ExportFormat.COCO.value:
        return error(
            "Formato não suportado no build v2 — use 'coco' "
            "(export YOLO permanece na task legada)",
            400,
        )

    augmentations = body.get("augmentations")
    if augmentations is not None and not isinstance(augmentations, dict):
        return error("Campo 'augmentations' deve ser objeto", 400)

    service = _get_service()
    try:
        split = service.validate_split(body.get("split"))
    except ValueError as exc:
        return error(str(exc), 400)

    dataset = service.get_dataset(parsed, tenant_id)
    if dataset is None:
        return error("Dataset não encontrado", 404)

    name = (body.get("name") or "").strip()
    version = name or service.next_version_label(parsed, tenant_id)

    from app.infrastructure.queue.tasks.versioning_v2 import (
        build_dataset_version_v2,
    )

    task = build_dataset_version_v2.delay(
        tenant_id=tenant_id,
        dataset_id=str(parsed),
        user_id=user_id,
        version=version,
        split=split,
        augmentations=augmentations,
        export_format=export_format,
        module_code=dataset.get("module_code") or "epi",
    )

    logger.info(
        "dataset_version_build_dispatched: dataset=%s version=%s task=%s",
        parsed, version, task.id,
    )
    return success(
        {
            "task_id": task.id,
            "dataset_id": str(parsed),
            "version": version,
            "split": split,
            "format": export_format,
            "status": "building",
        },
        "Build da versão iniciado",
        202,
    )


# ---------------------------------------------------------------------------
# Detalhe de versão
# ---------------------------------------------------------------------------

@datasets_bp.route("/dataset-versions/<version_id>", methods=["GET"])
@jwt_required()
def get_dataset_version(version_id: str):
    """Detalhe de uma dataset_version + presigned GET dos COCO por split."""
    parsed = _parse_uuid(version_id)
    if parsed is None:
        return error("ID de versão inválido", 400)

    tenant_id = str(get_tenant_id())
    service = _get_service()
    detail = service.get_version_detail(parsed, tenant_id)
    if detail is None:
        return error("Versão de dataset não encontrada", 404)

    return success({"version": detail})
