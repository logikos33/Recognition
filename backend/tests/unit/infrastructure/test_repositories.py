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


class TestFrameRepository:
    """Testes para FrameRepository."""

    def setup_method(self) -> None:
        self.pool = MockPool()
        from app.infrastructure.database.repositories.frame_repository import FrameRepository
        self.repo = FrameRepository(self.pool)  # type: ignore[arg-type]

    def test_create_frame(self) -> None:
        fid = uuid4()
        vid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": fid, "video_id": vid, "frame_number": 0,
            "filename": "frames/u/v/frame_0000.jpg",
            "is_annotated": False, "quality_status": "pending",
        }
        result = self.repo.create(vid, 0, "frames/u/v/frame_0000.jpg")
        assert result["frame_number"] == 0
        self.pool.mock_cursor.execute.assert_called_once()

    def test_get_by_video(self) -> None:
        vid = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "frame_number": 0},
            {"id": uuid4(), "frame_number": 1},
        ]
        result = self.repo.get_by_video(vid)
        assert len(result) == 2

    def test_get_by_id(self) -> None:
        fid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {"id": fid, "frame_number": 3}
        result = self.repo.get_by_id(fid)
        assert result is not None
        assert result["frame_number"] == 3

    def test_get_by_id_not_found(self) -> None:
        self.pool.mock_cursor.fetchone.return_value = None
        result = self.repo.get_by_id(uuid4())
        assert result is None

    def test_get_next_unannotated(self) -> None:
        fid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": fid, "frame_number": 0, "is_annotated": False,
        }
        result = self.repo.get_next_unannotated(uuid4())
        assert result is not None
        assert result["is_annotated"] is False

    def test_mark_annotated(self) -> None:
        fid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": fid, "is_annotated": True,
        }
        result = self.repo.mark_annotated(fid)
        assert result["is_annotated"] is True

    def test_update_quality_status_approved(self) -> None:
        fid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": fid, "quality_status": "approved",
            "quality_scores": '{"blur": 150.5, "brightness": 80.2}',
        }
        result = self.repo.update_quality_status(
            fid, "approved", {"blur": 150.5, "brightness": 80.2}
        )
        assert result["quality_status"] == "approved"
        self.pool.mock_cursor.execute.assert_called_once()

    def test_update_quality_status_rejected(self) -> None:
        fid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": fid, "quality_status": "rejected",
            "quality_scores": '{"reason": "blur"}',
        }
        result = self.repo.update_quality_status(fid, "rejected", {"reason": "blur"})
        assert result["quality_status"] == "rejected"

    def test_get_approved_by_video(self) -> None:
        vid = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "quality_status": "approved"},
            {"id": uuid4(), "quality_status": "pending"},
        ]
        result = self.repo.get_approved_by_video(vid)
        assert len(result) == 2

    def test_count_by_status(self) -> None:
        vid = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"is_annotated": False, "count": 5},
            {"is_annotated": True, "count": 3},
        ]
        result = self.repo.count_by_status(vid)
        assert result["annotated"] == 3
        assert result["pending"] == 5
        assert result["total"] == 8


class TestAnnotationRepository:
    """Testes para AnnotationRepository."""

    def setup_method(self) -> None:
        self.pool = MockPool()
        from app.infrastructure.database.repositories.annotation_repository import AnnotationRepository
        self.repo = AnnotationRepository(self.pool)  # type: ignore[arg-type]

    def test_create_class(self) -> None:
        uid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": 1, "user_id": uid, "name": "Capacete", "color": "#22c55e",
        }
        result = self.repo.create_class(uid, "Capacete", "#22c55e")
        assert result["name"] == "Capacete"

    def test_get_classes_by_user(self) -> None:
        uid = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "Capacete", "color": "#22c55e"},
            {"id": 2, "name": "Colete", "color": "#f59e0b"},
        ]
        result = self.repo.get_classes_by_user(uid)
        assert len(result) == 2

    def test_create_annotation(self) -> None:
        fid = uuid4()
        ann_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": ann_id, "frame_id": fid, "class_id": 1,
            "x_center": 0.5, "y_center": 0.5, "width": 0.3, "height": 0.4,
        }
        result = self.repo.create_annotation(fid, 1, 0.5, 0.5, 0.3, 0.4)
        assert result["class_id"] == 1
        assert result["x_center"] == 0.5

    def test_get_by_frame(self) -> None:
        fid = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "class_id": 1, "class_name": "Capacete",
             "x_center": 0.5, "y_center": 0.5, "width": 0.3, "height": 0.4},
        ]
        result = self.repo.get_by_frame(fid)
        assert len(result) == 1
        assert result[0]["class_name"] == "Capacete"

    def test_delete_by_frame(self) -> None:
        fid = uuid4()
        self.pool.mock_cursor.rowcount = 3
        result = self.repo.delete_by_frame(fid)
        assert result == 3

    def test_save_batch(self) -> None:
        fid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": uuid4(), "class_id": 1,
            "x_center": 0.5, "y_center": 0.5, "width": 0.3, "height": 0.4,
        }
        self.pool.mock_cursor.rowcount = 1
        annotations = [
            {"class_id": 1, "x_center": 0.5, "y_center": 0.5,
             "width": 0.3, "height": 0.4},
            {"class_id": 2, "x_center": 0.2, "y_center": 0.8,
             "width": 0.1, "height": 0.2},
        ]
        count = self.repo.save_batch(fid, annotations)
        assert count == 2
