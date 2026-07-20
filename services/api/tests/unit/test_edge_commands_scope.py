"""
Unit — S1: autorização por escopo nas rotas de device de /edge/commands.

Antes do S1 estas rotas tinham ZERO teste e nenhuma checagem de escopo: um
device enrolado só com heartbeat:write podia pollar/atualizar comandos.
Agora exigem commands:read (GET /pending) e commands:write (PATCH /<id>).

Padrão: authenticate_device é mockado (sem RS256 real) devolvendo
(tenant, site, device, scopes) — é a fronteira que require_device_scope usa.
"""
from unittest.mock import MagicMock

import app.api.v1.edge_commands.routes as cmd_routes
import app.core.device_auth as device_auth

TENANT = "11111111-1111-1111-1111-111111111111"
SITE_ID = "55555555-5555-5555-5555-555555555555"
DEVICE_ID = "device-abc123"
CMD_ID = "cmd-0001"


# Escopos como STRING (o que require_device_scope compara) — robusto a
# recognition_shared.enums estar mockado em sys.modules por outra suíte.
COMMANDS_READ = "commands:read"
COMMANDS_WRITE = "commands:write"
HEARTBEAT_WRITE = "heartbeat:write"


def _authed(*scopes: str):
    granted = list(scopes)
    return lambda req: (TENANT, SITE_ID, DEVICE_ID, granted)


class TestCommandsPendingScope:
    def test_with_commands_read_returns_200(self, client, monkeypatch):
        repo = MagicMock()
        repo.list_pending.return_value = []
        monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
        monkeypatch.setattr(
            device_auth, "authenticate_device", _authed(COMMANDS_READ)
        )
        resp = client.get(
            "/api/v1/edge/commands/pending",
            headers={"Authorization": "Bearer device-token"},
        )
        assert resp.status_code == 200
        repo.list_pending.assert_called_once()

    def test_without_scope_returns_403(self, client, monkeypatch):
        repo = MagicMock()
        monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
        # Só heartbeat:write — não pode ler comandos
        monkeypatch.setattr(
            device_auth, "authenticate_device", _authed(HEARTBEAT_WRITE)
        )
        resp = client.get(
            "/api/v1/edge/commands/pending",
            headers={"Authorization": "Bearer so-heartbeat"},
        )
        assert resp.status_code == 403
        repo.list_pending.assert_not_called()

    def test_no_device_returns_401(self, client, monkeypatch):
        monkeypatch.setattr(device_auth, "authenticate_device", lambda req: None)
        resp = client.get(
            "/api/v1/edge/commands/pending",
            headers={"Authorization": "Bearer invalido"},
        )
        assert resp.status_code == 401


class TestCommandsPatchScope:
    def test_with_commands_write_returns_200(self, client, monkeypatch):
        repo = MagicMock()
        repo.update_status.return_value = {"command_id": CMD_ID, "status": "done"}
        monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
        monkeypatch.setattr(
            device_auth, "authenticate_device", _authed(COMMANDS_WRITE)
        )
        resp = client.patch(
            f"/api/v1/edge/commands/{CMD_ID}",
            json={"status": "done"},
            headers={"Authorization": "Bearer device-token"},
        )
        assert resp.status_code == 200
        repo.update_status.assert_called_once()

    def test_read_scope_cannot_write_returns_403(self, client, monkeypatch):
        """commands:read não autoriza PATCH (menor privilégio por verbo)."""
        repo = MagicMock()
        monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
        monkeypatch.setattr(
            device_auth, "authenticate_device", _authed(COMMANDS_READ)
        )
        resp = client.patch(
            f"/api/v1/edge/commands/{CMD_ID}",
            json={"status": "done"},
            headers={"Authorization": "Bearer so-read"},
        )
        assert resp.status_code == 403
        repo.update_status.assert_not_called()

    def test_no_device_returns_401(self, client, monkeypatch):
        monkeypatch.setattr(device_auth, "authenticate_device", lambda req: None)
        resp = client.patch(
            f"/api/v1/edge/commands/{CMD_ID}",
            json={"status": "done"},
            headers={"Authorization": "Bearer invalido"},
        )
        assert resp.status_code == 401
