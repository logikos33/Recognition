"""
Recognition — Camera snapshot handlers (Bloco A: miniatura de triagem).

GET  /api/cameras/<camera_id>/snapshot          — estado do último snapshot
POST /api/cameras/<camera_id>/snapshot/refresh  — despacha nova captura

Por que snapshot, não HLS: CameraTriagePage precisa exibir uma imagem de
cada uma das 29 câmeras do gravador SEM tocar o channel_map/pipeline HLS —
ativar uma câmera draft (is_active=false) temporariamente pra preview é o
comportamento PROIBIDO que este módulo substitui. O gravador expõe ONVIF
GetSnapshotUri (D-85): um GET simples, sem HLS. O edge-sync-agent
(OnvifRecorderClient.get_snapshot / RtspTimestampRecorderClient.get_snapshot)
captura e sobe multipart pra POST /api/v1/edge/cameras/<id>/snapshot (device
auth, app.api.v1.edge.routes.upload_camera_snapshot), que grava no R2 e
atualiza o cache lido aqui.

Cache (Redis, sem migration — camera_snapshot_state.py): metadados do
último resultado, bytes vivem no R2. Fresco (< SNAPSHOT_FRESH_MINUTES, env,
default 10) -> POST /refresh é NO-OP: nunca bate no gravador a cada
re-render da tela de triagem.

Idempotência do refresh: antes de enfileirar um novo edge_command, checa se
já existe um `capture_snapshot` PENDENTE pra essa câmera (via
EdgeCommandRepository.list_by_site, sem tabela/coluna nova) — evita acumular
comandos duplicados quando a página re-renderiza com as 29 câmeras.
"""
import logging
import os
import time
from uuid import UUID

from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError, StorageError
from app.core.responses import error, success
from app.domain.services import camera_snapshot_state as snap_state

from .helpers import _get_camera_repo, _get_redis

logger = logging.getLogger(__name__)

_DEFAULT_FRESH_MINUTES = 10
_DEFAULT_URL_TTL_S = 900  # 15 min — folga sobre o tempo de exibição na triagem


def _fresh_minutes() -> int:
    try:
        return int(os.environ.get("SNAPSHOT_FRESH_MINUTES", str(_DEFAULT_FRESH_MINUTES)))
    except ValueError:
        return _DEFAULT_FRESH_MINUTES


def _get_edge_command_repo():  # type: ignore[no-untyped-def]
    """Factory isolada para facilitar mock em testes (mesmo padrão de
    config_handler.py)."""
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    from app.infrastructure.database.repositories.edge_command_repository import (  # noqa: PLC0415
        EdgeCommandRepository,
    )
    return EdgeCommandRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


def _lookup_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """Resolve camera_id (UUID) escopado ao tenant do JWT. Retorna
    (camera, error_response) — quando error_response não é None, o caller
    deve retorná-lo imediatamente (C-01: cross-tenant/UUID inválido -> 404/422,
    nunca 403 — não vaza existência)."""
    tenant_id = get_tenant_id()
    try:
        camera_uuid = UUID(camera_id)
    except ValueError:
        return None, error("camera_id deve ser UUID", 422)
    camera = _get_camera_repo().get_by_id_and_tenant(str(camera_uuid), tenant_id)
    if camera is None:
        return None, error("Câmera não encontrada", 404)
    return camera, None


def _has_pending_capture(tenant_id, site_id, camera_id: str) -> bool:  # type: ignore[no-untyped-def]
    """True se já existe um edge_command capture_snapshot pendente pra essa
    câmera — evita enfileirar duplicado (sem tabela/coluna nova, reusa a
    fila de edge_commands já existente como fonte de verdade)."""
    try:
        pending = _get_edge_command_repo().list_by_site(
            tenant_id=str(tenant_id), site_id=str(site_id), status="pending", limit=200,
        )
    except Exception:
        logger.warning("snapshot_pending_check_error camera=%s", camera_id, exc_info=True)
        return False
    return any(
        cmd.get("command_type") == "capture_snapshot"
        and (cmd.get("payload") or {}).get("camera_id") == str(camera_id)
        for cmd in pending
    )


@jwt_required()
def get_camera_snapshot(camera_id: str):  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Estado do último snapshot da câmera (triagem — Bloco A)
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: camera_id, type: string, required: true}
    responses:
      200: {description: "{status: none|pending|ready|failed, url?, captured_at?, error_reason?}"}
      404: {description: Câmera não encontrada}
    """
    try:
        camera, err = _lookup_camera(camera_id)
        if err is not None:
            return err
        tenant_id = get_tenant_id()

        state = snap_state.read_state(_get_redis(), str(tenant_id), camera_id)
        if state is None:
            return success({"status": "none", "url": None, "captured_at": None, "error_reason": None})

        payload = {
            "status": state.get("status", "none"),
            "captured_at": state.get("captured_at"),
            "error_reason": state.get("error_reason"),
            "url": None,
        }
        if state.get("status") in ("ready", "pending") and state.get("r2_key"):
            try:
                from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

                storage = get_storage(str(tenant_id))
                payload["url"] = storage.generate_presigned_download_url(
                    state["r2_key"], ttl=_DEFAULT_URL_TTL_S,
                )
            except StorageError:
                logger.warning("snapshot_presign_failed camera=%s", camera_id, exc_info=True)
                payload["status"] = "failed"
                payload["error_reason"] = "Falha ao gerar link de acesso à imagem"
        return success(payload)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_camera_snapshot_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def refresh_camera_snapshot(camera_id: str):  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Dispara nova captura de snapshot (edge_command capture_snapshot)
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: camera_id, type: string, required: true}
    responses:
      200: {description: Cache ainda fresco — nenhuma captura despachada (no-op)}
      202: {description: Captura despachada (ou já em andamento)}
      404: {description: Câmera não encontrada}
      422: {description: Câmera sem site edge associado — sem como despachar}
    """
    try:
        camera, err = _lookup_camera(camera_id)
        if err is not None:
            return err
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()

        site_id = camera.get("site_id")
        if not site_id:
            return error(
                "Câmera sem site edge associado — sem como despachar a captura", 422,
            )

        redis_client = _get_redis()
        state = snap_state.read_state(redis_client, str(tenant_id), camera_id)
        if snap_state.is_fresh(state, _fresh_minutes()):
            return success(
                {
                    "status": "ready", "queued": False, "reason": "fresh",
                    "captured_at": state.get("captured_at") if state else None,
                },
                status=200,
            )

        if _has_pending_capture(tenant_id, site_id, camera_id):
            return success(
                {"status": "pending", "queued": False, "reason": "already_pending"}, status=202,
            )

        command_id = f"snap:{camera_id}:{int(time.time() * 1000)}"
        try:
            _get_edge_command_repo().create(
                tenant_id=str(tenant_id),
                site_id=str(site_id),
                command_type="capture_snapshot",
                payload={"camera_id": str(camera_id), "channel": camera.get("channel")},
                command_id=command_id,
                created_by=str(user_id),
            )
        except Exception:
            logger.exception("snapshot_refresh_dispatch_error camera=%s", camera_id)
            return error("Erro ao despachar captura de snapshot", 500)

        # Marca "pending" no cache AGORA — sem isso, GET continuaria
        # reportando o resultado da captura ANTERIOR (ready/failed/none) até
        # o edge acabar de responder, e o polling do frontend pararia cedo
        # demais achando que um resultado velho já era a resposta nova.
        # Best-effort: se o Redis falhar aqui, o comando já foi enfileirado
        # (não desfazemos) — GET só fica "atrasado" pra refletir o pending.
        try:
            snap_state.write_pending(redis_client, str(tenant_id), camera_id)
        except Exception:
            logger.warning(
                "snapshot_pending_cache_write_failed camera=%s", camera_id, exc_info=True,
            )

        return success({"status": "pending", "queued": True}, status=202)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("refresh_camera_snapshot_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
