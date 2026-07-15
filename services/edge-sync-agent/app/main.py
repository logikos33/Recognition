"""Minimal entrypoint for the evidence + discovery APIs (task-090/091/096).

No main.py existed anywhere in this package before task-091. AGENT.md lists
the rest as placeholders alongside mqtt_consumer.py, model_manager.py,
heartbeat.py, etc. (the full edge-sync-agent daemon, Fase 4 of
EDGE_DEPLOYMENT_PLAN.md). This entrypoint wires what's needed to serve, on
ONE Flask app / ONE bound port:
  - the evidence mini-API with a real (non-stub) RecorderClient
    (`evidence_api.create_app`, task-090/091);
  - the ONVIF discovery API (`discovery_api.bp`, task-096) — registered onto
    the SAME app returned by `evidence_api.create_app` (not a second
    `create_app`/second port) so both share one TRUST_ANCHOR and one
    WireGuard-restricted bind-host validation (see evidence_api.py's
    `validate_bind_host` — ADR-0020: this process must never listen on
    0.0.0.0/::).
It intentionally does NOT start the heartbeat/config-poll/uploader loops —
those are separate, already-placeholder concerns tracked elsewhere; wiring
them together into one process daemon is future scope.

Run: `python -m app.main` (env-configured, see AGENT.md's "Variáveis de
Ambiente" table for the RECORDER_*/EVIDENCE_*/ONVIF_DISCOVERY_* entries).
"""

from __future__ import annotations

import logging
import os
import sys

from .discovery_api import bp as discovery_bp
from .evidence_api import create_app, run_server
from .evidence_auth import TrustAnchor
from .recorder_client import RecorderError
from .recorder_factory import build_recorder_client_from_env

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 8443
_DEFAULT_DISCOVERY_TIMEOUT_S = 3.0
_DEFAULT_DISCOVERY_MAX_RESPONSES = 50


def _read_public_key_pem(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        raise RecorderError(
            f"não foi possível ler EVIDENCE_TRUST_PUBLIC_KEY_PATH={path!r}: {exc}"
        ) from exc


def build_trust_anchor(env: dict[str, str] | None = None) -> TrustAnchor:
    source = env if env is not None else os.environ
    key_path = source.get(
        "EVIDENCE_TRUST_PUBLIC_KEY_PATH", "/run/secrets/evidence_trust_public_key.pem"
    )
    tenant_id = source.get("TENANT_ID", "")
    site_id = source.get("SITE_ID", "")
    public_key_pem = _read_public_key_pem(key_path)
    return TrustAnchor(public_key_pem=public_key_pem, tenant_id=tenant_id, site_id=site_id)


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    bind_host = os.environ.get("EVIDENCE_API_BIND_HOST", "")
    port = int(os.environ.get("EVIDENCE_API_PORT", str(_DEFAULT_PORT)))

    try:
        recorder_client = build_recorder_client_from_env()
        trust_anchor = build_trust_anchor()
    except RecorderError as exc:
        logger.error("evidence_api_startup_config_error %s", exc)
        sys.exit(1)

    app = create_app(recorder_client=recorder_client, trust_anchor=trust_anchor)
    app.config["DISCOVERY_TIMEOUT_S"] = float(
        os.environ.get("ONVIF_DISCOVERY_TIMEOUT_S", str(_DEFAULT_DISCOVERY_TIMEOUT_S))
    )
    app.config["DISCOVERY_MAX_RESPONSES"] = int(
        os.environ.get("ONVIF_DISCOVERY_MAX_RESPONSES", str(_DEFAULT_DISCOVERY_MAX_RESPONSES))
    )
    app.config["DISCOVERY_ENRICH_DEVICE_INFO"] = (
        os.environ.get("ONVIF_DISCOVERY_ENRICH_DEVICE_INFO", "true").strip().lower() != "false"
    )
    app.register_blueprint(discovery_bp, url_prefix="/api/v1/edge/discovery")
    run_server(app, host=bind_host, port=port)


if __name__ == "__main__":
    main()
