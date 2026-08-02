"""
Tests: app._check_redis_segments_config (item 1.6 do mutirão).

Boot-check best-effort: avisa (logger.warning, degraded_config=true) quando
o Redis principal está sem eviction (maxmemory-policy=noeviction ou
maxmemory=0) e SEGMENTS_REDIS_URL não está setada — a combinação que faz um
Redis cheio de segmento de vídeo derrubar o blocklist de JWT revogado
(revoked_jti:*) junto. Nunca deve impedir o boot da API (best-effort).
"""
import logging
from unittest.mock import MagicMock, patch

from app import _check_redis_segments_config


def _logger():
    return logging.getLogger("test_redis_segments_boot_check")


class TestRedisSegmentsBootCheck:
    def test_skips_entirely_when_segments_redis_url_set(self, monkeypatch):
        """Segmentos já isolados — o risco não se aplica, nem tenta CONFIG GET."""
        monkeypatch.setenv("SEGMENTS_REDIS_URL", "redis://segments-host:6379/2")
        with patch("redis.from_url") as mock_from_url:
            _check_redis_segments_config("redis://default:6379/0", _logger())
        mock_from_url.assert_not_called()

    def test_warns_when_noeviction_and_no_segments_url(self, monkeypatch, caplog):
        monkeypatch.delenv("SEGMENTS_REDIS_URL", raising=False)
        mock_redis = MagicMock()
        mock_redis.config_get.side_effect = lambda param: {
            "maxmemory": {"maxmemory": "0"},
            "maxmemory-policy": {"maxmemory-policy": "noeviction"},
        }[param]
        with patch("redis.from_url", return_value=mock_redis), caplog.at_level(logging.WARNING):
            _check_redis_segments_config("redis://default:6379/0", _logger())
        assert any(
            "redis_segments_degraded_config" in r.message and "degraded_config=true" in r.message
            for r in caplog.records
        )

    def test_no_warning_when_eviction_policy_configured(self, monkeypatch, caplog):
        """maxmemory setada com uma policy de eviction real (não noeviction) —
        risco não se aplica, sem warning."""
        monkeypatch.delenv("SEGMENTS_REDIS_URL", raising=False)
        mock_redis = MagicMock()
        mock_redis.config_get.side_effect = lambda param: {
            "maxmemory": {"maxmemory": "104857600"},
            "maxmemory-policy": {"maxmemory-policy": "volatile-ttl"},
        }[param]
        with patch("redis.from_url", return_value=mock_redis), caplog.at_level(logging.WARNING):
            _check_redis_segments_config("redis://default:6379/0", _logger())
        assert not any("redis_segments_degraded_config" in r.message for r in caplog.records)

    def test_config_get_blocked_is_silenced_with_debug_log(self, monkeypatch, caplog):
        """Redis gerenciado pode bloquear CONFIG GET — best-effort, nunca
        propaga exceção nem impede o boot."""
        monkeypatch.delenv("SEGMENTS_REDIS_URL", raising=False)
        mock_redis = MagicMock()
        mock_redis.config_get.side_effect = Exception("ERR unknown command 'CONFIG'")
        with patch("redis.from_url", return_value=mock_redis), caplog.at_level(logging.DEBUG):
            _check_redis_segments_config("redis://default:6379/0", _logger())  # não deve levantar
        assert any("redis_segments_config_check_skipped" in r.message for r in caplog.records)

    def test_connection_error_is_silenced(self, monkeypatch):
        monkeypatch.delenv("SEGMENTS_REDIS_URL", raising=False)
        with patch("redis.from_url", side_effect=ConnectionError("redis down")):
            _check_redis_segments_config("redis://default:6379/0", _logger())  # não deve levantar
