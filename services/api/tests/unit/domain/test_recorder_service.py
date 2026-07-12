"""
Tests: RecorderService (WS-B1, ADR-0034).

Cobre: CRUD, cifra/decifra de senha (Fernet), validação de protocol/port,
mascaramento de password_encrypted, test_connection (cascata de client +
update_status best-effort).
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.recorder_service import RecorderService

FERNET_KEY = Fernet.generate_key().decode()


def _service(repo=None):
    return RecorderService(repo or MagicMock())


class TestCreateRecorder:
    def test_requires_name_and_host(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        service = _service()
        with pytest.raises(ValidationError):
            service.create_recorder("tenant-1", uuid4(), {"name": "", "host": ""})

    def test_invalid_protocol_raises(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        service = _service()
        with pytest.raises(ValidationError):
            service.create_recorder(
                "tenant-1", uuid4(),
                {"name": "NVR 1", "host": "10.0.0.5", "protocol": "not-a-real-protocol"},
            )

    def test_invalid_port_raises(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        service = _service()
        with pytest.raises(ValidationError):
            service.create_recorder(
                "tenant-1", uuid4(), {"name": "NVR 1", "host": "10.0.0.5", "port": 99999}
            )

    def test_encrypts_password_before_create(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.create.return_value = {
            "id": uuid4(), "tenant_id": "tenant-1", "name": "NVR 1",
            "host": "10.0.0.5", "port": 80, "password_encrypted": "cipher",
        }
        service = _service(repo)
        service.create_recorder(
            "tenant-1", uuid4(),
            {"name": "NVR 1", "host": "10.0.0.5", "password": "secret123"},
        )
        call_data = repo.create.call_args.args[0]
        assert call_data["password_encrypted"] != "secret123"
        fernet = Fernet(FERNET_KEY.encode())
        assert fernet.decrypt(call_data["password_encrypted"].encode()).decode() == "secret123"

    def test_response_never_includes_password_encrypted(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.create.return_value = {
            "id": uuid4(), "name": "NVR 1", "password_encrypted": "cipher-text",
        }
        service = _service(repo)
        result = service.create_recorder(
            "tenant-1", uuid4(), {"name": "NVR 1", "host": "10.0.0.5"}
        )
        assert "password_encrypted" not in result

    def test_default_protocol_and_port_when_omitted(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.create.return_value = {"id": uuid4()}
        service = _service(repo)
        service.create_recorder("tenant-1", uuid4(), {"name": "NVR 1", "host": "10.0.0.5"})
        call_data = repo.create.call_args.args[0]
        assert call_data["protocol"] == "onvif"
        assert call_data["port"] == 80


class TestListGetRecorder:
    def test_list_masks_all_rows(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.list_by_tenant.return_value = [
            {"id": uuid4(), "password_encrypted": "x"},
            {"id": uuid4(), "password_encrypted": "y"},
        ]
        service = _service(repo)
        result = service.list_recorders("tenant-1")
        assert len(result) == 2
        assert all("password_encrypted" not in r for r in result)

    def test_get_recorder_returns_none_when_missing(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.get_by_id.return_value = None
        service = _service(repo)
        assert service.get_recorder(uuid4(), "tenant-1") is None

    def test_get_recorder_or_raise_raises_not_found(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.get_by_id.return_value = None
        service = _service(repo)
        with pytest.raises(NotFoundError):
            service.get_recorder_or_raise(uuid4(), "tenant-1")


class TestUpdateDeleteRecorder:
    def test_update_raises_not_found_when_repo_returns_none(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.update.return_value = None
        service = _service(repo)
        with pytest.raises(NotFoundError):
            service.update_recorder(uuid4(), "tenant-1", {"name": "novo nome"})

    def test_update_encrypts_new_password(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.update.return_value = {"id": uuid4()}
        service = _service(repo)
        service.update_recorder(uuid4(), "tenant-1", {"password": "newpass"})
        call_data = repo.update.call_args.args[2]
        assert "password" not in call_data
        assert "password_encrypted" in call_data

    def test_delete_raises_not_found_when_zero_rows(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.delete.return_value = 0
        service = _service(repo)
        with pytest.raises(NotFoundError):
            service.delete_recorder(uuid4(), "tenant-1")

    def test_delete_returns_true_on_success(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.delete.return_value = 1
        service = _service(repo)
        assert service.delete_recorder(uuid4(), "tenant-1") is True


class TestDecryptPassword:
    def test_roundtrip(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        service = _service()
        encrypted = service._encrypt_password("s3nha")
        assert service.decrypt_password(encrypted) == "s3nha"

    def test_empty_or_none_returns_empty_string(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        service = _service()
        assert service.decrypt_password(None) == ""
        assert service.decrypt_password("") == ""

    def test_corrupted_ciphertext_returns_empty_string_not_raise(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        service = _service()
        assert service.decrypt_password("not-a-valid-fernet-token") == ""


class TestConnection:
    def test_online_updates_status_ok(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.get_by_id.return_value = {
            "id": uuid4(), "host": "10.0.0.5", "port": 80,
            "protocol": "onvif", "password_encrypted": None,
        }
        repo.update_status.return_value = {"status": "online"}
        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        service = _service(repo)
        with patch(
            "app.infrastructure.nvr.factory.get_nvr_client", return_value=mock_client
        ):
            service.test_connection(uuid4(), "tenant-1")
        repo.update_status.assert_called_once()
        assert repo.update_status.call_args.args[2] == "online"

    def test_offline_updates_status_offline(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.get_by_id.return_value = {
            "id": uuid4(), "host": "10.0.0.5", "port": 80,
            "protocol": "onvif", "password_encrypted": None,
        }
        mock_client = MagicMock()
        mock_client.test_connection.return_value = False
        service = _service(repo)
        with patch(
            "app.infrastructure.nvr.factory.get_nvr_client", return_value=mock_client
        ):
            service.test_connection(uuid4(), "tenant-1")
        assert repo.update_status.call_args.args[2] == "offline"

    def test_exception_updates_status_error_without_raising(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.get_by_id.return_value = {
            "id": uuid4(), "host": "10.0.0.5", "port": 80,
            "protocol": "onvif", "password_encrypted": None,
        }
        service = _service(repo)
        with patch(
            "app.infrastructure.nvr.factory.get_nvr_client",
            side_effect=RuntimeError("conexão recusada"),
        ):
            service.test_connection(uuid4(), "tenant-1")  # não deve levantar
        assert repo.update_status.call_args.args[2] == "error"

    def test_raises_not_found_when_recorder_missing(self, monkeypatch):
        monkeypatch.setenv("CAMERA_SECRET_KEY", FERNET_KEY)
        repo = MagicMock()
        repo.get_by_id.return_value = None
        service = _service(repo)
        with pytest.raises(NotFoundError):
            service.test_connection(uuid4(), "tenant-1")
