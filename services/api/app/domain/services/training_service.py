"""
Recognition — Training Service.

Orquestra pipeline de treinamento YOLOv8. NÃO conhece Flask.
"""
import logging
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.infrastructure.database.repositories.training_repository import (
    TrainingRepository,
)

logger = logging.getLogger(__name__)


class TrainingService:
    """Use cases de treinamento."""

    def __init__(self, training_repo: TrainingRepository) -> None:
        self._training_repo = training_repo

    def create_job(
        self,
        user_id: UUID,
        preset: str = "balanced",
        model_size: str = "yolo26n",
        total_epochs: int = 100,
    ) -> dict:
        """Cria job de treinamento."""
        valid_presets = {"fast", "balanced", "quality"}
        if preset not in valid_presets:
            raise ValidationError(
                f"Preset inválido: {preset}. Válidos: {valid_presets}"
            )

        valid_models = {"yolo26n", "yolo26s", "yolo26m", "yolo26l", "yolo26x"}
        if model_size not in valid_models:
            raise ValidationError(
                f"Model size inválido: {model_size}. Válidos: {valid_models}"
            )

        job = self._training_repo.create_job(
            user_id=user_id,
            preset=preset,
            model_size=model_size,
            total_epochs=total_epochs,
        )
        job["id"] = str(job["id"])
        return job

    def get_job(self, job_id: UUID) -> dict:
        """Busca job por ID."""
        job = self._training_repo.get_job_by_id(job_id)
        if not job:
            raise NotFoundError("Training job", str(job_id))
        job["id"] = str(job["id"])
        return job

    def list_jobs(self, user_id: UUID) -> list[dict]:
        """Lista jobs do usuário."""
        jobs = self._training_repo.get_jobs_by_user(user_id)
        for j in jobs:
            j["id"] = str(j["id"])
        return jobs

    def update_progress(
        self,
        job_id: UUID,
        status: str,
        progress: int | None = None,
        current_epoch: int | None = None,
        metrics: dict | None = None,
        error_message: str | None = None,
    ) -> dict:
        """Atualiza progresso do job."""
        result = self._training_repo.update_job_status(
            job_id=job_id,
            status=status,
            progress=progress,
            current_epoch=current_epoch,
            metrics=metrics,
            error_message=error_message,
        )
        if not result:
            raise NotFoundError("Training job", str(job_id))
        result["id"] = str(result["id"])
        return result

    def list_models(self, user_id: UUID) -> list[dict]:
        """Lista modelos treinados do usuário."""
        models = self._training_repo.get_models_by_user(user_id)
        for m in models:
            m["id"] = str(m["id"])
        return models

    def register_model(self, data: dict) -> dict:
        """Registra modelo treinado."""
        model = self._training_repo.create_model(data)
        model["id"] = str(model["id"])
        return model

    def get_current_running_job(self, user_id: UUID) -> dict | None:
        """Busca job mais recente em execução (pending/running), ou o último job."""
        job = self._training_repo.get_current_running_job(user_id)
        if job is None:
            job = self._training_repo.get_latest_job(user_id)
        if job is None:
            return None
        job["id"] = str(job["id"])
        job["user_id"] = str(job["user_id"])
        return job

    def stop_job(self, job_id: UUID, user_id: UUID) -> dict | None:
        """Para job de treinamento."""
        result = self._training_repo.stop_job(job_id, user_id)
        if result:
            result["id"] = str(result["id"])
            result["user_id"] = str(result["user_id"])
        return result

    def activate_model(self, model_id: UUID, user_id: UUID) -> dict:
        """Ativa modelo (desativa outros do mesmo usuário)."""
        result = self._training_repo.activate_model(model_id, user_id)
        if not result:
            raise NotFoundError("Modelo", str(model_id))
        result["id"] = str(result["id"])
        return result
