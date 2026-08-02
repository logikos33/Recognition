"""
Tests: core/segments_redis.py (item 1.6 do mutirão).

Cobre: SEGMENTS_REDIS_URL setada -> client aponta pra ela; não setada ->
mesmo REDIS_URL padrão (client "default", comportamento inalterado);
variante binária (sem decode_responses) para os segmentos .ts.
"""
from unittest.mock import patch

from app.core.segments_redis import (
    get_segments_redis,
    get_segments_redis_binary,
    segments_redis_url,
)


class TestSegmentsRedisUrl:
    def test_uses_segments_redis_url_when_set(self, monkeypatch):
        monkeypatch.setenv("SEGMENTS_REDIS_URL", "redis://segments-host:6379/2")
        monkeypatch.setenv("REDIS_URL", "redis://default-host:6379/0")
        assert segments_redis_url() == "redis://segments-host:6379/2"

    def test_falls_back_to_redis_url_when_unset(self, monkeypatch):
        monkeypatch.delenv("SEGMENTS_REDIS_URL", raising=False)
        monkeypatch.setenv("REDIS_URL", "redis://default-host:6379/0")
        assert segments_redis_url() == "redis://default-host:6379/0"

    def test_falls_back_to_localhost_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("SEGMENTS_REDIS_URL", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        assert segments_redis_url() == "redis://localhost:6379"

    def test_empty_segments_redis_url_falls_back(self, monkeypatch):
        """Env setada mas vazia não deve "vencer" um REDIS_URL válido."""
        monkeypatch.setenv("SEGMENTS_REDIS_URL", "")
        monkeypatch.setenv("REDIS_URL", "redis://default-host:6379/0")
        assert segments_redis_url() == "redis://default-host:6379/0"


class TestGetSegmentsRedis:
    def test_client_targets_segments_url_when_set(self, monkeypatch):
        monkeypatch.setenv("SEGMENTS_REDIS_URL", "redis://segments-host:6379/2")
        with patch("redis.from_url") as mock_from_url:
            get_segments_redis()
        mock_from_url.assert_called_once_with(
            "redis://segments-host:6379/2", socket_timeout=5, decode_responses=True
        )

    def test_client_targets_default_redis_url_when_unset(self, monkeypatch):
        """Sem SEGMENTS_REDIS_URL: MESMO REDIS_URL/timeout que o resto do
        sistema usa — comportamento atual inalterado (zero mudança
        silenciosa de default)."""
        monkeypatch.delenv("SEGMENTS_REDIS_URL", raising=False)
        monkeypatch.setenv("REDIS_URL", "redis://default-host:6379/0")
        with patch("redis.from_url") as mock_from_url:
            get_segments_redis()
        mock_from_url.assert_called_once_with(
            "redis://default-host:6379/0", socket_timeout=5, decode_responses=True
        )


class TestGetSegmentsRedisBinary:
    def test_binary_variant_has_no_decode_responses(self, monkeypatch):
        monkeypatch.setenv("SEGMENTS_REDIS_URL", "redis://segments-host:6379/2")
        with patch("redis.from_url") as mock_from_url:
            get_segments_redis_binary()
        mock_from_url.assert_called_once_with(
            "redis://segments-host:6379/2", socket_timeout=5
        )

    def test_binary_variant_falls_back_to_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("SEGMENTS_REDIS_URL", raising=False)
        monkeypatch.setenv("REDIS_URL", "redis://default-host:6379/0")
        with patch("redis.from_url") as mock_from_url:
            get_segments_redis_binary()
        mock_from_url.assert_called_once_with(
            "redis://default-host:6379/0", socket_timeout=5
        )
