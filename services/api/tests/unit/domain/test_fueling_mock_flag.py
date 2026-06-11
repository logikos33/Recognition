"""Tests: feature flag fueling_use_mock (CD-03 — mata o mock).

Resolução da flag em _use_mock_data():
  1. tenants.feature_flags['fueling_use_mock'] (por tenant)
  2. env FUELING_USE_MOCK (fallback global, default true para a demo)
"""
from unittest.mock import MagicMock
from uuid import uuid4

from app.api.v1.fueling import routes as fueling_routes


def _patch_flags(monkeypatch, flags=None, raises=False):
    """Substitui TenantSettingsRepository e _get_pool no módulo de rotas."""
    monkeypatch.setattr(fueling_routes, "_get_pool", MagicMock())
    repo_cls = MagicMock()
    if raises:
        repo_cls.return_value.get_feature_flags.side_effect = RuntimeError("db down")
    else:
        repo_cls.return_value.get_feature_flags.return_value = flags or {}
    monkeypatch.setattr(fueling_routes, "TenantSettingsRepository", repo_cls)
    return repo_cls


class TestUseMockData:

    def test_tenant_flag_off_disables_mock(self, monkeypatch):
        _patch_flags(monkeypatch, {"fueling_use_mock": False})
        monkeypatch.setenv("FUELING_USE_MOCK", "true")
        assert fueling_routes._use_mock_data(uuid4()) is False

    def test_tenant_flag_on_enables_mock(self, monkeypatch):
        _patch_flags(monkeypatch, {"fueling_use_mock": True})
        monkeypatch.setenv("FUELING_USE_MOCK", "false")
        assert fueling_routes._use_mock_data(uuid4()) is True

    def test_missing_tenant_flag_falls_back_to_env(self, monkeypatch):
        _patch_flags(monkeypatch, {})
        monkeypatch.setenv("FUELING_USE_MOCK", "false")
        assert fueling_routes._use_mock_data(uuid4()) is False

    def test_default_is_mock_on_for_demo(self, monkeypatch):
        """Sem flag de tenant e sem env → default true (não quebra a demo)."""
        _patch_flags(monkeypatch, {})
        monkeypatch.delenv("FUELING_USE_MOCK", raising=False)
        assert fueling_routes._use_mock_data(uuid4()) is True

    def test_db_error_falls_back_to_env(self, monkeypatch):
        _patch_flags(monkeypatch, raises=True)
        monkeypatch.setenv("FUELING_USE_MOCK", "false")
        assert fueling_routes._use_mock_data(uuid4()) is False

    def test_env_truthy_variants(self, monkeypatch):
        _patch_flags(monkeypatch, {})
        for value in ("1", "true", "TRUE", "yes", "on"):
            monkeypatch.setenv("FUELING_USE_MOCK", value)
            assert fueling_routes._use_mock_data(uuid4()) is True
        for value in ("0", "false", "no", "off"):
            monkeypatch.setenv("FUELING_USE_MOCK", value)
            assert fueling_routes._use_mock_data(uuid4()) is False

    def test_other_tenant_flags_dont_affect_mock(self, monkeypatch):
        _patch_flags(monkeypatch, {"some_other_flag": False})
        monkeypatch.delenv("FUELING_USE_MOCK", raising=False)
        assert fueling_routes._use_mock_data(uuid4()) is True
