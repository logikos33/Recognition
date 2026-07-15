"""Tests for discovery_api: Flask route wiring, auth enforcement (reusing
task-090's TrustAnchor/EvidenceScope), and response shaping."""

from __future__ import annotations

import pytest

from app.discovery_api import create_app
from app.evidence_auth import TrustAnchor
from app.onvif_discovery import DiscoveredDevice

TENANT = "11111111-1111-1111-1111-111111111111"
SITE = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def trust_anchor(rsa_keypair):
    _, public_pem = rsa_keypair
    return TrustAnchor(public_key_pem=public_pem, tenant_id=TENANT, site_id=SITE)


def _fake_devices(*args, **kwargs):
    return [
        DiscoveredDevice(
            source_ip="192.168.1.64",
            xaddrs=["http://192.168.1.64/onvif/device_service"],
            types=["dn:NetworkVideoTransmitter"],
            scopes=["onvif://www.onvif.org/type/video_encoder"],
            endpoint_reference="urn:uuid:abc",
        )
    ]


@pytest.fixture
def client(trust_anchor):
    app = create_app(
        trust_anchor=trust_anchor,
        discover_devices_fn=_fake_devices,
        enrich_device_info=False,
    )
    app.testing = True
    return app.test_client()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── auth is mandatory ────────────────────────────────────────────────────


def test_scan_without_authorization_header_is_401(client):
    resp = client.get("/api/v1/edge/discovery/scan")
    assert resp.status_code == 401


def test_scan_with_malformed_token_is_401(client):
    resp = client.get("/api/v1/edge/discovery/scan", headers=_auth("not-a-jwt"))
    assert resp.status_code == 401


def test_scan_rejects_token_signed_by_wrong_key(client, other_rsa_keypair, make_evidence_token):
    other_private, _ = other_rsa_keypair
    token = make_evidence_token(
        tenant_id=TENANT,
        site_id=SITE,
        scopes=["discovery:read"],
        signing_key=other_private,
    )
    resp = client.get("/api/v1/edge/discovery/scan", headers=_auth(token))
    assert resp.status_code == 401


def test_scan_rejects_token_without_discovery_scope(client, make_evidence_token):
    token = make_evidence_token(
        tenant_id=TENANT, site_id=SITE, scopes=["evidence:read"]
    )
    resp = client.get("/api/v1/edge/discovery/scan", headers=_auth(token))
    assert resp.status_code == 401


def test_scan_rejects_token_for_different_tenant(client, make_evidence_token):
    token = make_evidence_token(
        tenant_id="99999999-9999-9999-9999-999999999999",
        site_id=SITE,
        scopes=["discovery:read"],
    )
    resp = client.get("/api/v1/edge/discovery/scan", headers=_auth(token))
    assert resp.status_code == 401


# ── happy path ────────────────────────────────────────────────────────────


def test_scan_returns_discovered_devices_with_valid_token(client, make_evidence_token):
    token = make_evidence_token(tenant_id=TENANT, site_id=SITE, scopes=["discovery:read"])
    resp = client.get("/api/v1/edge/discovery/scan", headers=_auth(token))
    assert resp.status_code == 200

    body = resp.get_json()
    assert body["status"] == "success"
    devices = body["data"]["devices"]
    assert len(devices) == 1
    device = devices[0]
    assert device["source_ip"] == "192.168.1.64"
    assert device["suggested_rtsp_url"] == "rtsp://192.168.1.64:554/"
    assert device["xaddrs"] == ["http://192.168.1.64/onvif/device_service"]
    # enrich_device_info=False in the fixture — no GetDeviceInformation call attempted
    assert device["device_info"] is None


def test_scan_drops_suggested_url_for_device_with_spoofed_source_ip(
    trust_anchor, make_evidence_token
):
    def _spoofed_devices(*args, **kwargs):
        return [DiscoveredDevice(source_ip="127.0.0.1", xaddrs=[], types=[], scopes=[])]

    app = create_app(
        trust_anchor=trust_anchor, discover_devices_fn=_spoofed_devices, enrich_device_info=False
    )
    app.testing = True
    client = app.test_client()

    token = make_evidence_token(tenant_id=TENANT, site_id=SITE, scopes=["discovery:read"])
    resp = client.get("/api/v1/edge/discovery/scan", headers=_auth(token))

    assert resp.status_code == 200
    device = resp.get_json()["data"]["devices"][0]
    assert device["suggested_rtsp_url"] is None


def test_scan_failure_returns_502_not_a_stack_trace(trust_anchor, make_evidence_token):
    def _raising_scan(*args, **kwargs):
        raise OSError("network unreachable")

    app = create_app(trust_anchor=trust_anchor, discover_devices_fn=_raising_scan)
    app.testing = True
    client = app.test_client()

    token = make_evidence_token(tenant_id=TENANT, site_id=SITE, scopes=["discovery:read"])
    resp = client.get("/api/v1/edge/discovery/scan", headers=_auth(token))

    assert resp.status_code == 502
    assert resp.get_json()["status"] == "error"


def test_scan_passes_configured_timeout_and_cap_to_scan_fn(trust_anchor, make_evidence_token):
    captured = {}

    def _capturing_scan(*, timeout_seconds, max_responses):
        captured["timeout_seconds"] = timeout_seconds
        captured["max_responses"] = max_responses
        return []

    app = create_app(
        trust_anchor=trust_anchor,
        discover_devices_fn=_capturing_scan,
        timeout_seconds=1.5,
        max_responses=7,
    )
    app.testing = True
    client = app.test_client()

    token = make_evidence_token(tenant_id=TENANT, site_id=SITE, scopes=["discovery:read"])
    resp = client.get("/api/v1/edge/discovery/scan", headers=_auth(token))

    assert resp.status_code == 200
    assert captured == {"timeout_seconds": 1.5, "max_responses": 7}


def test_scan_enriches_with_device_information_when_enabled(trust_anchor, make_evidence_token):
    def _devices_with_xaddr(*args, **kwargs):
        return [
            DiscoveredDevice(
                source_ip="192.168.1.64",
                xaddrs=["http://192.168.1.64/onvif/device_service"],
            )
        ]

    def _fake_fetch(xaddr, http_client=None, timeout=5.0):
        from app.onvif_discovery import DeviceInformation

        return DeviceInformation(
            manufacturer="Intelbras",
            model="VIP 1230",
            firmware_version="1.0",
            serial_number="SN1",
            hardware_id="HW1",
        )

    app = create_app(
        trust_anchor=trust_anchor,
        discover_devices_fn=_devices_with_xaddr,
        enrich_device_info=True,
    )
    app.testing = True

    import app.discovery_api as discovery_api_module

    original = discovery_api_module.fetch_device_information
    discovery_api_module.fetch_device_information = _fake_fetch
    try:
        client = app.test_client()
        token = make_evidence_token(tenant_id=TENANT, site_id=SITE, scopes=["discovery:read"])
        resp = client.get("/api/v1/edge/discovery/scan", headers=_auth(token))
    finally:
        discovery_api_module.fetch_device_information = original

    assert resp.status_code == 200
    device = resp.get_json()["data"]["devices"][0]
    assert device["device_info"]["manufacturer"] == "Intelbras"
