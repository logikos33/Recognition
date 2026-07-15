"""Local ONVIF discovery API — technician/cloud-facing view of what
onvif_discovery.discover_devices() found on the site's isolated camera
subnet (task-096).

Design decision — "how does discovery reach the cloud/technician" (full
reasoning in the task-096 PR description, summarized here):

  The scan itself MUST run on the edge (services/edge-sync-agent, this
  package) — it needs L2 multicast reach into the camera subnet behind the
  MikroTik (ADR-0020); the cloud monolith never has that network path.
  What the edge does with the *result* has two live consumers, both already
  established by task-090's mini-API pattern:
    - Local: a technician's tooling on the site LAN calls this endpoint
      directly.
    - Remote: the cloud proxies a request over the WireGuard tunnel to this
      same port, on demand — same "one code path, two network paths" model
      as evidence_api.py.

  This module deliberately returns RAW discovered devices (source_ip,
  xaddrs, types, scopes, validated suggested_rtsp_url, best-effort device
  info) and does NOT attempt to match them against a tenant's already-
  cadastradas cameras. That matching needs `cameras`/`ip_cameras` rows,
  which live in the CLOUD's per-tenant schema — this edge process has no DB
  access to them (same boundary onvif_recorder_client.py already respects:
  RECORDER_CHANNEL_MAP is edge-local config, not a cloud read). Building a
  NEW cloud endpoint that ingests a discovery result and matches it against
  `cameras.host`/`ip_cameras.host` is real, useful follow-up work, but it is
  NOT built in this task — there's no existing evidence a technician-facing
  workflow needs it yet (same restraint ADR-0051 applied to not building an
  onboarding wizard without evidence of need). The match itself, when built,
  is a trivial string-equality join on `host`/`ip` — the hard, network-
  bound part this task actually had to solve is the scan.

Auth: reuses task-090's TrustAnchor / EvidenceScope machinery (see
evidence_auth.py's EvidenceScope docstring for why `discovery:read` lives in
that enum instead of a new module) — every route requires a valid token,
there is no open endpoint, same as evidence_api.py.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from flask import Blueprint, Flask, current_app, jsonify

from .evidence_auth import EvidenceScope, TrustAnchor, require_evidence_scope
from .onvif_discovery import (
    DiscoveredDevice,
    build_suggested_rtsp_url,
    discover_devices,
    fetch_device_information,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 3.0
_DEFAULT_MAX_RESPONSES = 50
_DEFAULT_ENRICH = True

bp = Blueprint("discovery", __name__)


def _device_to_dict(device: DiscoveredDevice, *, enrich: bool) -> dict[str, Any]:
    suggested_rtsp_url = build_suggested_rtsp_url(device.source_ip)

    device_info: dict[str, Any] | None = None
    if enrich and device.xaddrs:
        # Best-effort: only the first XAddr is probed (typically the
        # device_service URL). A failed/unreachable device_service must not
        # remove the device from the result — fetch_device_information
        # already returns None rather than raising on any failure.
        info = fetch_device_information(device.xaddrs[0])
        if info is not None:
            device_info = {
                "manufacturer": info.manufacturer,
                "model": info.model,
                "firmware_version": info.firmware_version,
                "serial_number": info.serial_number,
                "hardware_id": info.hardware_id,
            }

    return {
        "source_ip": device.source_ip,
        "xaddrs": device.xaddrs,
        "types": device.types,
        "scopes": device.scopes,
        "endpoint_reference": device.endpoint_reference,
        "suggested_rtsp_url": suggested_rtsp_url,
        "device_info": device_info,
    }


@bp.route("/scan", methods=["GET"])
@require_evidence_scope(EvidenceScope.discovery_read)
def scan() -> Any:
    scan_fn: Callable[..., list[DiscoveredDevice]] = current_app.config.get(
        "DISCOVER_DEVICES_FN", discover_devices
    )
    timeout_seconds = current_app.config.get("DISCOVERY_TIMEOUT_S", _DEFAULT_TIMEOUT_SECONDS)
    max_responses = current_app.config.get("DISCOVERY_MAX_RESPONSES", _DEFAULT_MAX_RESPONSES)
    enrich = current_app.config.get("DISCOVERY_ENRICH_DEVICE_INFO", _DEFAULT_ENRICH)

    try:
        devices = scan_fn(timeout_seconds=timeout_seconds, max_responses=max_responses)
    except Exception as exc:  # noqa: BLE001 — scan failure must not 500 with a stack trace leak
        logger.warning("onvif_discovery_scan_failed err=%s", exc)
        return jsonify({"status": "error", "error": "scan_failed"}), 502

    payload = [_device_to_dict(d, enrich=enrich) for d in devices]
    logger.info("onvif_discovery_scan_served devices=%d", len(payload))
    return jsonify({"status": "success", "data": {"devices": payload}})


def create_app(
    trust_anchor: TrustAnchor | None = None,
    discover_devices_fn: Callable[..., list[DiscoveredDevice]] | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    max_responses: int = _DEFAULT_MAX_RESPONSES,
    enrich_device_info: bool = _DEFAULT_ENRICH,
) -> Flask:
    """Builds a standalone Flask app for this blueprint — used by tests and
    by anything that wants ONLY the discovery routes. Production wiring
    (main.py) registers `bp` onto the SAME app that already hosts
    evidence_api's blueprint, so both share one TRUST_ANCHOR and one bound
    port (see main.py for why: one Flask process, one bind-host validation,
    one WireGuard-restricted listening socket)."""
    app = Flask(__name__)
    app.config["TRUST_ANCHOR"] = trust_anchor
    app.config["DISCOVER_DEVICES_FN"] = discover_devices_fn or discover_devices
    app.config["DISCOVERY_TIMEOUT_S"] = timeout_seconds
    app.config["DISCOVERY_MAX_RESPONSES"] = max_responses
    app.config["DISCOVERY_ENRICH_DEVICE_INFO"] = enrich_device_info
    app.register_blueprint(bp, url_prefix="/api/v1/edge/discovery")
    return app
