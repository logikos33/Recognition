"""Blueprint /api/v1/edge/commands — fila de comandos remotos pro edge (migration 056).

POST  /api/v1/edge/commands                   JWT admin — cria comando
GET   /api/v1/edge/commands/pending           device auth — edge polling
PATCH /api/v1/edge/commands/<command_id>      device auth — atualiza status
GET   /api/v1/edge/commands                   JWT — lista comandos do site
"""
import logging

from flask import Blueprint, g, request

from app.core.auth import get_role, get_tenant_id, jwt_required_custom
from app.core.device_auth import require_device_scope
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.edge_command_repository import (
    EdgeCommandRepository,
)

edge_commands_bp = Blueprint("edge_commands", __name__, url_prefix="/api/v1/edge/commands")
logger = logging.getLogger(__name__)

_VALID_STATUSES = {"done", "failed", "expired"}
_ADMIN_ROLES = {"admin", "superadmin"}

# Bloco A: motivo bruto que o edge manda no ack (snapshot_executor.py) ->
# texto legível pra UI de triagem. Chaves não mapeadas passam como estão
# (melhor um motivo em inglês/técnico do que nenhum).
_SNAPSHOT_FAILURE_MESSAGES = {
    "auth": "Falha de autenticação no gravador — capturas suspensas",
    "timeout": "Timeout ao capturar imagem do canal",
    "sem sinal no canal": "Canal sem sinal",
    "upload_failed": "Falha ao enviar a imagem capturada",
    "unsupported": "Captura de snapshot não suportada neste dispositivo",
    "invalid_payload": "Comando de captura inválido",
    "capture_failed": "Falha ao capturar imagem do canal",
    # Draft fora do channel_map E comando sem canal utilizável (Bloco A,
    # achado em campo na RVB — canal 9): motivo específico, distinto de
    # "sem sinal" — o canal nem chegou a ser contatado.
    "no_channel": "Sem canal disponível para a captura — câmera fora do mapa e comando sem canal",
}


def _get_repo() -> EdgeCommandRepository:
    return EdgeCommandRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


def _bridge_snapshot_failure(tenant_id: str, row: dict, status: str, result: dict | None) -> None:
    """Espelha a falha de um comando `capture_snapshot` no cache Redis que
    GET /api/cameras/<id>/snapshot lê (camera_snapshot_state.py) — sem isso
    a UI de triagem ficaria presa em "pending" para sempre depois de uma
    falha (o sucesso já é escrito por app.api.v1.edge.routes.upload_camera_snapshot,
    que tem os bytes; a falha não passa por lá — nada é enviado).

    Best-effort, mesmo padrão de `_bridge_heartbeat_to_telemetry` em
    app.api.v1.edge.routes: NUNCA falha o ack por causa disso.
    """
    if row.get("command_type") != "capture_snapshot" or status != "failed":
        return
    camera_id = (row.get("payload") or {}).get("camera_id")
    if not camera_id:
        return
    try:
        from app.api.v1.cameras.helpers import _get_redis  # noqa: PLC0415
        from app.domain.services import camera_snapshot_state as snap_state  # noqa: PLC0415

        raw_reason = (result or {}).get("reason") or "capture_failed"
        reason = _SNAPSHOT_FAILURE_MESSAGES.get(raw_reason, raw_reason)
        snap_state.write_failed(_get_redis(), str(tenant_id), str(camera_id), reason)
    except Exception:
        logger.warning(
            "snapshot_failure_bridge_failed camera=%s", camera_id, exc_info=True
        )


def _fail_propagation_job_on_command_failure(
    row: dict, status: str, result: "dict | None"
) -> None:
    """Ack 'failed' de um comando run_propagation derruba o JOB de
    propagação imediatamente — sem isto o job ficaria 'running' até o
    timeout do reconciler (horas), com a UI mentindo o estado (bug real:
    box com release antiga ackou {'reason': 'unsupported'} e o job
    pendurou em edge_dispatched). Best-effort: falha aqui não pode
    derrubar o ack do device — o comando já foi atualizado."""
    if status != "failed" or (row or {}).get("command_type") != "run_propagation":
        return
    job_id = ((row or {}).get("payload") or {}).get("job_id")
    if not job_id:
        return
    try:
        from app.infrastructure.database.repositories.propagation_repository import (  # noqa: PLC0415
            PropagationRepository,
        )

        reason = str((result or {}).get("reason") or "comando edge falhou no box")
        PropagationRepository(DatabasePool.get_instance()).apply_callback_failed(
            str(job_id), f"edge: {reason}"
        )
    except Exception:
        logger.exception("fail_propagation_job_on_command_ack_error job=%s", job_id)


@edge_commands_bp.route("", methods=["POST"])
@jwt_required_custom
def create_command(current_user_id: str) -> tuple:
    """Cria comando remoto para o edge (admin only)."""
    try:
        if get_role() not in _ADMIN_ROLES:
            return error("Acesso restrito a admins", 403)
        tenant_id = get_tenant_id()
        body = request.get_json(silent=True) or {}
        site_id = body.get("site_id")
        command_type = body.get("command_type")
        if not site_id or not command_type:
            return error("site_id e command_type são obrigatórios", 422)
        import secrets
        command_id = body.get("command_id") or secrets.token_hex(16)
        row = _get_repo().create(
            tenant_id=tenant_id,
            site_id=site_id,
            command_type=command_type,
            payload=body.get("payload") or {},
            command_id=command_id,
            created_by=current_user_id,
        )
        if row is None:
            return success({"command_id": command_id, "created": False, "reason": "duplicate"})
        return success({"command": row, "command_id": command_id, "created": True}, status=201)
    except Exception:
        logger.exception("create_command_error")
        return error("Erro ao criar comando", 500)


@edge_commands_bp.route("/pending", methods=["GET"])
@require_device_scope("commands:read")  # DeviceTokenScope.commands_read
def poll_pending_commands() -> tuple:
    """Edge polling: lista comandos pendentes (device auth + escopo commands:read)."""
    _, site_id, _ = g.device_ctx
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        rows = _get_repo().list_pending(site_id=site_id, limit=limit)
        return success({"commands": rows, "count": len(rows)})
    except Exception:
        logger.exception("poll_pending_commands_error")
        return error("Erro ao consultar comandos", 500)


@edge_commands_bp.route("/<command_id>", methods=["PATCH"])
@require_device_scope("commands:write")  # DeviceTokenScope.commands_write
def update_command_status(command_id: str) -> tuple:
    """Edge atualiza status de comando após execução (device auth + commands:write)."""
    tenant_id, _, _ = g.device_ctx
    try:
        body = request.get_json(silent=True) or {}
        status = body.get("status")
        if status not in _VALID_STATUSES:
            return error(f"status deve ser um de: {sorted(_VALID_STATUSES)}", 422)
        row = _get_repo().update_status(
            command_id_str=command_id,
            tenant_id=tenant_id,
            status=status,
            result=body.get("result"),
        )
        if not row:
            return error("Comando não encontrado", 404)
        _bridge_snapshot_failure(tenant_id, row, status, body.get("result"))
        _fail_propagation_job_on_command_failure(row, status, body.get("result"))
        return success({"command": row})
    except Exception:
        logger.exception("update_command_status_error")
        return error("Erro ao atualizar comando", 500)


@edge_commands_bp.route("", methods=["GET"])
@jwt_required_custom
def list_commands(current_user_id: str) -> tuple:
    """Lista comandos de um site (admin view)."""
    try:
        # S5: consola de comandos é admin-only (antes: qualquer usuário do tenant)
        if get_role() not in _ADMIN_ROLES:
            return error("Acesso restrito a admins", 403)
        tenant_id = get_tenant_id()
        site_id = request.args.get("site_id")
        if not site_id:
            return error("site_id é obrigatório", 422)
        status = request.args.get("status")
        limit = min(int(request.args.get("limit", 50)), 200)
        rows = _get_repo().list_by_site(
            tenant_id=tenant_id,
            site_id=site_id,
            status=status or None,
            limit=limit,
        )
        return success({"commands": rows, "count": len(rows)})
    except Exception:
        logger.exception("list_commands_error")
        return error("Erro ao listar comandos", 500)
