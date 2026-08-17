"""
Tests: infrastructure/queue/tasks/search.py — dispatch da busca por
conteúdo (RunPod/OWLv2).

Cobre a cadeia de guardas ANTES de qualquer chamada de rede/GPU:
- training_third_party_cloud_enabled OFF → job 'failed', RunPod nunca
  contatado (mesmo gate ADR-0047/0060 reusado da propagação).
- sem API key RunPod resolvível → job 'failed'.
- 🔴 SEARCH_CLOUD_ALLOWED_DATES relida NA HORA do dispatch: ausente →
  'failed' sem contatar RunPod (nunca confia no que foi checado na
  criação do job).
- 🔴 revalidação da seleção (refetch por id+tenant): frame sumiu/mudou de
  tenant, ou passou a violar a janela de datas → 'failed', RunPod nunca
  contatado — falha-antes/passa-depois.
- happy path: env do runner tem MANIFEST_URL/CALLBACK_URL/CALLBACK_TOKEN/
  CONFIDENCE_THRESHOLD/PROGRESS_EVERY_N; manifesto sobe pro storage do
  tenant com termos+frames; callback_token gerado e SEMPRE revogado.
- corrida de stop / JobStoppedError: mesmo padrão de dispatch_propagation.
"""
from __future__ import annotations

import json
from contextlib import ExitStack
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.infrastructure.gpu.runpod_runner import JobKind, JobStoppedError
from app.infrastructure.queue.tasks import search as search_mod

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TENANT = "99999999-8888-7777-6666-555555555555"
_ALLOWED_RANGES = [(date(2026, 7, 31), date(2026, 7, 31))]


def _base_job(**overrides) -> dict:
    job = {
        "id": _JOB_ID,
        "tenant_id": _TENANT,
        "status": "queued",
        "selected_frame_ids": ["f1", "f2"],
        "frames_hash": "whatever",
        "terms": [{"label": "Capacete", "query": "safety helmet"}],
        "callback_token": None,
    }
    job.update(overrides)
    return job


def _frame(frame_id: str, *, captured_at=datetime(2026, 7, 31, 10, 0)) -> dict:
    return {
        "id": frame_id, "tenant_id": _TENANT,
        "r2_key": f"frames/{frame_id}.jpg", "captured_at": captured_at,
    }


class _Harness:
    """Bundle de mocks + patches padrão de dispatch_search — mesmo padrão
    de `test_propagation_dispatch.py::_Harness`."""

    def __init__(self, job: dict, frames: "list[dict] | None" = None) -> None:
        self.job = job
        self.search_repo = MagicMock()
        self.search_repo.get_by_id.return_value = job
        self.frame_repo = MagicMock()
        self.frame_repo.get_by_ids_and_tenant.return_value = frames or []
        self.storage = MagicMock()
        self.storage.generate_presigned_download_url.return_value = "https://r2/get?sig=1"
        self.run_runpod_job = MagicMock(return_value={
            "status": "completed", "metrics": {}, "pod_id": "pod-1",
        })
        self.third_party_enabled = True
        self.api_key = "runpod-key"
        self.allowed_ranges: "list[tuple] | None" = list(_ALLOWED_RANGES)

    def run(self) -> dict:
        with ExitStack() as stack:
            stack.enter_context(patch.object(search_mod, "DatabasePool"))
            stack.enter_context(patch.object(
                search_mod, "SearchRepository", return_value=self.search_repo,
            ))
            stack.enter_context(patch.object(
                search_mod, "FrameRepository", return_value=self.frame_repo,
            ))
            stack.enter_context(patch.object(
                search_mod, "get_storage", return_value=self.storage,
            ))
            stack.enter_context(patch.object(
                search_mod, "_third_party_cloud_training_enabled",
                return_value=self.third_party_enabled,
            ))
            stack.enter_context(patch.object(
                search_mod, "resolve_runpod_api_key", return_value=self.api_key,
            ))
            stack.enter_context(patch.object(
                search_mod, "cloud_search_allowed_dates",
                side_effect=lambda: self.allowed_ranges,
            ))
            stack.enter_context(patch.object(search_mod, "RunPodClient"))
            stack.enter_context(patch.object(
                search_mod, "_read_search_executor_source", return_value="# runner",
            ))
            stack.enter_context(patch.object(
                search_mod, "run_runpod_job", self.run_runpod_job,
            ))
            return search_mod.dispatch_search(job_id=_JOB_ID)


class TestThirdPartyCloudGate:
    def test_disabled_marks_failed_without_contacting_runpod(self) -> None:
        h = _Harness(_base_job())
        h.third_party_enabled = False

        result = h.run()

        assert result["status"] == "failed"
        assert "terceiro" in result["reason"]
        h.search_repo.mark_failed.assert_called_once()
        h.run_runpod_job.assert_not_called()


class TestApiKeyGate:
    def test_missing_api_key_marks_failed(self) -> None:
        h = _Harness(_base_job())
        h.api_key = ""

        result = h.run()

        assert result["status"] == "failed"
        assert "chave RunPod" in result["reason"]
        h.run_runpod_job.assert_not_called()


class TestCloudDatesGuardRevalidatedAtDispatch:
    def test_env_missing_at_dispatch_fails_even_if_it_existed_at_creation(self) -> None:
        """Guard relido NA HORA — mesmo que o job tenha sido criado com a
        env configurada, se ela sumiu/mudou até o dispatch, o job falha
        (nunca confia no que foi checado na criação)."""
        job = _base_job()
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames)
        h.allowed_ranges = None

        result = h.run()

        assert result["status"] == "failed"
        assert "SEARCH_CLOUD_ALLOWED_DATES" in result["reason"]
        h.run_runpod_job.assert_not_called()


class TestSelectionRevalidationAtDispatch:
    """O guard mais importante da task: refetch por id+tenant ANTES de
    qualquer manifesto/pod."""

    def test_frame_missing_since_creation_fails_before_runpod_call(self) -> None:
        job = _base_job(selected_frame_ids=["f1", "f2"])
        frames = [_frame("f1")]  # f2 sumiu (deletado ou mudou de tenant)
        h = _Harness(job, frames)

        result = h.run()

        assert result["status"] == "failed"
        assert "seleção mudou" in result["reason"]
        h.search_repo.mark_failed.assert_called_once()
        h.run_runpod_job.assert_not_called()

    def test_frame_now_outside_allowed_dates_fails(self) -> None:
        job = _base_job(selected_frame_ids=["f1", "f2"])
        frames = [_frame("f1"), _frame("f2", captured_at=datetime(2026, 8, 1, 10, 0))]
        h = _Harness(job, frames)

        result = h.run()

        assert result["status"] == "failed"
        assert "guard de nuvem falhou" in result["reason"]
        h.run_runpod_job.assert_not_called()

    def test_frame_missing_r2_key_fails(self) -> None:
        job = _base_job(selected_frame_ids=["f1", "f2"])
        f2 = _frame("f2")
        f2["r2_key"] = None
        frames = [_frame("f1"), f2]
        h = _Harness(job, frames)

        result = h.run()

        assert result["status"] == "failed"
        h.run_runpod_job.assert_not_called()

    def test_no_frames_selected_fails(self) -> None:
        job = _base_job(selected_frame_ids=[])
        h = _Harness(job, [])

        result = h.run()

        assert result["status"] == "failed"
        assert "sem frames selecionados" in result["reason"]
        h.run_runpod_job.assert_not_called()

    def test_no_terms_fails(self) -> None:
        job = _base_job(terms=[])
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames)

        result = h.run()

        assert result["status"] == "failed"
        assert "sem termos" in result["reason"]
        h.run_runpod_job.assert_not_called()


class TestHappyPathEnvAndManifest:
    def test_builds_manifest_and_calls_run_runpod_job_with_expected_env(self) -> None:
        job = _base_job(selected_frame_ids=["f1", "f2"])
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames)
        h.run_runpod_job.return_value = {
            "status": "completed",
            "metrics": {"gpu_cost": {"provider": "runpod", "actual_usd": 0.02}},
            "pod_id": "pod-1",
        }

        result = h.run()

        assert result["status"] == "completed"
        h.run_runpod_job.assert_called_once()
        call_kwargs = h.run_runpod_job.call_args.kwargs
        assert call_kwargs["kind"] == JobKind.SEARCH
        assert call_kwargs["executor_filename"] == "search_content.py"

        env = call_kwargs["env"]
        assert env["MANIFEST_URL"] == "https://r2/get?sig=1"
        assert env["CALLBACK_URL"].endswith(f"/api/v1/training/search/jobs/{_JOB_ID}/callback")
        assert len(env["CALLBACK_TOKEN"]) > 20
        assert env["CONFIDENCE_THRESHOLD"] == str(search_mod._DEFAULT_CONFIDENCE_THRESHOLD)
        assert env["PROGRESS_EVERY_N"] == str(search_mod._PROGRESS_EVERY_N)

        h.storage.upload_bytes.assert_called_once()
        manifest_key = h.storage.upload_bytes.call_args.args[0]
        assert manifest_key == f"search/{_TENANT}/{_JOB_ID}/manifest.json"
        manifest = json.loads(h.storage.upload_bytes.call_args.args[1])
        assert manifest["terms"] == [{"label": "Capacete", "query": "safety helmet"}]
        assert {f["frame_id"] for f in manifest["frames"]} == {"f1", "f2"}

        merged = h.search_repo.merge_metrics.call_args.args[1]
        assert merged["gpu_cost"]["actual_usd"] == 0.02

    def test_confidence_threshold_overridable_via_env(self, monkeypatch) -> None:
        monkeypatch.setenv("SEARCH_CONFIDENCE_THRESHOLD", "0.25")
        job = _base_job(selected_frame_ids=["f1", "f2"])
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames)

        h.run()

        env = h.run_runpod_job.call_args.kwargs["env"]
        assert env["CONFIDENCE_THRESHOLD"] == "0.25"

    def test_callback_token_revoked_even_when_run_runpod_job_raises(self) -> None:
        job = _base_job(selected_frame_ids=["f1", "f2"])
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames)
        h.run_runpod_job.side_effect = RuntimeError("pod RunPod crashou")

        result = h.run()

        assert result["status"] == "failed"
        # `repo` neste teste é um MagicMock — `revoke_callback_token` NÃO
        # cascateia pra `set_callback_token` como faz a classe real
        # (`SearchRepository.revoke_callback_token`, ver
        # search_repository.py); aqui verificamos que o dispatch CHAMA o
        # método de revogação (o comportamento de cascata é coberto à
        # parte pela implementação real do repository).
        h.search_repo.revoke_callback_token.assert_called_with(_JOB_ID)


class TestStopRaceAndJobStoppedError:
    def test_aborts_before_run_runpod_job_when_already_stopped(self) -> None:
        job = _base_job(selected_frame_ids=["f1", "f2"])
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames)
        h.search_repo.get_by_id.side_effect = [job, {"status": "stopped"}]

        result = h.run()

        assert result["status"] == "stopped"
        h.run_runpod_job.assert_not_called()

    def test_job_stopped_error_returns_stopped_never_overwrites_with_failed(self) -> None:
        job = _base_job(selected_frame_ids=["f1", "f2"])
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames)
        h.run_runpod_job.side_effect = JobStoppedError("parado")

        result = h.run()

        assert result["status"] == "stopped"
        h.search_repo.mark_failed.assert_not_called()


class TestMissingJob:
    def test_missing_job_returns_missing_without_touching_runpod(self) -> None:
        with patch.object(search_mod, "DatabasePool"), \
             patch.object(search_mod, "SearchRepository") as mock_repo_cls, \
             patch.object(search_mod, "run_runpod_job") as mock_run:
            repo = MagicMock()
            repo.get_by_id.return_value = None
            mock_repo_cls.return_value = repo

            result = search_mod.dispatch_search(job_id=_JOB_ID)

        assert result == {"job_id": _JOB_ID, "status": "missing"}
        mock_run.assert_not_called()
