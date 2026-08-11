"""
Tests: propagation_handlers.py::propagation_callback_handler — callback da
GPU remota (propagate_seeded.py) pro job de propagação semeada.

Cobre:
- auth: token ausente → 401; token errado/job sem token → 403 (hmac).
- status='failed'/'running': grava reason/metrics, nunca chama
  apply_propagation_proposals.
- status='completed': valida o payload ANTES de gravar QUALQUER coisa —
  "nunca sucesso silencioso":
  - proposals não é dict → 400, nada gravado;
  - frame_id fora do pool do job → 400, NADA gravado (nem os frames
    válidos do mesmo payload — falha-antes/passa-depois: sem essa
    validação, um frame de fora do pool vazaria pre_annotations);
  - bbox fora de [0,1] / não tem 4 elementos → 400, nada gravado;
  - class vazia/ausente → 400, nada gravado;
  - confidence fora de [0,1] → 400, nada gravado;
  - payload válido → grava em training_frames via
    FrameRepository.apply_propagation_proposals (mesmo shape do jsonb de
    pre_annotations), proposals_count correto, job marcado completed;
  - proposals={} (zero propostas, mas payload íntegro) → completed com
    proposals_count=0 — honesto, não é um erro.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.api.v1.training.propagation_handlers import propagation_callback_handler

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TENANT_ID = "99999999-8888-7777-6666-555555555555"
_TOKEN = "callback-token-valido-de-verdade"
_HANDLERS = "app.api.v1.training.propagation_handlers"


def _job(**overrides) -> dict:
    job = {
        "id": _JOB_ID, "tenant_id": _TENANT_ID, "status": "running",
        "callback_token": _TOKEN, "pool_frame_ids": ["f1", "f2"],
    }
    job.update(overrides)
    return job


def _call(app, *, body: dict, repo: MagicMock, frame_repo: MagicMock, token: str = _TOKEN):
    with app.test_request_context(
        f"/api/v1/training/propagation/jobs/{_JOB_ID}/callback",
        method="POST", json=body, headers={"X-Callback-Token": token},
    ), patch(f"{_HANDLERS}._get_propagation_repo", return_value=repo), \
         patch(f"{_HANDLERS}._get_frame_repo", return_value=frame_repo):
        response, status = propagation_callback_handler(_JOB_ID)
    return response.get_json(), status


class TestAuth:
    def test_missing_token_returns_401(self, app) -> None:
        repo = MagicMock()
        body, status = _call(app, body={"status": "running"}, repo=repo, frame_repo=MagicMock(), token="")
        assert status == 401

    def test_wrong_token_returns_403(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app, body={"status": "running"}, repo=repo, frame_repo=MagicMock(), token="token-errado",
        )
        assert status == 403

    def test_job_without_stored_token_returns_403(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job(callback_token=None)
        body, status = _call(app, body={"status": "running"}, repo=repo, frame_repo=MagicMock())
        assert status == 403

    def test_job_missing_returns_403(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = None
        body, status = _call(app, body={"status": "running"}, repo=repo, frame_repo=MagicMock())
        assert status == 403


class TestInvalidStatus:
    def test_unknown_status_returns_400(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(app, body={"status": "bogus"}, repo=repo, frame_repo=MagicMock())
        assert status == 400


class TestFailedStatus:
    def test_persists_failure_reason(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app, body={"status": "failed", "error_message": "sha256 divergente"},
            repo=repo, frame_repo=MagicMock(),
        )
        assert status == 200
        assert body["data"]["status"] == "failed"
        repo.apply_callback_failed.assert_called_once()
        assert "sha256" in repo.apply_callback_failed.call_args.args[1]


class TestRunningStatus:
    def test_merges_progress_metrics(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app,
            body={"status": "running", "metrics": {"frames_processed": 20, "frames_total": 662}},
            repo=repo, frame_repo=MagicMock(),
        )
        assert status == 200
        repo.merge_metrics.assert_called_once_with(
            _JOB_ID, {"frames_processed": 20, "frames_total": 662},
        )

    def test_invalid_metrics_type_returns_400(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        body, status = _call(
            app, body={"status": "running", "metrics": "not-a-dict"},
            repo=repo, frame_repo=MagicMock(),
        )
        assert status == 400
        repo.merge_metrics.assert_not_called()


class TestCompletedStatusValidation:
    """Falha-antes/passa-depois: cada teste aqui é um jeito do payload
    final estar malformado — sem a validação, algum desses gravaria
    pre_annotations com dado inválido/fora do pool."""

    def test_proposals_not_dict_returns_400_nothing_written(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        frame_repo = MagicMock()
        body, status = _call(
            app, body={"status": "completed", "proposals": ["not", "a", "dict"]},
            repo=repo, frame_repo=frame_repo,
        )
        assert status == 400
        frame_repo.apply_propagation_proposals.assert_not_called()
        repo.apply_callback_completed.assert_not_called()

    def test_frame_outside_pool_rejects_entire_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job(pool_frame_ids=["f1", "f2"])
        frame_repo = MagicMock()
        payload = {
            "f1": [{"bbox": [0.5, 0.5, 0.1, 0.1], "class": "capacete", "confidence": 0.9}],
            "frame-fora-do-pool": [{"bbox": [0.1, 0.1, 0.1, 0.1], "class": "bota", "confidence": 0.8}],
        }
        body, status = _call(
            app, body={"status": "completed", "proposals": payload},
            repo=repo, frame_repo=frame_repo,
        )
        assert status == 400
        assert "fora do pool" in body["error"]
        # NADA foi gravado — nem o frame f1, que era válido no mesmo payload
        frame_repo.apply_propagation_proposals.assert_not_called()
        repo.apply_callback_completed.assert_not_called()

    def test_bbox_out_of_range_rejects_entire_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        frame_repo = MagicMock()
        payload = {"f1": [{"bbox": [1.5, 0.5, 0.1, 0.1], "class": "capacete", "confidence": 0.9}]}
        body, status = _call(
            app, body={"status": "completed", "proposals": payload},
            repo=repo, frame_repo=frame_repo,
        )
        assert status == 400
        frame_repo.apply_propagation_proposals.assert_not_called()

    def test_bbox_wrong_length_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        frame_repo = MagicMock()
        payload = {"f1": [{"bbox": [0.5, 0.5, 0.1], "class": "capacete", "confidence": 0.9}]}
        body, status = _call(
            app, body={"status": "completed", "proposals": payload},
            repo=repo, frame_repo=frame_repo,
        )
        assert status == 400

    def test_empty_class_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        frame_repo = MagicMock()
        payload = {"f1": [{"bbox": [0.5, 0.5, 0.1, 0.1], "class": "  ", "confidence": 0.9}]}
        body, status = _call(
            app, body={"status": "completed", "proposals": payload},
            repo=repo, frame_repo=frame_repo,
        )
        assert status == 400
        frame_repo.apply_propagation_proposals.assert_not_called()

    def test_confidence_out_of_range_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        frame_repo = MagicMock()
        payload = {"f1": [{"bbox": [0.5, 0.5, 0.1, 0.1], "class": "capacete", "confidence": 1.2}]}
        body, status = _call(
            app, body={"status": "completed", "proposals": payload},
            repo=repo, frame_repo=frame_repo,
        )
        assert status == 400
        frame_repo.apply_propagation_proposals.assert_not_called()

    def test_proposal_not_object_rejects_payload(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job()
        frame_repo = MagicMock()
        payload = {"f1": ["not-an-object"]}
        body, status = _call(
            app, body={"status": "completed", "proposals": payload},
            repo=repo, frame_repo=frame_repo,
        )
        assert status == 400


class TestCompletedStatusSuccess:
    def test_valid_payload_writes_pre_annotations_and_completes_job(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job(pool_frame_ids=["f1", "f2"])
        frame_repo = MagicMock()
        payload = {
            "f1": [
                {"bbox": [0.5, 0.5, 0.1, 0.1], "class": "capacete", "confidence": 0.91},
                {"bbox": [0.2, 0.3, 0.05, 0.05], "class": "bota", "confidence": 0.77},
            ],
            "f2": [],
        }
        body, status = _call(
            app,
            body={"status": "completed", "proposals": payload, "metrics": {"frames_total": 2}},
            repo=repo, frame_repo=frame_repo,
        )

        assert status == 200
        assert body["data"]["status"] == "completed"
        assert body["data"]["proposals_count"] == 2

        # f1 recebeu as 2 propostas normalizadas (mesmo shape do jsonb de
        # pre_annotations: bbox/class/confidence)
        write_calls = {c.args[0]: c.args[2] for c in frame_repo.apply_propagation_proposals.call_args_list}
        assert set(write_calls) == {"f1", "f2"}
        assert len(write_calls["f1"]) == 2
        assert write_calls["f1"][0]["class"] == "capacete"
        assert write_calls["f1"][0]["bbox"] == [0.5, 0.5, 0.1, 0.1]
        assert write_calls["f2"] == []

        # tenant_id propagado pro guard de escopo do UPDATE (defesa em profundidade)
        for c in frame_repo.apply_propagation_proposals.call_args_list:
            assert c.args[1] == _TENANT_ID

        repo.apply_callback_completed.assert_called_once_with(
            _JOB_ID, 2, {"frames_total": 2},
        )

    def test_zero_proposals_is_honest_completed_not_an_error(self, app) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = _job(pool_frame_ids=["f1", "f2"])
        frame_repo = MagicMock()
        payload = {"f1": [], "f2": []}
        body, status = _call(
            app, body={"status": "completed", "proposals": payload},
            repo=repo, frame_repo=frame_repo,
        )
        assert status == 200
        assert body["data"]["status"] == "completed"
        assert body["data"]["proposals_count"] == 0
        repo.apply_callback_completed.assert_called_once_with(_JOB_ID, 0, {})
