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
        dataset_version_id: "UUID | str | None" = None,
        tenant_id: "UUID | str | None" = None,
        framework: "str | None" = None,
        base_model: "str | None" = None,
        hyperparams: "dict | None" = None,
    ) -> dict:
        """Cria job de treinamento.

        framework/base_model/hyperparams (linhagem, migration 097): o
        repository sempre aceitou os três, mas ninguém os repassava daqui —
        o job nascia com base_model NULL. Isso não é metadado cosmético: o
        gate de licença (ADR-0044) decide pela VARIANTE, e RF-DETR base é
        Apache 2.0 enquanto XL/2XL são PML. Linhagem nula passa no gate (cai
        no default RFDETRBase()) mas não prova nada numa auditoria.

        dataset_version_id (task B2 — fiar linhagem de dataset ponta a
        ponta): repassado ao repository, que já suportava o parâmetro mas
        nunca o recebia daqui — o job nascia sem referência a nenhuma versão
        real de dataset. Resolução de qual versão usar (explícita do caller
        vs. mais recente do usuário) é responsabilidade do handler da rota,
        não deste serviço.

        tenant_id é o tenant do CONTEXTO DA REQUISIÇÃO (get_tenant_id() no
        handler), NÃO o tenant de casa do user_id. Sem ele, o repository caía
        no fallback `(SELECT tenant_id FROM users WHERE id = user_id)` — o
        tenant de casa do superadmin — e um job criado sob contexto assumido
        (POST /tenants/<B>/assume) nascia taggeado com o tenant A do
        superadmin. O modelo resultante herdava A e ficava 404 na registry
        sob contexto B (get_for_tenant escopa por get_tenant_id()=B). Mesmo
        bug de #302/#313: repassar o contexto assumido, não o de casa.
        """
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
            dataset_version_id=dataset_version_id,
            tenant_id=tenant_id,
            framework=framework,
            base_model=base_model,
            hyperparams=hyperparams,
        )
        job["id"] = str(job["id"])
        if job.get("dataset_version_id") is not None:
            job["dataset_version_id"] = str(job["dataset_version_id"])
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

    @staticmethod
    def _stringify_model_uuids(model: dict) -> dict:
        """Converte UUIDs do modelo em str (id + campos da migration 090)."""
        model["id"] = str(model["id"])
        for key in ("user_id", "job_id", "created_by", "tenant_id"):
            if model.get(key) is not None:
                model[key] = str(model[key])
        return model

    def list_models(self, user_id: UUID) -> list[dict]:
        """Lista modelos treinados do usuário (inclui origin/owner_name/owner_email)."""
        models = self._training_repo.get_models_by_user(user_id)
        for m in models:
            self._stringify_model_uuids(m)
        return models

    def register_model(self, data: dict) -> dict:
        """Registra modelo treinado (pass-through de created_by/origin)."""
        model = self._training_repo.create_model(data)
        return self._stringify_model_uuids(model)

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
