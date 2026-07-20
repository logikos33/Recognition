"""
Unit — S1: autorização por escopo em POST /api/v1/edge/events/ingest.

Antes do S1 a ingestão de eventos do device não checava escopo. Agora exige
events:write. authenticate_device é mockado (sem RS256 real).
"""
from unittest.mock import MagicMock

import app.api.v1.edge_events.routes as evt_routes
import app.core.device_auth as device_auth

TENANT = "11111111-1111-1111-1111-111111111111"
SITE_ID = "55555555-5555-5555-5555-555555555555"
DEVICE_ID = "device-abc123"

_BODY = {"events": [{"event_type": "detection", "camera_id": "cam-1", "payload": {}}]}


# Escopos como STRING (robusto a enums mockado em sys.modules).
EVENTS_WRITE = "events:write"
CONFIG_READ = "config:read"


def _authed(*scopes: str):
    granted = list(scopes)
    return lambda req: (TENANT, SITE_ID, DEVICE_ID, granted)


class TestEventsIngestScope:
    def test_with_events_write_returns_200(self, client, monkeypatch):
        repo = MagicMock()
        repo.ingest.return_value = {"id": 1}
        monkeypatch.setattr(evt_routes, "_get_repo", lambda: repo)
        monkeypatch.setattr(
            device_auth, "authenticate_device", _authed(EVENTS_WRITE)
        )
        resp = client.post(
            "/api/v1/edge/events/ingest",
            json=_BODY,
            headers={"Authorization": "Bearer device-token"},
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["ingested"] == 1
        # Escopo tenant/site vem do device auth, nunca do corpo (C-01)
        assert repo.ingest.call_args.kwargs["tenant_id"] == TENANT
        assert repo.ingest.call_args.kwargs["site_id"] == SITE_ID

    def test_without_scope_returns_403(self, client, monkeypatch):
        repo = MagicMock()
        monkeypatch.setattr(evt_routes, "_get_repo", lambda: repo)
        monkeypatch.setattr(
            device_auth, "authenticate_device", _authed(CONFIG_READ)
        )
        resp = client.post(
            "/api/v1/edge/events/ingest",
            json=_BODY,
            headers={"Authorization": "Bearer so-config"},
        )
        assert resp.status_code == 403
        repo.ingest.assert_not_called()

    def test_no_device_returns_401(self, client, monkeypatch):
        monkeypatch.setattr(device_auth, "authenticate_device", lambda req: None)
        resp = client.post(
            "/api/v1/edge/events/ingest",
            json=_BODY,
            headers={"Authorization": "Bearer invalido"},
        )
        assert resp.status_code == 401
