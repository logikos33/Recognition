"""
Tests: infrastructure/queue/tasks/propagation.py — dispatch da propagação
semeada (RunPod).

Cobre a cadeia de guardas ANTES de qualquer chamada de rede/GPU:
- training_third_party_cloud_enabled OFF → job 'failed', RunPod nunca
  contatado (mesmo gate ADR-0047/0060 do treino, reusado).
- sem API key RunPod resolvível → job 'failed'.
- 🔴 revalidate_pool (o guard mais importante do PR) falhando → job
  'failed' com o motivo do PoolGuardError, RunPod nunca contatado —
  falha-antes/passa-depois: sem esta chamada, um pool que mudou entre a
  criação do job e o dispatch seguiria pra GPU sem ninguém notar.
- manifesto sem sementes com caixas (ex.: anotação apagada depois da
  criação do job) → job 'failed', sem disparar o RunPod.
- happy path: env do runner tem MANIFEST_URL/CALLBACK_TOKEN/SAM+DINOv2
  sha256/threshold; callback_token é gerado e SEMPRE revogado (inclusive
  quando run_runpod_job levanta); métricas (gpu_cost) são mescladas no job.
- corrida de stop: job já 'stopped' antes do provisioning aborta sem criar
  pod (mesmo padrão de tasks/training.py).
- JobStoppedError do runner: task retorna status 'stopped', nunca
  sobrescreve com 'failed'.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.domain.services.propagation_pool import compute_pool_hash
from app.infrastructure.gpu.runpod_runner import JobKind, JobStoppedError
from app.infrastructure.queue.tasks import propagation as propagation_mod

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TENANT = "99999999-8888-7777-6666-555555555555"
_CAMERA = "11111111-2222-3333-4444-555555555555"
_OTHER_CAMERA = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def _base_job(**overrides) -> dict:
    job = {
        "id": _JOB_ID,
        "tenant_id": _TENANT,
        "status": "queued",
        "pool_criteria": {
            "camera_ids": [_CAMERA], "date_from": "2026-07-31", "date_to": "2026-07-31",
        },
        "pool_frame_ids": ["f1", "f2"],
        "pool_hash": None,
        "seed_frame_ids": ["f1"],
        "callback_token": None,
    }
    job.update(overrides)
    return job


def _frame(frame_id: str, camera_id: str = _CAMERA) -> dict:
    return {
        "id": frame_id,
        "tenant_id": _TENANT,
        "camera_id": camera_id,
        "r2_key": f"frames/{frame_id}.jpg",
        "captured_at": datetime(2026, 7, 31, 10, 0, 0),
    }


def _seed_annotation(frame_id: str = "f1") -> dict:
    return {
        "frame_id": frame_id, "class_id": 1, "class_name": "capacete",
        "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1,
    }


def _pool_hash_for(job: dict) -> str:
    return compute_pool_hash(job["pool_frame_ids"])


class _Harness:
    """Bundle de mocks + patches padrão de dispatch_propagation. `run` faz
    o dispatch de fato dentro de um único ExitStack — evita reconstruir a
    mesma pilha de 9 `with patch.object(...)` em todo teste."""

    def __init__(self, job: dict, frames: "list[dict] | None" = None, seeds: "list[dict] | None" = None) -> None:
        self.job = job
        self.propagation_repo = MagicMock()
        self.propagation_repo.get_by_id.return_value = job
        self.frame_repo = MagicMock()
        self.frame_repo.get_by_ids.return_value = frames or []
        self.annotation_repo = MagicMock()
        self.annotation_repo.get_manual_annotations_for_frames.return_value = seeds or []
        self.storage = MagicMock()
        self.storage.generate_presigned_download_url.return_value = "https://r2/get?sig=1"
        self.run_runpod_job = MagicMock(return_value={
            "status": "completed", "metrics": {}, "pod_id": "pod-1",
        })
        self.third_party_enabled = True
        self.api_key = "runpod-key"

    def run(self) -> dict:
        with ExitStack() as stack:
            stack.enter_context(patch.object(propagation_mod, "DatabasePool"))
            stack.enter_context(patch.object(
                propagation_mod, "PropagationRepository", return_value=self.propagation_repo,
            ))
            stack.enter_context(patch.object(
                propagation_mod, "FrameRepository", return_value=self.frame_repo,
            ))
            stack.enter_context(patch.object(
                propagation_mod, "AnnotationRepository", return_value=self.annotation_repo,
            ))
            stack.enter_context(patch.object(
                propagation_mod, "get_storage", return_value=self.storage,
            ))
            stack.enter_context(patch.object(
                propagation_mod, "_third_party_cloud_training_enabled",
                return_value=self.third_party_enabled,
            ))
            stack.enter_context(patch.object(
                propagation_mod, "resolve_runpod_api_key", return_value=self.api_key,
            ))
            stack.enter_context(patch.object(propagation_mod, "RunPodClient"))
            stack.enter_context(patch.object(
                propagation_mod, "_read_propagate_executor_source", return_value="# runner",
            ))
            stack.enter_context(patch.object(
                propagation_mod, "run_runpod_job", self.run_runpod_job,
            ))
            return propagation_mod.dispatch_propagation(job_id=_JOB_ID)


class TestThirdPartyCloudGate:
    def test_disabled_marks_failed_without_contacting_runpod(self) -> None:
        h = _Harness(_base_job(pool_hash="whatever"))
        h.third_party_enabled = False

        result = h.run()

        assert result["status"] == "failed"
        assert "terceiro" in result["reason"]
        h.propagation_repo.mark_failed.assert_called_once()
        h.run_runpod_job.assert_not_called()


class TestApiKeyGate:
    def test_missing_api_key_marks_failed(self) -> None:
        h = _Harness(_base_job(pool_hash="whatever"))
        h.api_key = ""

        result = h.run()

        assert result["status"] == "failed"
        assert "chave RunPod" in result["reason"]
        h.run_runpod_job.assert_not_called()


class TestPoolGuardAtDispatch:
    """O guard mais importante do PR: revalidate_pool roda ANTES de
    qualquer manifesto/pod. Falha-antes/passa-depois: sem essa chamada,
    cada cenário abaixo chegaria até run_runpod_job normalmente."""

    def test_frame_reassigned_since_creation_fails_before_runpod_call(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2", camera_id=_OTHER_CAMERA)]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        result = h.run()

        assert result["status"] == "failed"
        assert "Guard de pool falhou" in result["reason"]
        h.propagation_repo.mark_failed.assert_called_once()
        h.run_runpod_job.assert_not_called()

    def test_pool_hash_mismatch_fails_before_runpod_call(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"], pool_hash="0" * 64)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        result = h.run()

        assert result["status"] == "failed"
        assert "Guard de pool falhou" in result["reason"]
        h.run_runpod_job.assert_not_called()

    def test_frame_deleted_since_creation_fails(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1")]  # f2 sumiu
        h = _Harness(job, frames, [_seed_annotation("f1")])

        result = h.run()

        assert result["status"] == "failed"
        assert "Guard de pool falhou" in result["reason"]
        h.run_runpod_job.assert_not_called()

    def test_tenant_mismatch_since_creation_fails(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), {**_frame("f2"), "tenant_id": "00000000-0000-0000-0000-000000000000"}]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        result = h.run()

        assert result["status"] == "failed"
        assert "Guard de pool falhou" in result["reason"]
        h.run_runpod_job.assert_not_called()


class TestNoSeedsWithBoxesAtDispatch:
    def test_seeds_without_manual_annotations_fails_before_runpod_call(self) -> None:
        """Sementes existiam na criação do job, mas as anotações humanas
        foram apagadas antes do dispatch — nenhuma caixa sobra pro
        manifesto, job falha sem contatar o RunPod."""
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [])  # sem anotações manuais

        result = h.run()

        assert result["status"] == "failed"
        assert "semente" in result["reason"]
        h.run_runpod_job.assert_not_called()


class TestHappyPathEnvAndManifest:
    def test_builds_manifest_and_calls_run_runpod_job_with_expected_env(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])
        h.run_runpod_job.return_value = {
            "status": "completed",
            "metrics": {"gpu_cost": {"provider": "runpod", "actual_usd": 0.05}},
            "pod_id": "pod-1",
        }

        result = h.run()

        assert result["status"] == "completed"
        h.run_runpod_job.assert_called_once()
        call_kwargs = h.run_runpod_job.call_args.kwargs
        assert call_kwargs["kind"] == JobKind.PROPAGATE
        assert call_kwargs["executor_filename"] == "propagate_seeded.py"

        env = call_kwargs["env"]
        assert env["MANIFEST_URL"] == "https://r2/get?sig=1"
        assert len(env["CALLBACK_TOKEN"]) > 20
        assert env["SAM_WEIGHTS_SHA256"] == propagation_mod._SAM_WEIGHTS_SHA256
        assert env["DINOV2_WEIGHTS_URL"] == propagation_mod._DINOV2_WEIGHTS_URL
        assert env["DINOV2_WEIGHTS_SHA256"] == propagation_mod._DINOV2_WEIGHTS_SHA256
        assert env["SIMILARITY_THRESHOLD"] == str(propagation_mod._DEFAULT_SIMILARITY_THRESHOLD)

        # manifesto foi de fato subido pro storage do tenant
        h.storage.upload_bytes.assert_called_once()
        manifest_key = h.storage.upload_bytes.call_args.args[0]
        assert manifest_key == f"propagation/{_TENANT}/{_JOB_ID}/manifest.json"
        manifest_body = h.storage.upload_bytes.call_args.args[1]
        import json as _json
        manifest = _json.loads(manifest_body)
        assert len(manifest["seeds"]) == 1
        assert manifest["seeds"][0]["boxes"][0]["class"] == "capacete"
        assert {p["frame_id"] for p in manifest["pool"]} == {"f1", "f2"}

        # métricas (gpu_cost) mescladas no job
        h.propagation_repo.merge_metrics.assert_called_once()
        merged = h.propagation_repo.merge_metrics.call_args.args[1]
        assert merged["gpu_cost"]["actual_usd"] == 0.05

    def test_callback_token_revoked_even_when_run_runpod_job_raises(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])
        h.run_runpod_job.side_effect = RuntimeError("pod RunPod crashou")

        result = h.run()

        assert result["status"] == "failed"
        assert "crashou" in result["reason"]
        none_calls = [
            c for c in h.propagation_repo.set_callback_token.call_args_list
            if c.args[1] is None
        ]
        assert none_calls, "callback_token deveria ter sido revogado (set p/ None)"


class TestStopRaceAndJobStoppedError:
    def test_aborts_before_run_runpod_job_when_already_stopped(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])
        # get_by_id é chamado de novo logo antes do provisioning — simula
        # um stop concorrente reportando 'stopped' nesse 2º refetch.
        h.propagation_repo.get_by_id.side_effect = [job, {"status": "stopped"}]

        result = h.run()

        assert result["status"] == "stopped"
        h.run_runpod_job.assert_not_called()

    def test_job_stopped_error_returns_stopped_never_overwrites_with_failed(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])
        h.run_runpod_job.side_effect = JobStoppedError("parado")

        result = h.run()

        assert result["status"] == "stopped"
        h.propagation_repo.mark_failed.assert_not_called()


class TestMissingJob:
    def test_missing_job_returns_missing_without_touching_runpod(self) -> None:
        with patch.object(propagation_mod, "DatabasePool"), \
             patch.object(propagation_mod, "PropagationRepository") as mock_repo_cls, \
             patch.object(propagation_mod, "run_runpod_job") as mock_run:
            repo = MagicMock()
            repo.get_by_id.return_value = None
            mock_repo_cls.return_value = repo

            result = propagation_mod.dispatch_propagation(job_id=_JOB_ID)

        assert result == {"job_id": _JOB_ID, "status": "missing"}
        mock_run.assert_not_called()
