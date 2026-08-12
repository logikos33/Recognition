"""
Unit — PATCH parcial de /api/cameras/<id>/config (WS10 + eixo COLETA).

Aceita fps_target, quality_preset e/ou collection_subtype (pelo menos um);
valida enums só dos campos presentes; body vazio → 400; todos os campos
seguem funcionando isoladamente ou combinados (compat).
Repositório usa COALESCE — campo ausente mantém o valor atual.

collection_subtype (0=principal/alta, 1=substream) é o eixo COLETA (frame
de treino) — independente de fps_target/quality_preset (eixo OPERAÇÃO).
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
        "collection_subtype": 0,
    }
    repo.update_config.return_value = {
        "id": CAMERA_ID,
        "tenant_id": TENANT,
        "site_id": None,
        "fps_target": 10,
        "quality_preset": "medium",
        "collection_subtype": 0,
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


class TestPatchConfigCollectionSubtype:
    """Eixo COLETA: collection_subtype (0=principal, 1=substream)."""

    def test_collection_subtype_zero_returns_200(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"collection_subtype": 0},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        args = camera_repo.update_config.call_args[0]
        assert args[2] is None  # fps_target
        assert args[3] is None  # quality_preset
        assert args[4] == 0  # collection_subtype

    def test_collection_subtype_one_returns_200(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"collection_subtype": 1},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        args = camera_repo.update_config.call_args[0]
        assert args[4] == 1

    def test_collection_subtype_only_patch_leaves_fps_quality_untouched(
        self, app, client, camera_repo
    ):
        """PATCH parcial só de collection_subtype: fps_target/quality_preset
        vão como None (COALESCE no repo mantém o valor atual)."""
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"collection_subtype": 1},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        camera_repo.update_config.assert_called_once()
        args = camera_repo.update_config.call_args[0]
        assert args[2] is None
        assert args[3] is None
        assert args[4] == 1

    def test_invalid_collection_subtype_2_returns_400(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"collection_subtype": 2},
            headers=_auth(app),
        )
        assert resp.status_code == 400
        camera_repo.update_config.assert_not_called()

    def test_bool_collection_subtype_returns_400(self, app, client, camera_repo):
        """bool é subclasse de int em Python — rejeitado explicitamente
        (mesmo padrão do handler para fps_target)."""
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"collection_subtype": True},
            headers=_auth(app),
        )
        assert resp.status_code == 400
        camera_repo.update_config.assert_not_called()

    def test_all_three_fields_together(self, app, client, camera_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 15, "quality_preset": "low", "collection_subtype": 1},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        args = camera_repo.update_config.call_args[0]
        assert args[2] == 15
        assert args[3] == "low"
        assert args[4] == 1


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
        assert "COALESCE(%s, collection_subtype)" in query
        assert "tenant_id = %s" in query
        assert params == (10, None, None, CAMERA_ID, TENANT)

    def test_sql_coalesce_includes_collection_subtype_value(self):
        repo, cur = self._repo_with_cursor()
        repo.update_config(uuid.UUID(CAMERA_ID), TENANT, None, None, 1)
        params = cur.execute.call_args[0][1]
        assert params == (None, None, 1, CAMERA_ID, TENANT)
