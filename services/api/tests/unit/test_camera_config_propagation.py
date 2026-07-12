"""
Unit — Propagação cloud→edge no PATCH /api/cameras/<id>/config (WS10).

Após update OK, se a câmera tem site_id, cria edge_command
'update_camera_config' (best-effort — NUNCA falha o PATCH).
Response ganha campo aditivo 'propagation': {'queued', 'reason'}.
"""
import uuid
from unittest.mock import MagicMock

from flask_jwt_extended import create_access_token

import app.api.v1.cameras.config_handler as config_handler
from app.domain.services.camera_service import CameraService

TENANT = "11111111-1111-1111-1111-111111111111"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"
SITE_ID = "55555555-5555-5555-5555-555555555555"


def _auth(app, role: str = "operator", tenant_id: str = TENANT) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _setup(monkeypatch, site_id: str | None):
    camera_repo = MagicMock()
    camera_repo.get_by_id.return_value = {
        "id": CAMERA_ID,
        "tenant_id": TENANT,
        "site_id": site_id,
    }
    camera_repo.update_config.return_value = {
        "id": CAMERA_ID,
        "tenant_id": TENANT,
        "site_id": site_id,
        "fps_target": 10,
        "quality_preset": "medium",
    }
    service = CameraService(camera_repo, fernet_key="")
    monkeypatch.setattr(config_handler, "_get_camera_service", lambda: service)

    command_repo = MagicMock()
    command_repo.create.return_value = {"id": str(uuid.uuid4()), "status": "pending"}
    monkeypatch.setattr(config_handler, "_get_edge_command_repo", lambda: command_repo)
    return command_repo


class TestConfigPropagation:

    def test_camera_with_site_queues_edge_command(self, app, client, monkeypatch):
        command_repo = _setup(monkeypatch, SITE_ID)
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["propagation"] == {"queued": True, "reason": None}

        kwargs = command_repo.create.call_args.kwargs
        assert kwargs["tenant_id"] == TENANT
        assert kwargs["site_id"] == SITE_ID
        assert kwargs["command_type"] == "update_camera_config"
        assert kwargs["payload"]["camera_id"] == CAMERA_ID
        assert kwargs["payload"]["fps_target"] == 10
        assert kwargs["payload"]["quality_preset"] == "medium"
        assert kwargs["command_id"].startswith(f"camcfg:{CAMERA_ID}:")

    def test_camera_without_site_returns_no_site(self, app, client, monkeypatch):
        command_repo = _setup(monkeypatch, None)
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["propagation"] == {"queued": False, "reason": "no_site"}
        command_repo.create.assert_not_called()

    def test_queue_failure_never_fails_patch(self, app, client, monkeypatch):
        """Best-effort: exceção na fila → PATCH 200 com reason='error'."""
        command_repo = _setup(monkeypatch, SITE_ID)
        command_repo.create.side_effect = RuntimeError("db down")
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["propagation"] == {"queued": False, "reason": "error"}
        assert data["fps_target"] == 10

    def test_operator_can_trigger_propagation(self, app, client, monkeypatch):
        """Producer é server-side: operator (sem acesso à rota POST admin-only
        de /edge/commands) consegue enfileirar via PATCH — intencional (WS10)."""
        command_repo = _setup(monkeypatch, SITE_ID)
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"quality_preset": "high"},
            headers=_auth(app, role="operator"),
        )
        assert resp.status_code == 200
        command_repo.create.assert_called_once()
