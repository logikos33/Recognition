"""Tests: CameraService."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.domain.services.camera_service import CameraService


class TestCameraService:
    """Testes para CameraService."""

    def setup_method(self) -> None:
        self.camera_repo = MagicMock()
        # Generate a valid Fernet key for tests
        from cryptography.fernet import Fernet
        self.fernet_key = Fernet.generate_key().decode()
        self.service = CameraService(self.camera_repo, self.fernet_key)

    def test_create_camera_success(self) -> None:
        uid = uuid4()
        cam_id = uuid4()
        self.camera_repo.create.return_value = {
            "id": cam_id, "name": "Camera 1",
            "host": "192.168.1.100", "port": 554,
        }
        result = self.service.create_camera(uid, {
            "name": "Camera 1",
            "host": "192.168.1.100",
        })
        assert result["name"] == "Camera 1"
        assert result["id"] == str(cam_id)

    def test_create_camera_missing_name(self) -> None:
        with pytest.raises(ValidationError, match="obrigatórios"):
            self.service.create_camera(uuid4(), {"host": "192.168.1.1"})

    def test_create_camera_missing_host(self) -> None:
        with pytest.raises(ValidationError, match="obrigatórios"):
            self.service.create_camera(uuid4(), {"name": "Cam"})

    def test_create_camera_with_password(self) -> None:
        uid = uuid4()
        self.camera_repo.create.return_value = {
            "id": uuid4(), "name": "Cam",
        }
        self.service.create_camera(uid, {
            "name": "Cam", "host": "10.0.0.1", "password": "secret123",
        })
        call_args = self.camera_repo.create.call_args[0][0]
        assert "password_encrypted" in call_args
        assert call_args["password_encrypted"] != "secret123"

    def test_list_cameras_operator(self) -> None:
        uid = uuid4()
        self.camera_repo.get_by_user.return_value = [
            {"id": uuid4(), "name": "Cam 1"},
        ]
        result = self.service.list_cameras(uid, is_admin=False)
        assert len(result) == 1
        self.camera_repo.get_by_user.assert_called_once()

    def test_list_cameras_admin(self) -> None:
        self.camera_repo.get_all.return_value = [
            {"id": uuid4(), "name": "Cam 1"},
            {"id": uuid4(), "name": "Cam 2"},
        ]
        result = self.service.list_cameras(uuid4(), is_admin=True)
        assert len(result) == 2
        self.camera_repo.get_all.assert_called_once()

    def test_get_camera_success(self) -> None:
        cam_id = uuid4()
        self.camera_repo.get_by_id.return_value = {
            "id": cam_id, "name": "Cam",
            "password_encrypted": "should-be-removed",
        }
        result = self.service.get_camera(cam_id)
        assert "password_encrypted" not in result

    def test_get_camera_not_found(self) -> None:
        self.camera_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_camera(uuid4())

    def test_delete_camera_success(self) -> None:
        uid = uuid4()
        cam_id = uuid4()
        self.camera_repo.get_by_id.return_value = {
            "id": cam_id, "user_id": uid,
        }
        self.service.delete_camera(cam_id, uid)
        self.camera_repo.delete.assert_called_once()

    def test_delete_camera_wrong_user(self) -> None:
        cam_id = uuid4()
        self.camera_repo.get_by_id.return_value = {
            "id": cam_id, "user_id": uuid4(),
        }
        with pytest.raises(AuthorizationError):
            self.service.delete_camera(cam_id, uuid4())

    def test_delete_camera_admin_override(self) -> None:
        cam_id = uuid4()
        self.camera_repo.get_by_id.return_value = {
            "id": cam_id, "user_id": uuid4(),
        }
        self.service.delete_camera(cam_id, uuid4(), is_admin=True)
        self.camera_repo.delete.assert_called_once()
