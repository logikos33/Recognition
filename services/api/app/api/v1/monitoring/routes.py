"""
Blueprint /api/v1/monitoring — observabilidade da frota edge (superadmin).

GET  /sites                          visão de frota: sites + devices + divergência OTA
POST /sites/<site_id>/query          telemetria sob demanda via fila de comandos
POST /sites/<site_id>/snapshot       snapshot sob demanda (câmeras) via fila de comandos
POST /sites/<site_id>/logtail        tail de logs de uma unit do box (SEMPRE auditado)
GET  /commands/<command_id>          continuação de comando que ficou pending
GET  /sites/<site_id>/thresholds     limiares do painel (migration 116)
PUT  /sites/<site_id>/thresholds     upsert de limiares (auditado com old/new)
GET  /sites/<site_id>/detections     último 'detection' por câmera + lag de ingest

Segurança (C-01):
  - TODAS as rotas: @jwt_required_custom + @require_superadmin_or_404 —
    não-superadmin recebe 404 (NÃO 403): a existência da página /monitoring
    não é revelada a quem não é superadmin (mesmo espírito do gate de
    tenant_context_routes.py).
  - site_id malformado ou inexistente → 404 igual (não vaza formato/existência).

ADR-0020 (canal outbound): a nuvem NUNCA alcança o box diretamente. Todo
"pergunte ao device" vira um comando 'monitoring.*' em public.edge_commands
que o box consome por polling (em idle, a cada ~60s) e responde preenchendo
`result`. As rotas POST esperam a resposta por até MONITORING_WAIT_S
(query/logtail, default 10s) ou MONITORING_SNAPSHOT_WAIT_S (default 8s);
sem resposta a tempo → state 'pending' e o front continua via
GET /commands/<command_id>. A 1ª chamada ficar pending é o caso NORMAL.

Auditoria (public.audit_log, target_type='edge_monitoring'):
  - query/snapshot: deduplicada em memória por (user_id, site_id, action)
    com TTL de 15 min — leituras repetidas do mesmo painel não inundam o
    audit_log. Best-effort POR WORKER: cada processo gunicorn tem o próprio
    dict; após restart/entre workers pode auditar de novo — aceitável para
    ações de leitura.
  - logtail e thresholds_updated: SEMPRE auditadas (logtail lê log do box;
    thresholds muda configuração — nunca deduplicar).
"""
import logging
import os
import secrets
import time
from typing import Any
from uuid import UUID

from flask import Blueprint, request

from app.core.auth import get_role, jwt_required_custom
from app.core.responses import error, success
from app.core.tenant import log_audit
from app.core.tenant_context import require_superadmin_or_404
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.edge_command_repository import (
    EdgeCommandRepository,
)
from app.infrastructure.database.repositories.edge_monitoring_repository import (
    EdgeMonitoringRepository,
)
from app.infrastructure.database.repositories.edge_software_channel_repository import (
    EdgeSoftwareChannelRepository,
)

monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/api/v1/monitoring")
logger = logging.getLogger(__name__)

_VALID_WINDOWS = {"2h", "24h", "7d", "30d"}
_TERMINAL_STATES = {"done", "failed"}
_POLL_INTERVAL_S = 0.5
_MAX_THRESHOLD_KEYS = 64
_MAX_UNIT_LEN = 128
_LOGTAIL_MAX_LINES = 500
_MAX_WINDOW_MINUTES = 60 * 24 * 30  # 30 dias

# Dedup de auditoria em memória: {(user_id, site_id, action): time.monotonic()}.
# Best-effort POR WORKER (ver docstring do módulo) — não é garantia global.
_AUDIT_DEDUP_TTL_S = 900.0  # 15 min
_audit_dedup: dict[tuple[str, str, str], float] = {}


def _get_repo() -> EdgeMonitoringRepository:
    return EdgeMonitoringRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


def _get_command_repo() -> EdgeCommandRepository:
    return EdgeCommandRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


def _get_channel_repo() -> EdgeSoftwareChannelRepository:
    return EdgeSoftwareChannelRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


# --------------------------------------------------------------------------- helpers


def _load_site_or_none(site_id: str) -> dict[str, Any] | None:
    """Site por id, ou None. site_id malformado conta como inexistente (→404),
    em vez de estourar DataError no Postgres e virar 500."""
    try:
        UUID(site_id)
    except (ValueError, TypeError, AttributeError):
        return None
    return _get_repo().get_site_any_tenant(site_id)


def _wait_env(env_name: str, default: float) -> float:
    """Lê a espera do env a cada request (testes/ops podem ajustar sem restart)."""
    try:
        return max(float(os.environ.get(env_name, default)), 0.0)
    except ValueError:
        return default


def _wait_for_result(command_id: str, wait_s: float) -> dict[str, Any] | None:
    """Espera o device responder o comando por até wait_s, consultando o banco
    a cada 0.5s. time.sleep é gevent/eventlet-patched em produção — não trava
    o worker inteiro, só esta greenlet."""
    deadline = time.monotonic() + wait_s
    while True:
        row = _get_repo().get_monitoring_command(command_id)
        if row and row.get("status") in _TERMINAL_STATES:
            return row
        if time.monotonic() >= deadline:
            return row
        time.sleep(_POLL_INTERVAL_S)


def _audit(
    action: str,
    current_user_id: Any,
    site: dict[str, Any],
    *,
    old_value: Any = None,
    new_value: Any = None,
    dedup: bool = False,
) -> None:
    """log_audit com contexto da request; dedup=True aplica o TTL de 15 min."""
    if dedup:
        key = (str(current_user_id), str(site["id"]), action)
        now = time.monotonic()
        last = _audit_dedup.get(key)
        if last is not None and now - last < _AUDIT_DEDUP_TTL_S:
            return
        # Poda oportunista das entradas expiradas — dict não cresce sem teto.
        for stale_key in [k for k, ts in _audit_dedup.items() if now - ts >= _AUDIT_DEDUP_TTL_S]:
            _audit_dedup.pop(stale_key, None)
        _audit_dedup[key] = now
    log_audit(
        actor_id=current_user_id,
        actor_role=get_role(),
        tenant_id=str(site["tenant_id"]),
        target_type="edge_monitoring",
        target_id=str(site["id"]),
        action=action,
        old_value=old_value,
        new_value=new_value,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )


def _dispatch_and_wait(
    site: dict[str, Any],
    command_type: str,
    payload: dict[str, Any],
    command_id: str,
    current_user_id: Any,
    wait_s: float,
) -> tuple:
    """Enfileira o comando 'monitoring.*' no tenant do site e espera resposta."""
    _get_command_repo().create(
        tenant_id=str(site["tenant_id"]),
        site_id=str(site["id"]),
        command_type=command_type,
        payload=payload,
        command_id=command_id,
        created_by=str(current_user_id),
    )
    row = _wait_for_result(command_id, wait_s)
    if row and row.get("status") in _TERMINAL_STATES:
        return success({
            "state": row["status"],
            "result": row.get("result"),
            "command_id": command_id,
        })
    # Box em idle faz poll a cada ~60s — 1ª chamada pending é o caso normal;
    # o front continua via GET /commands/<command_id>.
    return success({"state": "pending", "command_id": command_id})


def _validate_thresholds(raw: Any) -> str | None:
    """Valida o objeto de limiares; retorna mensagem de erro ou None se ok."""
    if not isinstance(raw, dict):
        return "thresholds deve ser um objeto {chave: valor}"
    if len(raw) > _MAX_THRESHOLD_KEYS:
        return f"thresholds: máximo de {_MAX_THRESHOLD_KEYS} chaves"
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            return "thresholds: chaves devem ser strings não vazias"
        if not isinstance(value, bool | int | float):
            return f"thresholds[{key!r}]: valor deve ser numérico ou booleano"
    return None


# --------------------------------------------------------------------------- routes


@monitoring_bp.route("/sites", methods=["GET"])
@jwt_required_custom
@require_superadmin_or_404
def list_sites(current_user_id: str) -> tuple:
    """Visão de frota: sites de todos os tenants + devices + divergência OTA.

    Por device: target_ref do canal OTA (public.edge_software_channels) e
    `divergent` comparando o edge_version do último heartbeat com o target.
    Sem heartbeat/canal/target → divergent=None (honesto: sem dado não há
    veredito, nem "ok" nem "divergente").
    """
    try:
        sites = _get_repo().list_sites_overview()
        channel_repo = _get_channel_repo()
        target_cache: dict[str, str | None] = {}
        for site in sites:
            for device in site.get("devices", []):
                channel = device.get("channel")
                if channel and channel not in target_cache:
                    target_cache[channel] = channel_repo.get_target_ref(channel)
                target_ref = target_cache.get(channel) if channel else None
                edge_version = device.get("edge_version")
                device["target_ref"] = target_ref
                device["divergent"] = (
                    edge_version != target_ref if (edge_version and target_ref) else None
                )
        return success({"sites": sites, "count": len(sites)})
    except Exception:
        logger.exception("monitoring_list_sites_error")
        return error("Erro ao listar sites", 500)


@monitoring_bp.route("/sites/<site_id>/query", methods=["POST"])
@jwt_required_custom
@require_superadmin_or_404
def query_site(site_id: str, current_user_id: str) -> tuple:
    """Telemetria sob demanda: body {"window": "2h"|"24h"|"7d"|"30d",
    "layers": [...]?, "max_points": int?} → comando 'monitoring.query'."""
    try:
        site = _load_site_or_none(site_id)
        if site is None:
            return error("Site não encontrado", 404)

        body = request.get_json(silent=True) or {}
        window = body.get("window")
        if window not in _VALID_WINDOWS:
            return error(f"window deve ser um de: {sorted(_VALID_WINDOWS)}", 422)
        layers = body.get("layers")
        if layers is not None and (
            not isinstance(layers, list) or not all(isinstance(x, str) for x in layers)
        ):
            return error("layers deve ser uma lista de strings", 422)
        max_points = body.get("max_points")
        if max_points is not None and (
            isinstance(max_points, bool)
            or not isinstance(max_points, int)
            or not 1 <= max_points <= 10000
        ):
            return error("max_points deve ser inteiro entre 1 e 10000", 422)

        payload: dict[str, Any] = {"window": window}
        if layers is not None:
            payload["layers"] = layers
        if max_points is not None:
            payload["max_points"] = max_points

        _audit(
            "edge_monitoring.query", current_user_id, site,
            new_value={"window": window}, dedup=True,
        )
        return _dispatch_and_wait(
            site, "monitoring.query", payload,
            f"mon-q-{secrets.token_hex(8)}", current_user_id,
            _wait_env("MONITORING_WAIT_S", 10.0),
        )
    except Exception:
        logger.exception("monitoring_query_error")
        return error("Erro ao consultar telemetria do site", 500)


@monitoring_bp.route("/sites/<site_id>/snapshot", methods=["POST"])
@jwt_required_custom
@require_superadmin_or_404
def snapshot_site(site_id: str, current_user_id: str) -> tuple:
    """Snapshot sob demanda das câmeras do site → comando 'monitoring.snapshot'."""
    try:
        site = _load_site_or_none(site_id)
        if site is None:
            return error("Site não encontrado", 404)
        _audit("edge_monitoring.snapshot", current_user_id, site, dedup=True)
        return _dispatch_and_wait(
            site, "monitoring.snapshot", {},
            f"mon-s-{secrets.token_hex(8)}", current_user_id,
            _wait_env("MONITORING_SNAPSHOT_WAIT_S", 8.0),
        )
    except Exception:
        logger.exception("monitoring_snapshot_error")
        return error("Erro ao solicitar snapshot", 500)


@monitoring_bp.route("/sites/<site_id>/logtail", methods=["POST"])
@jwt_required_custom
@require_superadmin_or_404
def logtail_site(site_id: str, current_user_id: str) -> tuple:
    """Tail de logs de uma unit do box: body {"unit": str, "lines": int<=500}
    → comando 'monitoring.logtail'. SEMPRE auditado (lê log do device)."""
    try:
        site = _load_site_or_none(site_id)
        if site is None:
            return error("Site não encontrado", 404)

        body = request.get_json(silent=True) or {}
        unit = body.get("unit")
        if not isinstance(unit, str) or not unit.strip() or len(unit) > _MAX_UNIT_LEN:
            return error(f"unit é obrigatório (string não vazia, até {_MAX_UNIT_LEN} chars)", 422)
        lines = body.get("lines", 200)
        if (
            isinstance(lines, bool)
            or not isinstance(lines, int)
            or not 1 <= lines <= _LOGTAIL_MAX_LINES
        ):
            return error(f"lines deve ser inteiro entre 1 e {_LOGTAIL_MAX_LINES}", 422)

        unit = unit.strip()
        _audit(
            "edge_monitoring.logtail", current_user_id, site,
            new_value={"unit": unit, "lines": lines},
        )
        return _dispatch_and_wait(
            site, "monitoring.logtail", {"unit": unit, "lines": lines},
            f"mon-l-{secrets.token_hex(8)}", current_user_id,
            _wait_env("MONITORING_WAIT_S", 10.0),
        )
    except Exception:
        logger.exception("monitoring_logtail_error")
        return error("Erro ao solicitar logtail", 500)


@monitoring_bp.route("/commands/<command_id>", methods=["GET"])
@jwt_required_custom
@require_superadmin_or_404
def get_command(command_id: str, current_user_id: str) -> tuple:
    """Continuação de comando pending. Só enxerga command_type 'monitoring.%'
    (filtro no repo) — comando de qualquer outro tipo → 404."""
    try:
        row = _get_repo().get_monitoring_command(command_id)
        if row is None:
            return error("Comando não encontrado", 404)
        return success({
            "state": row["status"],
            "result": row.get("result"),
            "command_id": command_id,
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        })
    except Exception:
        logger.exception("monitoring_get_command_error")
        return error("Erro ao consultar comando", 500)


@monitoring_bp.route("/sites/<site_id>/thresholds", methods=["GET"])
@jwt_required_custom
@require_superadmin_or_404
def get_thresholds(site_id: str, current_user_id: str) -> tuple:
    """Limiares do painel para o site — {} se nunca configurado."""
    try:
        site = _load_site_or_none(site_id)
        if site is None:
            return error("Site não encontrado", 404)
        row = _get_repo().get_thresholds(str(site["id"]))
        return success({
            "thresholds": (row or {}).get("thresholds") or {},
            "updated_at": row.get("updated_at") if row else None,
            "updated_by": str(row["updated_by"]) if row and row.get("updated_by") else None,
        })
    except Exception:
        logger.exception("monitoring_get_thresholds_error")
        return error("Erro ao consultar limiares", 500)


@monitoring_bp.route("/sites/<site_id>/thresholds", methods=["PUT"])
@jwt_required_custom
@require_superadmin_or_404
def put_thresholds(site_id: str, current_user_id: str) -> tuple:
    """Upsert dos limiares do site. SEMPRE auditado com old/new."""
    try:
        site = _load_site_or_none(site_id)
        if site is None:
            return error("Site não encontrado", 404)

        body = request.get_json(silent=True) or {}
        thresholds = body.get("thresholds")
        validation_error = _validate_thresholds(thresholds)
        if validation_error is not None:
            return error(validation_error, 422)

        repo = _get_repo()
        old_row = repo.get_thresholds(str(site["id"]))
        old_thresholds = (old_row or {}).get("thresholds") or {}
        row = repo.upsert_thresholds(
            site_id=str(site["id"]),
            tenant_id=str(site["tenant_id"]),
            thresholds=thresholds,
            updated_by=str(current_user_id),
        )
        _audit(
            "edge_monitoring.thresholds_updated", current_user_id, site,
            old_value=old_thresholds, new_value=thresholds,
        )
        return success({
            "thresholds": (row or {}).get("thresholds") or thresholds,
            "updated_at": row.get("updated_at") if row else None,
        })
    except Exception:
        logger.exception("monitoring_put_thresholds_error")
        return error("Erro ao salvar limiares", 500)


@monitoring_bp.route("/sites/<site_id>/detections", methods=["GET"])
@jwt_required_custom
@require_superadmin_or_404
def site_detections(site_id: str, current_user_id: str) -> tuple:
    """Último evento 'detection' por câmera + lag de ingest na janela.

    Por câmera: ingest_lag_s = received_at - occurred_at do ÚLTIMO evento e
    "chain": {"detection_to_ingest_s": ..., "ingest_to_notification_s": null}.
    ingest_to_notification_s é null porque o módulo de notificação ainda não
    está ligado ao fluxo edge — quando estiver, o timestamp de envio entra na
    cadeia; até lá, null honesto em vez de zero fictício.
    """
    try:
        site = _load_site_or_none(site_id)
        if site is None:
            return error("Site não encontrado", 404)

        raw_window = request.args.get("window_minutes", "60")
        try:
            window_minutes = int(raw_window)
        except (TypeError, ValueError):
            return error("window_minutes deve ser inteiro", 422)
        if not 1 <= window_minutes <= _MAX_WINDOW_MINUTES:
            return error(f"window_minutes deve estar entre 1 e {_MAX_WINDOW_MINUTES}", 422)

        rows = _get_repo().last_detection_per_camera(str(site["id"]), window_minutes)
        cameras = []
        for row in rows:
            occurred = row.get("last_occurred_at")
            received = row.get("last_received_at")
            lag_s = (
                (received - occurred).total_seconds()
                if occurred is not None and received is not None
                else None
            )
            cameras.append({
                "camera_id": str(row["camera_id"]) if row.get("camera_id") else None,
                "last_occurred_at": occurred,
                "last_received_at": received,
                "detections_in_window": row.get("detections_in_window"),
                "ingest_lag_s": lag_s,
                "chain": {
                    "detection_to_ingest_s": lag_s,
                    "ingest_to_notification_s": None,
                },
            })
        return success({
            "cameras": cameras,
            "window_minutes": window_minutes,
            "count": len(cameras),
        })
    except Exception:
        logger.exception("monitoring_site_detections_error")
        return error("Erro ao consultar detecções", 500)
