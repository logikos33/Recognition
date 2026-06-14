"""Testes — GET/PUT /api/cameras/<id>/models (atribuição de modelo por câmera).

Repositórios mockados — valida: validação de módulo, tenant isolation
(câmera e modelo devem ser do tenant do JWT), set e unset de modelo.
"""
import uuid
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.cameras.model_handlers as model_handlers

TENANT = "11111111-1111-1111-1111-111111111111"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"
MODEL_ID = "55555555-5555-5555-5555-555555555555"


def _auth_header(app, tenant_id=TENANT):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "tenant_test",
                "role": "admin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _assignment_row(epi=None, quality=None, counting=None):
    return {
        "id": CAMERA_ID,
        "model_epi_id": epi,
        "model_quality_id": quality,
        "model_counting_id": counting,
    }


@pytest.fixture
def mocked_repos(monkeypatch):
    camera_repo = MagicMock()
    training_repo = MagicMock()
    monkeypatch.setattr(model_handlers, "_get_camera_repo", lambda: camera_repo)
    monkeypatch.setattr(model_handlers, "_get_training_repo", lambda: training_repo)
    monkeypatch.setattr(model_handlers, "_notify_model_assignment", MagicMock())
    return camera_repo, training_repo


class TestGetCameraModels:
    def test_returns_assignments(self, app, client, mocked_repos):
        camera_repo, _ = mocked_repos
        camera_repo.get_model_assignments.return_value = _assignment_row(epi=MODEL_ID)

        resp = client.get(f"/api/cameras/{CAMERA_ID}/models", headers=_auth_header(app))
        assert resp.status_code == 200
        models = resp.get_json()["data"]["models"]
        assert models == {"epi": MODEL_ID, "quality": None, "counting": None}
        camera_repo.get_model_assignments.assert_called_with(CAMERA_ID, TENANT)

    def test_camera_not_found_or_other_tenant(self, app, client, mocked_repos):
        camera_repo, _ = mocked_repos
        camera_repo.get_model_assignments.return_value = None
        resp = client.get(f"/api/cameras/{CAMERA_ID}/models", headers=_auth_header(app))
        assert resp.status_code == 404

    def test_requires_jwt(self, client, mocked_repos):
        resp = client.get(f"/api/cameras/{CAMERA_ID}/models")
        assert resp.status_code == 401


class TestPutCameraModels:
    def test_assigns_model_validating_tenant_ownership(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_model_assignments.return_value = _assignment_row()
        training_repo.get_model_for_tenant.return_value = {"id": MODEL_ID, "name": "best"}
        camera_repo.set_model_assignment.return_value = _assignment_row(epi=MODEL_ID)

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/models",
            headers=_auth_header(app),
            json={"module": "epi", "model_id": MODEL_ID},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["models"]["epi"] == MODEL_ID
        # Modelo validado contra o tenant do JWT
        args = training_repo.get_model_for_tenant.call_args.args
        assert str(args[0]) == MODEL_ID
        assert args[1] == TENANT
        camera_repo.set_model_assignment.assert_called_once_with(
            CAMERA_ID, TENANT, "epi", MODEL_ID
        )

    def test_rejects_model_from_other_tenant(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_model_assignments.return_value = _assignment_row()
        training_repo.get_model_for_tenant.return_value = None  # não é do tenant

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/models",
            headers=_auth_header(app),
            json={"module": "epi", "model_id": MODEL_ID},
        )
        assert resp.status_code == 404
        camera_repo.set_model_assignment.assert_not_called()

    def test_invalid_module_rejected(self, app, client, mocked_repos):
        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/models",
            headers=_auth_header(app),
            json={"module": "fueling", "model_id": MODEL_ID},
        )
        assert resp.status_code == 400

    def test_invalid_model_uuid_rejected(self, app, client, mocked_repos):
        camera_repo, _ = mocked_repos
        camera_repo.get_model_assignments.return_value = _assignment_row()
        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/models",
            headers=_auth_header(app),
            json={"module": "epi", "model_id": "not-a-uuid"},
        )
        assert resp.status_code == 400

    def test_camera_not_found(self, app, client, mocked_repos):
        camera_repo, _ = mocked_repos
        camera_repo.get_model_assignments.return_value = None
        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/models",
            headers=_auth_header(app),
            json={"module": "epi", "model_id": MODEL_ID},
        )
        assert resp.status_code == 404

    def test_unassign_with_null_model_id(self, app, client, mocked_repos):
        camera_repo, training_repo = mocked_repos
        camera_repo.get_model_assignments.return_value = _assignment_row(epi=MODEL_ID)
        camera_repo.set_model_assignment.return_value = _assignment_row()

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/models",
            headers=_auth_header(app),
            json={"module": "epi", "model_id": None},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["models"]["epi"] is None
        training_repo.get_model_for_tenant.assert_not_called()
        camera_repo.set_model_assignment.assert_called_once_with(
            CAMERA_ID, TENANT, "epi", None
        )
