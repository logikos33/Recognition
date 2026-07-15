"""Mini-API local de evidência (recorder-first, ADR-0045 / task-090).

Serves evidence FROM the site's recorder/NVR — never persists it. Reachable
two ways, both going through the SAME auth + handlers:
  - Local: a client on the site LAN (technician tooling, dual-mode frontend).
  - Remote: cloud proxies a request over the WireGuard tunnel (ADR-0020) to
    this same port, on demand.

Network-layer safety (ADR-0020, C-04 — nunca confiar só na app layer):
  - This process MUST bind to the WireGuard/LAN interface address, never
    0.0.0.0 — validate_bind_host() enforces this at startup, not as an
    afterthought.
  - The camera-lockout lesson from ADR-0020 applies here too: this API talks
    to the recorder, never receives inbound traffic FROM the camera network
    directly, and never forwards raw camera credentials to a caller.

Every route requires a valid evidence access token (see evidence_auth.py) —
there is no open endpoint, including /health, by design (task-090 requirement).

Nothing here writes clip bytes to disk: GET /clip streams chunks straight
from the RecorderClient to the HTTP response.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, Flask, Response, current_app, jsonify, request, stream_with_context

from .evidence_auth import EvidenceScope, TrustAnchor, require_evidence_scope
from .recorder_client import NotConfiguredRecorderClient, RecorderClient, RecorderError

logger = logging.getLogger(__name__)

_FORBIDDEN_BIND_HOSTS = {"0.0.0.0", "::", ""}  # noqa: S104 — this IS the check that forbids it
_MAX_WINDOW = timedelta(hours=24)

bp = Blueprint("evidence", __name__)


def validate_bind_host(host: str | None) -> str:
    """Refuses to bind on any address that could expose this API to the public internet.

    ADR-0020: cameras/gravador are only reachable via the outbound-dialed
    WireGuard overlay — port-forwarding/public exposure is rejected by design,
    not just discouraged. This mini-API follows the same rule for itself.
    """
    normalized = (host or "").strip()
    if normalized in _FORBIDDEN_BIND_HOSTS:
        raise ValueError(
            "EVIDENCE_API_BIND_HOST inválido: "
            f"{host!r}. Deve ser o IP da interface WireGuard/LAN do site — "
            "nunca 0.0.0.0/::/vazio (ADR-0020, sem exposição à internet pública)."
        )
    return normalized


def _parse_window(args: Any) -> tuple[str, datetime, datetime] | None:
    """Parses & validates camera_id/start/end query params. None on any invalid input."""
    camera_id = args.get("camera_id")
    start_raw = args.get("start")
    end_raw = args.get("end")
    if not camera_id or not start_raw or not end_raw:
        return None
    try:
        start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if end <= start:
        return None
    if end - start > _MAX_WINDOW:
        return None
    return camera_id, start, end


def _event_to_dict(event: Any) -> dict:
    data = asdict(event)
    data["started_at"] = event.started_at.isoformat()
    data["ended_at"] = event.ended_at.isoformat()
    return data


@bp.route("/health", methods=["GET"])
@require_evidence_scope(EvidenceScope.evidence_read)
def health() -> Any:
    recorder: RecorderClient = current_app.config["RECORDER_CLIENT"]
    probe = recorder.health()
    return jsonify(
        {
            "status": "success",
            "data": {"reachable": probe.reachable, "detail": probe.detail},
        }
    )


@bp.route("/timeline", methods=["GET"])
@require_evidence_scope(EvidenceScope.evidence_read)
def timeline() -> Any:
    parsed = _parse_window(request.args)
    if parsed is None:
        return jsonify({"status": "error", "error": "invalid_params"}), 400
    camera_id, start, end = parsed

    recorder: RecorderClient = current_app.config["RECORDER_CLIENT"]
    try:
        events = recorder.list_events(camera_id, start, end)
    except RecorderError as exc:
        logger.warning("evidence_timeline_recorder_error camera_id=%s %s", camera_id, exc)
        return jsonify({"status": "error", "error": "recorder_unavailable"}), 502

    return jsonify(
        {"status": "success", "data": {"events": [_event_to_dict(e) for e in events]}}
    )


@bp.route("/clip", methods=["GET"])
@require_evidence_scope(EvidenceScope.evidence_stream)
def clip() -> Any:
    parsed = _parse_window(request.args)
    if parsed is None:
        return jsonify({"status": "error", "error": "invalid_params"}), 400
    camera_id, start, end = parsed

    recorder: RecorderClient = current_app.config["RECORDER_CLIENT"]
    try:
        chunks = recorder.stream_clip(camera_id, start, end)
        first_chunk = next(chunks)
    except RecorderError as exc:
        logger.warning("evidence_clip_recorder_error camera_id=%s %s", camera_id, exc)
        return jsonify({"status": "error", "error": "recorder_unavailable"}), 502
    except StopIteration:
        return jsonify({"status": "error", "error": "empty_clip"}), 404

    def _generate() -> Iterator[bytes]:
        # Pure pass-through: nothing is buffered to disk, chunks stream as
        # they arrive from the recorder (ADR-0033/0045 — reserva de disco
        # intocável, nada de cache permanente aqui).
        yield first_chunk
        yield from chunks

    logger.info("evidence_clip_streamed camera_id=%s start=%s end=%s", camera_id, start, end)
    return Response(stream_with_context(_generate()), mimetype="video/mp4")


def create_app(
    recorder_client: RecorderClient | None = None,
    trust_anchor: TrustAnchor | None = None,
) -> Flask:
    """Builds the evidence API Flask app.

    recorder_client defaults to NotConfiguredRecorderClient (fails loud, see
    recorder_client.py) — production wiring MUST inject the real task-091
    backend. trust_anchor is required for any route to succeed at runtime;
    it may be omitted only in tests that specifically exercise the
    "not configured" 500 path.
    """
    app = Flask(__name__)
    app.config["RECORDER_CLIENT"] = recorder_client or NotConfiguredRecorderClient()
    app.config["TRUST_ANCHOR"] = trust_anchor
    app.register_blueprint(bp, url_prefix="/api/v1/edge/evidence")
    return app


def run_server(app: Flask, host: str, port: int = 8443) -> None:
    """Starts the evidence API bound to *host* — validated, never 0.0.0.0.

    Uses Flask's built-in server (threaded) — the edge site's request volume
    for on-demand evidence lookups is low and the surface is already
    restricted to the WireGuard/LAN interface, so this is an acceptable MVP
    choice. Swapping to waitress/gunicorn before go-live is tracked as a
    follow-up (task-097), not a blocker for this task.
    """
    validated_host = validate_bind_host(host)
    logger.info("evidence_api_listening host=%s port=%d", validated_host, port)
    app.run(host=validated_host, port=port, threaded=True)
