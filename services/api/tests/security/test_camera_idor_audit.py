"""
Security regression tests — Camera IDOR (CVE-IDOR-camera-001, CVE-IDOR-camera-002).

Bug 1 (crud_handlers.get_camera): guard compared camera.get("user_id"), which is
always None in the camera dict (the field is "tenant_id"). The condition
short-circuited to False → the 403 never fired → any authenticated user could
read any camera cross-tenant, exposing rtsp_url_override credentials.

Bug 2 (module_handler): patch_camera_module / put_camera_schedule /
get_camera_module_current fetched the camera but contained no ownership check
(the comment "Verificar que câmera pertence ao usuário" was never implemented).

These tests FAIL on the vulnerable code and PASS after the fixes are applied.
"""
import uuid
from unittest.mock import MagicMock

from flask_jwt_extended import create_access_token

import app.api.v1.cameras.crud_handlers as crud_handlers
import app.api.v1.cameras.module_handler as module_handler

OWNER_ID = str(uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"))
REQUESTER_ID = str(uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002"))
CAMERA_ID = str(uuid.UUID("cccccccc-0000-0000-0000-000000000003"))


def _token(app, identity: str) -> dict[str, str]:
    """JWT token whose identity becomes the user_id in get_current_user_id()."""
    with app.app_context():
        token = create_access_token(
            identity=identity,
            additional_claims={
                "tenant_id": identity,
                "tenant_schema": "tenant_test",
                "role": "operator",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _camera_row(tenant_id: str) -> dict:
    return {
        "id": CAMERA_ID,
        "tenant_id": tenant_id,
        "name": "Cam IDOR Test",
        "host": "192.168.0.1",
        "active_module": "epi",
        "schedule_rules": [],
    }


# ---------------------------------------------------------------------------
# Bug 1 — GET /api/cameras/<id>  (crud_handlers.get_camera)
# ---------------------------------------------------------------------------

class TestGetCameraIdorGuard:
    """Guard must compare tenant_id, not the absent user_id key."""

    def test_cross_tenant_read_returns_403(self, app, client, monkeypatch):
        """Requester with a different id than the camera owner must get 403."""
        mock_svc = MagicMock()
        mock_svc.get_camera.return_value = _camera_row(tenant_id=OWNER_ID)
        monkeypatch.setattr(crud_handlers, "_get_camera_service", lambda: mock_svc)
        monkeypatch.setattr(crud_handlers, "_is_admin", lambda uid: False)

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}",
            headers=_token(app, REQUESTER_ID),
        )
        assert resp.status_code == 403

    def test_owner_read_returns_200(self, app, client, monkeypatch):
        """Camera owner must still receive their camera data."""
        mock_svc = MagicMock()
        mock_svc.get_camera.return_value = _camera_row(tenant_id=OWNER_ID)
        monkeypatch.setattr(crud_handlers, "_get_camera_service", lambda: mock_svc)
        monkeypatch.setattr(crud_handlers, "_is_admin", lambda uid: False)

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}",
            headers=_token(app, OWNER_ID),
        )
        assert resp.status_code == 200

    def test_admin_cross_tenant_read_returns_200(self, app, client, monkeypatch):
        """Admin override must still permit cross-tenant reads."""
        mock_svc = MagicMock()
        mock_svc.get_camera.return_value = _camera_row(tenant_id=OWNER_ID)
        monkeypatch.setattr(crud_handlers, "_get_camera_service", lambda: mock_svc)
        monkeypatch.setattr(crud_handlers, "_is_admin", lambda uid: True)

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}",
            headers=_token(app, REQUESTER_ID),
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Bug 2 — PATCH /api/cameras/<id>/module  (module_handler.patch_camera_module)
# ---------------------------------------------------------------------------

class TestPatchCameraModuleIdorGuard:
    """Cross-tenant module patch must be rejected; update_module must NOT be called."""

    def test_cross_tenant_patch_module_returns_403(self, app, client, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _camera_row(tenant_id=OWNER_ID)
        monkeypatch.setattr(module_handler, "_get_camera_repo", lambda: mock_repo)
        monkeypatch.setattr(module_handler, "_notify_module_changed", MagicMock())

        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/module",
            json={"module": "epi"},
            headers=_token(app, REQUESTER_ID),
        )
        assert resp.status_code == 403
        mock_repo.update_module.assert_not_called()

    def test_owner_patch_module_returns_200(self, app, client, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _camera_row(tenant_id=OWNER_ID)
        monkeypatch.setattr(module_handler, "_get_camera_repo", lambda: mock_repo)
        monkeypatch.setattr(module_handler, "_notify_module_changed", MagicMock())

        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/module",
            json={"module": "epi"},
            headers=_token(app, OWNER_ID),
        )
        assert resp.status_code == 200
        mock_repo.update_module.assert_called_once_with(CAMERA_ID, "epi")


# ---------------------------------------------------------------------------
# Bug 2 — PUT /api/cameras/<id>/schedule  (module_handler.put_camera_schedule)
# ---------------------------------------------------------------------------

class TestPutCameraScheduleIdorGuard:
    def test_cross_tenant_put_schedule_returns_403(self, app, client, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _camera_row(tenant_id=OWNER_ID)
        monkeypatch.setattr(module_handler, "_get_camera_repo", lambda: mock_repo)
        monkeypatch.setattr(
            module_handler, "validate_schedule_rules", lambda rules: (True, "")
        )

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/schedule",
            json={"rules": []},
            headers=_token(app, REQUESTER_ID),
        )
        assert resp.status_code == 403
        mock_repo.update_schedule.assert_not_called()

    def test_owner_put_schedule_returns_200(self, app, client, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _camera_row(tenant_id=OWNER_ID)
        monkeypatch.setattr(module_handler, "_get_camera_repo", lambda: mock_repo)
        monkeypatch.setattr(
            module_handler, "validate_schedule_rules", lambda rules: (True, "")
        )

        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/schedule",
            json={"rules": []},
            headers=_token(app, OWNER_ID),
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Bug 2 — GET /api/cameras/<id>/module/current
# ---------------------------------------------------------------------------

class TestGetCameraModuleCurrentIdorGuard:
    def test_cross_tenant_get_module_current_returns_403(self, app, client, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _camera_row(tenant_id=OWNER_ID)
        monkeypatch.setattr(module_handler, "_get_camera_repo", lambda: mock_repo)

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/module/current",
            headers=_token(app, REQUESTER_ID),
        )
        assert resp.status_code == 403

    def test_owner_get_module_current_returns_200(self, app, client, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _camera_row(tenant_id=OWNER_ID)
        monkeypatch.setattr(module_handler, "_get_camera_repo", lambda: mock_repo)
        monkeypatch.setattr(
            module_handler, "resolve_active_module", lambda camera: "epi"
        )

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/module/current",
            headers=_token(app, OWNER_ID),
        )
        assert resp.status_code == 200
