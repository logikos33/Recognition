"""
Tests: infrastructure/queue/tasks/gpu_reconciler.py — reconciliador de pods
RunPod órfãos (camada 3 de 3 de garantia de morte).

Cobre:
- reconcile_runpod_pods_impl (lógica pura, sem Celery real):
  - mata pod de job em estado terminal (completed/failed/stopped) no DB
  - mata pod sem job correspondente (órfão de verdade)
  - mata pod mais velho que o deadline do tipo de carga (started_at expirado)
  - NUNCA mexe em pod de outra origem (nome sem prefixo "recognition-")
  - mantém pod de job 'running' dentro do deadline
- job marcado 'failed' quando o reconciler mata um pod cujo job não estava
  em estado terminal (deadline estourado) — nunca 'completed'/'stopped'
  sobrescritos.
- reconcile_runpod_pods (task Celery): no-op sem pool/RUNPOD_API_KEY; nunca
  levanta (best-effort).
- _load_runpod_jobs cobre TAMBÉM propagation_jobs (migration 112) e
  search_jobs (migration 113, busca por conteúdo), união com
  training_jobs — _mark_job_failed roteia pra tabela certa via
  job["_table"].
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.infrastructure.gpu.runpod_client import RunPodError
from app.infrastructure.gpu.runpod_runner import JobKind
from app.infrastructure.queue.tasks.gpu_reconciler import (
    _load_runpod_jobs,
    _mark_job_failed,
    reconcile_runpod_pods,
    reconcile_runpod_pods_impl,
)

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _client(pods: list[dict]) -> MagicMock:
    client = MagicMock()
    client.list_pods.return_value = pods
    return client


class TestReconcileImpl:
    def test_terminates_pod_of_terminal_job(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "3600")
        client = _client([{"id": "pod-1", "name": "recognition-train-abcd1234"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={"pod-1": {
                "id": _JOB_ID, "status": "completed",
                "started_at": datetime.now(timezone.utc), "tenant_id": "t1",
            }},
        ):
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["terminated"] == ["pod-1"]
        client.terminate_pod.assert_called_once_with("pod-1")

    def test_terminates_orphan_pod_without_job(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "3600")
        client = _client([{"id": "pod-orphan", "name": "recognition-train-deadbeef"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={},
        ):
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["terminated"] == ["pod-orphan"]
        client.terminate_pod.assert_called_once_with("pod-orphan")

    def test_terminates_pod_older_than_deadline_and_marks_job_failed(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "60")
        old_start = datetime.now(timezone.utc) - timedelta(seconds=120)
        client = _client([{"id": "pod-expired", "name": "recognition-train-11112222"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={"pod-expired": {
                "id": _JOB_ID, "status": "running",
                "started_at": old_start, "tenant_id": "t1",
            }},
        ), patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._mark_job_failed"
        ) as mock_mark_failed:
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["terminated"] == ["pod-expired"]
        client.terminate_pod.assert_called_once_with("pod-expired")
        mock_mark_failed.assert_called_once()
        assert mock_mark_failed.call_args.args[1] == _JOB_ID

    def test_keeps_running_job_within_deadline(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "3600")
        recent_start = datetime.now(timezone.utc) - timedelta(seconds=30)
        client = _client([{"id": "pod-alive", "name": "recognition-train-33334444"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={"pod-alive": {
                "id": _JOB_ID, "status": "running",
                "started_at": recent_start, "tenant_id": "t1",
            }},
        ):
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["kept"] == ["pod-alive"]
        client.terminate_pod.assert_not_called()

    def test_never_touches_pods_from_other_origin(self) -> None:
        """Pod sem o prefixo "recognition-" nunca é tocado — pode ser um
        recurso manual do operador na mesma conta RunPod."""
        client = _client([{"id": "pod-manual", "name": "my-manual-experiment"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={},
        ):
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["kept"] == ["pod-manual"]
        client.terminate_pod.assert_not_called()

    def test_pods_without_id_are_skipped(self) -> None:
        client = _client([{"name": "recognition-train-nopedid"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={},
        ):
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result == {"terminated": [], "kept": []}
        client.terminate_pod.assert_not_called()


class TestLoadRunpodJobsCoversPropagation:
    """migration 112 — o reconciler passou a unir training_jobs e
    propagation_jobs; cada entrada carrega _kind/_table pra o resto do
    fluxo (_is_expired, _mark_job_failed) tratar as duas igual."""

    def test_union_tags_kind_and_table_correctly(self) -> None:
        pool = MagicMock()
        with patch(
            "app.infrastructure.database.repositories.training_repository.TrainingRepository._execute",
            return_value=[{
                "id": "train-1", "status": "running", "started_at": None,
                "gpu_instance_ref": "pod-train", "tenant_id": "t1",
            }],
        ), patch(
            "app.infrastructure.database.repositories.propagation_repository."
            "PropagationRepository._execute",
            return_value=[{
                "id": "prop-1", "status": "running", "started_at": None,
                "gpu_instance_ref": "pod-prop", "tenant_id": "t1",
            }],
        ), patch(
            "app.infrastructure.database.repositories.search_repository."
            "SearchRepository._execute",
            return_value=[{
                "id": "search-1", "status": "running", "started_at": None,
                "gpu_instance_ref": "pod-search", "tenant_id": "t1",
            }],
        ):
            jobs_by_pod = _load_runpod_jobs(pool)

        assert jobs_by_pod["pod-train"]["_kind"] == JobKind.TRAIN
        assert jobs_by_pod["pod-train"]["_table"] == "training_jobs"
        assert jobs_by_pod["pod-prop"]["_kind"] == JobKind.PROPAGATE
        assert jobs_by_pod["pod-prop"]["_table"] == "propagation_jobs"
        assert jobs_by_pod["pod-search"]["_kind"] == JobKind.SEARCH
        assert jobs_by_pod["pod-search"]["_table"] == "search_jobs"

    def test_terminates_pod_of_terminal_propagation_job(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_PROPAGATE", "3600")
        client = _client([{"id": "pod-prop", "name": "recognition-propagate-abcd1234"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={"pod-prop": {
                "id": _JOB_ID, "status": "completed",
                "started_at": datetime.now(timezone.utc), "tenant_id": "t1",
                "_kind": JobKind.PROPAGATE, "_table": "propagation_jobs",
            }},
        ):
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["terminated"] == ["pod-prop"]
        client.terminate_pod.assert_called_once_with("pod-prop")

    def test_expired_propagation_job_marked_failed_in_propagation_jobs_table(
        self, monkeypatch,
    ) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_PROPAGATE", "60")
        old_start = datetime.now(timezone.utc) - timedelta(seconds=120)
        client = _client([{"id": "pod-prop-old", "name": "recognition-propagate-99998888"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={"pod-prop-old": {
                "id": _JOB_ID, "status": "running",
                "started_at": old_start, "tenant_id": "t1",
                "_kind": JobKind.PROPAGATE, "_table": "propagation_jobs",
            }},
        ), patch(
            "app.infrastructure.database.repositories.propagation_repository."
            "PropagationRepository",
        ) as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["terminated"] == ["pod-prop-old"]
        mock_repo.mark_failed.assert_called_once()
        assert mock_repo.mark_failed.call_args.args[0] == _JOB_ID

    def test_expired_training_job_still_marked_failed_in_training_jobs_table(
        self, monkeypatch,
    ) -> None:
        """Regressão: a extensão pra propagation_jobs não pode quebrar o
        caminho de training_jobs pré-existente."""
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "60")
        old_start = datetime.now(timezone.utc) - timedelta(seconds=120)
        client = _client([{"id": "pod-train-old", "name": "recognition-train-11119999"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={"pod-train-old": {
                "id": _JOB_ID, "status": "running",
                "started_at": old_start, "tenant_id": "t1",
                "_kind": JobKind.TRAIN, "_table": "training_jobs",
            }},
        ), patch(
            "app.infrastructure.database.repositories.training_repository.TrainingRepository."
            "update_job_status",
        ) as mock_update:
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["terminated"] == ["pod-train-old"]
        mock_update.assert_called_once()
        assert mock_update.call_args.args[1] == "failed"


class TestLoadRunpodJobsCoversSearch:
    """migration 113 — o reconciler passou a unir search_jobs também
    (busca por conteúdo); mesmo tratamento de propagation_jobs."""

    def test_terminates_pod_of_terminal_search_job(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_SEARCH", "1800")
        client = _client([{"id": "pod-search", "name": "recognition-search-abcd1234"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={"pod-search": {
                "id": _JOB_ID, "status": "completed",
                "started_at": datetime.now(timezone.utc), "tenant_id": "t1",
                "_kind": JobKind.SEARCH, "_table": "search_jobs",
            }},
        ):
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["terminated"] == ["pod-search"]
        client.terminate_pod.assert_called_once_with("pod-search")

    def test_expired_search_job_marked_failed_in_search_jobs_table(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_SEARCH", "60")
        old_start = datetime.now(timezone.utc) - timedelta(seconds=120)
        client = _client([{"id": "pod-search-old", "name": "recognition-search-99998888"}])
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler._load_runpod_jobs",
            return_value={"pod-search-old": {
                "id": _JOB_ID, "status": "running",
                "started_at": old_start, "tenant_id": "t1",
                "_kind": JobKind.SEARCH, "_table": "search_jobs",
            }},
        ), patch(
            "app.infrastructure.database.repositories.search_repository.SearchRepository",
        ) as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            result = reconcile_runpod_pods_impl(client, pool=MagicMock())

        assert result["terminated"] == ["pod-search-old"]
        mock_repo.mark_failed.assert_called_once()
        assert mock_repo.mark_failed.call_args.args[0] == _JOB_ID


class TestMarkJobFailedRoutesToCorrectTable:
    def test_defaults_to_training_jobs_when_table_omitted(self) -> None:
        """Assinatura anterior (sem `table`) continua funcionando —
        default preserva o comportamento pré-migration-112."""
        with patch(
            "app.infrastructure.database.repositories.training_repository."
            "TrainingRepository.update_job_status",
        ) as mock_update:
            _mark_job_failed(MagicMock(), _JOB_ID, "motivo qualquer")
        mock_update.assert_called_once()

    def test_routes_to_propagation_jobs_table(self) -> None:
        with patch(
            "app.infrastructure.database.repositories.propagation_repository."
            "PropagationRepository",
        ) as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            _mark_job_failed(MagicMock(), _JOB_ID, "motivo", "propagation_jobs")
        mock_repo.mark_failed.assert_called_once()

    def test_routes_to_search_jobs_table(self) -> None:
        with patch(
            "app.infrastructure.database.repositories.search_repository.SearchRepository",
        ) as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            _mark_job_failed(MagicMock(), _JOB_ID, "motivo", "search_jobs")
        mock_repo.mark_failed.assert_called_once()
        assert mock_repo.mark_failed.call_args.args[0] == _JOB_ID
        assert mock_repo.mark_failed.call_args.args[0] == _JOB_ID


class TestReconcileTaskBestEffort:
    def test_skips_without_pool(self) -> None:
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler.DatabasePool"
        ) as mock_pool:
            mock_pool.get_instance.return_value = None
            result = reconcile_runpod_pods()
        assert result == {"terminated": [], "kept": []}

    def test_skips_without_api_key(self) -> None:
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler.DatabasePool"
        ) as mock_pool, patch(
            "app.infrastructure.queue.tasks.gpu_reconciler.resolve_runpod_api_key",
            return_value="",
        ):
            mock_pool.get_instance.return_value = MagicMock()
            result = reconcile_runpod_pods()
        assert result == {"terminated": [], "kept": []}

    def test_never_raises_on_runpod_error(self) -> None:
        with patch(
            "app.infrastructure.queue.tasks.gpu_reconciler.DatabasePool"
        ) as mock_pool, patch(
            "app.infrastructure.queue.tasks.gpu_reconciler.resolve_runpod_api_key",
            return_value="k",
        ), patch(
            "app.infrastructure.queue.tasks.gpu_reconciler.RunPodClient",
            side_effect=RunPodError("boom"),
        ):
            mock_pool.get_instance.return_value = MagicMock()
            result = reconcile_runpod_pods()
        assert result == {"terminated": [], "kept": []}
