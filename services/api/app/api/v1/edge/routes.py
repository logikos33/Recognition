"""Blueprint /api/v1/edge/ — endpoints do edge-sync-agent."""
import hashlib
import io
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import psycopg2.errors
from flask import Blueprint, g, jsonify, make_response, request
from pydantic import ValidationError
from recognition_shared.device import EnrollmentRequest
from recognition_shared.enums import DeviceTokenScope
from recognition_shared.heartbeat import Heartbeat

from app.constants import FrameSource, R2Prefix
from app.core.auth import get_role, get_tenant_id, jwt_required_custom
from app.core.device_auth import (
    extract_device_id_unverified,
    require_device_scope,
    verify_device_token,
)
from app.core.edge_offline import (
    OFFLINE_THRESHOLD_SECONDS,
    derive_site_health_status,
    is_site_offline,
)
from app.core.exceptions import AuthenticationError
from app.core.responses import error, success
from app.core.tenant import has_permission
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.edge_heartbeat_repository import (
    EdgeHeartbeatRepository,
)
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.edge_site_repository import (
    _DEVICE_ALREADY_ENROLLED,
    EdgeSiteRepository,
)
from app.infrastructure.database.repositories.edge_software_channel_repository import (
    EdgeSoftwareChannelRepository,
)
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.database.repositories.recorder_repository import RecorderRepository

edge_bp = Blueprint("edge", __name__, url_prefix="/api/v1/edge")
logger = logging.getLogger(__name__)

_VALID_DEPLOYMENT_MODES = {"cloud", "edge", "hybrid"}
_VALID_SITE_STATUSES = {"active", "inactive", "maintenance", "provisioning"}
# WS7: gate por permissão — default_roles de edge:manage == {admin, superadmin}
# (idêntico ao _ADMIN_ROLES inline anterior; paridade coberta por teste)
_MANAGE_PERMISSION = "edge:manage"

_DEFAULT_WINDOW_SECONDS = 24 * 3600   # 24 h
_MAX_WINDOW_SECONDS = 7 * 24 * 3600   # 7 d

# Shadow mode on-site (Onda 2): frame capturado pelo edge (NVR fora do
# alcance direto da nuvem, ADR-0020) — mesmo formato que nvr_extraction.py
# produz, só troca quem inicia o upload.
_ALLOWED_FRAME_EXTS = frozenset({"jpg", "jpeg"})
_MAX_FRAME_BYTES = 10 * 1024 * 1024  # 10 MB — mesmo teto de image_handlers.py


def _get_repo() -> EdgeHeartbeatRepository:
    pool = DatabasePool.get_instance()
    return EdgeHeartbeatRepository(pool)  # type: ignore[arg-type]


def _get_software_channel_repo() -> EdgeSoftwareChannelRepository:
    pool = DatabasePool.get_instance()
    return EdgeSoftwareChannelRepository(pool)  # type: ignore[arg-type]


# Campos de telemetria do Heartbeat espelhados no dashboard integrado (Pilha B).
_TELEMETRY_FIELDS = (
    "cpu_pct", "mem_pct", "gpu_pct", "gpu_mem_pct", "disk_pct",
    "inference_fps", "inference_latency_ms", "cameras_online", "cameras_total",
    "queue_depth", "upload_kbps", "download_kbps", "gpu_temp_c", "cpu_temp_c",
    "decode_fps", "decode_pct", "dropped_frames",
)


def _heartbeat_to_telemetry_payload(hb: Heartbeat) -> dict:
    """Extrai os campos de telemetria do Heartbeat como dict JSON-safe.

    Decimals viram float (json.dumps não serializa Decimal); enums viram str.
    """
    payload: dict = {}
    for field in _TELEMETRY_FIELDS:
        value = getattr(hb, field, None)
        if value is not None:
            payload[field] = float(value) if not isinstance(value, int) else value
    payload["status"] = hb.status.value
    if hb.edge_version:
        payload["edge_version"] = hb.edge_version
    return payload


def _bridge_heartbeat_to_telemetry(
    tenant_id: str, site_id: str, hb: Heartbeat, sampled_at: str
) -> None:
    """Alimenta a Pilha B (dashboard integrado ao vivo) a partir do heartbeat real.

    Best-effort e late-import: um erro aqui NUNCA derruba a ingestão do heartbeat
    (Pilha A é a fonte da verdade). Reusa DashboardEdgeService.ingest_edge_telemetry
    (insere em edge_telemetry_samples + publica em edge_telemetry:{tenant_id} → /monitor).
    """
    try:
        from app.domain.services.dashboard_edge_service import DashboardEdgeService
        from app.infrastructure.database.repositories.edge_telemetry_repository import (
            EdgeTelemetryRepository,
        )
        from app.infrastructure.database.repositories.model_training_metrics_repository import (
            ModelTrainingMetricsRepository,
        )

        pool = DatabasePool.get_instance()
        service = DashboardEdgeService(
            ModelTrainingMetricsRepository(pool), EdgeTelemetryRepository(pool)
        )
        sample = {
            "sampled_at": sampled_at,
            "label": hb.status.value,
            "payload": _heartbeat_to_telemetry_payload(hb),
        }
        service.ingest_edge_telemetry(tenant_id, site_id, [sample])
    except Exception as exc:  # noqa: BLE001 — bridge best-effort, nunca falha o heartbeat
        logger.warning("heartbeat_telemetry_bridge_failed: %s", exc)


def _get_site_repo() -> EdgeSiteRepository:
    pool = DatabasePool.get_instance()
    return EdgeSiteRepository(pool)  # type: ignore[arg-type]


def _get_camera_repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    return CameraRepository(pool)  # type: ignore[arg-type]


def _get_recorder_repo() -> RecorderRepository:
    pool = DatabasePool.get_instance()
    return RecorderRepository(pool)  # type: ignore[arg-type]


def _get_frame_repo() -> FrameRepository:
    pool = DatabasePool.get_instance()
    return FrameRepository(pool)  # type: ignore[arg-type]


def _image_dimensions(data: bytes) -> "tuple[int, int] | None":
    """Extrai (width, height) via PIL. None se bytes não formam imagem válida.
    Mesmo padrão de training/image_handlers.py — import local, PIL só é
    necessário aqui."""
    try:
        from PIL import Image  # noqa: PLC0415

        with Image.open(io.BytesIO(data)) as img:
            return int(img.size[0]), int(img.size[1])
    except Exception:
        return None


def _serialize_site(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "name": row["name"],
        "description": row.get("description"),
        "location": row.get("location"),
        "deployment_mode": row["deployment_mode"],
        "status": row["status"],
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
        "created_by": str(row["created_by"]) if row.get("created_by") else None,
    }


def _serialize_heartbeat_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "received_at": str(row["received_at"]) if row.get("received_at") else None,
        "status": row.get("status"),
        "inference_fps": float(row["inference_fps"]) if row.get("inference_fps") is not None else None,
        "cameras_online": row.get("cameras_online"),
        "cameras_total": row.get("cameras_total"),
        "cpu_pct": float(row["cpu_pct"]) if row.get("cpu_pct") is not None else None,
        "gpu_pct": float(row["gpu_pct"]) if row.get("gpu_pct") is not None else None,
        "queue_depth": row.get("queue_depth"),
        "gpu_temp_c": float(row["gpu_temp_c"]) if row.get("gpu_temp_c") is not None else None,
        "decode_pct": float(row["decode_pct"]) if row.get("decode_pct") is not None else None,
        "edge_version": row.get("edge_version"),
        "cpu_temp_c": float(row["cpu_temp_c"]) if row.get("cpu_temp_c") is not None else None,
        "decode_fps": float(row["decode_fps"]) if row.get("decode_fps") is not None else None,
        "dropped_frames": row.get("dropped_frames"),
    }


def _parse_window_seconds(window: str | None) -> int:
    """Parse '24h' / '7d' / '30m' → seconds; clamp 1..._MAX_WINDOW_SECONDS."""
    if not window:
        return _DEFAULT_WINDOW_SECONDS
    w = window.strip().lower()
    try:
        if w.endswith("d"):
            secs = int(w[:-1]) * 86400
        elif w.endswith("h"):
            secs = int(w[:-1]) * 3600
        elif w.endswith("m"):
            secs = int(w[:-1]) * 60
        else:
            secs = int(w)
    except (ValueError, IndexError):
        secs = _DEFAULT_WINDOW_SECONDS
    return min(max(secs, 1), _MAX_WINDOW_SECONDS)


def _derive_token_status(token: dict) -> str:
    """Deriva status de um enrollment token: active | used | expired."""
    if token.get("used_at") is not None:
        return "used"
    expires_at = token.get("expires_at")
    if expires_at is None:
        return "expired"
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return "expired"
    return "active"


# ---------------------------------------------------------------------------
# Device heartbeat ingest (RS256 device auth — no JWT)
# ---------------------------------------------------------------------------

@edge_bp.route("/heartbeat", methods=["POST"])
def ingest_heartbeat() -> tuple:
    """Recebe telemetria periódica do edge-sync-agent (RS256 device auth)."""
    # 1. Extract bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return error("Authorization header ausente ou inválido", 401)
    token = auth_header.removeprefix("Bearer ")

    # 2. Extract device_id without verifying (for DB lookup only)
    try:
        device_id = extract_device_id_unverified(token)
    except AuthenticationError as exc:
        logger.warning("edge_heartbeat: token decode failed")
        return error(str(exc), 401)

    # 3. Lookup device + public key
    repo = _get_repo()
    device = repo.get_device_by_device_id(device_id)
    if device is None:
        logger.warning("edge_heartbeat: unknown device_id")
        return error("Dispositivo não encontrado", 401)

    # 4. Check revoked before touching the signature
    if device.get("revoked"):
        logger.warning("edge_heartbeat: revoked device")
        return error("Dispositivo revogado", 403)

    # 5. Verify RS256 signature + expiry
    try:
        claims = verify_device_token(token, device["public_key_pem"])
    except AuthenticationError as exc:
        logger.warning("edge_heartbeat: token verification failed")
        return error(str(exc), 401)

    # 6. Defense-in-depth: claims tenant/site must match enrollment record
    enrollment_tenant = UUID(str(device["tenant_id"]))
    enrollment_site = UUID(str(device["site_id"]))
    if claims.tenant_id != enrollment_tenant or claims.site_id != enrollment_site:
        logger.warning(
            "edge_heartbeat: claims divergem do enrollment device=%s "
            "claims_tenant=%s enrollment_tenant=%s",
            device_id,
            str(claims.tenant_id)[:8],
            str(enrollment_tenant)[:8],
        )
        return error("Token adulterado: claims divergem do enrollment", 403)

    # 6b. Escopo mínimo: só um token com heartbeat:write ingere heartbeat (S1/ADR-0019).
    # Compara pelo VALOR string (membros de DeviceTokenScope são str) — robusto a
    # identidade de classe do enum.
    if "heartbeat:write" not in {getattr(s, "value", s) for s in claims.scopes}:
        logger.warning("edge_heartbeat: device sem escopo heartbeat:write")
        return error("Escopo insuficiente para esta operação", 403)

    # 7. Validate body with Heartbeat (Pydantic v2)
    body = request.get_json(silent=True) or {}
    try:
        hb = Heartbeat(**body)
    except ValidationError:
        return error("Payload inválido", 422, error_code="INVALID_PAYLOAD")

    # 8. Persist heartbeat + update last_seen (tenant/site/device from enrollment, never claims)
    enrolled_device_id = device["device_id"]
    row = repo.insert_heartbeat(enrollment_tenant, enrollment_site, enrolled_device_id, hb)
    repo.update_last_seen(enrolled_device_id, enrollment_tenant)

    # Pilha A→B: espelha a telemetria do heartbeat no dashboard integrado ao vivo
    # (edge_telemetry_samples + socket /monitor). Best-effort — ver decisão do Vitor
    # (heartbeat alimenta a Pilha B) em docs/edge/DIAGNOSTICO_OBSERVABILIDADE_2026-07-21.md.
    _bridge_heartbeat_to_telemetry(
        str(enrollment_tenant), str(enrollment_site), hb, str(row["received_at"])
    )

    logger.info(
        "edge_heartbeat: device=%s tenant=%s status=%s",
        enrolled_device_id,
        str(enrollment_tenant)[:8],
        hb.status.value,
    )

    return success(
        {"id": row["id"], "received_at": str(row["received_at"])},
        status=201,
    )


# ---------------------------------------------------------------------------
# Config poll (WS10) — canal pull cloud→edge consumido pelo ConfigPoller
# do edge-sync-agent (services/edge-sync-agent/app/config_poller.py).
# ---------------------------------------------------------------------------

@edge_bp.route("/config/poll", methods=["GET"])
@require_device_scope("config:read")  # DeviceTokenScope.config_read
def poll_edge_config() -> tuple:
    """Config das câmeras do site do device (device auth RS256 — sem JWT).

    CONTRATO DO CONSUMIDOR: o ConfigPoller aplica chaves de PRIMEIRO NÍVEL do
    body ({cameras, rules, scenario, model} — apply parcial), por isso esta
    rota NÃO usa o envelope success()/data. Devolver apenas {"cameras": [...]}
    é seguro: chaves ausentes não são tocadas no estado do agente.

    Segurança: exige escopo config:read (S1); escopo site/tenant vem do
    enrollment do device (C-01); o SELECT é enxuto e NUNCA inclui
    username/password_encrypted (C-05) — o device usa credenciais locais.
    """
    tenant_id, site_id, device_id = g.device_ctx
    try:
        cameras = _get_camera_repo().list_for_site_config(site_id, tenant_id)
        for cam in cameras:
            cam["id"] = str(cam["id"])

        # F1 — versionamento por conteúdo: config_version + ETag derivados do
        # payload (sem migration). Device manda If-None-Match; se nada mudou →
        # 304 (o caso comum; evita 28 câmeras × poll × payload grande).
        payload = {"cameras": cameras}
        canonical = json.dumps(payload, sort_keys=True, default=str)
        config_version = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        etag = f'"{config_version}"'

        if request.headers.get("If-None-Match") == etag:
            logger.info(
                "edge_config_poll: 304 device=%s site=%s v=%s",
                device_id, site_id[:8], config_version,
            )
            resp = make_response("", 304)
            resp.headers["ETag"] = etag
            resp.headers["Cache-Control"] = "no-cache"
            return resp

        payload["config_version"] = config_version
        logger.info(
            "edge_config_poll: 200 device=%s site=%s cameras=%d v=%s",
            device_id, site_id[:8], len(cameras), config_version,
        )
        resp = make_response(jsonify(payload), 200)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "no-cache"
        return resp
    except Exception:
        logger.exception("edge_config_poll_error")
        return error("Erro ao consultar config", 500)


# ---------------------------------------------------------------------------
# OTA bare-metal: target_ref por canal (ADR-0057 item 10, sem Docker — ver
# docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.4). A nuvem só INDICA; o agente
# decide se atualiza (app/ota/updater.py).
# ---------------------------------------------------------------------------


@edge_bp.route("/software/target", methods=["GET"])
@require_device_scope("config:read")  # DeviceTokenScope.config_read — mesmo escopo do config-poll
def get_software_target() -> tuple:
    """Ref-alvo do canal de software do device (device auth RS256).

    O canal vem do registro do device (`device_tokens.channel`, migration
    106) — não é escolhido pelo device via query param, é atribuído por um
    admin (`PUT /admin/software-channels/<channel>`). Sem target_ref
    publicado pro canal ainda -> `data: null` (o agente trata como "sem
    atualização", não como erro).
    """
    tenant_id, site_id, device_id = g.device_ctx
    device = _get_repo().get_device_by_device_id(device_id)
    if device is None or str(device["tenant_id"]) != tenant_id:
        return error("Dispositivo não encontrado", 404)

    channel = device.get("channel") or "dev"
    target_ref = _get_software_channel_repo().get_target_ref(channel)
    logger.info(
        "edge_software_target: device=%s channel=%s target_ref=%s",
        device_id, channel, target_ref,
    )
    return success({"channel": channel, "target_ref": target_ref})


# ---------------------------------------------------------------------------
# Shadow mode on-site (Onda 2, task-092-sequel): frame extraído pelo edge do
# NVR do cliente e enviado pro pool de anotação. O NVR fica numa VLAN
# isolada (ADR-0020) que a nuvem não alcança — a extração roda no edge
# (que está na LAN do gravador) e sobe o resultado, em vez da nuvem puxar
# o NVR diretamente (o que `nvr_extraction.py`/`extract_nvr_frames` faz
# para sites cloud-only). Mesmo destino (storage + training_frames,
# source='nvr') — não duplica schema/storage, só troca quem inicia o upload.
# ---------------------------------------------------------------------------


@edge_bp.route("/frames", methods=["POST"])
@require_device_scope("frames:write")
def upload_edge_frame() -> tuple:
    """Recebe um frame capturado on-site pelo edge (multipart).

    Campos: `file` (imagem, obrigatório) + form `camera_id`/`recorder_id`
    (obrigatórios — precisam pertencer ao MESMO tenant do device, C-01) +
    `captured_at` (opcional, ISO 8601) + `module_code` (opcional, default 'epi').
    """
    tenant_id, site_id, device_id = g.device_ctx

    file = request.files.get("file")
    if file is None:
        return error("Campo 'file' obrigatório (multipart)", 422)

    fname = file.filename or ""
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    if ext not in _ALLOWED_FRAME_EXTS:
        return error(
            f"Extensão não suportada: {ext!r} (aceita: {sorted(_ALLOWED_FRAME_EXTS)})", 422
        )

    data = file.read()
    if not data:
        return error("Arquivo vazio", 422)
    if len(data) > _MAX_FRAME_BYTES:
        return error(f"Arquivo excede o limite de {_MAX_FRAME_BYTES // (1024 * 1024)}MB", 422)

    dimensions = _image_dimensions(data)
    if dimensions is None:
        return error("Arquivo não é uma imagem válida", 422)
    width, height = dimensions

    camera_id_raw = request.form.get("camera_id")
    recorder_id_raw = request.form.get("recorder_id")
    if not camera_id_raw or not recorder_id_raw:
        return error("camera_id e recorder_id são obrigatórios", 422)
    try:
        recorder_uuid = UUID(recorder_id_raw)
        camera_uuid = UUID(camera_id_raw)
    except ValueError:
        return error("camera_id/recorder_id devem ser UUID", 422)

    captured_at = None
    captured_at_raw = request.form.get("captured_at")
    if captured_at_raw:
        try:
            captured_at = datetime.fromisoformat(captured_at_raw.replace("Z", "+00:00"))
        except ValueError:
            return error("captured_at inválido (ISO 8601 esperado)", 422)

    # C-01: camera_id/recorder_id devem pertencer ao tenant do device
    # (do enrollment, nunca do payload) — cross-tenant -> 404, não vaza existência.
    if _get_camera_repo().get_by_id_and_tenant(camera_id_raw, tenant_id) is None:
        return error("Câmera não encontrada", 404)
    if _get_recorder_repo().get_by_id(recorder_uuid, tenant_id) is None:
        return error("Gravador não encontrado", 404)

    module_code = request.form.get("module_code") or "epi"
    r2_key = f"{R2Prefix.TRAINING_IMAGES}/{tenant_id}/nvr/{recorder_id_raw}/{uuid4()}.jpg"

    try:
        from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

        get_storage(tenant_id).upload_bytes(r2_key, data, "image/jpeg")
        frame = _get_frame_repo().create(
            video_id=None,
            frame_number=0,
            filename=r2_key,
            source=FrameSource.NVR,
            r2_key=r2_key,
            camera_id=camera_uuid,
            recorder_id=recorder_uuid,
            width=width,
            height=height,
            captured_at=captured_at,
            tenant_id=tenant_id,
            module_code=module_code,
        )
    except Exception:
        logger.exception(
            "edge_frame_upload_error device=%s camera=%s recorder=%s",
            device_id, camera_id_raw, recorder_id_raw,
        )
        return error("Erro ao processar frame", 500)

    logger.info(
        "edge_frame_uploaded: device=%s camera=%s recorder=%s frame_id=%s",
        device_id, camera_id_raw, recorder_id_raw, frame.get("id"),
    )
    return success({"frame_id": str(frame["id"]), "r2_key": r2_key}, status=201)


# ---------------------------------------------------------------------------
# Observability: sites health (task-005)
# NOTE: must be registered before <site_id> dynamic routes to avoid ambiguity.
# ---------------------------------------------------------------------------

@edge_bp.route("/sites/health", methods=["GET"])
@jwt_required_custom
def get_sites_health(current_user_id) -> tuple:
    """Lista saúde dos sites do tenant com status derivado (O1).

    Status derivado: 'offline' se sem heartbeat ou heartbeat stale (> OFFLINE_THRESHOLD);
    caso contrário, usa o status do heartbeat (healthy/degraded/critical).
    """
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_repo()
    rows = repo.get_last_heartbeat_per_site(tenant_id)

    sites_health = []
    for row in rows:
        last_hb_at = row.get("received_at")
        derived_status = derive_site_health_status(last_hb_at, row.get("heartbeat_status"))
        sites_health.append({
            "site_id": str(row["site_id"]),
            "name": row["site_name"],
            "deployment_mode": row["deployment_mode"],
            "derived_status": derived_status,
            "last_heartbeat_at": str(last_hb_at) if last_hb_at else None,
            "inference_fps": float(row["inference_fps"]) if row.get("inference_fps") is not None else None,
            "cameras_online": row.get("cameras_online"),
            "cameras_total": row.get("cameras_total"),
            "cpu_pct": float(row["cpu_pct"]) if row.get("cpu_pct") is not None else None,
            "gpu_pct": float(row["gpu_pct"]) if row.get("gpu_pct") is not None else None,
            "gpu_mem_pct": (
                float(row["gpu_mem_pct"]) if row.get("gpu_mem_pct") is not None else None
            ),
            "queue_depth": row.get("queue_depth"),
            "gpu_temp_c": (
                float(row["gpu_temp_c"]) if row.get("gpu_temp_c") is not None else None
            ),
            "decode_pct": (
                float(row["decode_pct"]) if row.get("decode_pct") is not None else None
            ),
            "edge_version": row.get("edge_version"),
            "decode_fps": float(row["decode_fps"]) if row.get("decode_fps") is not None else None,
        })

    return success({"sites": sites_health})


# ---------------------------------------------------------------------------
# Observability: fleet overview (task-016)
# ---------------------------------------------------------------------------

@edge_bp.route("/overview", methods=["GET"])
@jwt_required_custom
def get_fleet_overview(current_user_id) -> tuple:
    """Contagens agregadas da frota edge do tenant (tela inicial do painel).

    Retorna:
      sites_total, sites_por_status, devices_total, devices_online,
      devices_revoked, sites_offline.

    sites_offline usa a MESMA regra de derive_site_health_status que /sites/health
    (C-05 — fonte única de verdade). Sites em 'provisioning' não contam como offline.
    """
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    hb_repo = _get_repo()
    site_repo = _get_site_repo()

    # Sites por status (tenant-scoped)
    status_rows = site_repo.get_site_status_counts(tenant_id)
    sites_por_status: dict[str, int] = {r["status"]: r["count"] for r in status_rows}
    sites_total = sum(sites_por_status.values())

    # Devices (tenant-scoped)
    device_counts = site_repo.get_device_fleet_counts(tenant_id, OFFLINE_THRESHOLD_SECONDS)
    devices_total = device_counts["total"]
    devices_online = device_counts["online"]
    devices_revoked = device_counts["revoked"]

    # Sites offline — mesma lógica de derive_site_health_status (C-05 fonte única)
    # Usa get_last_heartbeat_per_site_with_status para ter s.status disponível
    hb_rows = hb_repo.get_last_heartbeat_per_site_with_status(tenant_id)
    sites_offline = sum(
        1
        for row in hb_rows
        if is_site_offline(row.get("received_at"), row.get("heartbeat_status"), row["site_status"])
    )

    return success({
        "sites_total": sites_total,
        "sites_por_status": sites_por_status,
        "devices_total": devices_total,
        "devices_online": devices_online,
        "devices_revoked": devices_revoked,
        "sites_offline": sites_offline,
    })


# ---------------------------------------------------------------------------
# Admin: edge sites + enrollment tokens (task-003)
# ---------------------------------------------------------------------------

@edge_bp.route("/sites", methods=["POST"])
@jwt_required_custom
def create_site(current_user_id) -> tuple:
    """Cria edge site para o tenant do JWT (admin/superadmin only)."""
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    location = (body.get("location") or "").strip() or None
    deployment_mode = (body.get("deployment_mode") or "").strip()

    if not name:
        return error("Campo 'name' obrigatório", 400)
    if deployment_mode not in _VALID_DEPLOYMENT_MODES:
        return error("deployment_mode deve ser 'cloud', 'edge' ou 'hybrid'", 400)

    repo = _get_site_repo()
    site = repo.create_site(tenant_id, name, location, deployment_mode, str(current_user_id))
    logger.info("edge_site_created: tenant=%s site=%s", tenant_id[:8], site["id"])
    return success({"site": _serialize_site(site)}, status=201)


@edge_bp.route("/sites", methods=["GET"])
@jwt_required_custom
def list_sites(current_user_id) -> tuple:
    """Lista sites do tenant do JWT (admin/superadmin only)."""
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    sites = repo.list_sites(tenant_id)
    return success({"sites": [_serialize_site(s) for s in sites]})


@edge_bp.route("/sites/<site_id>", methods=["GET"])
@jwt_required_custom
def get_site_detail(site_id, current_user_id) -> tuple:
    """Detalhe de um site: campos + nº de devices + saúde derivada (task-017)."""
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    row = repo.get_site_detail(site_id, tenant_id)
    if row is None:
        return error("Site não encontrado", 404)

    derived_health = derive_site_health_status(
        row.get("last_heartbeat_at"), row.get("heartbeat_status")
    )

    return success({
        "site": {
            **_serialize_site(row),
            "device_count": int(row["device_count"]),
            "derived_health": derived_health,
            "last_heartbeat_at": (
                str(row["last_heartbeat_at"]) if row.get("last_heartbeat_at") else None
            ),
        }
    })


@edge_bp.route("/sites/<site_id>", methods=["PATCH"])
@jwt_required_custom
def update_site(site_id, current_user_id) -> tuple:
    """Atualização parcial de site: name, location, status, deployment_mode (task-017).

    tenant_id é imutável — ignorado se presente no body.
    Enums inválidos → 400. Site de outro tenant → 404 (C-01).
    """
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    body = request.get_json(silent=True) or {}
    body.pop("tenant_id", None)  # tenant_id imutável — nunca aceitar do body

    updates = {}

    if "name" in body:
        name = (body["name"] or "").strip()
        if not name:
            return error("Campo 'name' não pode ser vazio", 400)
        updates["name"] = name

    if "location" in body:
        updates["location"] = (body["location"] or "").strip() or None

    if "status" in body:
        status = (body["status"] or "").strip()
        if status not in _VALID_SITE_STATUSES:
            return error(
                "status deve ser 'active', 'inactive', 'maintenance' ou 'provisioning'", 400
            )
        updates["status"] = status

    if "deployment_mode" in body:
        deployment_mode = (body["deployment_mode"] or "").strip()
        if deployment_mode not in _VALID_DEPLOYMENT_MODES:
            return error("deployment_mode deve ser 'cloud', 'edge' ou 'hybrid'", 400)
        updates["deployment_mode"] = deployment_mode

    repo = _get_site_repo()
    row = repo.update_site(site_id, tenant_id, updates)
    if row is None:
        return error("Site não encontrado", 404)

    logger.info(
        "edge_site_updated: tenant=%s site=%s user=%s fields=%s",
        tenant_id[:8], site_id, str(current_user_id)[:8], sorted(updates.keys()),
    )

    return success({"site": _serialize_site(row)})


@edge_bp.route("/sites/<site_id>/enrollment-tokens", methods=["POST"])
@jwt_required_custom
def create_enrollment_token(site_id, current_user_id) -> tuple:
    """Gera enrollment token one-time para o site (admin/superadmin only).

    Retorna plaintext UMA vez; no banco fica apenas o SHA-256 hash.
    """
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    site = repo.get_site_by_id(site_id, tenant_id)
    if site is None:
        return error("Site não encontrado", 404)

    plaintext = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    record = repo.create_enrollment_token(
        site_id, tenant_id, token_hash, expires_at, str(current_user_id)
    )
    logger.info(
        "enrollment_token_created: tenant=%s site=%s token_id=%s",
        tenant_id[:8], site_id, record["id"],
    )
    return success(
        {
            "token": plaintext,
            "token_id": str(record["id"]),
            "site_id": site_id,
            "expires_at": str(record["expires_at"]),
            "used_at": None,
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# Enrollment token management: list + revoke (task-012)
# ---------------------------------------------------------------------------

@edge_bp.route("/sites/<site_id>/enrollment-tokens", methods=["GET"])
@jwt_required_custom
def list_enrollment_tokens(site_id, current_user_id) -> tuple:
    """Lista enrollment tokens do site com status derivado — sem hash/plaintext (C-05)."""
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    site = repo.get_site_by_id(site_id, tenant_id)
    if site is None:
        return error("Site não encontrado", 404)

    tokens = repo.list_enrollment_tokens(tenant_id, site_id)
    result = []
    for t in tokens:
        result.append({
            "id": str(t["id"]),
            "created_at": str(t["created_at"]) if t.get("created_at") else None,
            "expires_at": str(t["expires_at"]) if t.get("expires_at") else None,
            "used_at": str(t["used_at"]) if t.get("used_at") else None,
            "used_by_device_id": t.get("used_by_device_id"),
            "status": _derive_token_status(t),
        })
    return success({"tokens": result})


@edge_bp.route("/enrollment-tokens/<token_id>/revoke", methods=["POST"])
@jwt_required_custom
def revoke_enrollment_token(token_id, current_user_id) -> tuple:
    """Revoga enrollment token não utilizado (invalida por expires_at = now()).

    - Token já usado → 409
    - Token inexistente/cross-tenant → 404
    - Token já expirado → 200 no-op (idempotente)
    """
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    token = repo.get_enrollment_token_by_id(token_id, tenant_id)
    if token is None:
        return error("Token não encontrado", 404)

    if token.get("used_at") is not None:
        return error("Token já foi utilizado e não pode ser revogado", 409)

    repo.revoke_enrollment_token_if_unused(token_id, tenant_id)
    logger.info(
        "enrollment_token_revoked: tenant=%s token_id=%s user=%s",
        tenant_id[:8], token_id, str(current_user_id)[:8],
    )
    return success({"revoked": True, "token_id": token_id})


# ---------------------------------------------------------------------------
# Device enrollment (task-004)
# ---------------------------------------------------------------------------

_DEFAULT_SCOPES = [s.value for s in DeviceTokenScope]


@edge_bp.route("/enroll", methods=["POST"])
def enroll_device() -> tuple:
    """Device registration: consume one-time enrollment token, persist public key.

    tenant_id/site_id come exclusively from the enrollment_tokens row (C-01).
    """
    body = request.get_json(silent=True) or {}
    try:
        req = EnrollmentRequest(**body)
    except ValidationError:
        return error("Payload inválido", 422, error_code="INVALID_PAYLOAD")

    token_hash = hashlib.sha256(req.enrollment_token.encode()).hexdigest()
    fingerprint = hashlib.sha256(req.public_key_pem.encode()).hexdigest()

    repo = _get_site_repo()
    try:
        device = repo.enroll_device(
            token_hash=token_hash,
            device_id=req.device_id,
            device_name=req.device_name,
            public_key_pem=req.public_key_pem,
            fingerprint=fingerprint,
        )
    except ValueError as exc:
        if str(exc) == _DEVICE_ALREADY_ENROLLED:
            logger.warning("edge_enroll: device_id=%s já ativo (não revogado)", req.device_id)
            return error("Dispositivo já cadastrado e ativo neste tenant", 409)
        logger.warning("edge_enroll: invalid/used/expired token device=%s", req.device_id)
        return error("Enrollment token inválido, expirado ou já utilizado", 401)
    except psycopg2.errors.UniqueViolation:
        logger.warning("edge_enroll: duplicate device_id=%s", req.device_id)
        return error("Dispositivo já cadastrado neste tenant", 409)

    logger.info(
        "edge_enrolled: device=%s tenant=%s site=%s",
        req.device_id,
        str(device["tenant_id"])[:8],
        str(device["site_id"])[:8],
    )
    return success(
        {
            "tenant_id": str(device["tenant_id"]),
            "site_id": str(device["site_id"]),
            "device_id": device["device_id"],
            "scopes": _DEFAULT_SCOPES,
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# Observability: heartbeats history por site (task-009)
# ---------------------------------------------------------------------------

@edge_bp.route("/sites/<site_id>/heartbeats", methods=["GET"])
@jwt_required_custom
def list_site_heartbeats(site_id, current_user_id) -> tuple:
    """Série temporal de heartbeats de um site (paginada por cursor temporal).

    Query params:
      limit  — número de registros (default 100, máx 500)
      before — ISO timestamp exclusivo (cursor de paginação)
    """
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    # Validate site ownership (C-01 — 404 se site não pertencer ao tenant)
    site_repo = _get_site_repo()
    site = site_repo.get_site_by_id(site_id, tenant_id)
    if site is None:
        return error("Site não encontrado", 404)

    try:
        limit = int(request.args.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100
    limit = min(limit, 500)
    before = request.args.get("before") or None

    repo = _get_repo()
    rows = repo.list_heartbeats(tenant_id, site_id, limit=limit, before=before)
    return success({"heartbeats": [_serialize_heartbeat_row(r) for r in rows]})


# ---------------------------------------------------------------------------
# Observability: heartbeat summary por site (task-018)
# ---------------------------------------------------------------------------

@edge_bp.route("/sites/<site_id>/heartbeat-summary", methods=["GET"])
@jwt_required_custom
def get_heartbeat_summary(site_id, current_user_id) -> tuple:
    """Métricas agregadas de saúde de um site numa janela temporal (task-018).

    Query params:
      window — duração da janela (ex: 24h, 7d); default 24h, máx 7d
    """
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    site_repo = _get_site_repo()
    site = site_repo.get_site_by_id(site_id, tenant_id)
    if site is None:
        return error("Site não encontrado", 404)

    window_seconds = _parse_window_seconds(request.args.get("window"))

    repo = _get_repo()
    summary = repo.summary_for_site(tenant_id, site_id, window_seconds)

    derived_status = derive_site_health_status(
        summary.get("last_received_at"), summary.get("last_status")
    )

    return success({
        "site_id": site_id,
        "window_seconds": window_seconds,
        "heartbeat_count": int(summary["heartbeat_count"]),
        "avg_inference_fps": (
            float(summary["avg_inference_fps"])
            if summary.get("avg_inference_fps") is not None else None
        ),
        "max_inference_fps": (
            float(summary["max_inference_fps"])
            if summary.get("max_inference_fps") is not None else None
        ),
        "avg_inference_latency_ms": (
            float(summary["avg_inference_latency_ms"])
            if summary.get("avg_inference_latency_ms") is not None else None
        ),
        "uptime_pct": (
            float(summary["uptime_pct"])
            if summary.get("uptime_pct") is not None else None
        ),
        "last_status": summary.get("last_status"),
        "last_received_at": (
            str(summary["last_received_at"]) if summary.get("last_received_at") else None
        ),
        "derived_status": derived_status,
    })


# ---------------------------------------------------------------------------
# Device management: list + revoke (task-010, task-011)
# ---------------------------------------------------------------------------

@edge_bp.route("/sites/<site_id>/devices", methods=["GET"])
@jwt_required_custom
def list_site_devices(site_id, current_user_id) -> tuple:
    """Lista devices enrollados no site — sem public_key_pem/fingerprint (C-05)."""
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    site = repo.get_site_by_id(site_id, tenant_id)
    if site is None:
        return error("Site não encontrado", 404)

    devices = repo.list_devices(tenant_id, site_id)
    result = []
    for d in devices:
        result.append({
            "id": str(d["id"]),
            "device_id": d["device_id"],
            "device_name": d.get("device_name"),
            "revoked": d["revoked"],
            "last_seen_at": str(d["last_seen_at"]) if d.get("last_seen_at") else None,
            "enrolled_at": str(d["enrolled_at"]) if d.get("enrolled_at") else None,
        })
    return success({"devices": result})


@edge_bp.route("/devices/<device_pk>/revoke", methods=["POST"])
@jwt_required_custom
def revoke_device(device_pk, current_user_id) -> tuple:
    """Revoga dispositivo — corta acesso imediato (heartbeat passa a retornar 403).

    Idempotente: revogar device já revogado → 200 no-op.
    Cross-tenant → 404 (não vaza existência — C-01).
    """
    try:
        get_role()  # valida claim role — 401 se token sem role
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if not has_permission(_MANAGE_PERMISSION):
        return error("Acesso negado: requer role admin ou superadmin", 403)

    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip() or None

    repo = _get_site_repo()
    row = repo.revoke_device(device_pk, tenant_id, str(current_user_id), reason)
    if row is None:
        return error("Dispositivo não encontrado", 404)

    logger.info(
        "edge_device_revoked: tenant=%s device_pk=%s revoked_by=%s",
        tenant_id[:8], device_pk, str(current_user_id)[:8],
    )
    return success({
        "revoked": True,
        "device_id": row.get("device_id"),
        "revoked_at": str(row["revoked_at"]) if row.get("revoked_at") else None,
    })
