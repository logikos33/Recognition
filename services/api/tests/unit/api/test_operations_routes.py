"""Tests: operations/routes.py — template_id (B3), pausar/retomar (B1),
último disparo na listagem (B10).

Segue o padrão mock-based de test_scenarios_routes.py: repository mockado via
patch em `_get_repo`, sem banco real.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
CAMERA_ID = str(uuid4())
OTHER_TENANT_OP_ID = 999


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "role": "operator",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_repo(**overrides):
    repo = MagicMock()
    repo.get_by_id.return_value = overrides.get("get_by_id")
    repo.create.return_value = overrides.get("create")
    repo.set_status.return_value = overrides.get("set_status")
    repo.list_by_camera.return_value = overrides.get("list_by_camera", [])
    return repo


def _patch_repo(repo):
    return patch("app.api.v1.operations.routes._get_repo", return_value=repo)


# ---------------------------------------------------------------------------
# POST /api/cameras/<camera_id>/operations — B3: template_id na criação
# ---------------------------------------------------------------------------

class TestCreateOperationTemplateId:

    def test_template_id_forwarded_to_repo(self, client, auth_headers):
        repo = _mock_repo(create={"id": 1, "template_id": "epi", "version": 1})
        with _patch_repo(repo), \
             patch("app.api.v1.operations.routes.OperationTypeRegistry") as mock_reg, \
             patch("app.api.v1.operations.routes._publish_operation_reload"):
            op_class = MagicMock()
            op_class.return_value.validate_config.return_value = []
            mock_reg.get.return_value = op_class
            resp = client.post(
                f"/api/cameras/{CAMERA_ID}/operations",
                json={
                    "type_id": "position", "name": "Zona X", "config": {},
                    "template_id": "epi",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 201
        assert repo.create.call_args[0][6] == "epi"
        assert resp.get_json()["data"]["operation"]["template_id"] == "epi"

    def test_template_id_optional_defaults_to_none(self, client, auth_headers):
        repo = _mock_repo(create={"id": 1, "template_id": None, "version": 1})
        with _patch_repo(repo), \
             patch("app.api.v1.operations.routes.OperationTypeRegistry") as mock_reg, \
             patch("app.api.v1.operations.routes._publish_operation_reload"):
            op_class = MagicMock()
            op_class.return_value.validate_config.return_value = []
            mock_reg.get.return_value = op_class
            resp = client.post(
                f"/api/cameras/{CAMERA_ID}/operations",
                json={"type_id": "position", "name": "Zona X", "config": {}},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        assert repo.create.call_args[0][6] is None


# ---------------------------------------------------------------------------
# GET /api/cameras/<camera_id>/operations — B10: último disparo
# ---------------------------------------------------------------------------

class TestListOperationsLastEventAt:

    def test_last_event_at_present_in_response(self, client, auth_headers):
        rows = [{
            "id": 1, "name": "Zona X", "template_id": "epi",
            "last_event_at": "2026-08-29T14:32:00Z",
        }]
        repo = _mock_repo(list_by_camera=rows)
        with _patch_repo(repo):
            resp = client.get(f"/api/cameras/{CAMERA_ID}/operations", headers=auth_headers)
        assert resp.status_code == 200
        ops = resp.get_json()["data"]["operations"]
        assert ops[0]["last_event_at"] == "2026-08-29T14:32:00Z"

    def test_never_triggered_has_null_last_event_at(self, client, auth_headers):
        rows = [{"id": 1, "name": "Zona X", "template_id": "epi", "last_event_at": None}]
        repo = _mock_repo(list_by_camera=rows)
        with _patch_repo(repo):
            resp = client.get(f"/api/cameras/{CAMERA_ID}/operations", headers=auth_headers)
        assert resp.get_json()["data"]["operations"][0]["last_event_at"] is None


# ---------------------------------------------------------------------------
# POST /api/operations/<id>/pause and /resume — B1
# ---------------------------------------------------------------------------

class TestPauseOperation:

    def test_pause_sets_status_inactive(self, client, auth_headers):
        existing = {"id": 5, "tenant_id": TENANT_ID, "status": "active"}
        updated = {"id": 5, "tenant_id": TENANT_ID, "status": "inactive"}
        repo = _mock_repo(get_by_id=existing, set_status=updated)
        with _patch_repo(repo), patch("app.api.v1.operations.routes._publish_operation_reload"):
            resp = client.post("/api/operations/5/pause", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["operation"]["status"] == "inactive"
        repo.set_status.assert_called_once_with(TENANT_ID, 5, "inactive")

    def test_pause_cross_tenant_returns_404(self, client, auth_headers):
        """C-01: operação de outro tenant nunca aparece — 404, nunca 403."""
        repo = _mock_repo(get_by_id=None)
        with _patch_repo(repo):
            resp = client.post(f"/api/operations/{OTHER_TENANT_OP_ID}/pause", headers=auth_headers)
        assert resp.status_code == 404
        repo.set_status.assert_not_called()

    def test_pause_no_token_returns_401(self, client):
        assert client.post("/api/operations/5/pause").status_code == 401


class TestResumeOperation:

    def test_resume_sets_status_active(self, client, auth_headers):
        existing = {"id": 5, "tenant_id": TENANT_ID, "status": "inactive"}
        updated = {"id": 5, "tenant_id": TENANT_ID, "status": "active"}
        repo = _mock_repo(get_by_id=existing, set_status=updated)
        with _patch_repo(repo), patch("app.api.v1.operations.routes._publish_operation_reload"):
            resp = client.post("/api/operations/5/resume", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["operation"]["status"] == "active"
        repo.set_status.assert_called_once_with(TENANT_ID, 5, "active")

    def test_resume_cross_tenant_returns_404(self, client, auth_headers):
        repo = _mock_repo(get_by_id=None)
        with _patch_repo(repo):
            resp = client.post(f"/api/operations/{OTHER_TENANT_OP_ID}/resume", headers=auth_headers)
        assert resp.status_code == 404
        repo.set_status.assert_not_called()
