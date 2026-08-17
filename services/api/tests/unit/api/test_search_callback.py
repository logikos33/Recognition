"""
Tests: search_handlers.py::search_callback_handler — callback da GPU remota
(search_content.py) pro job de busca por conteúdo.

Cobre:
- auth: token ausente → 401; token errado/job sem token → 403 (hmac).
- status='failed'/'running': grava reason/metrics, nunca toca em results.
- status='completed': valida o payload ANTES de gravar QUALQUER coisa —
  "nunca sucesso silencioso":
  - findings ausente do payload → 400 (mesmo vazia sendo válida, ausente
    não é);
  - findings não é lista → 400;
  - frame_id fora da seleção do job → 400, nada gravado;
  - label desconhecido (fora de job.terms) → 400;
  - term não bate com o query registrado pro label → 400;
  - bbox fora de [0,1] / não tem 4 elementos → 400;
  - confidence fora de [0,1] → 400;
  - payload válido → apply_callback_completed chamado com findings_count e
    results corretos, job marcado completed;
  - findings=[] (lista vazia, mas presente) → completed com
    findings_count=0 — honesto, não é erro.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.api.v1.training.search_handlers import search_callback_handler

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TENANT_ID = "99999999-8888-7777-6666-555555555555"
_TOKEN = "callback-token-valido-de-verdade"
_HANDLERS = "app.api.v1.training.search_handlers"


def _job(**overrides) -> dict:
    job = {
        "id": _JOB_ID, "tenant_id": _TENANT_ID, "status": "running",
        "callback_token": _TOKEN, "selected_frame_ids": ["f1", "f2"],
        "terms": [{"label": "Capacete", "query": "safety helmet"}],
    }
    job.update(overrides)
    return job


def _call(app, *, body: dict, repo: MagicMock, token: str = _TOKEN):
    with app.test_request_context(
        f"/api/v1/training/search/jobs/{_JOB_ID}/callback",
        method="POST", json=body, headers={"X-Callback-Token": token},
    ), patch(f"{_HANDLERS}._get_search_repo", return_value=repo):
        response, status = search_callback_handler(_JOB_ID)
    return response.get_json(), status


class TestAuth:
    def test_missing_token_returns_401(self, app) -> None:
        repo = MagicMock()
        body, status = _call(app, body={"status": "running"}, repo=repo, token="")
        assert status == 401

    def test_wrong_token_returns_403(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(app, body={"status": "running"}, repo=repo, token="token-errado")
        assert status == 403

    def test_job_without_stored_token_returns_403(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job(callback_token=None)
        body, status = _call(app, body={"status": "running"}, repo=repo)
        assert status == 403

    def test_job_missing_returns_403(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = None
        body, status = _call(app, body={"status": "running"}, repo=repo)
        assert status == 403


class TestInvalidStatus:
    def test_unknown_status_returns_400(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(app, body={"status": "bogus"}, repo=repo)
        assert status == 400


class TestFailedStatus:
    def test_persists_failure_reason(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app, body={"status": "failed", "error_message": "manifesto ausente"}, repo=repo,
        )
        assert status == 200
        assert body["data"]["status"] == "failed"
        repo.apply_callback_failed.assert_called_once()
        assert "manifesto" in repo.apply_callback_failed.call_args.args[1]


class TestRunningStatus:
    def test_merges_progress_metrics(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app,
            body={"status": "running", "metrics": {"frames_processed": 10, "frames_total": 100}},
            repo=repo,
        )
        assert status == 200
        repo.merge_metrics.assert_called_once_with(
            _JOB_ID, {"frames_processed": 10, "frames_total": 100},
        )

    def test_invalid_metrics_type_returns_400(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app, body={"status": "running", "metrics": "not-a-dict"}, repo=repo,
        )
        assert status == 400
        repo.merge_metrics.assert_not_called()


class TestCompletedStatusValidation:
    def test_findings_absent_returns_400_nothing_written(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(app, body={"status": "completed"}, repo=repo)
        assert status == 400
        repo.apply_callback_completed.assert_not_called()

    def test_findings_not_a_list_returns_400(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app, body={"status": "completed", "findings": "not-a-list"}, repo=repo,
        )
        assert status == 400
        repo.apply_callback_completed.assert_not_called()

    def test_frame_outside_selection_rejects_entire_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job(selected_frame_ids=["f1"])
        findings = [
            {
                "frame_id": "frame-fora-da-selecao", "term": "safety helmet",
                "label": "Capacete", "bbox": [0.5, 0.5, 0.1, 0.1], "confidence": 0.9,
            },
        ]
        body, status = _call(
            app, body={"status": "completed", "findings": findings}, repo=repo,
        )
        assert status == 400
        assert "fora da seleção" in body["error"]
        repo.apply_callback_completed.assert_not_called()

    def test_unknown_label_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        findings = [
            {
                "frame_id": "f1", "term": "safety helmet", "label": "Rótulo Desconhecido",
                "bbox": [0.5, 0.5, 0.1, 0.1], "confidence": 0.9,
            },
        ]
        body, status = _call(
            app, body={"status": "completed", "findings": findings}, repo=repo,
        )
        assert status == 400
        repo.apply_callback_completed.assert_not_called()

    def test_term_mismatched_with_registered_query_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        findings = [
            {
                "frame_id": "f1", "term": "hard hat",  # não é o query registrado
                "label": "Capacete", "bbox": [0.5, 0.5, 0.1, 0.1], "confidence": 0.9,
            },
        ]
        body, status = _call(
            app, body={"status": "completed", "findings": findings}, repo=repo,
        )
        assert status == 400
        repo.apply_callback_completed.assert_not_called()

    def test_bbox_out_of_range_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        findings = [
            {
                "frame_id": "f1", "term": "safety helmet", "label": "Capacete",
                "bbox": [1.5, 0.5, 0.1, 0.1], "confidence": 0.9,
            },
        ]
        body, status = _call(
            app, body={"status": "completed", "findings": findings}, repo=repo,
        )
        assert status == 400
        repo.apply_callback_completed.assert_not_called()

    def test_bbox_wrong_length_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        findings = [
            {
                "frame_id": "f1", "term": "safety helmet", "label": "Capacete",
                "bbox": [0.5, 0.5, 0.1], "confidence": 0.9,
            },
        ]
        body, status = _call(
            app, body={"status": "completed", "findings": findings}, repo=repo,
        )
        assert status == 400

    def test_confidence_out_of_range_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        findings = [
            {
                "frame_id": "f1", "term": "safety helmet", "label": "Capacete",
                "bbox": [0.5, 0.5, 0.1, 0.1], "confidence": 1.2,
            },
        ]
        body, status = _call(
            app, body={"status": "completed", "findings": findings}, repo=repo,
        )
        assert status == 400
        repo.apply_callback_completed.assert_not_called()

    def test_finding_not_object_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app, body={"status": "completed", "findings": ["not-an-object"]}, repo=repo,
        )
        assert status == 400


class TestCompletedStatusSuccess:
    def test_valid_payload_persists_results_and_completes_job(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job(
            selected_frame_ids=["f1", "f2"],
            terms=[
                {"label": "Capacete", "query": "safety helmet"},
                {"label": "Bota", "query": "safety boot"},
            ],
        )
        findings = [
            {
                "frame_id": "f1", "term": "safety helmet", "label": "Capacete",
                "bbox": [0.5, 0.5, 0.1, 0.1], "confidence": 0.91,
            },
            {
                "frame_id": "f2", "term": "safety boot", "label": "Bota",
                "bbox": [0.2, 0.3, 0.05, 0.05], "confidence": 0.77,
            },
        ]
        body, status = _call(
            app,
            body={
                "status": "completed", "findings": findings,
                "metrics": {"frames_total": 2},
            },
            repo=repo,
        )

        assert status == 200
        assert body["data"]["status"] == "completed"
        assert body["data"]["findings_count"] == 2

        repo.apply_callback_completed.assert_called_once()
        call_args = repo.apply_callback_completed.call_args.args
        assert call_args[0] == _JOB_ID
        assert call_args[1] == 2
        results = call_args[2]
        assert {r["frame_id"] for r in results} == {"f1", "f2"}
        assert call_args[3] == {"frames_total": 2}

    def test_zero_findings_is_honest_completed_not_an_error(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app, body={"status": "completed", "findings": []}, repo=repo,
        )
        assert status == 200
        assert body["data"]["status"] == "completed"
        assert body["data"]["findings_count"] == 0
        repo.apply_callback_completed.assert_called_once_with(_JOB_ID, 0, [], {})
