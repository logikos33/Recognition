"""
Tests: tasks/training.py — dispatch RunPod REST real (WS-A4, substitui o
antigo fluxo Vast.ai — decisão do dono, `infrastructure/gpu/vast_client.py`
deletado).

Cobre:
- _get_runpod_training_context: None quando falta dataset COCO ou API key
  resolvível; contexto completo (incl. base_model/hyperparams pro license
  gate) quando ambos existem.
- _dispatch_runpod_train: sem contexto → erro claro; com contexto → roda o
  fluxo REST (_run_runpod_train_job); gate de terceiro ANTES de tudo; license
  gate RF-DETR (ADR-0044) roda ANTES de qualquer chamada de rede.
- _run_runpod_train_job: gera callback_token por-job, presigned URLs, delega
  o ciclo de vida completo (pod + watch + terminate) a
  `runpod_runner.run_runpod_job` — e SEMPRE revoga o callback_token
  (try/finally), inclusive quando `run_runpod_job` levanta.
- Achado da revisão adversarial original (ainda válido): stop deixa vazar 2º
  pod GPU pago — update_job() nunca sobrescreve status='stopped';
  _run_runpod_train_job recheca o status antes de criar o pod e aborta sem
  provisionar; dispatch_training NUNCA chama self.retry() para
  JobStoppedError.
- _build_training_dataset_zip: empacota train/val/test num zip único
  ("val" → "valid").
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mesmo guard de hermeticidade de test_training_dispatch_task.py: garante
# import REAL de celery_app/training mesmo que outro arquivo tenha deixado
# um stub (types.ModuleType sem __file__) em sys.modules.
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_TRAINING_KEY = "app.infrastructure.queue.tasks.training"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_TRAINING_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.gpu.license_gate import RfdetrLicenseError  # noqa: E402
from app.infrastructure.gpu.runpod_runner import JobKind, JobStoppedError  # noqa: E402
from app.infrastructure.queue.tasks import training as training_mod  # noqa: E402

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TENANT = "99999999-8888-7777-6666-555555555555"


def _artefato_ok():
    """Storage com a FONTE completa — o pré-flight lista os objetos soltos por
    split, não o zip (que o dispatch reconstrói e sobrescreve depois)."""
    st = MagicMock()
    st.list_keys.side_effect = lambda pre: [
        f"{pre}_annotations.coco.json", f"{pre}img.jpg",
    ]
    return st


class TestGetRunpodTrainingContext:
    def test_none_without_coco_dataset(self) -> None:
        mock_repo = MagicMock()
        mock_repo._execute_one.return_value = {
            "id": _JOB_ID, "tenant_id": _TENANT, "coco_r2_key": None,
            "framework": "rfdetr", "base_model": None, "hyperparams": {},
        }
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository", return_value=mock_repo):
            assert training_mod._get_runpod_training_context(_JOB_ID) is None

    def test_none_without_resolvable_api_key(self) -> None:
        mock_repo = MagicMock()
        mock_repo._execute_one.return_value = {
            "id": _JOB_ID, "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json", "framework": "rfdetr",
            "base_model": None, "hyperparams": {},
        }
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository", return_value=mock_repo), \
             patch.object(training_mod, "resolve_runpod_api_key", return_value=""):
            assert training_mod._get_runpod_training_context(_JOB_ID) is None

    def test_full_context_when_both_present(self) -> None:
        mock_repo = MagicMock()
        mock_repo._execute_one.return_value = {
            "id": _JOB_ID, "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json", "framework": "yolox",
            "base_model": None, "hyperparams": {},
        }
        with patch.object(training_mod, "get_storage", return_value=_artefato_ok()), \
             patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository", return_value=mock_repo), \
             patch.object(training_mod, "resolve_runpod_api_key", return_value="runpod-key"):
            ctx = training_mod._get_runpod_training_context(_JOB_ID)
        assert ctx == {
            "api_key": "runpod-key",
            "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json",
            "framework": "yolox",
            "base_model": None,
            "hyperparams": {},
        }

    def test_none_on_db_error(self) -> None:
        with patch.object(training_mod, "DatabasePool", side_effect=Exception("db down")):
            assert training_mod._get_runpod_training_context(_JOB_ID) is None

    def test_hyperparams_json_string_is_parsed(self) -> None:
        """Postgres pode devolver JSONB como string dependendo do driver —
        _get_runpod_training_context precisa normalizar pro license gate
        conseguir ler hyperparams.get('variant') etc."""
        mock_repo = MagicMock()
        mock_repo._execute_one.return_value = {
            "id": _JOB_ID, "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json", "framework": "rfdetr",
            "base_model": None, "hyperparams": '{"variant": "nano"}',
        }
        with patch.object(training_mod, "get_storage", return_value=_artefato_ok()), \
             patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository", return_value=mock_repo), \
             patch.object(training_mod, "resolve_runpod_api_key", return_value="k"):
            ctx = training_mod._get_runpod_training_context(_JOB_ID)
        assert ctx["hyperparams"] == {"variant": "nano"}


class TestDispatchRunpodTrainRouting:
    """C5 (task "treino honesto"): _dispatch_runpod_train gateia
    training_third_party_cloud_enabled ANTES de tudo (RunPod é GPU de
    terceiro) — os testes abaixo mockam a flag como True pra exercitar só a
    lógica de roteamento ctx None/presente."""

    def test_no_context_raises_dataset_ausente(self) -> None:
        with patch.object(
                 training_mod, "_third_party_cloud_training_enabled", return_value=True,
             ), \
             patch.object(training_mod, "_get_runpod_training_context", return_value=None), \
             patch.object(training_mod, "resolve_runpod_api_key", return_value="a-key"), \
             patch.object(training_mod, "_run_runpod_train_job") as mock_real, \
             pytest.raises(RuntimeError, match="dataset sem exportação COCO"):
            training_mod._dispatch_runpod_train(_JOB_ID, "yolo26n", 50, 640, 16, MagicMock())
        mock_real.assert_not_called()

    def test_with_context_uses_real_rest_flow(self) -> None:
        ctx = {
            "api_key": "k", "tenant_id": _TENANT, "coco_r2_key": "x", "framework": "rfdetr",
            "base_model": None, "hyperparams": {},
        }
        with patch.object(
                 training_mod, "_third_party_cloud_training_enabled", return_value=True,
             ), \
             patch.object(training_mod, "_get_runpod_training_context", return_value=ctx), \
             patch.object(training_mod, "_run_runpod_train_job") as mock_real:
            mock_real.return_value = {"model_path": "x", "metrics": {}, "source": "runpod"}
            training_mod._dispatch_runpod_train(_JOB_ID, "yolo26n", 50, 640, 16, MagicMock())
        mock_real.assert_called_once()

    def test_third_party_disabled_raises_before_checking_context(self) -> None:
        """C5: flag OFF levanta erro claro ANTES de sequer resolver o
        contexto (dataset/API key) — nunca dispara nada externo."""
        with patch.object(
                 training_mod, "_third_party_cloud_training_enabled", return_value=False,
             ), \
             patch.object(training_mod, "_get_runpod_training_context") as mock_ctx, \
             pytest.raises(RuntimeError, match="Treino em nuvem de terceiro desabilitado"):
            training_mod._dispatch_runpod_train(_JOB_ID, "yolo26n", 50, 640, 16, MagicMock())
        mock_ctx.assert_not_called()

    def test_license_gate_blocks_xl_variant_before_any_network_call(self) -> None:
        """ADR-0044 (decisão do dono): variante RF-DETR PML (xl/2xl) é
        rejeitada ANTES de _run_runpod_train_job rodar — nenhuma chamada de
        rede acontece pra um job que nunca poderia ser servido."""
        ctx = {
            "api_key": "k", "tenant_id": _TENANT, "coco_r2_key": "x", "framework": "rfdetr",
            "base_model": "RFDETRXLarge", "hyperparams": {},
        }
        with patch.object(
                 training_mod, "_third_party_cloud_training_enabled", return_value=True,
             ), \
             patch.object(training_mod, "_get_runpod_training_context", return_value=ctx), \
             patch.object(training_mod, "_run_runpod_train_job") as mock_real, \
             pytest.raises(RfdetrLicenseError, match="PML"):
            training_mod._dispatch_runpod_train(_JOB_ID, "yolo26n", 50, 640, 16, MagicMock())
        mock_real.assert_not_called()


class TestRunRunpodTrainJob:
    def _ctx(self) -> dict:
        return {
            "api_key": "runpod-key", "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json", "framework": "rfdetr",
            "base_model": None, "hyperparams": {},
        }

    def _patches(self, run_runpod_job_return=None, run_runpod_job_side_effect=None):
        mock_repo = MagicMock()
        mock_repo._execute_one.return_value = {"status": "running"}
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.return_value = "https://r2/get?sig=1"
        mock_storage.generate_presigned_upload_url.return_value = "https://r2/put?sig=1"

        runner = MagicMock(
            return_value=run_runpod_job_return or {
                "status": "completed", "metrics": {"mAP50": 0.7}, "pod_id": "pod-1",
            },
            side_effect=run_runpod_job_side_effect,
        )
        return mock_repo, mock_storage, runner

    def test_creates_callback_token_and_delegates_to_run_runpod_job(self) -> None:
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository") as mock_repo_cls, \
             patch.object(training_mod, "get_storage") as mock_get_storage, \
             patch.object(training_mod, "RunPodClient"), \
             patch.object(training_mod, "_read_remote_train_source", return_value="# runner"), \
             patch.object(training_mod, "run_runpod_job") as mock_run:
            mock_repo, mock_storage, runner = self._patches()
            mock_repo_cls.return_value = mock_repo
            mock_get_storage.return_value = mock_storage
            mock_run.side_effect = runner

            result = training_mod._run_runpod_train_job(
                self._ctx(), _JOB_ID, "yolo26n", 50, 640, 16, MagicMock(),
            )

        assert result["source"] == "runpod"
        assert result["metrics"] == {"mAP50": 0.7}
        # callback_token gerado e persistido antes do provisioning
        token_call = next(
            c for c in mock_repo._execute_mutation_no_return.call_args_list
            if "callback_token" in c.args[0] and "gpu_provider = 'runpod'" in c.args[0]
        )
        assert len(token_call.args[1][0]) > 20  # token não-trivial
        # run_runpod_job chamado com kind=TRAIN e o env certo
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["kind"] == JobKind.TRAIN
        assert call_kwargs["executor_filename"] == "remote_train.py"
        assert call_kwargs["env"]["DATASET_URL"] == "https://r2/get?sig=1"
        assert call_kwargs["env"]["FRAMEWORK"] == "rfdetr"
        assert "poll_status_fn" in call_kwargs
        assert "persist_instance_ref_fn" in call_kwargs
        assert "verify_completed_fn" in call_kwargs
        # callback_token revogado ao final
        revoke_call = next(
            c for c in mock_repo._execute_mutation_no_return.call_args_list
            if "callback_token = NULL" in c.args[0]
        )
        assert revoke_call.args[1] == (_JOB_ID,)
        # fix zip: DATASET_URL aponta pro zip empacotado, não pro prefixo cru
        zip_key = f"{self._ctx()['coco_r2_key']}/dataset.zip"
        mock_storage.upload_bytes.assert_called_once()
        upload_args = mock_storage.upload_bytes.call_args.args
        assert upload_args[0] == zip_key
        assert upload_args[2] == "application/zip"
        mock_storage.generate_presigned_download_url.assert_any_call(
            zip_key, ttl=training_mod._PRESIGNED_GET_TTL
        )

    def test_revokes_token_even_when_run_runpod_job_raises(self) -> None:
        """finally garante revogação — mesmo padrão do antigo destroy_instance
        Vast.ai (o terminate do pod em si é garantido DENTRO de
        run_runpod_job, camada 2 de garantia de morte)."""
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository") as mock_repo_cls, \
             patch.object(training_mod, "get_storage") as mock_get_storage, \
             patch.object(training_mod, "RunPodClient"), \
             patch.object(training_mod, "_read_remote_train_source", return_value="# runner"), \
             patch.object(
                 training_mod, "run_runpod_job",
                 side_effect=RuntimeError("Timeout runpod"),
             ):
            mock_repo, mock_storage, _ = self._patches()
            mock_repo_cls.return_value = mock_repo
            mock_get_storage.return_value = mock_storage

            with pytest.raises(RuntimeError, match="Timeout runpod"):
                training_mod._run_runpod_train_job(
                    self._ctx(), _JOB_ID, "yolo26n", 50, 640, 16, MagicMock(),
                )

        revoke_call = next(
            c for c in mock_repo._execute_mutation_no_return.call_args_list
            if "callback_token = NULL" in c.args[0]
        )
        assert revoke_call.args[1] == (_JOB_ID,)

    def test_persist_instance_ref_fn_updates_db_and_bumps_progress(self) -> None:
        update_fn = MagicMock()
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository") as mock_repo_cls, \
             patch.object(training_mod, "get_storage") as mock_get_storage, \
             patch.object(training_mod, "RunPodClient"), \
             patch.object(training_mod, "_read_remote_train_source", return_value="# runner"), \
             patch.object(training_mod, "run_runpod_job") as mock_run:
            mock_repo, mock_storage, _ = self._patches()
            mock_repo_cls.return_value = mock_repo
            mock_get_storage.return_value = mock_storage
            mock_run.return_value = {
                "status": "completed", "metrics": {}, "pod_id": "pod-9",
            }

            training_mod._run_runpod_train_job(
                self._ctx(), _JOB_ID, "yolo26n", 50, 640, 16, update_fn,
            )

            persist_fn = mock_run.call_args.kwargs["persist_instance_ref_fn"]
            persist_fn("pod-abc")

        ref_call = next(
            c for c in mock_repo._execute_mutation_no_return.call_args_list
            if "gpu_instance_ref" in c.args[0]
        )
        assert ref_call.args[1] == ("pod-abc", _JOB_ID)
        update_fn.assert_any_call("running", progress=5)

    def test_verify_completed_fn_checks_artifact(self) -> None:
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository") as mock_repo_cls, \
             patch.object(training_mod, "get_storage") as mock_get_storage, \
             patch.object(training_mod, "RunPodClient"), \
             patch.object(training_mod, "_read_remote_train_source", return_value="# runner"), \
             patch.object(training_mod, "run_runpod_job") as mock_run, \
             patch.object(
                 training_mod, "verify_model_artifact", return_value=True,
             ) as mock_verify:
            mock_repo, mock_storage, _ = self._patches()
            mock_repo_cls.return_value = mock_repo
            mock_get_storage.return_value = mock_storage
            mock_run.return_value = {"status": "completed", "metrics": {}, "pod_id": "p"}

            training_mod._run_runpod_train_job(
                self._ctx(), _JOB_ID, "yolo26n", 50, 640, 16, MagicMock(),
            )

            verify_fn = mock_run.call_args.kwargs["verify_completed_fn"]
            assert verify_fn({}) is True

        expected_key = training_mod.runpod_onnx_artifact_key(_TENANT, _JOB_ID)
        mock_verify.assert_called_once_with(_TENANT, expected_key)


class TestRunRunpodTrainJobStopRace:
    """Achado crítico da revisão (ainda válido com RunPod): stop entre o
    início do dispatch e a criação do pod não pode ser ignorado —
    provisionaria um segundo pod GPU pago pra um job já cancelado pelo
    usuário."""

    def _ctx(self) -> dict:
        return {
            "api_key": "runpod-key", "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json", "framework": "rfdetr",
            "base_model": None, "hyperparams": {},
        }

    def test_aborts_before_run_runpod_job_when_already_stopped(self) -> None:
        mock_repo = MagicMock()
        mock_repo._execute_one.return_value = {"status": "stopped"}
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.return_value = "https://r2/get"
        mock_storage.generate_presigned_upload_url.return_value = "https://r2/put"

        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository", return_value=mock_repo), \
             patch.object(training_mod, "get_storage", return_value=mock_storage), \
             patch.object(training_mod, "RunPodClient"), \
             patch.object(training_mod, "_read_remote_train_source", return_value="# runner"), \
             patch.object(training_mod, "run_runpod_job") as mock_run:
            with pytest.raises(JobStoppedError):
                training_mod._run_runpod_train_job(
                    self._ctx(), _JOB_ID, "yolo26n", 50, 640, 16, MagicMock(),
                )

        # Abortou ANTES de qualquer chamada ao runner genérico — nenhum pod
        # criado/terminado.
        mock_run.assert_not_called()


class TestUpdateJobNeverOverwritesStopped:
    """Achado da revisão: update_fn("running", ...) chamado durante o
    provisioning podia reverter um stop concorrente de volta para 'running'."""

    def test_sql_guards_against_stopped_status(self, monkeypatch) -> None:
        mock_repo = MagicMock()
        fake_compute = MagicMock()
        fake_compute.dispatch.return_value = {
            "model_path": "models/t/runpod/j/model.onnx", "metrics": {}, "source": "runpod",
        }
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "AnnotationRepository", return_value=mock_repo), \
             patch.object(training_mod, "_publish_progress"), \
             patch.object(
                 training_mod, "get_training_compute", return_value=fake_compute,
             ), \
             patch.object(training_mod, "verify_model_artifact", return_value=True):
            mock_repo._execute_one.return_value = None
            training_mod.dispatch_training(_JOB_ID, "dsv-1", epochs=1)

        update_calls = [
            c for c in mock_repo._execute_mutation_no_return.call_args_list
            if "training_jobs" in c.args[0] and "SET status" in c.args[0]
        ]
        assert update_calls, "update_job deveria ter rodado ao menos um UPDATE"
        for call in update_calls:
            assert "AND status != 'stopped'" in call.args[0]


class TestDispatchTrainingStopHandling:
    """dispatch_training NUNCA reagenda (self.retry) quando o dispatch
    RunPod detecta que o job foi parado — vs. falha real de infra."""

    def test_job_stopped_error_returns_without_retry(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_API_KEY", "runpod-key")
        monkeypatch.delenv("ULTRALYTICS_HUB_API_KEY", raising=False)
        mock_repo = MagicMock()

        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "AnnotationRepository", return_value=mock_repo), \
             patch.object(training_mod, "_publish_progress"), \
             patch.object(
                 training_mod, "_dispatch_runpod_train",
                 side_effect=JobStoppedError("job parado"),
             ):
            result = training_mod.dispatch_training(_JOB_ID, "dsv-1", epochs=1)

        assert result == {"job_id": _JOB_ID, "status": "stopped"}
        # NENHUM UPDATE de status='failed' — não sobrescreve o 'stopped' real
        assert not any(
            c.args[1][0] == "failed"
            for c in mock_repo._execute_mutation_no_return.call_args_list
            if "SET status" in c.args[0]
        )

    def test_generic_exception_still_retries(self, monkeypatch) -> None:
        """Regressão: falha real de infraestrutura CONTINUA reagendando."""
        monkeypatch.setenv("RUNPOD_API_KEY", "runpod-key")
        monkeypatch.delenv("ULTRALYTICS_HUB_API_KEY", raising=False)
        mock_repo = MagicMock()

        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "AnnotationRepository", return_value=mock_repo), \
             patch.object(training_mod, "_publish_progress"), \
             patch.object(
                 training_mod, "_dispatch_runpod_train",
                 side_effect=RuntimeError("pod RunPod crashou"),
             ):
            try:
                training_mod.dispatch_training(_JOB_ID, "dsv-1", epochs=1)
                raise AssertionError("deveria propagar via self.retry")
            except Exception as exc:
                # Celery real levantaria Retry; sem app Celery real aqui o
                # retry() cai no RuntimeError original encadeado (from exc).
                assert "pod RunPod crashou" in str(exc) or "Retry" in type(exc).__name__

        # Status 'failed' FOI gravado para falha genérica (comportamento preservado)
        assert any(
            c.args[1][0] == "failed"
            for c in mock_repo._execute_mutation_no_return.call_args_list
            if "SET status" in c.args[0]
        )


class TestBuildTrainingDatasetZip:
    """_build_training_dataset_zip: coco_r2_key é um PREFIXO (múltiplos
    objetos soltos por split), não um zip — sem empacotar, o presigned GET
    que remote_train.py baixa não é um zip válido e o dispatch real falha no
    primeiro passo. Cobre o fix: zip único, "val" renomeado pra "valid"
    (RFDETR/Roboflow-padrão), "test" mantido.
    """

    def _make_fake_storage(self, objects: dict[str, bytes]) -> MagicMock:
        storage = MagicMock()
        storage.list_keys.side_effect = lambda prefix: [
            k for k in objects if k.startswith(prefix)
        ]
        storage.download_bytes.side_effect = lambda key: objects[key]
        return storage

    def test_renames_val_to_valid_and_keeps_train_test(self) -> None:
        import zipfile
        from io import BytesIO

        prefix = "datasets/t/d/v1"
        objects = {
            f"{prefix}/train/_annotations.coco.json": b'{"images":[]}',
            f"{prefix}/train/img1.jpg": b"train-bytes",
            f"{prefix}/val/_annotations.coco.json": b'{"images":[]}',
            f"{prefix}/val/img2.jpg": b"val-bytes",
            f"{prefix}/test/_annotations.coco.json": b'{"images":[]}',
        }
        storage = self._make_fake_storage(objects)

        zip_bytes = training_mod._build_training_dataset_zip(storage, prefix)

        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
            assert names == {
                "train/_annotations.coco.json",
                "train/img1.jpg",
                "valid/_annotations.coco.json",  # "val" → "valid"
                "valid/img2.jpg",
                "test/_annotations.coco.json",
            }
            assert zf.read("valid/img2.jpg") == b"val-bytes"

    def test_empty_prefix_yields_empty_but_valid_zip(self) -> None:
        import zipfile
        from io import BytesIO

        storage = self._make_fake_storage({})
        zip_bytes = training_mod._build_training_dataset_zip(storage, "datasets/empty")

        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            assert zf.namelist() == []
