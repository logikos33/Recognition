"""
Tests: domain/services/module_service.py

Covers: factory functions (pool None → RuntimeError), list_tenant_modules
(stats exception caught), tenant_has_module, get_stats (_safe wrapper),
toggle_class (NotFoundError).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.domain.services.module_service import (
    ModuleService,
    _get_alert_repo,
    _get_camera_repo,
    _get_module_repo,
    _get_training_repo,
)

_POOL_PATH = "app.domain.services.module_service.DatabasePool"
_REPO_PATH = "app.domain.services.module_service._get_module_repo"
_CAM_REPO_PATH = "app.domain.services.module_service._get_camera_repo"
_ALERT_REPO_PATH = "app.domain.services.module_service._get_alert_repo"
_TRAINING_REPO_PATH = "app.domain.services.module_service._get_training_repo"


def _mock_training_repo(model=None):
    repo = MagicMock()
    repo.get_active_for_tenant.return_value = model
    return repo


def _mock_alert_repo(count=0):
    repo = MagicMock()
    repo.count_since.return_value = count
    repo.count_in_window.return_value = count
    repo.camera_hours_with_violation.return_value = 0
    repo.violation_hours_by_class.return_value = []
    return repo


class TestFactoryFunctionsPoolNone:

    def test_get_module_repo_raises_when_pool_none(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            with pytest.raises(RuntimeError, match="pool not initialized"):
                _get_module_repo()

    def test_get_camera_repo_raises_when_pool_none(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            with pytest.raises(RuntimeError, match="pool not initialized"):
                _get_camera_repo()

    def test_get_alert_repo_raises_when_pool_none(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            with pytest.raises(RuntimeError, match="pool not initialized"):
                _get_alert_repo()

    def test_get_module_repo_returns_repo_when_pool_ok(self):
        from app.infrastructure.database.repositories.module_repository import ModuleRepository
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = MagicMock()
            repo = _get_module_repo()
        assert isinstance(repo, ModuleRepository)

    def test_get_camera_repo_returns_repo_when_pool_ok(self):
        from app.infrastructure.database.repositories.camera_repository import CameraRepository
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = MagicMock()
            repo = _get_camera_repo()
        assert isinstance(repo, CameraRepository)

    def test_get_alert_repo_returns_repo_when_pool_ok(self):
        from app.infrastructure.database.repositories.alert_repository import AlertRepository
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = MagicMock()
            repo = _get_alert_repo()
        assert isinstance(repo, AlertRepository)

    def test_get_training_repo_raises_when_pool_none(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            with pytest.raises(RuntimeError, match="pool not initialized"):
                _get_training_repo()

    def test_get_training_repo_returns_repo_when_pool_ok(self):
        from app.infrastructure.database.repositories.training_repository import (
            TrainingRepository,
        )
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = MagicMock()
            repo = _get_training_repo()
        assert isinstance(repo, TrainingRepository)


class TestListTenantModules:

    def test_returns_modules_with_stats(self):
        mock_module_repo = MagicMock()
        mock_module_repo.get_by_tenant.return_value = [{"module_code": "epi", "enabled": True}]
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 3
        mock_camera_repo.count_by_module.return_value = 5
        mock_alert_repo = _mock_alert_repo(count=2)

        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_module_repo), \
             patch(_CAM_REPO_PATH, return_value=mock_camera_repo), \
             patch(_ALERT_REPO_PATH, return_value=mock_alert_repo), \
             patch(_TRAINING_REPO_PATH, return_value=_mock_training_repo()):
            result = svc.list_tenant_modules("t-1")

        assert len(result) == 1
        assert result[0]["cameras_count"] == 3
        assert result[0]["alerts_today"] == 2

    def test_stats_exception_caught_returns_zeros(self):
        mock_module_repo = MagicMock()
        mock_module_repo.get_by_tenant.return_value = [{"module_code": "fueling", "enabled": True}]
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_module_repo), \
             patch.object(svc, "get_stats", side_effect=Exception("db error")):
            result = svc.list_tenant_modules("t-1")
        assert result[0]["cameras_count"] == 0
        assert result[0]["alerts_today"] == 0

    def test_empty_modules_returns_empty_list(self):
        mock_module_repo = MagicMock()
        mock_module_repo.get_by_tenant.return_value = []
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_module_repo):
            assert svc.list_tenant_modules("t-1") == []

    def test_multiple_modules_returned(self):
        mock_module_repo = MagicMock()
        mock_module_repo.get_by_tenant.return_value = [
            {"module_code": "epi", "enabled": True},
            {"module_code": "fueling", "enabled": True},
        ]
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 1
        mock_camera_repo.count_by_module.return_value = 2
        mock_alert_repo = _mock_alert_repo(count=0)

        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_module_repo), \
             patch(_CAM_REPO_PATH, return_value=mock_camera_repo), \
             patch(_ALERT_REPO_PATH, return_value=mock_alert_repo), \
             patch(_TRAINING_REPO_PATH, return_value=_mock_training_repo()):
            result = svc.list_tenant_modules("t-1")
        assert len(result) == 2


class TestGetModule:

    def test_returns_module_when_found(self):
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"module_code": "epi"}
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            assert svc.get_module("t-1", "epi")["module_code"] == "epi"

    def test_returns_none_when_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = None
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            assert svc.get_module("t-1", "missing") is None


class TestTenantHasModule:

    def test_returns_true_when_enabled(self):
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": True}
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            assert svc.tenant_has_module("t-1", "epi") is True

    def test_returns_false_when_disabled(self):
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": False}
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            assert svc.tenant_has_module("t-1", "epi") is False

    def test_returns_false_when_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = None
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            assert svc.tenant_has_module("t-1", "missing") is False


class TestGetClasses:

    def test_returns_classes_list(self):
        mock_repo = MagicMock()
        mock_repo.get_classes.return_value = [{"class_id": 0, "name": "helmet"}]
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            result = svc.get_classes("epi")
        assert result[0]["name"] == "helmet"


class TestGetStats:

    _EXPECTED_KEYS = {
        # chaves originais (retro-compatíveis)
        "cameras_active", "cameras_total", "alerts_today", "alerts_week",
        # KPIs BI (WS3)
        "alerts_last_hour", "alerts_prev_hour",
        "active_model_name", "active_model_map50",
        "compliance_rate", "compliance_by_class",
    }

    def _run(self, camera_repo, alert_repo, training_repo=None):
        svc = ModuleService()
        with patch(_CAM_REPO_PATH, return_value=camera_repo), \
             patch(_ALERT_REPO_PATH, return_value=alert_repo), \
             patch(_TRAINING_REPO_PATH, return_value=training_repo or _mock_training_repo()):
            return svc.get_stats("t-1", "epi")

    def test_returns_all_stat_keys(self):
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 2
        mock_camera_repo.count_by_module.return_value = 4
        result = self._run(mock_camera_repo, _mock_alert_repo(count=5))
        assert set(result.keys()) == self._EXPECTED_KEYS

    def test_safe_wrapper_returns_zero_on_camera_exception(self):
        mock_camera_repo = MagicMock()
        # _safe logs fn.__name__ — MagicMock needs __name__ set explicitly
        mock_camera_repo.count_by_status = MagicMock(
            __name__="count_by_status", side_effect=Exception("db error")
        )
        mock_camera_repo.count_by_module.return_value = 0
        result = self._run(mock_camera_repo, _mock_alert_repo(count=0))
        assert result["cameras_active"] == 0

    def test_safe_wrapper_returns_zero_on_alert_exception(self):
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 1
        mock_camera_repo.count_by_module.return_value = 2
        mock_alert_repo = _mock_alert_repo()
        mock_alert_repo.count_since = MagicMock(
            __name__="count_since", side_effect=Exception("timeout")
        )
        result = self._run(mock_camera_repo, mock_alert_repo)
        assert result["alerts_today"] == 0
        assert result["alerts_week"] == 0

    def test_alerts_hour_windows(self):
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 1
        mock_camera_repo.count_by_module.return_value = 1
        mock_alert_repo = _mock_alert_repo()
        mock_alert_repo.count_in_window.side_effect = [7, 3]  # última hora, hora anterior
        result = self._run(mock_camera_repo, mock_alert_repo)
        assert result["alerts_last_hour"] == 7
        assert result["alerts_prev_hour"] == 3

    def test_compliance_none_when_no_active_cameras(self):
        """0 câmeras ativas → compliance_rate None (card mostra '—')."""
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 0
        mock_camera_repo.count_by_module.return_value = 3
        result = self._run(mock_camera_repo, _mock_alert_repo())
        assert result["compliance_rate"] is None
        assert result["compliance_by_class"] == {}

    def test_compliance_proxy_calculation(self):
        """2 câmeras ativas → 48 horas-câmera; 12 com violação → 75.0%."""
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 2
        mock_camera_repo.count_by_module.return_value = 2
        mock_alert_repo = _mock_alert_repo()
        mock_alert_repo.camera_hours_with_violation.return_value = 12
        mock_alert_repo.violation_hours_by_class.return_value = [
            {"class": "no_helmet", "hours": 12},
            {"class": "no_vest", "hours": 24},
        ]
        result = self._run(mock_camera_repo, mock_alert_repo)
        assert result["compliance_rate"] == 75.0
        assert result["compliance_by_class"] == {"no_helmet": 75.0, "no_vest": 50.0}

    def test_compliance_capped_at_zero(self):
        """Horas com violação acima do total → clamp em 0%, nunca negativo."""
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 1
        mock_camera_repo.count_by_module.return_value = 1
        mock_alert_repo = _mock_alert_repo()
        mock_alert_repo.camera_hours_with_violation.return_value = 999
        result = self._run(mock_camera_repo, mock_alert_repo)
        assert result["compliance_rate"] == 0.0

    def test_active_model_fields(self):
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 1
        mock_camera_repo.count_by_module.return_value = 1
        training_repo = _mock_training_repo(
            model={"name": "epi-v3", "map50": 0.87, "is_active": True}
        )
        result = self._run(mock_camera_repo, _mock_alert_repo(), training_repo)
        assert result["active_model_name"] == "epi-v3"
        assert result["active_model_map50"] == 0.87

    def test_active_model_none_when_absent(self):
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 1
        mock_camera_repo.count_by_module.return_value = 1
        result = self._run(mock_camera_repo, _mock_alert_repo(), _mock_training_repo(None))
        assert result["active_model_name"] is None
        assert result["active_model_map50"] is None

    def test_safe_swallows_training_repo_exception(self):
        """Falha isolada no repo de modelos → campos None, nunca 500."""
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 1
        mock_camera_repo.count_by_module.return_value = 1
        training_repo = MagicMock()
        training_repo.get_active_for_tenant = MagicMock(
            __name__="get_active_for_tenant", side_effect=Exception("db down")
        )
        result = self._run(mock_camera_repo, _mock_alert_repo(), training_repo)
        assert result["active_model_name"] is None
        assert result["active_model_map50"] is None
        # demais chaves continuam presentes
        assert result["cameras_active"] == 1


class TestToggleClass:
    """task-073/achado #6: toggle_class agora exige tenant_id + module_code.

    module_classes é catálogo global (sem tenant_id) — o isolamento
    multi-tenant é: tenant precisa ter o módulo habilitado (tenant_has_module)
    E o class_id precisa pertencer a module_code (filtro no repository).
    Qualquer uma das duas falhas → NotFoundError (404), nunca 403.
    """

    def test_returns_result_when_class_found(self):
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": True}
        mock_repo.toggle_class_active.return_value = {"id": "cls-1", "is_active": True}
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            result = svc.toggle_class("t-1", "epi", "cls-1", True)
        assert result["is_active"] is True

    def test_raises_not_found_error_when_class_missing(self):
        from app.core.exceptions import NotFoundError
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": True}
        mock_repo.toggle_class_active.return_value = None
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            with pytest.raises(NotFoundError):
                svc.toggle_class("t-1", "epi", "bad-id", False)

    def test_deactivate_class(self):
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": True}
        mock_repo.toggle_class_active.return_value = {"id": "cls-1", "is_active": False}
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            result = svc.toggle_class("t-1", "epi", "cls-1", False)
        mock_repo.toggle_class_active.assert_called_once_with("epi", "cls-1", False)
        assert result["is_active"] is False

    def test_raises_not_found_when_tenant_module_disabled(self):
        """Tenant sem o módulo habilitado → 404, nem chega a tocar o repo de classes."""
        from app.core.exceptions import NotFoundError
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = None
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            with pytest.raises(NotFoundError):
                svc.toggle_class("tenant-sem-modulo", "fueling", "cls-1", True)
        mock_repo.toggle_class_active.assert_not_called()

    def test_raises_not_found_when_class_belongs_to_other_module(self):
        """Tenant TEM o módulo epi habilitado mas class_id pertence a outro
        module_code (ou outro tenant) — repository retorna None, service
        propaga 404 (nunca vaza a existência da classe alheia)."""
        from app.core.exceptions import NotFoundError
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": True}
        mock_repo.toggle_class_active.return_value = None
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            with pytest.raises(NotFoundError):
                svc.toggle_class("t-1", "epi", "class-de-outro-tenant", True)
