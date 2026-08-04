"""
Tests: infrastructure/gpu/training_compute.py — abstração TrainingCompute
(WS-D1, ADR-0039).

Cobre:
  - VastAiProvider/LocalProvider: wrappers finos, delegam pros dispatchers
    já existentes (_dispatch_vast_ai/_simulate_training) com os args certos.
  - LocalProvider: validado rodando o corpo REAL de _simulate_training (não
    mockado) — só time.sleep é acelerado, sem dependência externa nenhuma.
  - EdgeProvider: BLOQUEADO-HARDWARE — testado só com mock (EdgeCommandRepository/
    EdgeSiteRepository), nunca contra hardware real. Fail-loud sem tenant_id
    ou sem edge_sites cadastrado.
  - get_training_compute: precedência vast > edge (opt-in por flag + site) > local.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.gpu.training_compute import (
    EdgeProvider,
    LocalProvider,
    VastAiProvider,
    get_training_compute,
)

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_DSV_ID = "11111111-2222-3333-4444-555555555555"
_TENANT_ID = "99999999-8888-7777-6666-555555555555"
_SITE_ID = "22222222-3333-4444-5555-666666666666"


class TestVastAiProvider:
    def test_dispatch_delegates_to_existing_dispatcher(self):
        update_fn = MagicMock()
        fake_result = {"model_path": "x.onnx", "metrics": {}, "source": "vast_ai"}
        with patch(
            "app.infrastructure.queue.tasks.training._dispatch_vast_ai",
            return_value=fake_result,
        ) as mock_dispatch:
            result = VastAiProvider().dispatch(
                _JOB_ID, _DSV_ID, "rfdetr_n", 50, 640, 16, update_fn, tenant_id=_TENANT_ID
            )
        # tenant_id é propagado (task-086): _dispatch_vast_ai precisa dele
        # pra decidir o gate ADR-0047 do fluxo legado Vast+Roboflow.
        mock_dispatch.assert_called_once_with(
            _JOB_ID, "rfdetr_n", 50, 640, 16, update_fn, tenant_id=_TENANT_ID
        )
        assert result == fake_result


class TestLocalProvider:
    def test_dispatch_delegates_to_existing_simulator(self):
        update_fn = MagicMock()
        fake_result = {"model_path": "x.pt", "metrics": {}, "source": "simulated"}
        with patch(
            "app.infrastructure.queue.tasks.training._simulate_training",
            return_value=fake_result,
        ) as mock_sim:
            result = LocalProvider().dispatch(
                _JOB_ID, _DSV_ID, "rfdetr_n", 50, 640, 16, update_fn, tenant_id=_TENANT_ID
            )
        mock_sim.assert_called_once_with(_JOB_ID, "rfdetr_n", 50, update_fn)
        assert result == fake_result

    def test_real_simulate_training_body_runs_end_to_end(self, monkeypatch):
        """Validação real (não mockada) do LocalProvider — só acelera o
        time.sleep, sem tocar rede/GPU/banco. Prova que a abstração não
        quebrou o contrato de retorno do _simulate_training real.

        C1/C2 (task "treino honesto"): _simulate_training recusa rodar sem
        TRAINING_SIMULATION_ENABLED=true (defesa em profundidade) — e o
        artefato nasce marcado: metrics['simulated']=True + filename
        prefixado SIMULATED_.
        """
        import app.infrastructure.queue.tasks.training as training_mod
        monkeypatch.setattr(training_mod.time, "sleep", lambda *_: None)
        monkeypatch.setenv("TRAINING_SIMULATION_ENABLED", "true")

        update_fn = MagicMock()
        result = LocalProvider().dispatch(
            _JOB_ID, _DSV_ID, "rfdetr_n", epochs=4, imgsz=640, batch=16,
            update_fn=update_fn, tenant_id=None,
        )

        assert result["source"] == "simulated"
        assert "mAP50" in result["metrics"]
        assert result["metrics"]["simulated"] is True
        assert result["model_path"] == f"models/{_JOB_ID}/SIMULATED_best.pt"
        # update_fn chamado a cada step (10 steps fixos em _simulate_training)
        assert update_fn.call_count == 10
        # Cada atualização de progresso também carrega o marcador
        for call in update_fn.call_args_list:
            assert call.kwargs["metrics"]["simulated"] is True

    def test_real_simulate_training_refuses_without_flag(self, monkeypatch):
        """Defesa em profundidade: mesmo chamado diretamente (bypassando
        get_training_compute), _simulate_training nunca roda sem o opt-in
        explícito — ADR-0017."""
        import app.infrastructure.queue.tasks.training as training_mod
        monkeypatch.delenv("TRAINING_SIMULATION_ENABLED", raising=False)
        monkeypatch.setattr(training_mod.time, "sleep", lambda *_: None)

        with pytest.raises(RuntimeError, match="TRAINING_SIMULATION_ENABLED"):
            LocalProvider().dispatch(
                _JOB_ID, _DSV_ID, "rfdetr_n", epochs=4, imgsz=640, batch=16,
                update_fn=MagicMock(), tenant_id=None,
            )


class TestEdgeProvider:
    """BLOQUEADO-HARDWARE — mock only, ver issue de validação de hardware."""

    def test_requires_tenant_id(self):
        with pytest.raises(ValueError, match="tenant_id"):
            EdgeProvider().dispatch(
                _JOB_ID, _DSV_ID, "rfdetr_n", 50, 640, 16, MagicMock(), tenant_id=None
            )

    def test_no_edge_sites_raises(self):
        mock_site_repo = MagicMock()
        mock_site_repo.list_sites.return_value = []
        with patch(
            "app.infrastructure.database.repositories.edge_site_repository.EdgeSiteRepository",
            return_value=mock_site_repo,
        ), patch("app.infrastructure.database.connection.DatabasePool"):
            with pytest.raises(RuntimeError, match="edge_sites"):
                EdgeProvider().dispatch(
                    _JOB_ID, _DSV_ID, "rfdetr_n", 50, 640, 16, MagicMock(),
                    tenant_id=_TENANT_ID,
                )

    def test_enqueues_edge_command_and_returns_running_status(self):
        mock_site_repo = MagicMock()
        mock_site_repo.list_sites.return_value = [{"id": _SITE_ID}]
        mock_command_repo = MagicMock()
        update_fn = MagicMock()

        with patch(
            "app.infrastructure.database.repositories.edge_site_repository.EdgeSiteRepository",
            return_value=mock_site_repo,
        ), patch(
            "app.infrastructure.database.repositories.edge_command_repository.EdgeCommandRepository",
            return_value=mock_command_repo,
        ), patch("app.infrastructure.database.connection.DatabasePool"):
            result = EdgeProvider().dispatch(
                _JOB_ID, _DSV_ID, "rfdetr_n", 50, 640, 16, update_fn,
                tenant_id=_TENANT_ID,
            )

        assert result["status"] == "running"
        assert result["source"] == "edge"
        mock_command_repo.create.assert_called_once()
        kwargs = mock_command_repo.create.call_args.kwargs
        assert kwargs["tenant_id"] == _TENANT_ID
        assert kwargs["site_id"] == _SITE_ID
        assert kwargs["command_type"] == "start_training"
        assert kwargs["payload"]["job_id"] == _JOB_ID
        assert kwargs["payload"]["dataset_version_id"] == _DSV_ID
        update_fn.assert_called_once_with("running", progress=0)

    def test_command_enqueue_failure_propagates_fail_loud(self):
        """Diferente de _notify_model_change (best-effort) — aqui, se o
        enqueue falhar, o dispatch NÃO deve fingir que o treino começou."""
        mock_site_repo = MagicMock()
        mock_site_repo.list_sites.return_value = [{"id": _SITE_ID}]
        mock_command_repo = MagicMock()
        mock_command_repo.create.side_effect = RuntimeError("db down")

        with patch(
            "app.infrastructure.database.repositories.edge_site_repository.EdgeSiteRepository",
            return_value=mock_site_repo,
        ), patch(
            "app.infrastructure.database.repositories.edge_command_repository.EdgeCommandRepository",
            return_value=mock_command_repo,
        ), patch("app.infrastructure.database.connection.DatabasePool"):
            with pytest.raises(RuntimeError, match="db down"):
                EdgeProvider().dispatch(
                    _JOB_ID, _DSV_ID, "rfdetr_n", 50, 640, 16, MagicMock(),
                    tenant_id=_TENANT_ID,
                )


class TestGetTrainingCompute:
    def test_vast_key_resolved_returns_vast_provider(self):
        with patch(
            "app.infrastructure.gpu.vast_client.resolve_vast_api_key",
            return_value="a-key",
        ):
            compute = get_training_compute(_TENANT_ID)
        assert isinstance(compute, VastAiProvider)

    def test_no_vast_key_no_tenant_raises_without_simulation_flag(self, monkeypatch):
        """C1/ADR-0017 (task "treino honesto"): sem provedor real e sem o
        opt-in explícito de simulação, get_training_compute FALHA ALTO —
        nunca cai silenciosamente em LocalProvider (era o default antigo,
        terceira aparição da doença do fallback silencioso no projeto)."""
        monkeypatch.delenv("TRAINING_SIMULATION_ENABLED", raising=False)
        with patch(
            "app.infrastructure.gpu.vast_client.resolve_vast_api_key",
            return_value="",
        ), pytest.raises(RuntimeError, match="Nenhum provedor de treino real"):
            get_training_compute(None)

    def test_no_vast_key_returns_local_provider_when_simulation_flag_enabled(
        self, monkeypatch,
    ):
        """Com o opt-in explícito (env inequívoco), LocalProvider volta a
        ser alcançável — mas só assim, nunca por default."""
        monkeypatch.setenv("TRAINING_SIMULATION_ENABLED", "true")
        with patch(
            "app.infrastructure.gpu.vast_client.resolve_vast_api_key",
            return_value="",
        ):
            compute = get_training_compute(None)
        assert isinstance(compute, LocalProvider)

    def test_edge_flag_without_site_raises_without_simulation_flag(self, monkeypatch):
        monkeypatch.delenv("TRAINING_SIMULATION_ENABLED", raising=False)
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_feature_flags.return_value = {
            "training_compute_target": "edge"
        }
        with patch(
            "app.infrastructure.gpu.vast_client.resolve_vast_api_key", return_value=""
        ), patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository",
            return_value=mock_settings_repo,
        ), patch(
            "app.infrastructure.database.repositories.edge_site_repository.EdgeSiteRepository"
        ) as mock_site_repo_cls, patch(
            "app.infrastructure.database.connection.DatabasePool"
        ):
            mock_site_repo_cls.return_value.list_sites.return_value = []
            with pytest.raises(RuntimeError, match="edge_site"):
                get_training_compute(_TENANT_ID)

    def test_edge_flag_with_site_returns_edge_provider(self):
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_feature_flags.return_value = {
            "training_compute_target": "edge"
        }
        with patch(
            "app.infrastructure.gpu.vast_client.resolve_vast_api_key", return_value=""
        ), patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository",
            return_value=mock_settings_repo,
        ), patch(
            "app.infrastructure.database.repositories.edge_site_repository.EdgeSiteRepository"
        ) as mock_site_repo_cls, patch(
            "app.infrastructure.database.connection.DatabasePool"
        ):
            mock_site_repo_cls.return_value.list_sites.return_value = [{"id": _SITE_ID}]
            compute = get_training_compute(_TENANT_ID)
        assert isinstance(compute, EdgeProvider)

    def test_no_edge_flag_raises_without_simulation_flag(self, monkeypatch):
        monkeypatch.delenv("TRAINING_SIMULATION_ENABLED", raising=False)
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_feature_flags.return_value = {}
        with patch(
            "app.infrastructure.gpu.vast_client.resolve_vast_api_key", return_value=""
        ), patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository",
            return_value=mock_settings_repo,
        ), patch("app.infrastructure.database.connection.DatabasePool"), pytest.raises(
            RuntimeError, match="Nenhum provedor de treino real"
        ):
            get_training_compute(_TENANT_ID)

    def test_no_edge_flag_returns_local_provider_when_simulation_flag_enabled(
        self, monkeypatch,
    ):
        monkeypatch.setenv("TRAINING_SIMULATION_ENABLED", "true")
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_feature_flags.return_value = {}
        with patch(
            "app.infrastructure.gpu.vast_client.resolve_vast_api_key", return_value=""
        ), patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository",
            return_value=mock_settings_repo,
        ), patch("app.infrastructure.database.connection.DatabasePool"):
            compute = get_training_compute(_TENANT_ID)
        assert isinstance(compute, LocalProvider)
