"""Tests: Repository pattern (mocked database)."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from contextlib import contextmanager
from uuid import uuid4

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.infrastructure.database.repositories.video_repository import VideoRepository
from app.infrastructure.database.repositories.camera_repository import CameraRepository


class MockPool:
    """Lightweight mock for DatabasePool with context manager support."""

    def __init__(self) -> None:
        self.mock_cursor = MagicMock()
        self.mock_conn = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.mock_conn
        self.mock_conn.commit()


class TestUserRepository:
    """Testes para UserRepository."""

    def setup_method(self) -> None:
        self.pool = MockPool()
        self.repo = UserRepository(self.pool)  # type: ignore[arg-type]

    def test_create_user(self) -> None:
        uid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": uid, "email": "test@test.com",
            "name": "Test", "role": "operator",
            "is_active": True, "created_at": "2024-01-01",
        }
        result = self.repo.create("test@test.com", "hashed", "Test")
        assert result["email"] == "test@test.com"
        self.pool.mock_cursor.execute.assert_called_once()

    def test_get_by_email(self) -> None:
        self.pool.mock_cursor.fetchone.return_value = {
            "id": uuid4(), "email": "test@test.com",
            "name": "Test", "role": "operator",
            "password_hash": "hashed", "is_active": True,
            "created_at": "2024-01-01",
        }
        result = self.repo.get_by_email("test@test.com")
        assert result is not None
        assert result["email"] == "test@test.com"

    def test_get_by_email_not_found(self) -> None:
        self.pool.mock_cursor.fetchone.return_value = None
        result = self.repo.get_by_email("nonexistent@test.com")
        assert result is None

    def test_exists_by_email(self) -> None:
        self.pool.mock_cursor.fetchone.return_value = {"exists": True}
        assert self.repo.exists_by_email("test@test.com") is True

    def test_exists_by_email_false(self) -> None:
        self.pool.mock_cursor.fetchone.return_value = {"exists": False}
        assert self.repo.exists_by_email("new@test.com") is False


class TestVideoRepository:
    """Testes para VideoRepository."""

    def setup_method(self) -> None:
        self.pool = MockPool()
        self.repo = VideoRepository(self.pool)  # type: ignore[arg-type]

    def test_create_video(self) -> None:
        vid = uuid4()
        uid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": vid, "user_id": uid, "filename": "test.mp4",
            "status": "uploaded", "frame_count": 0, "created_at": "2024-01-01",
        }
        result = self.repo.create(uid, "test.mp4", "original.mp4", 1024)
        assert result["filename"] == "test.mp4"

    def test_get_by_user(self) -> None:
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "filename": "v1.mp4"},
            {"id": uuid4(), "filename": "v2.mp4"},
        ]
        result = self.repo.get_by_user(uuid4())
        assert len(result) == 2

    def test_update_status(self) -> None:
        vid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": vid, "status": "processing",
        }
        result = self.repo.update_status(vid, "processing")
        assert result["status"] == "processing"


class TestCameraRepository:
    """Testes para CameraRepository."""

    def setup_method(self) -> None:
        self.pool = MockPool()
        self.repo = CameraRepository(self.pool)  # type: ignore[arg-type]

    def test_create_camera(self) -> None:
        cam_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": cam_id, "name": "Camera 1",
            "host": "192.168.1.100", "port": 554,
            "manufacturer": "generic", "is_active": True,
        }
        result = self.repo.create({
            "user_id": uuid4(),
            "name": "Camera 1",
            "host": "192.168.1.100",
        })
        assert result["name"] == "Camera 1"

    def test_get_all(self) -> None:
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "name": "Cam 1"},
            {"id": uuid4(), "name": "Cam 2"},
        ]
        result = self.repo.get_all()
        assert len(result) == 2

    def test_delete(self) -> None:
        self.pool.mock_cursor.rowcount = 1
        result = self.repo.delete(uuid4())
        assert result == 1
