"""Tests: TrainingService."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.training_service import TrainingService


class TestTrainingService:
    """Testes para TrainingService."""

    def setup_method(self) -> None:
        self.training_repo = MagicMock()
        self.service = TrainingService(self.training_repo)

    def test_create_job_success(self) -> None:
        jid = uuid4()
        self.training_repo.create_job.return_value = {
            "id": jid, "preset": "balanced",
            "model_size": "yolov8n", "status": "pending",
        }
        result = self.service.create_job(uuid4())
        assert result["preset"] == "balanced"
        assert result["id"] == str(jid)

    def test_create_job_invalid_preset(self) -> None:
        with pytest.raises(ValidationError, match="Preset inválido"):
            self.service.create_job(uuid4(), preset="invalid")

    def test_create_job_invalid_model(self) -> None:
        with pytest.raises(ValidationError, match="Model size inválido"):
            self.service.create_job(uuid4(), model_size="yolov99")

    def test_get_job_success(self) -> None:
        jid = uuid4()
        self.training_repo.get_job_by_id.return_value = {
            "id": jid, "status": "running",
        }
        result = self.service.get_job(jid)
        assert result["id"] == str(jid)

    def test_get_job_not_found(self) -> None:
        self.training_repo.get_job_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_job(uuid4())

    def test_list_jobs(self) -> None:
        self.training_repo.get_jobs_by_user.return_value = [
            {"id": uuid4(), "status": "completed"},
            {"id": uuid4(), "status": "pending"},
        ]
        result = self.service.list_jobs(uuid4())
        assert len(result) == 2

    def test_update_progress(self) -> None:
        jid = uuid4()
        self.training_repo.update_job_status.return_value = {
            "id": jid, "status": "running", "progress": 50,
        }
        result = self.service.update_progress(jid, "running", progress=50)
        assert result["progress"] == 50

    def test_list_models(self) -> None:
        self.training_repo.get_models_by_user.return_value = [
            {"id": uuid4(), "name": "Model v1"},
        ]
        result = self.service.list_models(uuid4())
        assert len(result) == 1

    def test_activate_model_success(self) -> None:
        mid = uuid4()
        self.training_repo.activate_model.return_value = {
            "id": mid, "is_active": True,
        }
        result = self.service.activate_model(mid, uuid4())
        assert result["is_active"] is True

    def test_activate_model_not_found(self) -> None:
        self.training_repo.activate_model.return_value = None
        with pytest.raises(NotFoundError):
            self.service.activate_model(uuid4(), uuid4())
