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
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.infrastructure.gpu.runpod_client import RunPodError
from app.infrastructure.queue.tasks.gpu_reconciler import (
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
