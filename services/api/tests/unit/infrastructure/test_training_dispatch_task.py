"""
Tests: tasks/training.py — regressão do merge develop×staging (Cluster C / PR-1).

Cobre:
- Precedência de credenciais: VAST_API_KEY > ULTRALYTICS_HUB_API_KEY > simulação
- INSERT em trained_models propaga created_by/origin/tenant_id (migration 090)
- origin lido de result['source'] top-level ('vast_ai' | 'simulated' | fallback 'unknown')
- _dispatch_vast_ai: model_path usa r2_key do metrics.json; sem r2_key → tenant REAL
  do job (nunca tenant de teste hardcoded) + warning 'registro parcial'
- job_handlers.get_current_job_status_handler: gpu_enabled aceita VAST_API_KEY
  (var realmente usada pelo dispatch) além de VAST_AI_API_KEY (legado)
"""
from __future__ import annotations

import json
import logging
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Garante import REAL de celery_app/training mesmo que outro arquivo de teste
# tenha deixado um stub de celery_app em sys.modules (padrão pré-existente de
# tests/unit/domain/test_versioning_helpers.py). Stubs via types.ModuleType
# não têm __file__ — é o marcador para evictar e reimportar o real.
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_TRAINING_KEY = "app.infrastructure.queue.tasks.training"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_TRAINING_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue.tasks import training as training_mod  # noqa: E402

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_DSV_ID = "11111111-2222-3333-4444-555555555555"
_REAL_TENANT = "99999999-8888-7777-6666-555555555555"


def _run_dispatch(monkeypatch, env: dict[str, str], vast_result=None, hub_result=None,
                  sim_result=None, existing_model=None, resolved_vast_key=None):
    """Executa dispatch_training com repo/redis mockados e env controlado.

    `resolved_vast_key`: quando setado, simula resolve_vast_api_key encontrando
    uma chave no integration store do tenant — MESMO com env vazio (WS-D1/
    ADR-0039). Patcheia tanto training_mod.resolve_vast_api_key (gate externo,
    já importado por `from ... import` no topo de training.py) quanto o
    módulo fonte (app.infrastructure.gpu.vast_client), lido de novo a cada
    chamada pelo late-import de get_training_compute (training_compute.py).

    Retorna (repo_mock, mocks das 3 branches de dispatch).
    """
    for var in ("VAST_API_KEY", "ULTRALYTICS_HUB_API_KEY", "VAST_AI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    if resolved_vast_key is not None:
        fake_resolver = MagicMock(return_value=resolved_vast_key)
        monkeypatch.setattr(training_mod, "resolve_vast_api_key", fake_resolver)
        monkeypatch.setattr(
            "app.infrastructure.gpu.vast_client.resolve_vast_api_key", fake_resolver
        )

    default_result = {
        "model_path": f"models/{_JOB_ID}/best.pt",
        "metrics": {"mAP50": 0.5, "precision": 0.6, "recall": 0.4},
        "source": "simulated",
    }
    with patch.object(training_mod, "DatabasePool"), \
         patch.object(training_mod, "AnnotationRepository") as mock_repo_cls, \
         patch.object(training_mod, "_publish_progress"), \
         patch.object(
             training_mod, "_dispatch_vast_ai",
             return_value=vast_result or default_result,
         ) as mock_vast, \
         patch.object(
             training_mod, "_dispatch_hub",
             return_value=hub_result or default_result,
         ) as mock_hub, \
         patch.object(
             training_mod, "_simulate_training",
             return_value=sim_result or default_result,
         ) as mock_sim:
        # Guarda anti-duplicação (ajuste #2) consulta trained_models por job_id
        # antes do INSERT — sem modelo pré-existente no caminho padrão.
        mock_repo_cls.return_value._execute_one.return_value = existing_model
        result = training_mod.dispatch_training(_JOB_ID, _DSV_ID, epochs=5)

    assert result["status"] == "completed"
    return mock_repo_cls.return_value, mock_vast, mock_hub, mock_sim


def _find_insert_call(repo_mock):
    """Localiza a chamada de INSERT INTO trained_models no repo mockado."""
    for call in repo_mock._execute_mutation_no_return.call_args_list:
        sql = call.args[0]
        if "INSERT INTO trained_models" in sql:
            return sql, call.args[1]
    raise AssertionError("INSERT INTO trained_models não foi executado")


class TestDispatchPrecedence:
    """Precedência: VAST_API_KEY > ULTRALYTICS_HUB_API_KEY > simulação."""

    def test_vast_key_wins_over_hub_key(self, monkeypatch) -> None:
        repo, mock_vast, mock_hub, mock_sim = _run_dispatch(
            monkeypatch,
            env={"VAST_API_KEY": "vast-key", "ULTRALYTICS_HUB_API_KEY": "hub-key"},
        )
        mock_vast.assert_called_once()
        mock_hub.assert_not_called()
        mock_sim.assert_not_called()

    def test_hub_key_used_when_no_vast_key(self, monkeypatch) -> None:
        repo, mock_vast, mock_hub, mock_sim = _run_dispatch(
            monkeypatch, env={"ULTRALYTICS_HUB_API_KEY": "hub-key"},
        )
        mock_vast.assert_not_called()
        mock_hub.assert_called_once()
        mock_sim.assert_not_called()

    def test_simulation_when_no_keys(self, monkeypatch) -> None:
        repo, mock_vast, mock_hub, mock_sim = _run_dispatch(monkeypatch, env={})
        mock_vast.assert_not_called()
        mock_hub.assert_not_called()
        mock_sim.assert_called_once()

    def test_legacy_vast_ai_api_key_alone_does_not_trigger_vast_dispatch(
        self, monkeypatch,
    ) -> None:
        """O dispatch usa VAST_API_KEY; VAST_AI_API_KEY sozinha cai na simulação.

        Regressão do achado da auditoria: gpu_enabled anunciava GPU (VAST_AI_API_KEY)
        mas o dispatch nunca a usava — documenta o contrato real do worker.
        """
        repo, mock_vast, mock_hub, mock_sim = _run_dispatch(
            monkeypatch, env={"VAST_AI_API_KEY": "legacy-key"},
        )
        mock_vast.assert_not_called()
        mock_sim.assert_called_once()

    def test_tenant_scoped_vast_key_triggers_dispatch_without_env_var(
        self, monkeypatch,
    ) -> None:
        """WS-D1/ADR-0039 — bug achado construindo TrainingCompute: o gate
        antigo (`os.environ.get("VAST_API_KEY")`) ignorava chave resolvida só
        via integration store do tenant (sem env var setada), mesmo o
        docstring do módulo sempre tendo alegado essa precedência. Falha
        antes do fix: mock_vast nunca era chamado aqui (caía em hub/simulação
        mesmo com uma chave "resolvível"); passa depois: resolve_vast_api_key
        retornando algo (via get_training_compute) já basta pra disparar
        _dispatch_vast_ai, sem nenhuma env var de GPU setada.
        """
        repo, mock_vast, mock_hub, mock_sim = _run_dispatch(
            monkeypatch, env={"ULTRALYTICS_HUB_API_KEY": "hub-key"},
            resolved_vast_key="tenant-store-key",
        )
        mock_vast.assert_called_once()
        mock_hub.assert_not_called()
        mock_sim.assert_not_called()


class TestTrainedModelInsertPropagation:
    """INSERT em trained_models propaga created_by/origin/tenant_id (migration 090)."""

    def test_insert_propagates_lineage_columns(self, monkeypatch) -> None:
        repo, *_ = _run_dispatch(
            monkeypatch,
            env={"VAST_API_KEY": "vast-key"},
            vast_result={
                "model_path": f"models/{_REAL_TENANT}/vast/{_JOB_ID}.onnx",
                "metrics": {"mAP50": 0.81, "precision": 0.9, "recall": 0.7},
                "source": "vast_ai",
            },
        )
        sql, params = _find_insert_call(repo)
        # Colunas de linhagem (090) presentes no INSERT
        assert "created_by, origin, tenant_id" in sql
        # created_by/tenant_id resolvidos do job real (não hardcoded)
        assert "tj.user_id" in sql
        assert "u.tenant_id" in sql
        assert "JOIN users u ON u.id = tj.user_id" in sql
        # model_path do resultado do dispatch
        assert f"models/{_REAL_TENANT}/vast/{_JOB_ID}.onnx" in params

    def test_origin_vast_ai_read_from_result_source_top_level(self, monkeypatch) -> None:
        repo, *_ = _run_dispatch(
            monkeypatch,
            env={"VAST_API_KEY": "vast-key"},
            vast_result={
                "model_path": "models/t/vast/x.onnx",
                "metrics": {"mAP50": 0.8},
                "source": "vast_ai",
            },
        )
        _, params = _find_insert_call(repo)
        assert "vast_ai" in params

    def test_origin_simulated_propagated(self, monkeypatch) -> None:
        repo, *_ = _run_dispatch(monkeypatch, env={})
        _, params = _find_insert_call(repo)
        assert "simulated" in params

    def test_origin_defaults_to_unknown_when_source_missing(self, monkeypatch) -> None:
        repo, *_ = _run_dispatch(
            monkeypatch,
            env={},
            sim_result={"model_path": "models/x/best.pt", "metrics": {}},
        )
        _, params = _find_insert_call(repo)
        assert "unknown" in params


class TestRegisterDuplicationGuard:
    """Ajuste vinculante #2: job_id sem UNIQUE — modelo existente pula o INSERT."""

    def test_existing_model_skips_insert(self, monkeypatch) -> None:
        repo, *_ = _run_dispatch(
            monkeypatch, env={}, existing_model={"id": "model-ja-registrado"},
        )
        inserts = [
            call for call in repo._execute_mutation_no_return.call_args_list
            if "INSERT INTO trained_models" in call.args[0]
        ]
        assert inserts == []

    def test_guard_queries_by_job_id_before_insert(self, monkeypatch) -> None:
        """A guarda (_execute_one) roda ANTES do INSERT — não necessariamente a
        primeira chamada geral a _execute_one, já que _get_job_tenant_id
        (WS-D1/ADR-0039, resolve o compute_target) também usa _execute_one
        antes disso pra saber o tenant do job. Usa mock_calls (ordem
        cronológica real entre métodos diferentes do mesmo mock) em vez de
        assumir índice fixo."""
        repo, *_ = _run_dispatch(monkeypatch, env={})

        def _is_guard_call(call) -> bool:
            return call[0] == "_execute_one" and "trained_models" in call.args[0]

        def _is_insert_call(call) -> bool:
            return (
                call[0] == "_execute_mutation_no_return"
                and "INSERT INTO trained_models" in call.args[0]
            )

        guard_idx = next(i for i, c in enumerate(repo.mock_calls) if _is_guard_call(c))
        insert_idx = next(i for i, c in enumerate(repo.mock_calls) if _is_insert_call(c))
        assert guard_idx < insert_idx, "guarda deve rodar antes do INSERT"


class TestDispatchVastAiModelPath:
    """_dispatch_vast_ai: r2_key do metrics.json; sem r2_key → tenant REAL + warning."""

    def _run(self, tmp_path, metrics: dict | None, with_onnx: bool = True,
             tenant_id: str | None = _REAL_TENANT):
        out_dir = tmp_path / "vast_out"
        out_dir.mkdir()
        if metrics is not None:
            (out_dir / "metrics.json").write_text(json.dumps(metrics))
        if with_onnx:
            (out_dir / "model.onnx").write_bytes(b"onnx-fake")

        proc = MagicMock(returncode=0, stderr="", stdout="")
        with patch("tempfile.mkdtemp", return_value=str(out_dir)), \
             patch("subprocess.run", return_value=proc), \
             patch.object(training_mod, "_get_job_tenant_id", return_value=tenant_id):
            return training_mod._dispatch_vast_ai(
                _JOB_ID, "rfdetr", epochs=1, imgsz=640, batch=8, update_fn=MagicMock(),
            )

    def test_model_path_uses_r2_key_from_metrics(self, tmp_path) -> None:
        r2_key = f"models/{_REAL_TENANT}/vast/model_20260711.onnx"
        result = self._run(tmp_path, metrics={"map50": 0.7, "r2_key": r2_key})
        assert result["model_path"] == r2_key
        assert result["source"] == "vast_ai"

    def test_without_r2_key_uses_real_job_tenant(self, tmp_path, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger=training_mod.__name__):
            result = self._run(tmp_path, metrics={"map50": 0.7})
        assert result["model_path"] == f"models/{_REAL_TENANT}/vast/{_JOB_ID}.onnx"
        # Nunca o tenant de TESTE hardcoded
        assert "0000000000AA" not in result["model_path"]
        assert "registro parcial" in caplog.text

    def test_without_r2_key_and_unknown_tenant_registers_partially(
        self, tmp_path, caplog,
    ) -> None:
        with caplog.at_level(logging.WARNING, logger=training_mod.__name__):
            result = self._run(tmp_path, metrics={"map50": 0.7}, tenant_id=None)
        assert result["model_path"] == ""
        assert "artefato sem r2_key" in caplog.text

    def test_no_onnx_files_yields_empty_model_path(self, tmp_path) -> None:
        result = self._run(tmp_path, metrics={"map50": 0.7}, with_onnx=False)
        assert result["model_path"] == ""


class TestGetJobTenantId:
    def test_returns_tenant_from_job_row(self) -> None:
        tenant = uuid4()
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "AnnotationRepository") as mock_repo_cls:
            mock_repo_cls.return_value._execute_one.return_value = {"tenant_id": tenant}
            assert training_mod._get_job_tenant_id(_JOB_ID) == str(tenant)

    def test_returns_none_when_job_missing(self) -> None:
        with patch.object(training_mod, "DatabasePool"), \
             patch.object(training_mod, "AnnotationRepository") as mock_repo_cls:
            mock_repo_cls.return_value._execute_one.return_value = None
            assert training_mod._get_job_tenant_id(_JOB_ID) is None

    def test_returns_none_on_db_error(self) -> None:
        with patch.object(training_mod, "DatabasePool") as mock_pool:
            mock_pool.get_instance.side_effect = RuntimeError("db down")
            assert training_mod._get_job_tenant_id(_JOB_ID) is None


class TestGpuEnabledFlag:
    """job_handlers: gpu_enabled deve aceitar a var que o dispatch realmente usa."""

    def _call_handler(self, app):
        from app.api.v1.training.job_handlers import get_current_job_status_handler

        with app.test_request_context("/api/training/jobs/current"), \
             patch(
                 "app.api.v1.training.job_handlers.get_current_user_id",
                 return_value=str(uuid4()),
             ), \
             patch("app.api.v1.training.job_handlers.get_training_service") as mock_svc:
            mock_svc.return_value.get_current_running_job.return_value = None
            response, status = get_current_job_status_handler()
        assert status == 200
        return response.get_json()["data"]

    def _clear_gpu_env(self, monkeypatch) -> None:
        for var in ("VAST_API_KEY", "VAST_AI_API_KEY", "ULTRALYTICS_HUB_API_KEY"):
            monkeypatch.delenv(var, raising=False)

    def test_gpu_enabled_with_vast_api_key(self, app, monkeypatch) -> None:
        """Regressão: VAST_API_KEY (usada pelo dispatch) deve habilitar gpu_enabled."""
        self._clear_gpu_env(monkeypatch)
        monkeypatch.setenv("VAST_API_KEY", "vast-key")
        data = self._call_handler(app)
        assert data["gpu_enabled"] is True

    def test_gpu_enabled_with_legacy_vast_ai_api_key(self, app, monkeypatch) -> None:
        self._clear_gpu_env(monkeypatch)
        monkeypatch.setenv("VAST_AI_API_KEY", "legacy-key")
        data = self._call_handler(app)
        assert data["gpu_enabled"] is True

    def test_gpu_disabled_without_keys(self, app, monkeypatch) -> None:
        self._clear_gpu_env(monkeypatch)
        data = self._call_handler(app)
        assert data["gpu_enabled"] is False
