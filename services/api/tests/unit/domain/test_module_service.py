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
)

_POOL_PATH = "app.domain.services.module_service.DatabasePool"
_REPO_PATH = "app.domain.services.module_service._get_module_repo"
_CAM_REPO_PATH = "app.domain.services.module_service._get_camera_repo"
_ALERT_REPO_PATH = "app.domain.services.module_service._get_alert_repo"


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


class TestListTenantModules:

    def test_returns_modules_with_stats(self):
        mock_module_repo = MagicMock()
        mock_module_repo.get_by_tenant.return_value = [{"module_code": "epi", "enabled": True}]
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 3
        mock_camera_repo.count_by_module.return_value = 5
        mock_alert_repo = MagicMock()
        mock_alert_repo.count_since.return_value = 2

        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_module_repo), \
             patch(_CAM_REPO_PATH, return_value=mock_camera_repo), \
             patch(_ALERT_REPO_PATH, return_value=mock_alert_repo):
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
        mock_alert_repo = MagicMock()
        mock_alert_repo.count_since.return_value = 0

        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_module_repo), \
             patch(_CAM_REPO_PATH, return_value=mock_camera_repo), \
             patch(_ALERT_REPO_PATH, return_value=mock_alert_repo):
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

    def test_returns_all_stat_keys(self):
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 2
        mock_camera_repo.count_by_module.return_value = 4
        mock_alert_repo = MagicMock()
        mock_alert_repo.count_since.return_value = 5

        svc = ModuleService()
        with patch(_CAM_REPO_PATH, return_value=mock_camera_repo), \
             patch(_ALERT_REPO_PATH, return_value=mock_alert_repo):
            result = svc.get_stats("t-1", "epi")

        assert set(result.keys()) == {"cameras_active", "cameras_total", "alerts_today", "alerts_week"}

    def test_safe_wrapper_returns_zero_on_camera_exception(self):
        mock_camera_repo = MagicMock()
        # _safe logs fn.__name__ — MagicMock needs __name__ set explicitly
        mock_camera_repo.count_by_status = MagicMock(
            __name__="count_by_status", side_effect=Exception("db error")
        )
        mock_camera_repo.count_by_module.return_value = 0
        mock_alert_repo = MagicMock()
        mock_alert_repo.count_since.return_value = 0

        svc = ModuleService()
        with patch(_CAM_REPO_PATH, return_value=mock_camera_repo), \
             patch(_ALERT_REPO_PATH, return_value=mock_alert_repo):
            result = svc.get_stats("t-1", "epi")

        assert result["cameras_active"] == 0

    def test_safe_wrapper_returns_zero_on_alert_exception(self):
        mock_camera_repo = MagicMock()
        mock_camera_repo.count_by_status.return_value = 1
        mock_camera_repo.count_by_module.return_value = 2
        mock_alert_repo = MagicMock()
        mock_alert_repo.count_since = MagicMock(
            __name__="count_since", side_effect=Exception("timeout")
        )

        svc = ModuleService()
        with patch(_CAM_REPO_PATH, return_value=mock_camera_repo), \
             patch(_ALERT_REPO_PATH, return_value=mock_alert_repo):
            result = svc.get_stats("t-1", "epi")

        assert result["alerts_today"] == 0
        assert result["alerts_week"] == 0


class TestToggleClass:

    def test_returns_result_when_class_found(self):
        mock_repo = MagicMock()
        mock_repo.toggle_class_active.return_value = {"id": "cls-1", "is_active": True}
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            result = svc.toggle_class("cls-1", True)
        assert result["is_active"] is True

    def test_raises_not_found_error_when_class_missing(self):
        from app.core.exceptions import NotFoundError
        mock_repo = MagicMock()
        mock_repo.toggle_class_active.return_value = None
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            with pytest.raises(NotFoundError):
                svc.toggle_class("bad-id", False)

    def test_deactivate_class(self):
        mock_repo = MagicMock()
        mock_repo.toggle_class_active.return_value = {"id": "cls-1", "is_active": False}
        svc = ModuleService()
        with patch(_REPO_PATH, return_value=mock_repo):
            result = svc.toggle_class("cls-1", False)
        mock_repo.toggle_class_active.assert_called_once_with("cls-1", False)
        assert result["is_active"] is False
