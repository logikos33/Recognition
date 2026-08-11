"""
Tests: app/api/v1/training/job_handlers.py::training_progress_callback_handler
— guard de artefato (task "treino não pode mentir").

Antes desta task, um callback da GPU remota dizendo status='completed'
gravava training_jobs.status='completed' direto — sem NENHUMA confirmação
de que o artefato ONNX chegou de fato no R2 (export falho, bug de upload,
callback adulterado). `_downgrade_to_failed_if_artifact_unverified`
reconfirma via HEAD/exists real (`verify_model_artifact`) antes de deixar o
payload seguir pro update_job_status — sem artefato confirmável, rebaixa
'completed' → 'failed' com motivo legível.

Falha-antes/passa-depois: sem o guard, os dois primeiros testes desta
classe passariam status='completed' pro banco mesmo com o artefato ausente.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TENANT_ID = "99999999-8888-7777-6666-555555555555"
_TOKEN = "callback-token-valido-de-verdade"


def _call_callback(app, *, body: dict, repo: MagicMock, tenant_id, artifact_verified: bool):
    from app.api.v1.training.job_handlers import training_progress_callback_handler

    with app.test_request_context(
        f"/api/v1/training/jobs/{_JOB_ID}/progress-callback",
        method="POST",
        json=body,
        headers={"X-Callback-Token": _TOKEN},
    ), patch(
        "app.api.v1.training.job_handlers._get_training_repo", return_value=repo,
    ), patch(
        "app.infrastructure.queue.tasks.training._get_job_tenant_id",
        return_value=tenant_id,
    ), patch(
        "app.infrastructure.storage.verify_model_artifact",
        return_value=artifact_verified,
    ) as mock_verify:
        response, status = training_progress_callback_handler(_JOB_ID)
    return response.get_json(), status, mock_verify


def _repo_with_token() -> MagicMock:
    repo = MagicMock()
    repo.get_job_by_id.return_value = {"id": _JOB_ID, "callback_token": _TOKEN}
    return repo


class TestCompletedWithoutVerifiedArtifact:
    def test_downgrades_status_to_failed(self, app) -> None:
        repo = _repo_with_token()
        body, status, mock_verify = _call_callback(
            app,
            body={"status": "completed", "progress": 100, "metrics": {"mAP50": 0.9}},
            repo=repo,
            tenant_id=_TENANT_ID,
            artifact_verified=False,
        )
        assert status == 200  # envelope success — o payload interno é que muda
        assert body["data"]["status"] == "failed"
        mock_verify.assert_called_once()

    def test_persists_failed_with_legible_reason(self, app) -> None:
        repo = _repo_with_token()
        _call_callback(
            app,
            body={"status": "completed", "progress": 100, "metrics": {}},
            repo=repo,
            tenant_id=_TENANT_ID,
            artifact_verified=False,
        )
        repo.update_job_status.assert_called_once()
        call = repo.update_job_status.call_args
        assert call.args[1] == "failed"
        error_message = call.kwargs["error_message"]
        assert "artefato" in error_message.lower()
        assert "confirmado" in error_message.lower()

    def test_never_persists_completed_when_unverified(self, app) -> None:
        repo = _repo_with_token()
        _call_callback(
            app,
            body={"status": "completed", "progress": 100, "metrics": {}},
            repo=repo,
            tenant_id=_TENANT_ID,
            artifact_verified=False,
        )
        persisted_status = repo.update_job_status.call_args.args[1]
        assert persisted_status != "completed"


class TestCompletedWithVerifiedArtifact:
    def test_status_stays_completed(self, app) -> None:
        repo = _repo_with_token()
        body, status, mock_verify = _call_callback(
            app,
            body={"status": "completed", "progress": 100, "metrics": {"mAP50": 0.9}},
            repo=repo,
            tenant_id=_TENANT_ID,
            artifact_verified=True,
        )
        assert status == 200
        assert body["data"]["status"] == "completed"
        mock_verify.assert_called_once()
        assert repo.update_job_status.call_args.args[1] == "completed"


class TestNonCompletedStatusSkipsArtifactCheck:
    def test_running_status_never_calls_verify(self, app) -> None:
        repo = _repo_with_token()
        _, _status, mock_verify = _call_callback(
            app,
            body={"status": "running", "progress": 40, "metrics": {}},
            repo=repo,
            tenant_id=_TENANT_ID,
            artifact_verified=False,  # deliberadamente False — não deve importar
        )
        mock_verify.assert_not_called()
        assert repo.update_job_status.call_args.args[1] == "running"

    def test_failed_status_never_calls_verify(self, app) -> None:
        repo = _repo_with_token()
        _, _status, mock_verify = _call_callback(
            app,
            body={"status": "failed", "error_message": "GPU crashou"},
            repo=repo,
            tenant_id=_TENANT_ID,
            artifact_verified=True,
        )
        mock_verify.assert_not_called()
        assert repo.update_job_status.call_args.args[1] == "failed"
