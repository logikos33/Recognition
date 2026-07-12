"""
Tests: pre_annotation/ — backend plugável (WS-B4, OFF por padrão).

Cobre:
- factory.get_pre_annotation_backend: flag desligada por padrão (env),
  tenant pode ligar via feature_flags, nome de backend desconhecido → None
- DinoSamHttpBackend.predict_and_store: HTTP real (mockado), erro de rede/
  resposta malformada propaga
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests

from app.domain.services.pre_annotation.dino_sam_backend import DinoSamHttpBackend
from app.domain.services.pre_annotation.factory import get_pre_annotation_backend

_TENANT_ID = str(uuid4())


class TestGetPreAnnotationBackend:
    def test_disabled_by_default_returns_none(self, monkeypatch):
        monkeypatch.delenv("PRE_ANNOTATION_ENABLED", raising=False)
        with patch(
            "app.domain.services.pre_annotation.factory._get_feature_flags",
            return_value={},
        ):
            assert get_pre_annotation_backend(_TENANT_ID) is None

    def test_env_enabled_returns_dino_sam_backend(self, monkeypatch):
        monkeypatch.setenv("PRE_ANNOTATION_ENABLED", "true")
        with patch(
            "app.domain.services.pre_annotation.factory._get_feature_flags",
            return_value={},
        ):
            backend = get_pre_annotation_backend(_TENANT_ID)
        assert isinstance(backend, DinoSamHttpBackend)

    def test_tenant_flag_overrides_env_to_disable(self, monkeypatch):
        monkeypatch.setenv("PRE_ANNOTATION_ENABLED", "true")
        with patch(
            "app.domain.services.pre_annotation.factory._get_feature_flags",
            return_value={"pre_annotation_enabled": False},
        ):
            assert get_pre_annotation_backend(_TENANT_ID) is None

    def test_tenant_flag_overrides_env_to_enable(self, monkeypatch):
        monkeypatch.setenv("PRE_ANNOTATION_ENABLED", "false")
        with patch(
            "app.domain.services.pre_annotation.factory._get_feature_flags",
            return_value={"pre_annotation_enabled": True},
        ):
            backend = get_pre_annotation_backend(_TENANT_ID)
        assert isinstance(backend, DinoSamHttpBackend)

    def test_unknown_backend_name_returns_none(self, monkeypatch):
        monkeypatch.setenv("PRE_ANNOTATION_ENABLED", "true")
        with patch(
            "app.domain.services.pre_annotation.factory._get_feature_flags",
            return_value={"pre_annotation_backend": "does-not-exist"},
        ):
            assert get_pre_annotation_backend(_TENANT_ID) is None

    def test_get_feature_flags_is_fail_soft_when_pool_missing(self):
        """_get_feature_flags real (não mockada) nunca propaga — sem pool
        inicializado, retorna {} e o factory cai no fallback env."""
        from app.domain.services.pre_annotation.factory import _get_feature_flags
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=None,
        ):
            assert _get_feature_flags(_TENANT_ID) == {}


class TestDinoSamHttpBackend:
    def test_predict_and_store_returns_annotations_count(self):
        backend = DinoSamHttpBackend(base_url="http://pre-annotation-service:8080")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "success": True,
            "data": {"frame_id": "x", "status": "success", "annotations_count": 4},
        }
        with patch("requests.post", return_value=mock_resp) as mock_post:
            count = backend.predict_and_store("frame-123", "epi")
        assert count == 4
        mock_post.assert_called_once()
        url = mock_post.call_args.args[0]
        assert url == "http://pre-annotation-service:8080/api/v1/pre-annotate/frame-123"

    def test_predict_and_store_raises_on_backend_error(self):
        backend = DinoSamHttpBackend(base_url="http://pre-annotation-service:8080")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": False, "error": "frame not found"}
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="frame not found"):
                backend.predict_and_store("frame-123", "epi")

    def test_predict_and_store_propagates_network_error(self):
        backend = DinoSamHttpBackend(base_url="http://pre-annotation-service:8080")
        with patch("requests.post", side_effect=requests.ConnectionError("unreachable")):
            with pytest.raises(requests.ConnectionError):
                backend.predict_and_store("frame-123", "epi")

    def test_base_url_from_env_when_not_given(self, monkeypatch):
        monkeypatch.setenv("PRE_ANNOTATION_URL", "http://custom-host:9999")
        backend = DinoSamHttpBackend()
        assert backend._base_url == "http://custom-host:9999"
