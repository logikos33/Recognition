"""Tests: Repository pattern (mocked database)."""
from unittest.mock import MagicMock
from contextlib import contextmanager
from uuid import uuid4

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

    def test_get_by_id(self) -> None:
        vid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": vid, "filename": "raw-videos/u/v/test.mp4", "status": "uploaded",
        }
        result = self.repo.get_by_id(vid)
        assert result is not None
        assert result["status"] == "uploaded"

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
            "tenant_id": uuid4(),
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


class TestDatasetRepository:
    """Testes para DatasetRepository."""

    def setup_method(self) -> None:
        self.pool = MockPool()
        from app.infrastructure.database.repositories.dataset_repository import DatasetRepository
        self.repo = DatasetRepository(self.pool)  # type: ignore[arg-type]

    def test_create_dataset(self) -> None:
        uid = uuid4()
        did = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": did, "user_id": uid, "version": "v1.0.0",
            "frame_count": 100,
        }
        result = self.repo.create({
            "user_id": uid, "version": "v1.0.0",
            "frame_count": 100, "train_count": 70,
            "val_count": 20, "test_count": 10,
        })
        assert result["version"] == "v1.0.0"

    def test_get_by_id(self) -> None:
        did = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": did, "version": "v1.0.0",
        }
        result = self.repo.get_by_id(did)
        assert result is not None
        assert result["version"] == "v1.0.0"

    def test_get_by_user(self) -> None:
        uid = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "version": "v1.0.0"},
            {"id": uuid4(), "version": "v1.1.0"},
        ]
        result = self.repo.get_by_user(uid)
        assert len(result) == 2

    def test_get_latest(self) -> None:
        uid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": uuid4(), "version": "v2.0.0",
        }
        result = self.repo.get_latest(uid)
        assert result is not None
        assert result["version"] == "v2.0.0"


class TestBaseExecuteMany:
    """Tests for _execute_many in BaseRepository."""

    def setup_method(self) -> None:
        self.pool = MockPool()
        from app.infrastructure.database.repositories.frame_repository import FrameRepository
        self.repo = FrameRepository(self.pool)  # type: ignore[arg-type]

    def test_execute_many_bulk(self) -> None:
        vid = uuid4()
        self.pool.mock_cursor.rowcount = 3
        count = self.repo.create_bulk([
            {"video_id": str(vid), "frame_number": 0,
             "filename": "frames/a.jpg", "timestamp_seconds": None},
            {"video_id": str(vid), "frame_number": 1,
             "filename": "frames/b.jpg", "timestamp_seconds": None},
            {"video_id": str(vid), "frame_number": 2,
             "filename": "frames/c.jpg", "timestamp_seconds": None},
        ])
        assert count == 3


class TestTrainingRepository:
    """Testes para TrainingRepository."""

    def setup_method(self) -> None:
        self.pool = MockPool()
        from app.infrastructure.database.repositories.training_repository import TrainingRepository
        self.repo = TrainingRepository(self.pool)  # type: ignore[arg-type]

    def test_create_job(self) -> None:
        uid = uuid4()
        job_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": job_id, "user_id": uid, "status": "queued",
            "preset": "balanced", "model_size": "yolo26n", "total_epochs": 100,
        }
        result = self.repo.create_job(uid, "balanced", "yolo26n", 100)
        assert result["status"] == "queued"
        assert result["preset"] == "balanced"

    def test_get_job_by_id(self) -> None:
        job_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": job_id, "status": "running",
        }
        result = self.repo.get_job_by_id(job_id)
        assert result is not None
        assert result["status"] == "running"

    def test_get_job_by_id_not_found(self) -> None:
        self.pool.mock_cursor.fetchone.return_value = None
        result = self.repo.get_job_by_id(uuid4())
        assert result is None

    def test_get_jobs_by_user(self) -> None:
        uid = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "status": "completed"},
            {"id": uuid4(), "status": "queued"},
        ]
        result = self.repo.get_jobs_by_user(uid)
        assert len(result) == 2

    def test_update_job_status_simple(self) -> None:
        job_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": job_id, "status": "running",
        }
        result = self.repo.update_job_status(job_id, "running")
        assert result["status"] == "running"

    def test_update_job_status_with_progress(self) -> None:
        job_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": job_id, "status": "running", "progress": 50,
        }
        result = self.repo.update_job_status(job_id, "running", progress=50, current_epoch=50)
        assert result["progress"] == 50

    def test_update_job_status_completed(self) -> None:
        job_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": job_id, "status": "completed",
        }
        result = self.repo.update_job_status(
            job_id, "completed", metrics={"map50": 0.85}
        )
        assert result["status"] == "completed"

    def test_update_job_status_failed(self) -> None:
        job_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": job_id, "status": "failed",
        }
        result = self.repo.update_job_status(
            job_id, "failed", error_message="CUDA out of memory"
        )
        assert result["status"] == "failed"

    def test_create_model(self) -> None:
        uid = uuid4()
        model_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": model_id, "name": "Model v1",
            "model_path": "models/best.pt", "is_active": False,
        }
        result = self.repo.create_model({
            "user_id": uid,
            "job_id": uuid4(),
            "name": "Model v1",
            "model_path": "models/best.pt",
            "map50": 0.85,
            "precision": 0.90,
            "recall": 0.80,
        })
        assert result["name"] == "Model v1"

    def test_get_models_by_user(self) -> None:
        uid = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "name": "Model v1", "is_active": True},
        ]
        result = self.repo.get_models_by_user(uid)
        assert len(result) == 1

    def test_activate_model(self) -> None:
        model_id = uuid4()
        uid = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": model_id, "is_active": True,
        }
        self.pool.mock_cursor.rowcount = 1
        result = self.repo.activate_model(model_id, uid)
        assert result["is_active"] is True


class TestAlertRepository:
    """Testes para AlertRepository."""

    def setup_method(self) -> None:
        self.pool = MockPool()
        from app.infrastructure.database.repositories.alert_repository import AlertRepository
        self.repo = AlertRepository(self.pool)  # type: ignore[arg-type]

    def test_create_alert(self) -> None:
        cam_id = uuid4()
        alert_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": alert_id, "camera_id": cam_id,
            "confidence": 0.95, "acknowledged": False,
        }
        result = self.repo.create(
            cam_id,
            [{"class": "no_helmet", "box": [0.1, 0.2, 0.3, 0.4]}],
            0.95,
            "evidence/cam1/2024-01.jpg",
        )
        assert result["confidence"] == 0.95

    def test_get_by_camera(self) -> None:
        cam_id = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "confidence": 0.9, "acknowledged": False},
            {"id": uuid4(), "confidence": 0.8, "acknowledged": True},
        ]
        result = self.repo.get_by_camera(cam_id)
        assert len(result) == 2

    def test_get_unacknowledged_with_camera(self) -> None:
        cam_id = uuid4()
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "acknowledged": False},
        ]
        result = self.repo.get_unacknowledged(cam_id)
        assert len(result) == 1

    def test_get_unacknowledged_all(self) -> None:
        self.pool.mock_cursor.fetchall.return_value = [
            {"id": uuid4(), "acknowledged": False},
            {"id": uuid4(), "acknowledged": False},
        ]
        result = self.repo.get_unacknowledged()
        assert len(result) == 2

    def test_acknowledge(self) -> None:
        alert_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {
            "id": alert_id, "acknowledged": True,
        }
        result = self.repo.acknowledge(alert_id)
        assert result["acknowledged"] is True

    def test_count_by_camera(self) -> None:
        cam_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = {"count": 7}
        count = self.repo.count_by_camera(cam_id)
        assert count == 7

    def test_count_by_camera_none_row(self) -> None:
        cam_id = uuid4()
        self.pool.mock_cursor.fetchone.return_value = None
        count = self.repo.count_by_camera(cam_id)
        assert count == 0
