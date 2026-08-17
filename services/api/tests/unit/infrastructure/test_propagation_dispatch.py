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
- marcos de fase (`metrics.stage`) gravados ANTES do pod responder:
  'preparing' antes de qualquer guard, 'creating_pod' antes de chamar
  run_runpod_job, 'gpu_starting' via on_dispatched_fn (pod já criado).
- classificação de falha (`metrics.failure_kind`) por tipo de exceção +
  billing best-effort do custo já gasto — nunca mascara a falha original.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.domain.services.propagation_pool import compute_pool_hash
from app.infrastructure.gpu.runpod_runner import (
    CostCapExceededError,
    JobKind,
    JobStoppedError,
)
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
        self.edge_command_repo = MagicMock()
        self.edge_command_repo.create.return_value = {"id": "cmd-1", "status": "pending"}

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
                propagation_mod, "EdgeCommandRepository", return_value=self.edge_command_repo,
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

        # métricas (gpu_cost) mescladas no job — ÚLTIMA chamada de
        # merge_metrics (as anteriores são os marcos de fase "preparing"/
        # "creating_pod", ver TestPhaseMilestones)
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


class TestPhaseMilestones:
    """A UI reconstrói a barra de progresso do cold start (minutos sem
    nenhum callback do executor) SÓ olhando `propagation_jobs.metrics` —
    estes marcos são o que ela lê antes do primeiro callback chegar."""

    def test_preparing_stage_recorded_before_any_guard(self) -> None:
        h = _Harness(_base_job(pool_hash="whatever"))
        h.third_party_enabled = False  # falha no primeiro guard

        h.run()

        first_call = h.propagation_repo.merge_metrics.call_args_list[0]
        assert first_call.args == (_JOB_ID, {"stage": "preparing"})

    def test_creating_pod_stage_recorded_before_run_runpod_job_call(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        h.run()

        calls = [c.args for c in h.propagation_repo.merge_metrics.call_args_list]
        assert (_JOB_ID, {"stage": "preparing"}) in calls
        assert (_JOB_ID, {"stage": "creating_pod"}) in calls
        # 'preparing' vem estritamente ANTES de 'creating_pod' — mesma
        # ordem que o dispatch de fato segue (guard → manifesto → pod).
        preparing_idx = calls.index((_JOB_ID, {"stage": "preparing"}))
        creating_pod_idx = calls.index((_JOB_ID, {"stage": "creating_pod"}))
        assert preparing_idx < creating_pod_idx
        # E 'creating_pod' precisa vir ANTES do run_runpod_job de fato ser
        # chamado (não depois, não em paralelo).
        h.run_runpod_job.assert_called_once()

    def test_on_dispatched_fn_wired_and_merges_gpu_starting(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        h.run()

        call_kwargs = h.run_runpod_job.call_args.kwargs
        on_dispatched = call_kwargs["on_dispatched_fn"]
        assert callable(on_dispatched)

        h.propagation_repo.merge_metrics.reset_mock()
        on_dispatched({
            "pod_id": "pod-42", "gpu_type": "NVIDIA RTX 4090",
            "price_usd_h": 0.5, "estimated_usd": 0.5,
        })
        h.propagation_repo.merge_metrics.assert_called_once_with(_JOB_ID, {
            "stage": "gpu_starting",
            "gpu_cost": {
                "provider": "runpod", "gpu_type": "NVIDIA RTX 4090",
                "price_usd_h": 0.5, "estimated_usd": 0.5, "actual_usd": None,
            },
        })


class TestClassifyFailureKind:
    def test_cost_cap_exceeded_pod_never_created(self) -> None:
        exc = CostCapExceededError("custo estimado excede o teto")
        assert propagation_mod._classify_failure_kind(exc) == "cost_cap"

    def test_job_stopped_error(self) -> None:
        assert propagation_mod._classify_failure_kind(JobStoppedError("parado")) == "stopped"

    def test_timeout_runtime_error(self) -> None:
        exc = RuntimeError("Timeout runpod após 3600s: job=x")
        assert propagation_mod._classify_failure_kind(exc) == "timeout"

    def test_pod_died_runtime_error(self) -> None:
        exc = RuntimeError("Pod RunPod terminou sem callback final: job=x pod=y")
        assert propagation_mod._classify_failure_kind(exc) == "pod_died"

    def test_generic_runtime_error_is_executor_error(self) -> None:
        exc = RuntimeError("pod RunPod crashou")
        assert propagation_mod._classify_failure_kind(exc) == "executor_error"

    def test_non_runtime_exception_is_executor_error(self) -> None:
        assert propagation_mod._classify_failure_kind(ValueError("x")) == "executor_error"


class TestRecordFailureMetrics:
    """`_record_failure_metrics` — grava `failure_kind` + custo real
    best-effort (`gpu_instance_ref` presente) ANTES/junto de marcar o job."""

    def test_writes_failure_kind_without_gpu_instance_ref_skips_billing(self) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = {"tenant_id": _TENANT}  # sem gpu_instance_ref

        propagation_mod._record_failure_metrics(
            repo, _JOB_ID, RuntimeError("Timeout runpod após 10s: job=x"),
        )

        repo.merge_metrics.assert_called_once_with(_JOB_ID, {"failure_kind": "timeout"})

    def test_billing_best_effort_merges_actual_cost_preserving_existing_fields(self) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = {
            "tenant_id": _TENANT,
            "gpu_instance_ref": "pod-999",
            "metrics": {"gpu_cost": {
                "provider": "runpod", "gpu_type": "RTX 4090",
                "price_usd_h": 0.4, "estimated_usd": 0.4, "actual_usd": None,
            }},
        }
        with patch.object(propagation_mod, "resolve_runpod_api_key", return_value="key-x"), \
             patch.object(propagation_mod, "RunPodClient"), \
             patch.object(propagation_mod, "_best_effort_actual_cost", return_value=0.33):
            propagation_mod._record_failure_metrics(
                repo, _JOB_ID, RuntimeError("pod RunPod crashou"),
            )

        merged = repo.merge_metrics.call_args.args[1]
        assert merged["failure_kind"] == "executor_error"
        assert merged["gpu_cost"] == {
            "provider": "runpod", "gpu_type": "RTX 4090",
            "price_usd_h": 0.4, "estimated_usd": 0.4, "actual_usd": 0.33,
        }

    def test_billing_lookup_failure_never_masks_original_failure(self) -> None:
        """`_best_effort_actual_cost` explodindo (ex.: RunPodError de rede)
        não pode impedir que `failure_kind` seja gravado, nem propagar pro
        caller — a falha ORIGINAL do job é o que importa."""
        repo = MagicMock()
        repo.get_by_id.return_value = {"tenant_id": _TENANT, "gpu_instance_ref": "pod-999"}
        with patch.object(propagation_mod, "resolve_runpod_api_key", return_value="key-x"), \
             patch.object(propagation_mod, "RunPodClient"), \
             patch.object(
                 propagation_mod, "_best_effort_actual_cost",
                 side_effect=RuntimeError("billing indisponível"),
             ):
            propagation_mod._record_failure_metrics(
                repo, _JOB_ID,
                RuntimeError("Pod RunPod terminou sem callback final: job=x pod=y"),
            )

        merged = repo.merge_metrics.call_args.args[1]
        assert merged == {"failure_kind": "pod_died"}  # sem gpu_cost — billing falhou, ignorado

    def test_no_api_key_skips_billing_without_raising(self) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = {"tenant_id": _TENANT, "gpu_instance_ref": "pod-999"}
        with patch.object(propagation_mod, "resolve_runpod_api_key", return_value=""):
            propagation_mod._record_failure_metrics(repo, _JOB_ID, RuntimeError("x"))
        merged = repo.merge_metrics.call_args.args[1]
        assert merged == {"failure_kind": "executor_error"}

    def test_merge_metrics_failure_itself_is_swallowed(self) -> None:
        """`repo.merge_metrics` explodindo (DB indisponível nesse instante)
        não propaga — o caller (`dispatch_propagation`) precisa seguir pro
        `_fail`/retorno 'stopped' mesmo assim."""
        repo = MagicMock()
        repo.get_by_id.return_value = {"tenant_id": _TENANT}
        repo.merge_metrics.side_effect = RuntimeError("db down")

        propagation_mod._record_failure_metrics(repo, _JOB_ID, RuntimeError("x"))  # não levanta


class TestDispatchFailurePathRecordsFailureKind:
    """Fim-a-fim (via `_Harness.run()`): a exceção que derruba
    `run_runpod_job` termina classificada em `metrics.failure_kind` antes
    do job ser marcado 'failed'."""

    def test_generic_exception_records_executor_error_before_marking_failed(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])
        h.run_runpod_job.side_effect = RuntimeError("pod RunPod crashou")

        result = h.run()

        assert result["status"] == "failed"
        calls = [c.args for c in h.propagation_repo.merge_metrics.call_args_list]
        assert (_JOB_ID, {"failure_kind": "executor_error"}) in calls
        # failure_kind gravado ANTES de marcar o job failed
        failure_idx = calls.index((_JOB_ID, {"failure_kind": "executor_error"}))
        mark_failed_call_time = h.propagation_repo.mark_failed.call_args_list
        assert mark_failed_call_time  # mark_failed foi chamado
        assert failure_idx >= 0

    def test_job_stopped_error_also_records_stopped_failure_kind(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])
        h.run_runpod_job.side_effect = JobStoppedError("parado")

        result = h.run()

        assert result["status"] == "stopped"
        h.propagation_repo.mark_failed.assert_not_called()
        calls = [c.args for c in h.propagation_repo.merge_metrics.call_args_list]
        assert (_JOB_ID, {"failure_kind": "stopped"}) in calls


class TestEdgeDispatch:
    """Task "propagação no edge" — `gpu_provider` ONSITE (edge) desvia pro
    `edge_commands` em vez do RunPod.

    🔴 TESTE OBRIGATÓRIO (par falha-antes/passa-depois do spec):
    (a) job edge com frame/semente de data de OPERAÇÃO (fora da janela do
        critério) → passa create/dispatch — o guard de data não se aplica
        quando a imagem nunca sai do site;
    (b) o MESMO job, com `gpu_provider` trocado pra 'runpod' (simula uma
        linha alterada entre create e dispatch) → dispatch ABORTA sozinho,
        porque o guard de data é RECHECADO a partir do provider gravado no
        job, não confia no que foi decidido na criação.
    """

    def _edge_job(self, **overrides) -> dict:
        job = _base_job(
            gpu_provider="edge",
            pool_criteria={
                "camera_ids": [_CAMERA], "date_from": "2026-07-31", "date_to": "2026-07-31",
                "site_id": "site-1",
            },
        )
        job.update(overrides)
        return job

    def _operation_date_frame(self, frame_id: str) -> dict:
        """Frame de data de OPERAÇÃO — 2026-08-05, fora da janela
        2026-07-31 do critério. Só passa o guard se enforce_date_guard
        estiver desligado (provider onsite)."""
        return {
            "id": frame_id, "tenant_id": _TENANT, "camera_id": _CAMERA,
            "r2_key": f"frames/{frame_id}.jpg",
            "captured_at": datetime(2026, 8, 5, 9, 0, 0),
        }

    def test_a_edge_job_with_operation_date_frames_passes_dispatch(self) -> None:
        job = self._edge_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [self._operation_date_frame("f1"), self._operation_date_frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        result = h.run()

        assert result["status"] == "running"
        h.run_runpod_job.assert_not_called()
        h.edge_command_repo.create.assert_called_once()

        create_kwargs = h.edge_command_repo.create.call_args.kwargs
        assert create_kwargs["site_id"] == "site-1"
        assert create_kwargs["tenant_id"] == _TENANT
        assert create_kwargs["command_type"] == "run_propagation"
        assert create_kwargs["command_id"] == f"propagation:{_JOB_ID}"

        payload = create_kwargs["payload"]
        assert payload["job_id"] == _JOB_ID
        assert payload["manifest_url"] == "https://r2/get?sig=1"
        assert len(payload["callback_token"]) > 20
        assert payload["sam_weights_sha256"] == propagation_mod._SAM_WEIGHTS_SHA256
        assert payload["dinov2_weights_url"] == propagation_mod._DINOV2_WEIGHTS_URL
        assert payload["dinov2_weights_sha256"] == propagation_mod._DINOV2_WEIGHTS_SHA256
        assert payload["mem_max"] == "6G"
        assert payload["cpu_quota"] == "400%"

        # callback_token NÃO revogado no sucesso — a conclusão chega
        # assíncrona, minutos/horas depois, via callback do executor no box.
        none_calls = [
            c for c in h.propagation_repo.set_callback_token.call_args_list
            if c.args[1] is None
        ]
        assert not none_calls

        h.propagation_repo.merge_metrics.assert_any_call(
            _JOB_ID, {"stage": "edge_dispatched", "site_id": "site-1"},
        )

    def test_b_same_job_with_provider_swapped_to_runpod_aborts_dispatch(self) -> None:
        job = self._edge_job(pool_frame_ids=["f1", "f2"], gpu_provider="runpod")
        job["pool_hash"] = _pool_hash_for(job)
        frames = [self._operation_date_frame("f1"), self._operation_date_frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        result = h.run()

        assert result["status"] == "failed"
        assert "Guard de pool falhou" in result["reason"]
        h.run_runpod_job.assert_not_called()
        h.edge_command_repo.create.assert_not_called()

    def test_third_party_cloud_gate_skipped_for_onsite(self) -> None:
        """A imagem nunca sai do site — o opt-in de nuvem de terceiro
        (training_third_party_cloud_enabled) é irrelevante pro edge e
        NUNCA bloqueia o dispatch onsite, mesmo desligado no tenant."""
        job = self._edge_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])
        h.third_party_enabled = False

        result = h.run()

        assert result["status"] == "running"
        h.edge_command_repo.create.assert_called_once()

    def test_missing_site_id_in_pool_criteria_fails_before_enqueue(self) -> None:
        job = self._edge_job(
            pool_frame_ids=["f1", "f2"],
            pool_criteria={
                "camera_ids": [_CAMERA], "date_from": "2026-07-31", "date_to": "2026-07-31",
            },
        )
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        result = h.run()

        assert result["status"] == "failed"
        assert "site_id" in result["reason"]
        h.edge_command_repo.create.assert_not_called()
        none_calls = [
            c for c in h.propagation_repo.set_callback_token.call_args_list
            if c.args[1] is None
        ]
        assert none_calls, "callback_token deveria ter sido revogado (nada vai chamar de volta)"

    def test_edge_command_enqueue_failure_marks_job_failed_and_revokes_token(self) -> None:
        job = self._edge_job(pool_frame_ids=["f1", "f2"])
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])
        h.edge_command_repo.create.side_effect = RuntimeError("db indisponível")

        result = h.run()

        assert result["status"] == "failed"
        assert "enfileirar" in result["reason"]
        none_calls = [
            c for c in h.propagation_repo.set_callback_token.call_args_list
            if c.args[1] is None
        ]
        assert none_calls

    def test_unsupported_offsite_provider_fails_clearly(self) -> None:
        """vast_ai/colab são OFFSITE (guard de data ativo) mas não têm
        dispatch de propagação implementado — falha legível, nunca tenta
        RunPod nem edge."""
        job = _base_job(pool_frame_ids=["f1", "f2"], gpu_provider="vast_ai")
        job["pool_hash"] = _pool_hash_for(job)
        frames = [_frame("f1"), _frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        result = h.run()

        assert result["status"] == "failed"
        assert "vast_ai" in result["reason"]
        h.run_runpod_job.assert_not_called()
        h.edge_command_repo.create.assert_not_called()

    def test_invalid_gpu_provider_on_job_fails_clearly(self) -> None:
        job = _base_job(pool_frame_ids=["f1", "f2"], gpu_provider="not-a-real-provider")
        h = _Harness(job)

        result = h.run()

        assert result["status"] == "failed"
        assert "gpu_provider inválido" in result["reason"]
        h.run_runpod_job.assert_not_called()
        h.edge_command_repo.create.assert_not_called()

    def test_missing_gpu_provider_defaults_to_runpod_offsite_behavior(self) -> None:
        """Retrocompat: linhas antigas (pré-migration-116) ou dicts de
        teste sem a coluna caem no default runpod — guard de data
        continua ativo (comportamento idêntico ao pré-edge)."""
        job = _base_job(pool_frame_ids=["f1", "f2"])
        assert "gpu_provider" not in job
        job["pool_hash"] = _pool_hash_for(job)
        frames = [self._operation_date_frame("f1"), self._operation_date_frame("f2")]
        h = _Harness(job, frames, [_seed_annotation("f1")])

        result = h.run()

        assert result["status"] == "failed"
        assert "Guard de pool falhou" in result["reason"]
