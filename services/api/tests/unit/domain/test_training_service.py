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
            "model_size": "yolo26n", "status": "pending",
        }
        result = self.service.create_job(uuid4())
        assert result["preset"] == "balanced"
        assert result["id"] == str(jid)

    def test_create_job_passes_dataset_version_id_to_repo(self) -> None:
        """task B2: dataset_version_id chega ao repository (INSERT real)."""
        jid = uuid4()
        dsv_id = uuid4()
        self.training_repo.create_job.return_value = {
            "id": jid, "preset": "balanced", "model_size": "yolo26n",
            "status": "pending", "dataset_version_id": dsv_id,
        }
        result = self.service.create_job(uuid4(), dataset_version_id=dsv_id)

        self.training_repo.create_job.assert_called_once()
        assert self.training_repo.create_job.call_args.kwargs["dataset_version_id"] == dsv_id
        assert result["dataset_version_id"] == str(dsv_id)

    def test_create_job_without_dataset_version_id_stays_none(self) -> None:
        """Sem dataset_version_id resolvido, o job nasce com a coluna NULL."""
        jid = uuid4()
        self.training_repo.create_job.return_value = {
            "id": jid, "preset": "balanced", "model_size": "yolo26n",
            "status": "pending", "dataset_version_id": None,
        }
        result = self.service.create_job(uuid4())

        assert self.training_repo.create_job.call_args.kwargs["dataset_version_id"] is None
        assert result["dataset_version_id"] is None

    def test_create_job_forwards_assumed_tenant_id_to_repo(self) -> None:
        """Contexto assumido: o tenant do JWT (get_tenant_id()) chega ao repo,
        NÃO o tenant de casa do user_id.

        Falha-antes/passa-depois: antes do fix create_job não aceitava
        tenant_id e o repository caía no fallback
        `(SELECT tenant_id FROM users WHERE id=user_id)` = tenant de casa do
        superadmin. Um job criado sob contexto assumido (POST /tenants/<B>/assume)
        nascia taggeado com o tenant A do superadmin; o modelo resultante
        herdava A e ficava 404 na registry sob contexto B (#302/#313).
        """
        jid = uuid4()
        assumed_tenant = uuid4()  # tenant B (alvo assumido) != tenant de casa
        self.training_repo.create_job.return_value = {
            "id": jid, "preset": "balanced", "model_size": "yolo26n",
            "status": "pending",
        }
        self.service.create_job(uuid4(), tenant_id=assumed_tenant)

        assert (
            self.training_repo.create_job.call_args.kwargs["tenant_id"]
            == assumed_tenant
        )

    def test_create_job_invalid_preset(self) -> None:
        with pytest.raises(ValidationError, match="Preset inválido"):
            self.service.create_job(uuid4(), preset="invalid")

    def test_create_job_invalid_model(self) -> None:
        with pytest.raises(ValidationError, match="Model size inválido"):
            self.service.create_job(uuid4(), model_size="yolov99")

    def test_get_job_success(self) -> None:
        jid, tenant_id = uuid4(), str(uuid4())
        self.training_repo.get_job_for_tenant.return_value = {
            "id": jid, "status": "running",
        }
        result = self.service.get_job(jid, tenant_id)
        assert result["id"] == str(jid)
        self.training_repo.get_job_for_tenant.assert_called_once_with(jid, tenant_id)

    def test_get_job_not_found(self) -> None:
        """Job de outro tenant (ou inexistente) → NotFoundError (C-01)."""
        self.training_repo.get_job_for_tenant.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_job(uuid4(), str(uuid4()))

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
        """Escopo por tenant (C-01) — ver get_models_by_tenant."""
        self.training_repo.get_models_by_tenant.return_value = [
            {"id": uuid4(), "name": "Model v1"},
        ]
        result = self.service.list_models(str(uuid4()))
        assert len(result) == 1
        self.training_repo.get_models_by_tenant.assert_called_once()


class TestLinhagemBaseModel:
    """base_model NULL é regressão de linhagem: o gate de licença (ADR-0044)
    decide pela VARIANTE — base é Apache, XL/2XL são PML. Ver D-164."""

    def test_create_job_repassa_linhagem_ao_repository(self):
        from unittest.mock import MagicMock
        from uuid import uuid4
        from app.domain.services.training_service import TrainingService

        repo = MagicMock()
        repo.create_job.return_value = {"id": uuid4()}
        svc = TrainingService(repo)
        svc.create_job(uuid4(), framework="rfdetr", base_model="base",
                       hyperparams={"lr": 1e-4})
        kw = repo.create_job.call_args.kwargs
        assert kw["framework"] == "rfdetr"
        assert kw["base_model"] == "base"
        assert kw["hyperparams"] == {"lr": 1e-4}
