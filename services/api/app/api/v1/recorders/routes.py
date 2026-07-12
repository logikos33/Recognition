"""
Recognition — Recorders API (WS-B1, ADR-0034).

CRUD de gravadores NVR/DVR + teste de conexão + timeline de gravações +
disparo de extração de frames (Celery, queue=extraction).

Todas as rotas exigem JWT; mutações exigem @require_training_role('write')
(mesmo gate da pipeline de treino — recorder é fonte de dado de treino).
Toda query filtra por tenant_id (C-01).
"""
import logging
from datetime import datetime
from uuid import UUID

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_tenant_id, require_training_role
from app.core.responses import error, success
from app.domain.services.recorder_service import RecorderService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.recorder_repository import (
    RecorderRepository,
)

logger = logging.getLogger(__name__)

recorders_bp = Blueprint("recorders", __name__, url_prefix="/api/v1/recorders")


def _get_service() -> RecorderService:
    return RecorderService(RecorderRepository(DatabasePool.get_instance()))


def _parse_uuid(value: str) -> "UUID | None":
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


@recorders_bp.route("", methods=["GET"], strict_slashes=False)
@jwt_required()
def list_recorders():
    tenant_id = str(get_tenant_id())
    items = _get_service().list_recorders(tenant_id)
    return success({"recorders": items, "total": len(items)})


@recorders_bp.route("", methods=["POST"], strict_slashes=False)
@jwt_required()
@require_training_role("write")
def create_recorder():
    """ValidationError (400) propaga pro handler global @app.errorhandler
    (EpiMonitorError) — mesmo padrão de annotation_handlers.py."""
    tenant_id = str(get_tenant_id())
    user_id = get_current_user_id()
    data = request.get_json(silent=True) or {}
    recorder = _get_service().create_recorder(tenant_id, user_id, data)
    return success({"recorder": recorder}, "Gravador criado", 201)


@recorders_bp.route("/<recorder_id>", methods=["GET"])
@jwt_required()
def get_recorder(recorder_id: str):
    parsed = _parse_uuid(recorder_id)
    if parsed is None:
        return error("ID de gravador inválido", 400)
    tenant_id = str(get_tenant_id())
    recorder = _get_service().get_recorder(parsed, tenant_id)
    if recorder is None:
        return error("Gravador não encontrado", 404)
    return success({"recorder": recorder})


@recorders_bp.route("/<recorder_id>", methods=["PUT"])
@jwt_required()
@require_training_role("write")
def update_recorder(recorder_id: str):
    parsed = _parse_uuid(recorder_id)
    if parsed is None:
        return error("ID de gravador inválido", 400)
    tenant_id = str(get_tenant_id())
    data = request.get_json(silent=True) or {}
    recorder = _get_service().update_recorder(parsed, tenant_id, data)
    return success({"recorder": recorder}, "Gravador atualizado")


@recorders_bp.route("/<recorder_id>", methods=["DELETE"])
@jwt_required()
@require_training_role("write")
def delete_recorder(recorder_id: str):
    parsed = _parse_uuid(recorder_id)
    if parsed is None:
        return error("ID de gravador inválido", 400)
    tenant_id = str(get_tenant_id())
    _get_service().delete_recorder(parsed, tenant_id)
    return success({"deleted": True, "id": recorder_id}, "Gravador removido")


@recorders_bp.route("/<recorder_id>/test", methods=["POST"])
@jwt_required()
@require_training_role("write")
def test_recorder_connection(recorder_id: str):
    parsed = _parse_uuid(recorder_id)
    if parsed is None:
        return error("ID de gravador inválido", 400)
    tenant_id = str(get_tenant_id())
    result = _get_service().test_connection(parsed, tenant_id)
    return success({"recorder": result})


@recorders_bp.route("/<recorder_id>/recordings", methods=["GET"])
@jwt_required()
def get_recordings(recorder_id: str):
    """Timeline de gravações (ADR-0034): busca segmentos existentes no
    intervalo pedido. Query params: channel (int, default 1), from/to
    (ISO 8601)."""
    parsed = _parse_uuid(recorder_id)
    if parsed is None:
        return error("ID de gravador inválido", 400)
    tenant_id = str(get_tenant_id())

    channel = request.args.get("channel", 1, type=int)
    from_str = request.args.get("from")
    to_str = request.args.get("to")
    if not from_str or not to_str:
        return error("Parâmetros 'from' e 'to' (ISO 8601) são obrigatórios", 400)
    try:
        start = datetime.fromisoformat(from_str.replace("Z", "+00:00")).replace(tzinfo=None)
        end = datetime.fromisoformat(to_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return error("'from'/'to' devem ser timestamps ISO 8601 válidos", 400)
    if start >= end:
        return error("'from' deve ser anterior a 'to'", 400)

    service = _get_service()
    recorder = service.get_recorder_or_raise(parsed, tenant_id)

    from app.infrastructure.nvr.factory import get_nvr_client  # noqa: PLC0415

    try:
        password = service.decrypt_password(recorder.get("password_encrypted"))
        client = get_nvr_client(recorder, password)
        segments = client.search_recordings(channel, start, end)
    except Exception as exc:
        logger.error(
            "recorder_recordings_search_failed: id=%s err=%s", recorder_id, exc, exc_info=True,
        )
        return error("Falha ao buscar timeline de gravações", 502)

    return success({
        "recorder_id": recorder_id,
        "channel": channel,
        "segments": [
            {"channel": s.channel, "start": s.start.isoformat(), "end": s.end.isoformat()}
            for s in segments
        ],
    })


@recorders_bp.route("/<recorder_id>/extract-frames", methods=["POST"])
@jwt_required()
@require_training_role("write")
def extract_frames(recorder_id: str):
    """Dispara extração de frames (Celery, WS-B1). Body: {channel, from, to,
    interval_seconds?, module_code?}."""
    parsed = _parse_uuid(recorder_id)
    if parsed is None:
        return error("ID de gravador inválido", 400)
    tenant_id = str(get_tenant_id())

    data = request.get_json(silent=True) or {}
    channel = data.get("channel", 1)
    from_str = data.get("from")
    to_str = data.get("to")
    if not from_str or not to_str:
        return error("Campos 'from' e 'to' (ISO 8601) são obrigatórios", 400)
    try:
        datetime.fromisoformat(str(from_str).replace("Z", "+00:00"))
        datetime.fromisoformat(str(to_str).replace("Z", "+00:00"))
    except ValueError:
        return error("'from'/'to' devem ser timestamps ISO 8601 válidos", 400)

    interval_seconds = int(data.get("interval_seconds", 5))
    module_code = data.get("module_code", "epi")

    _get_service().get_recorder_or_raise(parsed, tenant_id)  # 404 se não existir/outro tenant

    from app.infrastructure.queue.tasks.nvr_extraction import (  # noqa: PLC0415
        extract_nvr_frames,
    )

    task = extract_nvr_frames.delay(
        str(parsed), tenant_id, channel, str(from_str), str(to_str),
        interval_seconds, module_code,
    )
    return success(
        {"task_id": task.id, "recorder_id": recorder_id, "status": "queued"},
        "Extração de frames iniciada", 202,
    )
