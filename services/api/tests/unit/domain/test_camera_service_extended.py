"""
Tests: CameraService — build_rtsp_url, build_stream_url, update_camera,
delete_camera, get_camera, record_test_result (item-24).

Extends existing test_camera_service.py with the methods at lines 149–230.
"""
import pytest
from cryptography.fernet import Fernet
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.services.camera_service import CameraService


def _make_service():
    repo = MagicMock()
    key = Fernet.generate_key().decode()
    return CameraService(repo, key), repo


def _cam(camera_id=None, tenant_id=None, **kwargs):
    camera_id = camera_id or uuid4()
    tenant_id = tenant_id or uuid4()
    base = {
        "id": camera_id,
        "tenant_id": tenant_id,
        "name": "Test",
        "host": "192.168.1.1",
        "port": 554,
        "username": "admin",
        "password_encrypted": "",
        "manufacturer": "generic",
        "channel": 1,
        "subtype": 0,
        "rtsp_url_override": None,
        "is_active": True,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# get_camera
# ---------------------------------------------------------------------------

class TestGetCamera:

    def test_get_camera_success(self):
        service, repo = _make_service()
        cam = _cam()
        repo.get_by_id.return_value = cam
        result = service.get_camera(cam["id"])
        assert result["id"] == str(cam["id"])
        assert "password_encrypted" not in result

    def test_get_camera_not_found_raises(self):
        service, repo = _make_service()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.get_camera(uuid4())


# ---------------------------------------------------------------------------
# build_rtsp_url
# ---------------------------------------------------------------------------

class TestBuildRtspUrl:

    def test_rtsp_url_generic(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(
            camera_id=camera_id, tenant_id=tenant_id,
            manufacturer="generic", host="10.0.0.1", port=554,
            username="user",
        )
        url = service.build_rtsp_url(camera_id, tenant_id)
        assert url.startswith("rtsp://")
        assert "10.0.0.1" in url
        assert "/stream1" in url

    def test_rtsp_url_hikvision(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(
            camera_id=camera_id, tenant_id=tenant_id,
            manufacturer="hikvision", channel=1, subtype=0,
        )
        url = service.build_rtsp_url(camera_id, tenant_id)
        assert "Streaming/Channels" in url

    def test_rtsp_url_intelbras(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(
            camera_id=camera_id, tenant_id=tenant_id,
            manufacturer="intelbras",
        )
        url = service.build_rtsp_url(camera_id, tenant_id)
        assert "cam/realmonitor" in url

    def test_rtsp_url_dahua(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(
            camera_id=camera_id, tenant_id=tenant_id,
            manufacturer="dahua",
        )
        url = service.build_rtsp_url(camera_id, tenant_id)
        assert "cam/realmonitor" in url

    def test_rtsp_url_override_used_when_set(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(
            camera_id=camera_id, tenant_id=tenant_id,
            rtsp_url_override="rtsp://override.host/stream",
        )
        url = service.build_rtsp_url(camera_id, tenant_id)
        assert url == "rtsp://override.host/stream"

    def test_rtsp_url_not_found_raises(self):
        service, repo = _make_service()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.build_rtsp_url(uuid4(), uuid4())

    def test_rtsp_url_wrong_user_raises(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)
        with pytest.raises(AuthorizationError):
            service.build_rtsp_url(camera_id, uuid4())  # different user

    def test_rtsp_url_admin_can_access_other_tenant(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)
        # admin bypass
        url = service.build_rtsp_url(camera_id, uuid4(), is_admin=True)
        assert url.startswith("rtsp://")


# ---------------------------------------------------------------------------
# build_stream_url
# ---------------------------------------------------------------------------

class TestBuildStreamUrl:

    def test_stream_url_hikvision_non_554_returns_http(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(
            camera_id=camera_id, tenant_id=tenant_id,
            manufacturer="hikvision", port=8080,
        )
        url = service.build_stream_url(camera_id, tenant_id)
        assert url.startswith("http://")
        assert "ISAPI" in url

    def test_stream_url_hikvision_554_falls_back_to_rtsp(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        cam = _cam(
            camera_id=camera_id, tenant_id=tenant_id,
            manufacturer="hikvision", port=554,
        )
        repo.get_by_id.return_value = cam
        url = service.build_stream_url(camera_id, tenant_id)
        assert url.startswith("rtsp://")

    def test_stream_url_override_returns_override(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(
            camera_id=camera_id, tenant_id=tenant_id,
            rtsp_url_override="rtsp://override/stream",
        )
        url = service.build_stream_url(camera_id, tenant_id)
        assert url == "rtsp://override/stream"

    def test_stream_url_not_found_raises(self):
        service, repo = _make_service()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.build_stream_url(uuid4(), uuid4())

    def test_stream_url_wrong_user_raises(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)
        with pytest.raises(AuthorizationError):
            service.build_stream_url(camera_id, uuid4())


# ---------------------------------------------------------------------------
# update_camera
# ---------------------------------------------------------------------------

class TestUpdateCamera:

    def test_update_name_success(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        existing = _cam(camera_id=camera_id, tenant_id=tenant_id)
        updated = {**existing, "name": "New Name"}
        repo.get_by_id.return_value = existing
        repo.update.return_value = {**updated, "id": camera_id}

        result = service.update_camera(camera_id, tenant_id, {"name": "New Name"})
        assert result["id"] == str(camera_id)
        assert "password_encrypted" not in result

    def test_update_password_encrypts(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)
        repo.update.return_value = {"id": camera_id, "name": "Cam"}

        service.update_camera(camera_id, tenant_id, {"password": "newsecret"})
        call_data = repo.update.call_args[0][1]
        assert "password_encrypted" in call_data
        assert call_data["password_encrypted"] != "newsecret"

    def test_update_no_fields_raises(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)

        with pytest.raises(ValidationError, match="Nenhum campo"):
            service.update_camera(camera_id, tenant_id, {"unknown_field": "val"})

    def test_update_not_found_raises(self):
        service, repo = _make_service()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.update_camera(uuid4(), uuid4(), {"name": "X"})

    def test_update_wrong_user_raises(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)
        with pytest.raises(AuthorizationError):
            service.update_camera(camera_id, uuid4(), {"name": "X"})

    def test_update_admin_can_update_other_tenant(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)
        repo.update.return_value = {"id": camera_id, "name": "Updated"}

        result = service.update_camera(camera_id, uuid4(), {"name": "Updated"}, is_admin=True)
        assert result["id"] == str(camera_id)


# ---------------------------------------------------------------------------
# delete_camera
# ---------------------------------------------------------------------------

class TestDeleteCamera:

    def test_delete_success(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)

        service.delete_camera(camera_id, tenant_id)
        repo.delete.assert_called_once_with(camera_id)

    def test_delete_not_found_raises(self):
        service, repo = _make_service()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.delete_camera(uuid4(), uuid4())

    def test_delete_wrong_user_raises(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)
        with pytest.raises(AuthorizationError):
            service.delete_camera(camera_id, uuid4())

    def test_delete_admin_override(self):
        service, repo = _make_service()
        tenant_id = uuid4()
        camera_id = uuid4()
        repo.get_by_id.return_value = _cam(camera_id=camera_id, tenant_id=tenant_id)
        service.delete_camera(camera_id, uuid4(), is_admin=True)
        repo.delete.assert_called_once_with(camera_id)


# ---------------------------------------------------------------------------
# record_test_result
# ---------------------------------------------------------------------------

class TestRecordTestResult:

    def test_record_success(self):
        service, repo = _make_service()
        camera_id = uuid4()
        service.record_test_result(camera_id, None)
        repo.update_last_tested.assert_called_once_with(camera_id, None)

    def test_record_with_error_message(self):
        service, repo = _make_service()
        camera_id = uuid4()
        service.record_test_result(camera_id, "Connection refused")
        repo.update_last_tested.assert_called_once_with(camera_id, "Connection refused")

    def test_record_swallows_exception(self):
        service, repo = _make_service()
        repo.update_last_tested.side_effect = Exception("DB unavailable")
        # Should not raise — best-effort
        service.record_test_result(uuid4(), None)
