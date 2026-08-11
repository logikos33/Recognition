"""
Tests: infrastructure/gpu/training_compute.py — abstração TrainingCompute
(WS-D1, ADR-0039) + task "treino não pode mentir" (LocalProvider/simulação
deletados; GpuProvider.LOCAL agora é sempre erro alto e legível) + runner
genérico RunPod (substitui Vast.ai — decisão do dono).

Cobre:
  - RunPodProvider: wrapper fino, delega pro dispatcher já existente
    (_dispatch_runpod_train) com os args certos.
  - EdgeProvider: BLOQUEADO-HARDWARE — testado só com mock (EdgeCommandRepository/
    EdgeSiteRepository), nunca contra hardware real. Fail-loud sem tenant_id
    ou sem edge_sites cadastrado.
  - get_training_compute: precedência runpod > edge (opt-in por flag + site) >
    erro alto sempre (nenhuma simulação) — tenant explicitamente configurado
    com training_compute_target='local' recebe mensagem própria ("treino
    local não suportado").
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.gpu.training_compute import (
    EdgeProvider,
    RunPodProvider,
    get_training_compute,
)

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_DSV_ID = "11111111-2222-3333-4444-555555555555"
_TENANT_ID = "99999999-8888-7777-6666-555555555555"
_SITE_ID = "22222222-3333-4444-5555-666666666666"


class TestRunPodProvider:
    def test_dispatch_delegates_to_existing_dispatcher(self):
        update_fn = MagicMock()
        fake_result = {"model_path": "x.onnx", "metrics": {}, "source": "runpod"}
        with patch(
            "app.infrastructure.queue.tasks.training._dispatch_runpod_train",
            return_value=fake_result,
        ) as mock_dispatch:
            result = RunPodProvider().dispatch(
                _JOB_ID, _DSV_ID, "rfdetr_n", 50, 640, 16, update_fn, tenant_id=_TENANT_ID
            )
        # tenant_id é propagado (task-086): _dispatch_runpod_train precisa dele
        # pra decidir o gate ADR-0047 do fluxo de terceiro.
        mock_dispatch.assert_called_once_with(
            _JOB_ID, "rfdetr_n", 50, 640, 16, update_fn, tenant_id=_TENANT_ID
        )
        assert result == fake_result


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
    def test_runpod_key_resolved_returns_runpod_provider(self):
        with patch(
            "app.infrastructure.gpu.runpod_client.resolve_runpod_api_key",
            return_value="a-key",
        ):
            compute = get_training_compute(_TENANT_ID)
        assert isinstance(compute, RunPodProvider)

    def test_no_runpod_key_no_tenant_raises(self):
        """C1/ADR-0017 (task "treino honesto") + task "treino não pode
        mentir": sem provedor real, get_training_compute FALHA ALTO sempre —
        não existe mais nenhum fallback (LocalProvider/simulação foram
        deletados; era o default antigo, terceira aparição da doença do
        fallback silencioso no projeto)."""
        with patch(
            "app.infrastructure.gpu.runpod_client.resolve_runpod_api_key",
            return_value="",
        ), pytest.raises(RuntimeError, match="Nenhum provedor de treino real"):
            get_training_compute(None)

    def test_local_compute_target_raises_clear_message(self):
        """Task "treino não pode mentir": tenant explicitamente configurado
        com training_compute_target='local' recebe uma mensagem PRÓPRIA e
        legível — nunca simula, nunca cai no erro genérico."""
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_feature_flags.return_value = {
            "training_compute_target": "local"
        }
        with patch(
            "app.infrastructure.gpu.runpod_client.resolve_runpod_api_key", return_value="",
        ), patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository",
            return_value=mock_settings_repo,
        ), patch("app.infrastructure.database.connection.DatabasePool"), pytest.raises(
            RuntimeError, match="Treino local não suportado"
        ):
            get_training_compute(_TENANT_ID)

    def test_edge_flag_without_site_raises(self):
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_feature_flags.return_value = {
            "training_compute_target": "edge"
        }
        with patch(
            "app.infrastructure.gpu.runpod_client.resolve_runpod_api_key", return_value="",
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
            "app.infrastructure.gpu.runpod_client.resolve_runpod_api_key", return_value="",
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

    def test_no_edge_flag_raises(self):
        mock_settings_repo = MagicMock()
        mock_settings_repo.get_feature_flags.return_value = {}
        with patch(
            "app.infrastructure.gpu.runpod_client.resolve_runpod_api_key", return_value="",
        ), patch(
            "app.infrastructure.database.repositories.tenant_settings_repository."
            "TenantSettingsRepository",
            return_value=mock_settings_repo,
        ), patch("app.infrastructure.database.connection.DatabasePool"), pytest.raises(
            RuntimeError, match="Nenhum provedor de treino real"
        ):
            get_training_compute(_TENANT_ID)
