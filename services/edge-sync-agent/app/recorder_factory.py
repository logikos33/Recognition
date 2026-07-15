"""Selects and configures the real RecorderClient for this edge process.

Config source decision (task-091): the site's gravador (protocol, host,
port, credentials, camera_id→channel map) is configured via environment
variables local to the edge device, NOT pulled from the cloud's
`public.recorders` table (infra/migrations/099_recorders.sql). That table
serves a different consumer — the WS-B1 cloud-side training-frame
extraction flow (ADR-0034), initiated from the tenant admin UI, with its
own `recorders.channels` (a count, not a camera→channel map) and no wiring
into GET /api/v1/edge/config/poll today. Threading edge-side recorder
credentials through the cloud config-poll pipeline would need a new
migration + poll-endpoint field + ConfigPoller changes — a larger
cross-cutting change out of scope for this task. Env vars are also simply
correct for a value that's static per site and set once at deployment,
same as RECORDER_* being analogous to how the device's own enrollment
identity is provisioned locally, not polled.

One recorder per site is assumed (ADR-0045: the gravador IS the evidence
source for the site) — no support here for multiple recorders per edge
process.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .onvif_recorder_client import OnvifRecorderClient
from .recorder_client import RecorderClient, RecorderError
from .rtsp_timestamp_recorder_client import RtspTimestampRecorderClient

logger = logging.getLogger(__name__)

# Cascata da ADR-0034 restrita ao que este processo sabe falar hoje: ONVIF
# Profile G (caminho aberto/preferido) e o fallback RTSP-com-timestamp
# (Dahua/Intelbras). Hikvision ISAPI existe no monolito (WS-B1) mas não foi
# portado aqui — nenhum cliente RVB usa Hikvision (CLAUDE.md); adicionar
# quando houver necessidade real, não especulativamente.
_RTSP_FALLBACK_PROTOCOLS = frozenset({"dahua", "intelbras", "rtsp"})
_SUPPORTED_PROTOCOLS = frozenset({"onvif"} | _RTSP_FALLBACK_PROTOCOLS)


def build_recorder_client(
    protocol: str,
    host: str,
    port: int,
    username: str,
    password: str,
    channel_map: dict[str, int],
    http_client: Any = None,
) -> RecorderClient:
    """Resolves a concrete RecorderClient for *protocol*.

    Raises RecorderError for an unsupported/unmapped protocol — no silent
    fallback to a default client (ADR-0017 discipline: a misconfigured
    protocol string must fail loud, same as NotConfiguredRecorderClient does
    for "no client at all").
    """
    normalized = (protocol or "").strip().lower()
    if normalized not in _SUPPORTED_PROTOCOLS:
        raise RecorderError(
            f"protocolo de gravador não suportado: {protocol!r}. "
            f"Suportados: {', '.join(sorted(_SUPPORTED_PROTOCOLS))}."
        )

    if normalized == "onvif":
        return OnvifRecorderClient(
            host=host,
            port=port,
            username=username,
            password=password,
            channel_map=channel_map,
            http_client=http_client,
        )

    return RtspTimestampRecorderClient(
        host=host,
        port=port,
        username=username,
        password=password,
        channel_map=channel_map,
    )


def build_recorder_client_from_env(env: dict[str, str] | None = None) -> RecorderClient:
    """Reads RECORDER_* env vars and builds the configured RecorderClient.

    Required: RECORDER_PROTOCOL, RECORDER_HOST, RECORDER_PORT.
    Optional: RECORDER_USERNAME, RECORDER_PASSWORD (default "").
    RECORDER_CHANNEL_MAP: JSON object mapping camera_id (str) -> ONVIF/RTSP
    channel (int), e.g. '{"11111111-...": 1, "22222222-...": 2}'. Missing or
    malformed -> RecorderError (no silent empty map: every camera_id lookup
    would then fail anyway, but failing here gives a clearer error at
    startup instead of at first request).
    """
    source = env if env is not None else os.environ

    protocol = source.get("RECORDER_PROTOCOL", "")
    host = source.get("RECORDER_HOST", "")
    port_raw = source.get("RECORDER_PORT", "")
    if not protocol or not host or not port_raw:
        raise RecorderError(
            "RECORDER_PROTOCOL, RECORDER_HOST e RECORDER_PORT são obrigatórios "
            "para configurar o RecorderClient real (task-091) — sem fallback silencioso."
        )
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RecorderError(f"RECORDER_PORT inválido: {port_raw!r}") from exc

    username = source.get("RECORDER_USERNAME", "")
    password = source.get("RECORDER_PASSWORD", "")

    channel_map_raw = source.get("RECORDER_CHANNEL_MAP", "")
    channel_map = _parse_channel_map(channel_map_raw)

    return build_recorder_client(
        protocol=protocol,
        host=host,
        port=port,
        username=username,
        password=password,
        channel_map=channel_map,
    )


def _parse_channel_map(raw: str) -> dict[str, int]:
    if not raw.strip():
        raise RecorderError(
            "RECORDER_CHANNEL_MAP é obrigatório (JSON camera_id -> canal) — "
            "sem ele nenhum camera_id resolve para um canal do gravador."
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RecorderError(f"RECORDER_CHANNEL_MAP não é JSON válido: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RecorderError("RECORDER_CHANNEL_MAP deve ser um objeto JSON {camera_id: canal}")
    try:
        return {str(k): int(v) for k, v in parsed.items()}
    except (TypeError, ValueError) as exc:
        raise RecorderError(f"RECORDER_CHANNEL_MAP tem valor de canal inválido: {exc}") from exc
