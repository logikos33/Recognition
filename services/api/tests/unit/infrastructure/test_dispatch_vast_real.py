"""
Tests: tasks/training.py — dispatch Vast.ai REST real (WS-A4).

Cobre:
- _get_vast_context: None quando falta dataset COCO ou API key resolvível;
  contexto completo quando ambos existem.
- _dispatch_vast_ai: sem contexto → cai no fluxo legado (_dispatch_vast_ai_legacy);
  com contexto → roda o fluxo REST (_run_vast_remote_training).
- _run_vast_remote_training: gera callback_token por-job, presigned URLs,
  cria instância, delega ao watchdog, e SEMPRE destrói a instância + revoga
  o callback_token (try/finally) — inclusive quando o watchdog levanta.
- _watch_vast_job: completed via DB → retorna metrics; failed → RuntimeError;
  stopped → _JobStoppedError (distinto — não deve reagendar); instância
  morta 3x seguidas → RuntimeError; timeout → RuntimeError.
- Achado da revisão adversarial (stop deixa vazar 2ª instância GPU paga):
  update_job() nunca sobrescreve status='stopped'; _run_vast_remote_training
  recheca o status antes de create_instance e aborta sem provisionar;
  dispatch_training NUNCA chama self.retry() para _JobStoppedError.
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

from app.infrastructure.gpu.vast_client import VastAIError  # noqa: E402
from app.infrastructure.queue.tasks import training as training_mod  # noqa: E402

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TENANT = "99999999-8888-7777-6666-555555555555"


class TestGetVastContext:
    def test_none_without_coco_dataset(self) -> None:
        mock_repo = MagicMock()
        mock_repo._execute_one.return_value = {
            "id": _JOB_ID, "tenant_id": _TENANT, "coco_r2_key": None,
            "framework": "rfdetr",
        }
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository", return_value=mock_repo):
            assert training_mod._get_vast_context(_JOB_ID) is None

    def test_none_without_resolvable_api_key(self) -> None:
        mock_repo = MagicMock()
        mock_repo._execute_one.return_value = {
            "id": _JOB_ID, "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json", "framework": "rfdetr",
        }
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository", return_value=mock_repo), \
             patch.object(training_mod, "resolve_vast_api_key", return_value=""):
            assert training_mod._get_vast_context(_JOB_ID) is None

    def test_full_context_when_both_present(self) -> None:
        mock_repo = MagicMock()
        mock_repo._execute_one.return_value = {
            "id": _JOB_ID, "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json", "framework": "yolox",
        }
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository", return_value=mock_repo), \
             patch.object(training_mod, "resolve_vast_api_key", return_value="vast-key"):
            ctx = training_mod._get_vast_context(_JOB_ID)
        assert ctx == {
            "api_key": "vast-key",
            "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json",
            "framework": "yolox",
        }

    def test_none_on_db_error(self) -> None:
        with patch.object(training_mod, "DatabasePool", side_effect=Exception("db down")):
            assert training_mod._get_vast_context(_JOB_ID) is None


class TestDispatchVastAiRouting:
    """C5 (task "treino honesto"): _dispatch_vast_ai agora gateia
    training_third_party_cloud_enabled ANTES de tudo (Vast.ai é GPU de
    terceiro) — os testes abaixo mockam a flag como True pra exercitar só a
    lógica de roteamento ctx None/presente.

    C1: ctx None (dataset ausente) NÃO cai mais automaticamente no fluxo
    legado (_dispatch_vast_ai_legacy) — levanta erro claro (achado desta
    task: treinar no dataset PÚBLICO do Roboflow quando o dataset do tenant
    está ausente seria uma substituição silenciosa)."""

    def test_no_context_raises_dataset_ausente(self) -> None:
        """C1 (task "treino não pode mentir"): sem contexto (dataset ausente),
        _dispatch_vast_ai levanta erro claro — nunca cai em outro dataset
        (o fluxo legado que fazia isso foi deletado)."""
        with patch.object(
                 training_mod, "_third_party_cloud_training_enabled", return_value=True,
             ), \
             patch.object(training_mod, "_get_vast_context", return_value=None), \
             patch.object(training_mod, "resolve_vast_api_key", return_value="a-key"), \
             patch.object(training_mod, "_run_vast_remote_training") as mock_real, \
             pytest.raises(RuntimeError, match="dataset sem exportação COCO"):
            training_mod._dispatch_vast_ai(_JOB_ID, "yolo26n", 50, 640, 16, MagicMock())
        mock_real.assert_not_called()

    def test_with_context_uses_real_rest_flow(self) -> None:
        ctx = {"api_key": "k", "tenant_id": _TENANT, "coco_r2_key": "x", "framework": "rfdetr"}
        with patch.object(
                 training_mod, "_third_party_cloud_training_enabled", return_value=True,
             ), \
             patch.object(training_mod, "_get_vast_context", return_value=ctx), \
             patch.object(training_mod, "_run_vast_remote_training") as mock_real:
            mock_real.return_value = {"model_path": "x", "metrics": {}, "source": "vast_ai"}
            training_mod._dispatch_vast_ai(_JOB_ID, "yolo26n", 50, 640, 16, MagicMock())
        mock_real.assert_called_once()

    def test_third_party_disabled_raises_before_checking_context(self) -> None:
        """C5: flag OFF levanta erro claro ANTES de sequer resolver o
        contexto (dataset/API key) — nunca dispara nada externo."""
        with patch.object(
                 training_mod, "_third_party_cloud_training_enabled", return_value=False,
             ), \
             patch.object(training_mod, "_get_vast_context") as mock_ctx, \
             pytest.raises(RuntimeError, match="Treino em nuvem de terceiro desabilitado"):
            training_mod._dispatch_vast_ai(_JOB_ID, "yolo26n", 50, 640, 16, MagicMock())
        mock_ctx.assert_not_called()


class TestRunVastRemoteTraining:
    def _ctx(self) -> dict:
        return {
            "api_key": "vast-key", "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json", "framework": "rfdetr",
        }

    def _patches(self, mock_client_cls, watch_result=None, watch_side_effect=None):
        mock_repo = MagicMock()
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.return_value = "https://r2/get?sig=1"
        mock_storage.generate_presigned_upload_url.return_value = "https://r2/put?sig=1"

        mock_client = MagicMock()
        mock_client.search_offers.return_value = [{"id": 123, "dph_total": 0.4}]
        mock_client.create_instance.return_value = {"new_contract": 999}
        mock_client_cls.return_value = mock_client

        watcher = MagicMock(
            return_value=watch_result or {"model_path": "x", "metrics": {}, "source": "vast_ai"},
            side_effect=watch_side_effect,
        )

        return mock_repo, mock_storage, mock_client, watcher

    def test_creates_callback_token_and_destroys_instance_on_success(self) -> None:
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository") as mock_repo_cls, \
             patch.object(training_mod, "get_storage") as mock_get_storage, \
             patch.object(training_mod, "VastAIClient") as mock_client_cls, \
             patch.object(training_mod, "_read_remote_train_source", return_value="# runner"), \
             patch.object(training_mod, "_watch_vast_job") as mock_watch:
            mock_repo, mock_storage, mock_client, watcher = self._patches(mock_client_cls)
            mock_repo_cls.return_value = mock_repo
            mock_get_storage.return_value = mock_storage
            mock_watch.side_effect = watcher

            result = training_mod._run_vast_remote_training(
                self._ctx(), _JOB_ID, "yolo26n", 50, 640, 16, MagicMock(),
            )

        assert result["source"] == "vast_ai"
        # callback_token gerado e persistido antes do provisioning
        token_call = next(
            c for c in mock_repo._execute_mutation_no_return.call_args_list
            if "callback_token" in c.args[0] and "gpu_provider" in c.args[0]
        )
        assert len(token_call.args[1][0]) > 20  # token não-trivial
        # instância criada e destruída (nunca vaza GPU paga)
        mock_client.create_instance.assert_called_once()
        mock_client.destroy_instance.assert_called_once_with(999)
        # callback_token revogado ao final
        revoke_call = next(
            c for c in mock_repo._execute_mutation_no_return.call_args_list
            if "callback_token = NULL" in c.args[0]
        )
        assert revoke_call.args[1] == (_JOB_ID,)
        # fix zip: DATASET_URL aponta pro zip empacotado, não pro prefixo cru
        # (coco_r2_key sozinho não é baixável — remote_train.py espera um
        # zip único; ver _build_vast_dataset_zip)
        zip_key = f"{self._ctx()['coco_r2_key']}/dataset.zip"
        mock_storage.upload_bytes.assert_called_once()
        upload_args = mock_storage.upload_bytes.call_args.args
        assert upload_args[0] == zip_key
        assert upload_args[2] == "application/zip"
        mock_storage.generate_presigned_download_url.assert_any_call(
            zip_key, ttl=training_mod._PRESIGNED_GET_TTL
        )

    def test_destroys_instance_even_when_watchdog_raises(self) -> None:
        """finally garante destroy — instância não vaza GPU paga em erro."""
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository") as mock_repo_cls, \
             patch.object(training_mod, "get_storage") as mock_get_storage, \
             patch.object(training_mod, "VastAIClient") as mock_client_cls, \
             patch.object(training_mod, "_read_remote_train_source", return_value="# runner"), \
             patch.object(
                 training_mod, "_watch_vast_job",
                 side_effect=RuntimeError("Timeout vast_ai"),
             ):
            mock_repo, mock_storage, mock_client, _ = self._patches(mock_client_cls)
            mock_repo_cls.return_value = mock_repo
            mock_get_storage.return_value = mock_storage

            try:
                training_mod._run_vast_remote_training(
                    self._ctx(), _JOB_ID, "yolo26n", 50, 640, 16, MagicMock(),
                )
                raise AssertionError("deveria propagar RuntimeError do watchdog")
            except RuntimeError:
                pass

        mock_client.destroy_instance.assert_called_once_with(999)

    def test_raises_when_no_offers_available(self) -> None:
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository") as mock_repo_cls, \
             patch.object(training_mod, "get_storage") as mock_get_storage, \
             patch.object(training_mod, "VastAIClient") as mock_client_cls, \
             patch.object(training_mod, "_read_remote_train_source", return_value="# runner"):
            mock_repo, mock_storage, mock_client, _ = self._patches(mock_client_cls)
            mock_client.search_offers.return_value = []
            mock_repo_cls.return_value = mock_repo
            mock_get_storage.return_value = mock_storage

            try:
                training_mod._run_vast_remote_training(
                    self._ctx(), _JOB_ID, "yolo26n", 50, 640, 16, MagicMock(),
                )
                raise AssertionError("deveria levantar sem ofertas de GPU")
            except RuntimeError as exc:
                assert "oferta" in str(exc).lower() or "GPU" in str(exc)
        mock_client.create_instance.assert_not_called()
        mock_client.destroy_instance.assert_not_called()


class TestWatchVastJob:
    """verify_model_artifact é mockado True por padrão (autouse) — os testes
    aqui exercitam o poll/timeout/estado, não o guard de artefato em si
    (esse tem sua própria classe, TestWatchVastJobArtifactGuard)."""

    @pytest.fixture(autouse=True)
    def _artifact_verified(self):
        with patch.object(training_mod, "verify_model_artifact", return_value=True):
            yield

    def _repo(self, statuses: list[dict]) -> MagicMock:
        repo = MagicMock()
        repo._execute_one.side_effect = statuses
        return repo

    def test_completed_status_returns_metrics(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_POLL_INTERVAL_SECONDS", "0")
        repo = self._repo([{"status": "completed", "metrics": {"mAP50": 0.8}}])
        client = MagicMock()
        result = training_mod._watch_vast_job(
            client, repo, _JOB_ID, 999, "models/t/vast/j/model.onnx", _TENANT,
        )
        assert result == {
            "model_path": "models/t/vast/j/model.onnx",
            "metrics": {"mAP50": 0.8},
            "source": "vast_ai",
        }
        client.get_instance_status.assert_not_called()

    def test_failed_status_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_POLL_INTERVAL_SECONDS", "0")
        repo = self._repo([{"status": "failed", "metrics": {}}])
        client = MagicMock()
        try:
            training_mod._watch_vast_job(client, repo, _JOB_ID, 999, "x", _TENANT)
            raise AssertionError("deveria levantar em status failed")
        except RuntimeError as exc:
            assert "failed" in str(exc)

    def test_dead_instance_three_times_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_POLL_INTERVAL_SECONDS", "0")
        repo = self._repo([{"status": "running"}] * 3)
        client = MagicMock()
        client.get_instance_status.return_value = {"actual_status": "exited"}
        try:
            training_mod._watch_vast_job(client, repo, _JOB_ID, 999, "x", _TENANT)
            raise AssertionError("deveria levantar após 3 polls mortos")
        except RuntimeError as exc:
            assert "sem callback final" in str(exc)
        assert client.get_instance_status.call_count == 3

    def test_alive_instance_resets_dead_counter(self, monkeypatch) -> None:
        """2 polls mortos + 1 vivo + 2 mortos NÃO deve levantar (contador reseta)."""
        monkeypatch.setenv("VAST_POLL_INTERVAL_SECONDS", "0")
        repo = self._repo(
            [{"status": "running"}] * 4 + [{"status": "completed", "metrics": {}}]
        )
        client = MagicMock()
        client.get_instance_status.side_effect = [
            {"actual_status": "exited"},
            {"actual_status": "exited"},
            {"actual_status": "running"},
            {"actual_status": "exited"},
        ]
        result = training_mod._watch_vast_job(client, repo, _JOB_ID, 999, "x", _TENANT)
        assert result["source"] == "vast_ai"

    def test_poll_failure_is_tolerated(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_POLL_INTERVAL_SECONDS", "0")
        repo = self._repo(
            [{"status": "running"}, {"status": "completed", "metrics": {}}]
        )
        client = MagicMock()
        client.get_instance_status.side_effect = VastAIError("timeout de rede")
        result = training_mod._watch_vast_job(client, repo, _JOB_ID, 999, "x", _TENANT)
        assert result["source"] == "vast_ai"

    def test_timeout_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_TIMEOUT_SECONDS", "0")
        monkeypatch.setenv("VAST_POLL_INTERVAL_SECONDS", "0")
        repo = MagicMock()
        client = MagicMock()
        try:
            training_mod._watch_vast_job(client, repo, _JOB_ID, 999, "x", _TENANT)
            raise AssertionError("deveria levantar por timeout imediato")
        except RuntimeError as exc:
            assert "Timeout vast_ai" in str(exc)

    def test_stopped_status_raises_job_stopped_error_not_generic(self, monkeypatch) -> None:
        """'stopped' é distinto de 'failed': dispatch_training NÃO deve
        reagendar (self.retry) quando o job foi parado explicitamente."""
        monkeypatch.setenv("VAST_POLL_INTERVAL_SECONDS", "0")
        repo = self._repo([{"status": "stopped", "metrics": {}}])
        client = MagicMock()
        try:
            training_mod._watch_vast_job(client, repo, _JOB_ID, 999, "x", _TENANT)
            raise AssertionError("deveria levantar _JobStoppedError")
        except training_mod._JobStoppedError:
            pass
        except RuntimeError:
            raise AssertionError(
                "status='stopped' deve levantar _JobStoppedError, não RuntimeError genérico"
            ) from None


class TestWatchVastJobArtifactGuard:
    """Task "treino não pode mentir": mesmo com training_jobs.status já
    'completed' no banco (escrito pelo callback), o watchdog reconfirma o
    artefato antes de repassar sucesso — defesa em profundidade contra
    qualquer escrita de status que não passe pela verificação do callback."""

    def test_completed_without_verified_artifact_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_POLL_INTERVAL_SECONDS", "0")
        repo = MagicMock()
        repo._execute_one.return_value = {"status": "completed", "metrics": {}}
        client = MagicMock()
        with patch.object(training_mod, "verify_model_artifact", return_value=False):
            try:
                training_mod._watch_vast_job(
                    client, repo, _JOB_ID, 999, "models/t/vast/j/model.onnx", _TENANT,
                )
                raise AssertionError("deveria levantar sem artefato confirmado")
            except RuntimeError as exc:
                assert "artefato" in str(exc).lower()

    def test_completed_with_verified_artifact_returns(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_POLL_INTERVAL_SECONDS", "0")
        repo = MagicMock()
        repo._execute_one.return_value = {"status": "completed", "metrics": {"mAP50": 0.9}}
        client = MagicMock()
        with patch.object(
            training_mod, "verify_model_artifact", return_value=True,
        ) as mock_verify:
            result = training_mod._watch_vast_job(
                client, repo, _JOB_ID, 999, "models/t/vast/j/model.onnx", _TENANT,
            )
        assert result["metrics"] == {"mAP50": 0.9}
        mock_verify.assert_called_once_with(_TENANT, "models/t/vast/j/model.onnx")


class TestUpdateJobNeverOverwritesStopped:
    """Achado da revisão: update_fn("running", ...) chamado durante o
    provisioning podia reverter um stop concorrente de volta para 'running'."""

    def test_sql_guards_against_stopped_status(self, monkeypatch) -> None:
        mock_repo = MagicMock()
        fake_compute = MagicMock()
        fake_compute.dispatch.return_value = {
            "model_path": "models/t/vast/j/model.onnx", "metrics": {}, "source": "vast_ai",
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


class TestRunVastRemoteTrainingStopRace:
    """Achado crítico da revisão: stop entre o início do dispatch e a
    criação da instância não podia ser ignorado — provisionaria uma
    segunda instância GPU paga para um job já cancelado pelo usuário."""

    def _ctx(self) -> dict:
        return {
            "api_key": "vast-key", "tenant_id": _TENANT,
            "coco_r2_key": "datasets/t/d/v1/train.coco.json", "framework": "rfdetr",
        }

    def test_aborts_before_create_instance_when_already_stopped(self) -> None:
        mock_repo = MagicMock()
        # Primeira leitura (recheck pré-create_instance) já reporta 'stopped'
        mock_repo._execute_one.return_value = {"status": "stopped"}
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.return_value = "https://r2/get"
        mock_storage.generate_presigned_upload_url.return_value = "https://r2/put"
        mock_client = MagicMock()

        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "TrainingRepository", return_value=mock_repo), \
             patch.object(training_mod, "get_storage", return_value=mock_storage), \
             patch.object(training_mod, "VastAIClient", return_value=mock_client), \
             patch.object(training_mod, "_read_remote_train_source", return_value="# runner"):
            try:
                training_mod._run_vast_remote_training(
                    self._ctx(), _JOB_ID, "yolo26n", 50, 640, 16, MagicMock(),
                )
                raise AssertionError("deveria abortar com _JobStoppedError")
            except training_mod._JobStoppedError:
                pass

        # Nenhuma oferta buscada, nenhuma instância criada/destruída —
        # abortou ANTES de qualquer chamada de provisioning à Vast.ai.
        mock_client.search_offers.assert_not_called()
        mock_client.create_instance.assert_not_called()
        mock_client.destroy_instance.assert_not_called()


class TestDispatchTrainingStopHandling:
    """dispatch_training NUNCA reagenda (self.retry) quando o dispatch
    Vast.ai detecta que o job foi parado — vs. falha real de infra."""

    def test_job_stopped_error_returns_without_retry(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_API_KEY", "vast-key")
        monkeypatch.delenv("ULTRALYTICS_HUB_API_KEY", raising=False)
        mock_repo = MagicMock()

        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "AnnotationRepository", return_value=mock_repo), \
             patch.object(training_mod, "_publish_progress"), \
             patch.object(
                 training_mod, "_dispatch_vast_ai",
                 side_effect=training_mod._JobStoppedError("job parado"),
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
        monkeypatch.setenv("VAST_API_KEY", "vast-key")
        monkeypatch.delenv("ULTRALYTICS_HUB_API_KEY", raising=False)
        mock_repo = MagicMock()

        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "AnnotationRepository", return_value=mock_repo), \
             patch.object(training_mod, "_publish_progress"), \
             patch.object(
                 training_mod, "_dispatch_vast_ai",
                 side_effect=RuntimeError("instância Vast.ai crashou"),
             ):
            try:
                training_mod.dispatch_training(_JOB_ID, "dsv-1", epochs=1)
                raise AssertionError("deveria propagar via self.retry")
            except Exception as exc:
                # Celery real levantaria Retry; sem app Celery real aqui o
                # retry() cai no RuntimeError original encadeado (from exc).
                assert "instância Vast.ai crashou" in str(exc) or "Retry" in type(exc).__name__

        # Status 'failed' FOI gravado para falha genérica (comportamento preservado)
        assert any(
            c.args[1][0] == "failed"
            for c in mock_repo._execute_mutation_no_return.call_args_list
            if "SET status" in c.args[0]
        )


class TestBuildVastDatasetZip:
    """_build_vast_dataset_zip: coco_r2_key é um PREFIXO (múltiplos objetos
    soltos por split), não um zip — sem empacotar, o presigned GET que
    remote_train.py baixa não é um zip válido e o dispatch real falha no
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

        zip_bytes = training_mod._build_vast_dataset_zip(storage, prefix)

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
        zip_bytes = training_mod._build_vast_dataset_zip(storage, "datasets/empty")

        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            assert zf.namelist() == []
