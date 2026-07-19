"""
Unit — S5: rotas admin de edge que estavam sem gate de role.

- GET  /api/v1/edge/commands           (console de comandos) — admin only
- PATCH /api/v1/site-gateways/<id>/status                     — admin only

Antes: qualquer usuário JWT do tenant podia listar comandos do site / alterar
o status do gateway. Agora exigem admin/superadmin (gateways:manage no gateway).
"""
import uuid
from unittest.mock import MagicMock

from flask_jwt_extended import create_access_token

import app.api.v1.edge_commands.routes as cmd_routes
import app.api.v1.site_gateways.routes as gw_routes

TENANT = "11111111-1111-1111-1111-111111111111"
SITE_ID = "55555555-5555-5555-5555-555555555555"


def _auth(app, role: str) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": TENANT,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


class TestListCommandsAdminGate:
    def test_operator_forbidden(self, app, client, monkeypatch):
        repo = MagicMock()
        monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
        resp = client.get(
            f"/api/v1/edge/commands?site_id={SITE_ID}", headers=_auth(app, "operator")
        )
        assert resp.status_code == 403
        repo.list_by_site.assert_not_called()

    def test_admin_allowed(self, app, client, monkeypatch):
        repo = MagicMock()
        repo.list_by_site.return_value = []
        monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
        resp = client.get(
            f"/api/v1/edge/commands?site_id={SITE_ID}", headers=_auth(app, "admin")
        )
        assert resp.status_code == 200
        repo.list_by_site.assert_called_once()


class TestGatewayStatusAdminGate:
    def test_operator_forbidden(self, app, client, monkeypatch):
        repo = MagicMock()
        monkeypatch.setattr(gw_routes, "_get_repo", lambda: repo)
        resp = client.patch(
            f"/api/v1/site-gateways/{SITE_ID}/status",
            json={"status": "active"},
            headers=_auth(app, "operator"),
        )
        assert resp.status_code == 403
        repo.update_status.assert_not_called()

    def test_admin_allowed(self, app, client, monkeypatch):
        repo = MagicMock()
        repo.update_status.return_value = {"site_id": SITE_ID, "status": "active"}
        monkeypatch.setattr(gw_routes, "_get_repo", lambda: repo)
        resp = client.patch(
            f"/api/v1/site-gateways/{SITE_ID}/status",
            json={"status": "active"},
            headers=_auth(app, "admin"),
        )
        assert resp.status_code == 200
        repo.update_status.assert_called_once()
