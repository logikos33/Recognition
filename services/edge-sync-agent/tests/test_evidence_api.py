"""Tests for evidence_api: Flask routes, auth enforcement, streaming, bind-host guard."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from urllib.parse import quote

import pytest

from app.evidence_api import create_app, run_server, validate_bind_host
from app.evidence_auth import TrustAnchor
from app.recorder_client import InMemoryRecorderClient, NotConfiguredRecorderClient, RecorderEvent

TENANT = "11111111-1111-1111-1111-111111111111"
SITE = "22222222-2222-2222-2222-222222222222"

_NOW = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
# ISO timestamps contain "+00:00" — must be percent-encoded in query strings
# (an unencoded "+" is parsed as a literal space), so all URL-building below
# uses the quoted forms.
_START = (_NOW - timedelta(minutes=10)).isoformat()
_END = _NOW.isoformat()
_START_Q = quote(_START, safe="")
_END_Q = quote(_END, safe="")


@pytest.fixture
def trust_anchor(rsa_keypair):
    _, public_pem = rsa_keypair
    return TrustAnchor(public_key_pem=public_pem, tenant_id=TENANT, site_id=SITE)


@pytest.fixture
def recorder():
    return InMemoryRecorderClient(
        events=[
            RecorderEvent(
                event_id="evt-1",
                camera_id="cam-1",
                started_at=_NOW - timedelta(minutes=5),
                ended_at=_NOW - timedelta(minutes=4),
                event_type="motion",
            )
        ],
        clip_chunks=[b"chunk-a", b"chunk-b"],
    )


@pytest.fixture
def client(recorder, trust_anchor):
    app = create_app(recorder_client=recorder, trust_anchor=trust_anchor)
    app.testing = True
    return app.test_client()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── auth is mandatory on every route ─────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/edge/evidence/health",
        "/api/v1/edge/evidence/timeline?camera_id=cam-1&start=" + _START_Q + "&end=" + _END_Q,
        "/api/v1/edge/evidence/clip?camera_id=cam-1&start=" + _START_Q + "&end=" + _END_Q,
    ],
)
def test_missing_authorization_header_is_401(client, path):
    resp = client.get(path)
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/edge/evidence/health",
        "/api/v1/edge/evidence/timeline?camera_id=cam-1&start=" + _START_Q + "&end=" + _END_Q,
        "/api/v1/edge/evidence/clip?camera_id=cam-1&start=" + _START_Q + "&end=" + _END_Q,
    ],
)
def test_garbage_token_is_401(client, path):
    resp = client.get(path, headers=_auth("garbage.token.value"))
    assert resp.status_code == 401


def test_wrong_scope_is_401_on_clip(client, make_evidence_token):
    """Token only has evidence:read — /clip requires evidence:stream."""
    token = make_evidence_token(scopes=["evidence:read"])
    resp = client.get(
        f"/api/v1/edge/evidence/clip?camera_id=cam-1&start={_START_Q}&end={_END_Q}",
        headers=_auth(token),
    )
    assert resp.status_code == 401


def test_trust_anchor_missing_is_500_not_configured(recorder, make_evidence_token):
    app = create_app(recorder_client=recorder, trust_anchor=None)
    app.testing = True
    c = app.test_client()
    token = make_evidence_token()

    resp = c.get("/api/v1/edge/evidence/health", headers=_auth(token))

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "not_configured"


# ── happy paths ───────────────────────────────────────────────────────────────


def test_health_ok(client, make_evidence_token):
    token = make_evidence_token()
    resp = client.get("/api/v1/edge/evidence/health", headers=_auth(token))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["data"]["reachable"] is True


def test_timeline_returns_events_for_camera(client, make_evidence_token):
    token = make_evidence_token()
    resp = client.get(
        f"/api/v1/edge/evidence/timeline?camera_id=cam-1&start={_START_Q}&end={_END_Q}",
        headers=_auth(token),
    )

    assert resp.status_code == 200
    events = resp.get_json()["data"]["events"]
    assert len(events) == 1
    assert events[0]["event_id"] == "evt-1"


def test_timeline_empty_for_unknown_camera(client, make_evidence_token):
    token = make_evidence_token()
    resp = client.get(
        f"/api/v1/edge/evidence/timeline?camera_id=cam-ghost&start={_START_Q}&end={_END_Q}",
        headers=_auth(token),
    )

    assert resp.status_code == 200
    assert resp.get_json()["data"]["events"] == []


def test_clip_streams_bytes(client, make_evidence_token):
    token = make_evidence_token()
    resp = client.get(
        f"/api/v1/edge/evidence/clip?camera_id=cam-1&start={_START_Q}&end={_END_Q}",
        headers=_auth(token),
    )

    assert resp.status_code == 200
    assert resp.mimetype == "video/mp4"
    assert resp.get_data() == b"chunk-achunk-b"


# ── input validation ─────────────────────────────────────────────────────────


def test_timeline_missing_params_is_400(client, make_evidence_token):
    token = make_evidence_token()
    resp = client.get("/api/v1/edge/evidence/timeline?camera_id=cam-1", headers=_auth(token))
    assert resp.status_code == 400


def test_timeline_end_before_start_is_400(client, make_evidence_token):
    token = make_evidence_token()
    resp = client.get(
        f"/api/v1/edge/evidence/timeline?camera_id=cam-1&start={_END_Q}&end={_START_Q}",
        headers=_auth(token),
    )
    assert resp.status_code == 400


def test_clip_missing_params_is_400(client, make_evidence_token):
    token = make_evidence_token()
    resp = client.get("/api/v1/edge/evidence/clip?camera_id=cam-1", headers=_auth(token))
    assert resp.status_code == 400


def test_timeline_malformed_datetime_is_400(client, make_evidence_token):
    token = make_evidence_token()
    resp = client.get(
        "/api/v1/edge/evidence/timeline?camera_id=cam-1&start=not-a-date&end=" + _END_Q,
        headers=_auth(token),
    )
    assert resp.status_code == 400


def test_clip_empty_clip_is_404(trust_anchor, make_evidence_token):
    app = create_app(
        recorder_client=InMemoryRecorderClient(clip_chunks=[]), trust_anchor=trust_anchor
    )
    app.testing = True
    c = app.test_client()
    token = make_evidence_token()

    resp = c.get(
        f"/api/v1/edge/evidence/clip?camera_id=cam-1&start={_START_Q}&end={_END_Q}",
        headers=_auth(token),
    )
    assert resp.status_code == 404


def test_timeline_window_too_wide_is_400(client, make_evidence_token):
    token = make_evidence_token()
    too_wide_start = quote((_NOW - timedelta(hours=48)).isoformat(), safe="")
    resp = client.get(
        f"/api/v1/edge/evidence/timeline?camera_id=cam-1&start={too_wide_start}&end={_END_Q}",
        headers=_auth(token),
    )
    assert resp.status_code == 400


# ── recorder failure surfaces as 502, not a crash ────────────────────────────


def test_clip_recorder_unreachable_is_502(trust_anchor, make_evidence_token):
    app = create_app(
        recorder_client=InMemoryRecorderClient(reachable=False), trust_anchor=trust_anchor
    )
    app.testing = True
    c = app.test_client()
    token = make_evidence_token()

    resp = c.get(
        f"/api/v1/edge/evidence/clip?camera_id=cam-1&start={_START_Q}&end={_END_Q}",
        headers=_auth(token),
    )
    assert resp.status_code == 502


def test_not_configured_recorder_client_is_502_end_to_end(trust_anchor, make_evidence_token):
    """No task-091 backend wired: fails loud with 502, never fakes a 200."""
    app = create_app(recorder_client=NotConfiguredRecorderClient(), trust_anchor=trust_anchor)
    app.testing = True
    c = app.test_client()
    token = make_evidence_token()

    resp = c.get(
        f"/api/v1/edge/evidence/timeline?camera_id=cam-1&start={_START_Q}&end={_END_Q}",
        headers=_auth(token),
    )
    assert resp.status_code == 502


# ── bind-host guard (ADR-0020: never exposed to the public internet) ────────


@pytest.mark.parametrize("bad_host", ["0.0.0.0", "::", "", None])
def test_validate_bind_host_rejects_public_binds(bad_host):
    with pytest.raises(ValueError):
        validate_bind_host(bad_host)


@pytest.mark.parametrize("good_host", ["10.8.0.2", "192.168.88.5", "wg0.site.local"])
def test_validate_bind_host_accepts_private_overlay_addresses(good_host):
    assert validate_bind_host(good_host) == good_host


def test_run_server_rejects_public_bind_before_touching_app():
    fake_app = MagicMock()
    with pytest.raises(ValueError):
        run_server(fake_app, host="0.0.0.0")
    fake_app.run.assert_not_called()


def test_run_server_binds_validated_host():
    fake_app = MagicMock()
    run_server(fake_app, host="10.8.0.2", port=9000)
    fake_app.run.assert_called_once_with(host="10.8.0.2", port=9000, threaded=True)
