"""
Testes — Task 045: novos endpoints de modelo por câmera.

Cobre:
  GET  /api/cameras/<id>/available-models
  PUT  /api/cameras/<id>/model  (admin-only, via active_module)
  GET  /api/cameras/<id>/effective-model

Estratégia: repositórios e Redis são mockados — testes são unitários/integração
de camada de rota, sem banco real.
"""
import uuid
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.cameras.model_handlers as model_handlers

TENANT = "11111111-1111-1111-1111-111111111111"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"
MODEL_ID = "55555555-5555-5555-5555-555555555555"


def _token(app, role: str = "admin", tenant_id: str = TENANT) -> dict[str, str]:
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


def _cam_row(
    active_module: str = "epi",
    epi: object = None,
    quality: object = None,
    counting: object = None,
) -> dict:
    return {
        "id": CAMERA_ID,
        "active_module": active_module,
        "model_epi_id": epi,
        "model_quality_id": quality,
        "model_counting_id": counting,
    }


@pytest.fixture()
def mocked_repos(monkeypatch):
    camera_repo = MagicMock()
    training_repo = MagicMock()
    monkeypatch.setattr(model_handlers, "_get_camera_repo", lambda: camera_repo)
    monkeypatch.setattr(model_handlers, "_get_training_repo", lambda: training_repo)
    monkeypatch.setattr(model_handlers, "_notify_model_assignment", MagicMock())
    return camera_repo, training_repo


# ---------------------------------------------------------------------------
# GET /api/cameras/<id>/available-models
# ---------------------------------------------------------------------------

class TestGetAvailableModels:
    def test_no_auth_returns_401(self, client, mocked_repos):
        resp = client.get(f"/api/cameras/{CAMERA_ID}/available-models")
        assert resp.status_code == 401

    def test_camera_not_found_returns_404(self, app, client, mocked_repos):
        camera_repo, _ = mocked_repos
        camera_repo.get_module_and_models.return_value = None

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/available-models",
            headers=_token(app),
        )
        assert resp.status_code == 404

    def test_returns_model_list_for_tenant(self, app, client, mocked_repos):
        import datetime
        camera_repo, training_repo = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row()
        training_repo.list_for_tenant.return_value = [
            {
                "id": MODEL_ID,
                "name": "best_v1",
                "model_path": "tenant/models/best_v1.pt",
                "is_active": True,
                "created_at": datetime.datetime(2026, 1, 1, 12, 0, 0),
            }
        ]

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/available-models",
            headers=_token(app),
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["camera_id"] == CAMERA_ID
        assert body["active_module"] == "epi"
        assert len(body["models"]) == 1
        m = body["models"][0]
        assert m["id"] == MODEL_ID
        assert m["name"] == "best_v1"
        assert m["r2_key"] == "tenant/models/best_v1.pt"
        assert m["active"] is True

        training_repo.list_for_tenant.assert_called_once_with(TENANT)

    def test_empty_model_list(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row()
        training_repo.list_for_tenant.return_value = []

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/available-models",
            headers=_token(app),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["models"] == []


# ---------------------------------------------------------------------------
# PUT /api/cameras/<id>/model  (admin-only, active_module resolved from camera)
# ---------------------------------------------------------------------------

class TestSetCameraModel:
    def test_no_auth_returns_401(self, client, mocked_repos):
        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            json={"model_id": MODEL_ID},
        )
        assert resp.status_code == 401

    def test_non_admin_returns_403(self, app, client, mocked_repos):
        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            headers=_token(app, role="operator"),
            json={"model_id": MODEL_ID},
        )
        assert resp.status_code == 403

    def test_viewer_returns_403(self, app, client, mocked_repos):
        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            headers=_token(app, role="viewer"),
            json={"model_id": MODEL_ID},
        )
        assert resp.status_code == 403

    def test_camera_not_found_returns_404(self, app, client, mocked_repos):
        camera_repo, _ = mocked_repos
        camera_repo.get_module_and_models.return_value = None

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            headers=_token(app),
            json={"model_id": MODEL_ID},
        )
        assert resp.status_code == 404

    def test_unsupported_module_returns_422(self, app, client, mocked_repos):
        camera_repo, _ = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row(active_module="fueling")

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            headers=_token(app),
            json={"model_id": MODEL_ID},
        )
        assert resp.status_code == 422

    def test_invalid_model_uuid_returns_400(self, app, client, mocked_repos):
        camera_repo, _ = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row()

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            headers=_token(app),
            json={"model_id": "not-a-uuid"},
        )
        assert resp.status_code == 400

    def test_model_not_in_tenant_returns_404(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row()
        training_repo.get_model_for_tenant.return_value = None

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            headers=_token(app),
            json={"model_id": MODEL_ID},
        )
        assert resp.status_code == 404
        camera_repo.set_model_assignment.assert_not_called()

    def test_valid_admin_assigns_model(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row(active_module="epi")
        training_repo.get_model_for_tenant.return_value = {"id": MODEL_ID, "name": "v1"}
        camera_repo.set_model_assignment.return_value = _cam_row(epi=MODEL_ID)

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            headers=_token(app, role="admin"),
            json={"model_id": MODEL_ID},
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["module"] == "epi"
        assert body["model_id"] == MODEL_ID
        assert body["models"]["epi"] == MODEL_ID

        camera_repo.set_model_assignment.assert_called_once_with(
            CAMERA_ID, TENANT, "epi", MODEL_ID
        )

    def test_superadmin_can_assign_model(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row()
        training_repo.get_model_for_tenant.return_value = {"id": MODEL_ID}
        camera_repo.set_model_assignment.return_value = _cam_row(epi=MODEL_ID)

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            headers=_token(app, role="superadmin"),
            json={"model_id": MODEL_ID},
        )
        assert resp.status_code == 200

    def test_null_model_id_clears_assignment(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row(epi=MODEL_ID)
        camera_repo.set_model_assignment.return_value = _cam_row()

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/model",
            headers=_token(app),
            json={"model_id": None},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["model_id"] is None
        training_repo.get_model_for_tenant.assert_not_called()
        camera_repo.set_model_assignment.assert_called_once_with(
            CAMERA_ID, TENANT, "epi", None
        )


# ---------------------------------------------------------------------------
# GET /api/cameras/<id>/effective-model
# ---------------------------------------------------------------------------

class TestGetEffectiveModel:
    def test_no_auth_returns_401(self, client, mocked_repos):
        resp = client.get(f"/api/cameras/{CAMERA_ID}/effective-model")
        assert resp.status_code == 401

    def test_camera_not_found_returns_404(self, app, client, mocked_repos):
        camera_repo, _ = mocked_repos
        camera_repo.get_module_and_models.return_value = None

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/effective-model",
            headers=_token(app),
        )
        assert resp.status_code == 404

    def test_returns_override_when_camera_has_model_assigned(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row(
            active_module="epi", epi=MODEL_ID
        )

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/effective-model",
            headers=_token(app),
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["model_id"] == MODEL_ID
        assert body["source"] == "override"
        assert body["module"] == "epi"
        training_repo.get_active_for_tenant.assert_not_called()

    def test_returns_inherited_when_no_override(self, app, client, mocked_repos):
        inherited_id = "66666666-6666-6666-6666-666666666666"
        camera_repo, training_repo = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row(active_module="epi")
        training_repo.get_active_for_tenant.return_value = {"id": inherited_id}

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/effective-model",
            headers=_token(app),
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["model_id"] == inherited_id
        assert body["source"] == "inherited"
        assert body["module"] == "epi"

    def test_inherited_with_no_active_model_returns_null(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_module_and_models.return_value = _cam_row(active_module="quality")
        training_repo.get_active_for_tenant.return_value = None

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/effective-model",
            headers=_token(app),
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["model_id"] is None
        assert body["source"] == "inherited"
        assert body["module"] == "quality"
