"""
Unit — GET /api/v1/edge/software/target (OTA bare-metal, ADR-0057 item 10).

Canal pull cloud→edge consumido pelo app/ota/updater.py do edge-sync-agent.
A nuvem só INDICA o target_ref; nunca aplica/empurra nada no device.

Segurança: mesmo device auth RS256 do config-poll (401 sem token, 403 sem
escopo config:read, cross-tenant → 404 — não vaza existência de device C-01).
"""
from unittest.mock import MagicMock

import app.api.v1.edge.routes as edge_routes
import app.core.device_auth as device_auth

TENANT = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT = "99999999-9999-9999-9999-999999999999"
SITE_ID = "55555555-5555-5555-5555-555555555555"
DEVICE_ID = "device-abc123"

CONFIG_READ = "config:read"
HEARTBEAT_WRITE = "heartbeat:write"


def _authed(*scopes: str):
    granted = list(scopes) or [CONFIG_READ]
    return lambda req: (TENANT, SITE_ID, DEVICE_ID, granted)


def _device_row(tenant_id=TENANT, channel="dev"):
    return {
        "id": "device-pk-1",
        "tenant_id": tenant_id,
        "site_id": SITE_ID,
        "device_id": DEVICE_ID,
        "revoked": False,
        "channel": channel,
    }


def test_no_token_returns_401(client):
    resp = client.get("/api/v1/edge/software/target")
    assert resp.status_code == 401


def test_device_without_config_read_scope_returns_403(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(HEARTBEAT_WRITE))
    resp = client.get(
        "/api/v1/edge/software/target", headers={"Authorization": "Bearer so-heartbeat"}
    )
    assert resp.status_code == 403


def test_returns_target_ref_for_devices_channel(client, monkeypatch):
    repo = MagicMock()
    repo.get_device_by_device_id.return_value = _device_row(channel="dev")
    channel_repo = MagicMock()
    channel_repo.get_target_ref.return_value = "abc123"
    monkeypatch.setattr(edge_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(edge_routes, "_get_software_channel_repo", lambda: channel_repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))

    resp = client.get(
        "/api/v1/edge/software/target", headers={"Authorization": "Bearer d"}
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["target_ref"] == "abc123"
    assert body["data"]["channel"] == "dev"
    channel_repo.get_target_ref.assert_called_once_with("dev")


def test_no_target_published_yet_returns_null_not_error(client, monkeypatch):
    repo = MagicMock()
    repo.get_device_by_device_id.return_value = _device_row()
    channel_repo = MagicMock()
    channel_repo.get_target_ref.return_value = None
    monkeypatch.setattr(edge_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(edge_routes, "_get_software_channel_repo", lambda: channel_repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))

    resp = client.get(
        "/api/v1/edge/software/target", headers={"Authorization": "Bearer d"}
    )

    assert resp.status_code == 200
    assert resp.get_json()["data"]["target_ref"] is None


def test_defaults_to_dev_channel_when_device_channel_is_missing(client, monkeypatch):
    """Devices enrolled before migration 106 won't have `channel` populated by
    the ALTER TABLE's own DEFAULT if somehow read as None — fall back to 'dev'."""
    repo = MagicMock()
    row = _device_row()
    row["channel"] = None
    repo.get_device_by_device_id.return_value = row
    channel_repo = MagicMock()
    channel_repo.get_target_ref.return_value = "xyz"
    monkeypatch.setattr(edge_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(edge_routes, "_get_software_channel_repo", lambda: channel_repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))

    client.get("/api/v1/edge/software/target", headers={"Authorization": "Bearer d"})

    channel_repo.get_target_ref.assert_called_once_with("dev")


def test_cross_tenant_device_returns_404_not_403(client, monkeypatch):
    """C-01: a defense-in-depth re-check here must not leak existence across
    tenants — 404, not 403, if the fetched row's tenant somehow diverges."""
    repo = MagicMock()
    repo.get_device_by_device_id.return_value = _device_row(tenant_id=OTHER_TENANT)
    monkeypatch.setattr(edge_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))

    resp = client.get(
        "/api/v1/edge/software/target", headers={"Authorization": "Bearer d"}
    )
    assert resp.status_code == 404


def test_unknown_device_returns_404(client, monkeypatch):
    repo = MagicMock()
    repo.get_device_by_device_id.return_value = None
    monkeypatch.setattr(edge_routes, "_get_repo", lambda: repo)
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))

    resp = client.get(
        "/api/v1/edge/software/target", headers={"Authorization": "Bearer d"}
    )
    assert resp.status_code == 404


def test_route_registered(app):
    rules = {str(r) for r in app.url_map.iter_rules()}
    assert "/api/v1/edge/software/target" in rules
