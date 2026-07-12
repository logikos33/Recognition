"""
Unit — PATCH parcial de /api/cameras/<id>/config (WS10).

Aceita fps_target e/ou quality_preset (pelo menos um); valida enums só dos
campos presentes; body vazio → 400; ambos os campos seguem funcionando (compat).
Repositório usa COALESCE — campo ausente mantém o valor atual.
"""
import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.cameras.config_handler as config_handler
from app.domain.services.camera_service import CameraService
from app.infrastructure.database.repositories.camera_repository import CameraRepository

TENANT = "11111111-1111-1111-1111-111111111111"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"


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


@pytest.fixture()
def camera_repo(monkeypatch):
    repo = MagicMock()
    repo.get_by_id.return_value = {
        "id": CAMERA_ID,
        "tenant_id": TENANT,
        "site_id": None,
        "fps_target": 5,
        "quality_preset": "medium",
    }
    repo.update_config.return_value = {
        "id": CAMERA_ID,
        "tenant_id": TENANT,
        "site_id": None,
        "fps_target": 10,
        "quality_preset": "medium",
    }
    service = CameraService(repo, fernet_key="")
    monkeypatch.setattr(config_handler, "_get_camera_service", lambda: service)
    monkeypatch.setattr(config_handler, "_get_edge_command_repo", lambda: MagicMock())
    return repo


class TestPatchConfigPartial:

    def test_only_fps_target_returns_200(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        # quality_preset ausente → None no repo (COALESCE mantém valor atual)
        args = camera_repo.update_config.call_args[0]
        assert args[2] == 10
        assert args[3] is None

    def test_only_quality_preset_returns_200(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"quality_preset": "high"},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        args = camera_repo.update_config.call_args[0]
        assert args[2] is None
        assert args[3] == "high"

    def test_both_fields_still_work(self, app, client, camera_repo):
        """Compat: body com ambos os campos (cameraService.patchConfig atual)."""
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 15, "quality_preset": "low"},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        args = camera_repo.update_config.call_args[0]
        assert args[2] == 15
        assert args[3] == "low"

    def test_empty_body_returns_400(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={},
            headers=_auth(app),
        )
        assert resp.status_code == 400
        camera_repo.update_config.assert_not_called()

    def test_invalid_fps_returns_400(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 7},
            headers=_auth(app),
        )
        assert resp.status_code == 400

    def test_non_int_fps_returns_400(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": "10"},
            headers=_auth(app),
        )
        assert resp.status_code == 400

    def test_invalid_quality_returns_400(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"quality_preset": "ultra"},
            headers=_auth(app),
        )
        assert resp.status_code == 400


class TestUpdateConfigCoalesceSql:
    """Repo: COALESCE fixo no SQL — zero SQL dinâmico com input (C-05)."""

    @staticmethod
    def _repo_with_cursor():
        cur = MagicMock()
        cur.fetchone.return_value = None

        @contextmanager
        def _conn_ctx():
            conn = MagicMock()
            conn.cursor.return_value = cur
            yield conn

        pool = MagicMock()
        pool.get_connection.side_effect = _conn_ctx
        return CameraRepository(pool), cur

    def test_sql_uses_coalesce_and_tenant_filter(self):
        repo, cur = self._repo_with_cursor()
        repo.update_config(uuid.UUID(CAMERA_ID), TENANT, 10, None)
        query = cur.execute.call_args[0][0]
        params = cur.execute.call_args[0][1]
        assert "COALESCE(%s, fps_target)" in query
        assert "COALESCE(%s, quality_preset)" in query
        assert "tenant_id = %s" in query
        assert params == (10, None, CAMERA_ID, TENANT)
