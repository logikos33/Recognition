"""Tests: scenarios/routes.py — camera scenario + operation-types catalog."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
CAMERA_ID = str(uuid4())

_SAMPLE_CAMERA = {
    "id": CAMERA_ID,
    "name": "Cam-Test",
    "site_id": None,
    "schedule_rules": [],
}


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


def _mock_repos(camera=None, modules=None, classes=None, operations=None, alert_rules=None):
    cam_repo = MagicMock()
    cam_repo.get_by_id_and_tenant.return_value = camera

    mod_repo = MagicMock()
    mod_repo.get_by_tenant.return_value = modules or []
    mod_repo.get_classes.return_value = classes or []

    op_repo = MagicMock()
    op_repo.list_by_camera.return_value = operations or []

    alert_repo = MagicMock()
    alert_repo.list_for_camera_scenario.return_value = alert_rules or []

    return cam_repo, mod_repo, op_repo, alert_repo


def _patch_repos(cam_repo, mod_repo, op_repo, alert_repo):
    return (
        patch("app.api.v1.scenarios.routes._get_camera_repo", return_value=cam_repo),
        patch("app.api.v1.scenarios.routes._get_module_repo", return_value=mod_repo),
        patch("app.api.v1.scenarios.routes._get_operation_repo", return_value=op_repo),
        patch("app.api.v1.scenarios.routes._get_alert_repo", return_value=alert_repo),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/cameras/<camera_id>/scenario
# ---------------------------------------------------------------------------

class TestGetCameraScenario:

    def test_no_token_returns_401(self, client):
        assert client.get(f"/api/v1/cameras/{CAMERA_ID}/scenario").status_code == 401

    def test_camera_not_found_returns_404(self, client, auth_headers):
        cam_repo, mod_repo, op_repo, alert_repo = _mock_repos(camera=None)
        with _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)[0], \
             _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)[1], \
             _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)[2], \
             _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)[3]:
            resp = client.get(f"/api/v1/cameras/{CAMERA_ID}/scenario", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_complete_scenario_structure(self, client, auth_headers):
        cam_repo, mod_repo, op_repo, alert_repo = _mock_repos(camera=_SAMPLE_CAMERA)
        patches = _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)
        with patches[0], patches[1], patches[2], patches[3]:
            resp = client.get(f"/api/v1/cameras/{CAMERA_ID}/scenario", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        scenario = data["data"]["scenario"]
        assert scenario["camera"]["name"] == "Cam-Test"
        assert "modules" in scenario
        assert "operations" in scenario
        assert "alert_rules" in scenario
        assert "schedule" in scenario

    def test_disabled_modules_excluded(self, client, auth_headers):
        modules = [
            {"module_code": "epi", "enabled": True, "config": None,
             "activated_at": None, "expires_at": None},
            {"module_code": "fueling", "enabled": False, "config": None,
             "activated_at": None, "expires_at": None},
        ]
        cam_repo, mod_repo, op_repo, alert_repo = _mock_repos(
            camera=_SAMPLE_CAMERA, modules=modules
        )
        patches = _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)
        with patches[0], patches[1], patches[2], patches[3]:
            resp = client.get(f"/api/v1/cameras/{CAMERA_ID}/scenario", headers=auth_headers)
        modules_out = resp.get_json()["data"]["scenario"]["modules"]
        assert len(modules_out) == 1
        assert modules_out[0]["module_code"] == "epi"

    def test_operations_and_alert_rules_included(self, client, auth_headers):
        ops = [{"id": "op1", "type": "count_line", "config": {}}]
        rules = [{"id": "r1", "violation_type": "no_helmet", "enabled": True}]
        cam_repo, mod_repo, op_repo, alert_repo = _mock_repos(
            camera=_SAMPLE_CAMERA, operations=ops, alert_rules=rules
        )
        patches = _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)
        with patches[0], patches[1], patches[2], patches[3]:
            resp = client.get(f"/api/v1/cameras/{CAMERA_ID}/scenario", headers=auth_headers)
        scenario = resp.get_json()["data"]["scenario"]
        assert len(scenario["operations"]) == 1
        assert len(scenario["alert_rules"]) == 1

    def test_tenant_isolation_wrong_camera_returns_404(self, client, auth_headers):
        other_camera_id = str(uuid4())
        cam_repo, mod_repo, op_repo, alert_repo = _mock_repos(camera=None)
        patches = _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)
        with patches[0], patches[1], patches[2], patches[3]:
            resp = client.get(f"/api/v1/cameras/{other_camera_id}/scenario", headers=auth_headers)
        assert resp.status_code == 404

    def test_camera_id_passed_to_repo(self, client, auth_headers):
        cam_repo, mod_repo, op_repo, alert_repo = _mock_repos(camera=_SAMPLE_CAMERA)
        patches = _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)
        with patches[0], patches[1], patches[2], patches[3]:
            client.get(f"/api/v1/cameras/{CAMERA_ID}/scenario", headers=auth_headers)
        call_args = cam_repo.get_by_id_and_tenant.call_args[0]
        assert call_args[0] == CAMERA_ID
        assert call_args[1] == TENANT_ID

    def test_schedule_from_camera_field(self, client, auth_headers):
        camera_with_schedule = {**_SAMPLE_CAMERA, "schedule_rules": [{"day": "mon", "start": "08:00"}]}
        cam_repo, mod_repo, op_repo, alert_repo = _mock_repos(camera=camera_with_schedule)
        patches = _patch_repos(cam_repo, mod_repo, op_repo, alert_repo)
        with patches[0], patches[1], patches[2], patches[3]:
            resp = client.get(f"/api/v1/cameras/{CAMERA_ID}/scenario", headers=auth_headers)
        schedule = resp.get_json()["data"]["scenario"]["schedule"]
        assert len(schedule) == 1


# ---------------------------------------------------------------------------
# GET /api/v1/scenarios/operation-types
# ---------------------------------------------------------------------------

class TestListScenarioOperationTypes:

    def test_no_token_returns_401(self, client):
        assert client.get("/api/v1/scenarios/operation-types").status_code == 401

    def test_returns_types_for_module(self, client, auth_headers):
        with patch("app.api.v1.scenarios.routes.OperationTypeRegistry") as mock_reg:
            mock_reg.to_catalog.return_value = [{"type_id": "count_line", "name": "Count Line"}]
            resp = client.get(
                "/api/v1/scenarios/operation-types?module=epi",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["module"] == "epi"
        assert len(data["data"]["types"]) == 1
        assert data["data"]["types"][0]["type_id"] == "count_line"

    def test_unknown_module_returns_empty_list(self, client, auth_headers):
        with patch("app.api.v1.scenarios.routes.OperationTypeRegistry") as mock_reg:
            mock_reg.to_catalog.return_value = []
            resp = client.get(
                "/api/v1/scenarios/operation-types?module=unknown",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["types"] == []

    def test_no_module_param_returns_empty_module_string(self, client, auth_headers):
        with patch("app.api.v1.scenarios.routes.OperationTypeRegistry") as mock_reg:
            mock_reg.to_catalog.return_value = []
            resp = client.get("/api/v1/scenarios/operation-types", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["module"] == ""

    def test_success_is_true(self, client, auth_headers):
        with patch("app.api.v1.scenarios.routes.OperationTypeRegistry") as mock_reg:
            mock_reg.to_catalog.return_value = []
            resp = client.get(
                "/api/v1/scenarios/operation-types?module=epi",
                headers=auth_headers,
            )
        assert resp.get_json()["success"] is True
