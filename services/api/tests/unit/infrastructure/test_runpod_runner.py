"""
Tests: infrastructure/gpu/runpod_runner.py — runner genérico de job GPU no
RunPod (ciclo de vida único reusado por 'train' e 'propagate', 3 camadas de
garantia de morte).

Cobre:
- build_onstart: embute o executor via heredoc, embrulha com `timeout` +
  `trap ... EXIT` chamando DELETE /v1/pods/$RUNPOD_POD_ID (camada 1).
- timeout/teto por tipo de carga: defaults + override por env; cálculo de
  custo estimado; CostCapExceededError acima do teto.
- _watch (watchdog, camada 2): completed/stopped/failed via poll_status_fn;
  verify_completed_fn recusando sucesso; pod morto 3x seguidas; timeout;
  poll de pod tolerante a erro de rede.
- run_runpod_job: ciclo de vida completo (preço→teto→onstart→create_pod→
  persist ref→watch→terminate SEMPRE→billing) — inclusive com um executor
  DUMMY e kind="propagate" (ponto de injeção pronto pro PR futuro).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.infrastructure.gpu.runpod_client import RunPodError
from app.infrastructure.gpu.runpod_runner import (
    CostCapExceededError,
    cloud_type_default,
    container_disk_gb_default,
    JobKind,
    JobStoppedError,
    build_onstart,
    check_cost_cap,
    estimate_cost_usd,
    gpu_type_default,
    max_usd_for_kind,
    poll_interval_seconds,
    run_runpod_job,
    timeout_seconds_for_kind,
)
from app.infrastructure.gpu.runpod_runner import _watch  # noqa: PLC2701 — testa direto

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

# Executor "dummy" — prova que o runner genérico não é acoplado ao
# remote_train.py: qualquer script self-contained funciona como carga.
_DUMMY_EXECUTOR_SOURCE = (
    "print('propagate dummy executor rodou')\n"
)


class TestBuildOnstart:
    def test_embeds_executor_via_heredoc(self) -> None:
        onstart = build_onstart(_DUMMY_EXECUTOR_SOURCE, timeout_seconds=120)
        assert "print('propagate dummy executor rodou')" in onstart
        assert "cat > /root/executor.py" in onstart

    def test_wraps_with_timeout(self) -> None:
        onstart = build_onstart(_DUMMY_EXECUTOR_SOURCE, timeout_seconds=300)
        assert "timeout 300 python3 /root/executor.py" in onstart

    def test_has_trap_exit_calling_delete_pod(self) -> None:
        onstart = build_onstart(_DUMMY_EXECUTOR_SOURCE, timeout_seconds=120)
        assert "trap '" in onstart
        assert "EXIT" in onstart
        assert "DELETE" in onstart
        assert "/v1/pods/${RUNPOD_POD_ID}" in onstart
        assert "${RUNPOD_API_KEY}" in onstart

    def test_custom_executor_filename(self) -> None:
        onstart = build_onstart(
            _DUMMY_EXECUTOR_SOURCE, timeout_seconds=60, executor_filename="propagate.py"
        )
        assert "cat > /root/propagate.py" in onstart
        assert "timeout 60 python3 /root/propagate.py" in onstart


class TestTimeoutsAndCaps:
    def test_default_timeout_train(self, monkeypatch) -> None:
        monkeypatch.delenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", raising=False)
        assert timeout_seconds_for_kind(JobKind.TRAIN) == 3600

    def test_timeout_override_via_env(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "7200")
        assert timeout_seconds_for_kind(JobKind.TRAIN) == 7200

    def test_default_timeout_propagate(self, monkeypatch) -> None:
        monkeypatch.delenv("RUNPOD_TIMEOUT_SECONDS_PROPAGATE", raising=False)
        assert timeout_seconds_for_kind(JobKind.PROPAGATE) == 3600

    def test_default_max_usd(self, monkeypatch) -> None:
        monkeypatch.delenv("RUNPOD_MAX_USD_TRAIN", raising=False)
        monkeypatch.delenv("RUNPOD_MAX_USD_PROPAGATE", raising=False)
        assert max_usd_for_kind(JobKind.TRAIN) == 2.00
        assert max_usd_for_kind(JobKind.PROPAGATE) == 2.00

    def test_max_usd_override_via_env(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_MAX_USD_TRAIN", "5.50")
        assert max_usd_for_kind(JobKind.TRAIN) == 5.50

    def test_invalid_env_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_MAX_USD_TRAIN", "not-a-float")
        assert max_usd_for_kind(JobKind.TRAIN) == 2.00

    def test_gpu_type_default(self, monkeypatch) -> None:
        monkeypatch.delenv("RUNPOD_GPU_TYPE", raising=False)
        assert gpu_type_default() == "NVIDIA GeForce RTX 4090"

    def test_gpu_type_override(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_GPU_TYPE", "NVIDIA A100")
        assert gpu_type_default() == "NVIDIA A100"

    def test_poll_interval_default(self, monkeypatch) -> None:
        monkeypatch.delenv("RUNPOD_POLL_INTERVAL_SECONDS", raising=False)
        assert poll_interval_seconds() == 60

    def test_estimate_cost(self) -> None:
        assert estimate_cost_usd(price_usd_h=0.5, timeout_seconds=3600) == 0.5
        assert estimate_cost_usd(price_usd_h=0.5, timeout_seconds=1800) == 0.25

    def test_check_cost_cap_passes_within_budget(self) -> None:
        check_cost_cap(JobKind.TRAIN, estimated_cost=1.99)  # não levanta

    def test_check_cost_cap_raises_above_budget(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_MAX_USD_TRAIN", "2.00")
        with pytest.raises(CostCapExceededError, match=r"\$2\.50.*teto"):
            check_cost_cap(JobKind.TRAIN, estimated_cost=2.50)

    def test_check_cost_cap_uses_propagate_env(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_MAX_USD_PROPAGATE", "0.50")
        with pytest.raises(CostCapExceededError, match="RUNPOD_MAX_USD_PROPAGATE"):
            check_cost_cap(JobKind.PROPAGATE, estimated_cost=1.0)


class TestWatch:
    """verify_completed_fn=None por padrão nos testes que não exercitam
    o guard de verificação — esse tem sua própria classe."""

    def _client(self) -> MagicMock:
        return MagicMock()

    def test_completed_status_returns_metrics(self, monkeypatch) -> None:
        poll = MagicMock(return_value={"status": "completed", "metrics": {"mAP50": 0.8}})
        result = _watch(self._client(), "pod-1", _JOB_ID, poll, None, 60, 0)
        assert result == {"status": "completed", "metrics": {"mAP50": 0.8}}

    def test_failed_status_raises(self) -> None:
        poll = MagicMock(return_value={"status": "failed"})
        with pytest.raises(RuntimeError, match="failed"):
            _watch(self._client(), "pod-1", _JOB_ID, poll, None, 60, 0)

    def test_stopped_status_raises_job_stopped_error(self) -> None:
        poll = MagicMock(return_value={"status": "stopped"})
        with pytest.raises(JobStoppedError):
            _watch(self._client(), "pod-1", _JOB_ID, poll, None, 60, 0)

    def test_verify_completed_fn_rejects_success(self) -> None:
        poll = MagicMock(return_value={"status": "completed", "metrics": {}})
        verify = MagicMock(return_value=False)
        with pytest.raises(RuntimeError, match="verificação"):
            _watch(self._client(), "pod-1", _JOB_ID, poll, verify, 60, 0)

    def test_verify_completed_fn_accepts_success(self) -> None:
        poll = MagicMock(return_value={"status": "completed", "metrics": {"x": 1}})
        verify = MagicMock(return_value=True)
        result = _watch(self._client(), "pod-1", _JOB_ID, poll, verify, 60, 0)
        assert result["metrics"] == {"x": 1}
        verify.assert_called_once()

    def test_dead_pod_three_times_raises(self) -> None:
        poll = MagicMock(return_value={"status": "running"})
        client = MagicMock()
        client.get_pod.return_value = {"desiredStatus": "EXITED"}
        with pytest.raises(RuntimeError, match="sem callback final"):
            _watch(client, "pod-1", _JOB_ID, poll, None, 60, 0)
        assert client.get_pod.call_count == 3

    def test_alive_pod_resets_dead_counter(self) -> None:
        statuses = [
            {"status": "running"}, {"status": "running"}, {"status": "running"},
            {"status": "running"}, {"status": "completed", "metrics": {}},
        ]
        poll = MagicMock(side_effect=statuses)
        client = MagicMock()
        client.get_pod.side_effect = [
            {"desiredStatus": "EXITED"},
            {"desiredStatus": "EXITED"},
            {"desiredStatus": "RUNNING"},
            {"desiredStatus": "EXITED"},
        ]
        result = _watch(client, "pod-1", _JOB_ID, poll, None, 60, 0)
        assert result["status"] == "completed"

    def test_pod_poll_failure_is_tolerated(self) -> None:
        poll = MagicMock(side_effect=[{"status": "running"}, {"status": "completed", "metrics": {}}])
        client = MagicMock()
        client.get_pod.side_effect = RunPodError("timeout de rede")
        result = _watch(client, "pod-1", _JOB_ID, poll, None, 60, 0)
        assert result["status"] == "completed"

    def test_timeout_raises(self) -> None:
        poll = MagicMock(return_value={"status": "running"})
        client = MagicMock()
        client.get_pod.return_value = {"desiredStatus": "RUNNING"}
        with pytest.raises(RuntimeError, match="Timeout runpod"):
            _watch(client, "pod-1", _JOB_ID, poll, None, timeout_seconds=0, poll_interval=0)


class TestRunRunpodJob:
    """Ciclo de vida completo — inclusive com kind='propagate' e um
    executor dummy, provando que o ponto de injeção não é acoplado a
    'train' (a carga 'propagate' de verdade chega num PR futuro)."""

    def _client(self, price: float = 0.40) -> MagicMock:
        client = MagicMock()
        client.api_key = "runpod-key"
        client.get_gpu_price.return_value = price
        client.create_pod.return_value = {"id": "pod-123"}
        client.get_billing.return_value = [{"podId": "pod-123", "amount": 0.12}]
        return client

    def test_happy_path_train_creates_pod_watches_and_terminates(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "60")
        monkeypatch.setenv("RUNPOD_POLL_INTERVAL_SECONDS", "0")
        client = self._client()
        persist_ref = MagicMock()
        poll_status = MagicMock(return_value={"status": "completed", "metrics": {"mAP50": 0.9}})

        result = run_runpod_job(
            kind=JobKind.TRAIN,
            job_id=_JOB_ID,
            client=client,
            executor_source="print('train')",
            env={"FOO": "bar"},
            poll_status_fn=poll_status,
            persist_instance_ref_fn=persist_ref,
        )

        assert result["status"] == "completed"
        assert result["metrics"]["mAP50"] == 0.9
        assert result["metrics"]["gpu_cost"]["provider"] == "runpod"
        assert result["metrics"]["gpu_cost"]["price_usd_h"] == 0.40
        assert result["metrics"]["gpu_cost"]["actual_usd"] == 0.12
        assert result["pod_id"] == "pod-123"

        persist_ref.assert_called_once_with("pod-123")
        client.create_pod.assert_called_once()
        create_kwargs = client.create_pod.call_args.kwargs
        assert create_kwargs["env"]["FOO"] == "bar"
        assert create_kwargs["env"]["RUNPOD_API_KEY"] == "runpod-key"
        assert create_kwargs["env"]["RUNPOD_MAX_SECONDS"] == "60"
        assert create_kwargs["gpu_type_id"] == gpu_type_default()
        # SEMPRE termina o pod (camada 2 de garantia de morte)
        client.terminate_pod.assert_called_once_with("pod-123")

    def test_propagate_kind_with_dummy_executor(self, monkeypatch) -> None:
        """Ponto de injeção genérico: mesma função, outro JobKind e outro
        executor — sem nenhuma mudança de código, só de parâmetros."""
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_PROPAGATE", "30")
        monkeypatch.setenv("RUNPOD_POLL_INTERVAL_SECONDS", "0")
        client = self._client()
        poll_status = MagicMock(return_value={"status": "completed", "metrics": {}})

        result = run_runpod_job(
            kind=JobKind.PROPAGATE,
            job_id="propagate-job-1",
            client=client,
            executor_source=_DUMMY_EXECUTOR_SOURCE,
            executor_filename="propagate.py",
            env={},
            poll_status_fn=poll_status,
            persist_instance_ref_fn=MagicMock(),
        )

        assert result["status"] == "completed"
        create_kwargs = client.create_pod.call_args.kwargs
        assert create_kwargs["name"].startswith("recognition-propagate-")
        assert "propagate.py" in create_kwargs["docker_start_cmd"][2]
        client.terminate_pod.assert_called_once_with("pod-123")

    def test_cost_cap_exceeded_never_creates_pod(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_MAX_USD_TRAIN", "0.01")
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "3600")
        client = self._client(price=1.0)  # $1/h * 1h = $1.00 >> $0.01 cap

        with pytest.raises(CostCapExceededError):
            run_runpod_job(
                kind=JobKind.TRAIN,
                job_id=_JOB_ID,
                client=client,
                executor_source="print('x')",
                env={},
                poll_status_fn=MagicMock(),
                persist_instance_ref_fn=MagicMock(),
            )

        client.create_pod.assert_not_called()
        client.terminate_pod.assert_not_called()

    def test_terminate_runs_even_when_watch_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "60")
        monkeypatch.setenv("RUNPOD_POLL_INTERVAL_SECONDS", "0")
        client = self._client()
        poll_status = MagicMock(return_value={"status": "failed"})

        with pytest.raises(RuntimeError, match="failed"):
            run_runpod_job(
                kind=JobKind.TRAIN,
                job_id=_JOB_ID,
                client=client,
                executor_source="print('x')",
                env={},
                poll_status_fn=poll_status,
                persist_instance_ref_fn=MagicMock(),
            )

        client.terminate_pod.assert_called_once_with("pod-123")

    def test_on_dispatched_fn_called_with_expected_fields(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "60")
        monkeypatch.setenv("RUNPOD_POLL_INTERVAL_SECONDS", "0")
        client = self._client(price=0.55)
        on_dispatched = MagicMock()
        poll_status = MagicMock(return_value={"status": "completed", "metrics": {}})

        result = run_runpod_job(
            kind=JobKind.TRAIN,
            job_id=_JOB_ID,
            client=client,
            executor_source="print('x')",
            env={},
            poll_status_fn=poll_status,
            persist_instance_ref_fn=MagicMock(),
            on_dispatched_fn=on_dispatched,
        )

        assert result["status"] == "completed"
        on_dispatched.assert_called_once_with({
            "pod_id": "pod-123",
            "gpu_type": gpu_type_default(),
            "price_usd_h": 0.55,
            "estimated_usd": estimate_cost_usd(0.55, 60),
        })

    def test_on_dispatched_fn_called_before_watch_even_if_watch_raises(self, monkeypatch) -> None:
        """Sinal de "pod criado, GPU acordando" precisa chegar mesmo se o
        watchdog depois falhar (timeout, pod morto) — não é condicionado a
        sucesso."""
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "60")
        monkeypatch.setenv("RUNPOD_POLL_INTERVAL_SECONDS", "0")
        client = self._client()
        on_dispatched = MagicMock()
        poll_status = MagicMock(return_value={"status": "failed"})

        with pytest.raises(RuntimeError, match="failed"):
            run_runpod_job(
                kind=JobKind.TRAIN,
                job_id=_JOB_ID,
                client=client,
                executor_source="print('x')",
                env={},
                poll_status_fn=poll_status,
                persist_instance_ref_fn=MagicMock(),
                on_dispatched_fn=on_dispatched,
            )

        on_dispatched.assert_called_once()

    def test_on_dispatched_fn_absence_behaves_like_before(self, monkeypatch) -> None:
        """Sem `on_dispatched_fn` (default None) — comportamento idêntico
        ao runner antes deste parâmetro existir, nenhuma chamada extra."""
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "60")
        monkeypatch.setenv("RUNPOD_POLL_INTERVAL_SECONDS", "0")
        client = self._client()
        poll_status = MagicMock(return_value={"status": "completed", "metrics": {}})

        result = run_runpod_job(
            kind=JobKind.TRAIN,
            job_id=_JOB_ID,
            client=client,
            executor_source="print('x')",
            env={},
            poll_status_fn=poll_status,
            persist_instance_ref_fn=MagicMock(),
        )

        assert result["status"] == "completed"
        assert result["pod_id"] == "pod-123"

    def test_billing_lookup_failure_is_best_effort(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_TIMEOUT_SECONDS_TRAIN", "60")
        monkeypatch.setenv("RUNPOD_POLL_INTERVAL_SECONDS", "0")
        client = self._client()
        client.get_billing.side_effect = RunPodError("billing indisponível")
        poll_status = MagicMock(return_value={"status": "completed", "metrics": {}})

        result = run_runpod_job(
            kind=JobKind.TRAIN,
            job_id=_JOB_ID,
            client=client,
            executor_source="print('x')",
            env={},
            poll_status_fn=poll_status,
            persist_instance_ref_fn=MagicMock(),
        )
        assert result["metrics"]["gpu_cost"]["actual_usd"] is None


class TestPodSpecEnvOverrides:
    """RUNPOD_CONTAINER_DISK_GB / RUNPOD_CLOUD_TYPE — spec do pod tunável
    por env (community sem 40GB livres derrubava o create_pod 3x no DEV)."""

    def test_defaults_sem_env(self, monkeypatch) -> None:
        monkeypatch.delenv("RUNPOD_CONTAINER_DISK_GB", raising=False)
        monkeypatch.delenv("RUNPOD_CLOUD_TYPE", raising=False)
        assert container_disk_gb_default() == 40
        assert cloud_type_default() == "COMMUNITY"

    def test_env_overrides(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_CONTAINER_DISK_GB", "20")
        monkeypatch.setenv("RUNPOD_CLOUD_TYPE", "SECURE")
        assert container_disk_gb_default() == 20
        assert cloud_type_default() == "SECURE"

    def test_run_runpod_job_passa_spec_pro_create_pod(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_CONTAINER_DISK_GB", "20")
        monkeypatch.setenv("RUNPOD_CLOUD_TYPE", "SECURE")
        client = MagicMock()
        client.get_gpu_price.return_value = 0.30
        client.create_pod.return_value = {"id": "pod-spec"}
        client.get_billing.return_value = []
        run_runpod_job(
            kind="propagate",
            job_id="job-spec",
            client=client,
            executor_source="print('x')",
            env={},
            poll_status_fn=lambda: {"status": "completed", "metrics": {}},
            persist_instance_ref_fn=lambda pod_id: None,
            poll_interval=0,
        )
        kwargs = client.create_pod.call_args.kwargs
        assert kwargs["container_disk_gb"] == 20
        assert kwargs["cloud_type"] == "SECURE"
