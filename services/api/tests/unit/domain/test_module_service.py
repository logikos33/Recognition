"""
Tests: ModuleService — list, get, has, get_classes, get_stats, toggle_class (item-24).
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.domain.services.module_service import ModuleService


class TestModuleService:

    def setup_method(self):
        self.module_repo = MagicMock()
        self.camera_repo = MagicMock()
        self.alert_repo = MagicMock()
        self.service = ModuleService()

    def _patch_repos(self):
        return (
            patch("app.domain.services.module_service._get_module_repo", return_value=self.module_repo),
            patch("app.domain.services.module_service._get_camera_repo", return_value=self.camera_repo),
            patch("app.domain.services.module_service._get_alert_repo", return_value=self.alert_repo),
        )

    # ------------------------------------------------------------------
    # list_tenant_modules
    # ------------------------------------------------------------------

    def test_list_tenant_modules_returns_modules_with_stats(self):
        tenant_id = str(uuid4())
        self.module_repo.get_by_tenant.return_value = [
            {"module_code": "epi", "enabled": True},
        ]
        self.camera_repo.count_by_status.return_value = 3
        self.camera_repo.count_by_module.return_value = 5
        self.alert_repo.count_since.return_value = 7

        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            result = self.service.list_tenant_modules(tenant_id)

        assert len(result) == 1
        assert result[0]["module_code"] == "epi"
        assert result[0]["cameras_count"] == 3
        assert result[0]["alerts_today"] == 7

    def test_list_tenant_modules_stats_error_returns_zero(self):
        # Use real callables so _safe can access fn.__name__ (MagicMock lacks __name__)
        def _fail(*a, **kw):
            raise Exception("DB error")

        tenant_id = str(uuid4())
        self.module_repo.get_by_tenant.return_value = [
            {"module_code": "quality", "enabled": True},
        ]
        self.camera_repo.count_by_status = _fail
        self.camera_repo.count_by_module = _fail
        self.alert_repo.count_since = _fail

        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            result = self.service.list_tenant_modules(tenant_id)

        assert result[0]["cameras_count"] == 0
        assert result[0]["alerts_today"] == 0

    def test_list_tenant_modules_empty(self):
        self.module_repo.get_by_tenant.return_value = []
        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            result = self.service.list_tenant_modules(str(uuid4()))
        assert result == []

    # ------------------------------------------------------------------
    # get_module
    # ------------------------------------------------------------------

    def test_get_module_returns_module(self):
        tenant_id = str(uuid4())
        expected = {"module_code": "epi", "enabled": True}
        self.module_repo.get_tenant_module.return_value = expected

        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            result = self.service.get_module(tenant_id, "epi")
        assert result == expected

    def test_get_module_returns_none_when_not_found(self):
        self.module_repo.get_tenant_module.return_value = None
        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            result = self.service.get_module(str(uuid4()), "missing")
        assert result is None

    # ------------------------------------------------------------------
    # tenant_has_module
    # ------------------------------------------------------------------

    def test_tenant_has_module_true_when_enabled(self):
        self.module_repo.get_tenant_module.return_value = {"enabled": True}
        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            assert self.service.tenant_has_module("t1", "epi") is True

    def test_tenant_has_module_false_when_disabled(self):
        self.module_repo.get_tenant_module.return_value = {"enabled": False}
        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            assert self.service.tenant_has_module("t1", "epi") is False

    def test_tenant_has_module_false_when_not_found(self):
        self.module_repo.get_tenant_module.return_value = None
        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            assert self.service.tenant_has_module("t1", "epi") is False

    # ------------------------------------------------------------------
    # get_classes
    # ------------------------------------------------------------------

    def test_get_classes_delegates_to_repo(self):
        classes = [{"name": "helmet", "color": "#22c55e"}]
        self.module_repo.get_classes.return_value = classes
        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            result = self.service.get_classes("epi")
        assert result == classes

    # ------------------------------------------------------------------
    # get_stats
    # ------------------------------------------------------------------

    def test_get_stats_returns_all_counts(self):
        self.camera_repo.count_by_status.return_value = 4
        self.camera_repo.count_by_module.return_value = 6
        self.alert_repo.count_since.return_value = 10

        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            result = self.service.get_stats("tenant-1", "epi")

        assert result["cameras_active"] == 4
        assert result["cameras_total"] == 6
        assert result["alerts_today"] == 10
        assert result["alerts_week"] == 10

    def test_get_stats_safe_on_error(self):
        def _fail(*a, **kw):
            raise Exception("fail")

        self.camera_repo.count_by_status = _fail
        self.camera_repo.count_by_module = _fail
        self.alert_repo.count_since = _fail

        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            result = self.service.get_stats("tenant-1", "epi")

        assert result["cameras_active"] == 0
        assert result["alerts_today"] == 0

    # ------------------------------------------------------------------
    # toggle_class
    # ------------------------------------------------------------------

    def test_toggle_class_success(self):
        expected = {"id": "cls-1", "is_active": False}
        self.module_repo.toggle_class_active.return_value = expected

        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            result = self.service.toggle_class("cls-1", False)
        assert result["is_active"] is False

    def test_toggle_class_not_found_raises(self):
        self.module_repo.toggle_class_active.return_value = None

        p1, p2, p3 = self._patch_repos()
        with p1, p2, p3:
            with pytest.raises(NotFoundError):
                self.service.toggle_class("missing-cls", True)
