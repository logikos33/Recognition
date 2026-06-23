"""
Tests: core/quality_video_security.py

Covers: _extract_tenant_from_key, _check_rate_limit (Redis ok/fail/exceeded),
_log_access (pool None / DB exception / success), generate_quality_view_url
(invalid prefix, tenant mismatch, ttl cap, presign error, success),
verify_andon_access (private IPs, external override, invalid IP).
"""
import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.core.quality_video_security import (
    MAX_VIDEO_URL_TTL,
    RATE_LIMIT_MAX,
    RateLimitError,
    SecurityError,
    _check_rate_limit,
    _extract_tenant_from_key,
    _log_access,
    generate_quality_view_url,
    verify_andon_access,
)

_POOL_PATH = "app.infrastructure.database.connection.DatabasePool"


# ---------------------------------------------------------------------------
# _extract_tenant_from_key
# ---------------------------------------------------------------------------

class TestExtractTenantFromKey:

    def test_extracts_tenant_from_valid_key(self):
        assert _extract_tenant_from_key("quality-clips/rvb/cam-123/file.mp4") == "rvb"

    def test_extracts_tenant_from_recordings(self):
        assert _extract_tenant_from_key("quality-recordings/acme/session.mp4") == "acme"

    def test_returns_none_when_no_slash(self):
        assert _extract_tenant_from_key("nopath") is None

    def test_returns_second_segment(self):
        assert _extract_tenant_from_key("prefix/mytenant/rest") == "mytenant"

    def test_returns_none_for_empty_string(self):
        assert _extract_tenant_from_key("") is None


# ---------------------------------------------------------------------------
# _check_rate_limit
# ---------------------------------------------------------------------------

class TestCheckRateLimit:

    def test_allows_when_under_limit(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        with patch("app.core.quality_video_security.os.environ.get", return_value="redis://localhost:6379/0"), \
             patch("redis.from_url", return_value=mock_redis):
            _check_rate_limit("user-1")  # should not raise
        mock_redis.expire.assert_called_once()

    def test_raises_rate_limit_error_when_exceeded(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = RATE_LIMIT_MAX + 1
        with patch("app.core.quality_video_security.os.environ.get", return_value="redis://localhost:6379/0"), \
             patch("redis.from_url", return_value=mock_redis):
            with pytest.raises(RateLimitError):
                _check_rate_limit("user-exceeded")

    def test_does_not_set_expire_after_first_increment(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 5  # not the first increment
        with patch("app.core.quality_video_security.os.environ.get", return_value="redis://localhost:6379/0"), \
             patch("redis.from_url", return_value=mock_redis):
            _check_rate_limit("user-2")
        mock_redis.expire.assert_not_called()

    def test_redis_exception_does_not_block_access(self):
        with patch("redis.from_url", side_effect=Exception("redis down")):
            _check_rate_limit("user-3")  # should not raise

    def test_at_exactly_limit_does_not_raise(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = RATE_LIMIT_MAX
        with patch("app.core.quality_video_security.os.environ.get", return_value="redis://localhost:6379/0"), \
             patch("redis.from_url", return_value=mock_redis):
            _check_rate_limit("user-at-limit")  # exactly at limit, should not raise


# ---------------------------------------------------------------------------
# _log_access
# ---------------------------------------------------------------------------

class TestLogAccess:

    def test_pool_none_returns_silently(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            _log_access("u-1", "rvb", "clip", "clip-123", "192.168.1.1")

    def test_db_exception_silenced(self):
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("db crash")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            _log_access("u-1", "rvb", "clip", "clip-123", "10.0.0.1")

    def test_inserts_access_log_row(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        @contextmanager
        def _conn_ctx():
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            _log_access("u-1", "rvb", "recording", "rec-456", "192.168.1.5")

        mock_cursor.execute.assert_called_once()
        params = mock_cursor.execute.call_args[0][1]
        assert "u-1" in params
        assert "rvb" in params
        assert "rec-456" in params

    def test_null_ip_passed_as_none(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        @contextmanager
        def _conn_ctx():
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            _log_access("u-1", "acme", "clip", "c-1", None)

        params = mock_cursor.execute.call_args[0][1]
        assert params[4] is None


# ---------------------------------------------------------------------------
# generate_quality_view_url
# ---------------------------------------------------------------------------

_R2_PATH = "app.infrastructure.storage.r2_storage.R2Storage"
_RATE_LIMIT_PATH = "app.core.quality_video_security._check_rate_limit"
_LOG_ACCESS_PATH = "app.core.quality_video_security._log_access"


class TestGenerateQualityViewUrl:

    def _call(self, r2_key="quality-clips/rvb/cam/file.mp4", tenant_schema="rvb",
               user_id="u-1", resource_type="clip", resource_id="c-1",
               ttl=900, ip_address=None):
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.return_value = "https://r2.example.com/signed"
        with patch(_RATE_LIMIT_PATH), \
             patch(_LOG_ACCESS_PATH), \
             patch(_R2_PATH) as r2_cls:
            r2_cls.get_instance.return_value = mock_storage
            return generate_quality_view_url(
                r2_key, tenant_schema, user_id, resource_type, resource_id, ttl, ip_address
            )

    def test_raises_security_error_for_invalid_prefix(self):
        with pytest.raises(SecurityError, match="fora do módulo"):
            generate_quality_view_url(
                "uploads/rvb/file.mp4", "rvb", "u-1", "clip", "c-1"
            )

    def test_raises_security_error_for_tenant_mismatch(self):
        with pytest.raises(SecurityError, match="outro tenant"):
            generate_quality_view_url(
                "quality-clips/evil/file.mp4", "rvb", "u-1", "clip", "c-1"
            )

    def test_ttl_capped_at_max(self):
        result = self._call(ttl=9999)
        assert result["expires_in"] == MAX_VIDEO_URL_TTL

    def test_ttl_below_max_preserved(self):
        result = self._call(ttl=300)
        assert result["expires_in"] == 300

    def test_returns_url_and_expires_in(self):
        result = self._call()
        assert "url" in result
        assert result["url"] == "https://r2.example.com/signed"
        assert "expires_in" in result

    def test_presign_error_propagated(self):
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.side_effect = Exception("S3 error")
        with patch(_RATE_LIMIT_PATH), \
             patch(_LOG_ACCESS_PATH), \
             patch(_R2_PATH) as r2_cls:
            r2_cls.get_instance.return_value = mock_storage
            with pytest.raises(Exception, match="S3 error"):
                generate_quality_view_url(
                    "quality-clips/rvb/f.mp4", "rvb", "u-1", "clip", "c-1"
                )

    def test_all_valid_quality_prefixes_accepted(self):
        prefixes = [
            "quality-recordings/rvb/file.mp4",
            "quality-clips/rvb/file.mp4",
            "quality-frames/rvb/frame.jpg",
            "quality-models/rvb/model.pt",
            "quality-snapshots/rvb/snap.jpg",
        ]
        for key in prefixes:
            result = self._call(r2_key=key, tenant_schema="rvb")
            assert result["url"] == "https://r2.example.com/signed"

    def test_rate_limit_error_propagated(self):
        with patch(_RATE_LIMIT_PATH, side_effect=RateLimitError("exceeded")), \
             patch(_LOG_ACCESS_PATH):
            with pytest.raises(RateLimitError):
                generate_quality_view_url(
                    "quality-clips/rvb/f.mp4", "rvb", "u-1", "clip", "c-1"
                )

    def test_log_access_called(self):
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.return_value = "https://url"
        with patch(_RATE_LIMIT_PATH), \
             patch(_LOG_ACCESS_PATH) as log_mock, \
             patch(_R2_PATH) as r2_cls:
            r2_cls.get_instance.return_value = mock_storage
            generate_quality_view_url(
                "quality-clips/rvb/f.mp4", "rvb", "u-1", "clip", "c-1", ip_address="10.0.0.1"
            )
        log_mock.assert_called_once_with("u-1", "rvb", "clip", "c-1", "10.0.0.1")


# ---------------------------------------------------------------------------
# verify_andon_access
# ---------------------------------------------------------------------------

class TestVerifyAndonAccess:

    def test_private_ip_10_allowed(self):
        assert verify_andon_access("10.0.0.5") is True

    def test_private_ip_192_168_allowed(self):
        assert verify_andon_access("192.168.1.100") is True

    def test_private_ip_172_16_allowed(self):
        assert verify_andon_access("172.16.5.10") is True

    def test_loopback_allowed(self):
        assert verify_andon_access("127.0.0.1") is True

    def test_public_ip_rejected(self):
        assert verify_andon_access("8.8.8.8") is False

    def test_empty_string_rejected(self):
        assert verify_andon_access("") is False

    def test_invalid_ip_rejected(self):
        assert verify_andon_access("not-an-ip") is False

    def test_andon_allow_external_overrides(self, monkeypatch):
        monkeypatch.setenv("ANDON_ALLOW_EXTERNAL", "true")
        assert verify_andon_access("8.8.8.8") is True

    def test_andon_allow_external_false_still_blocks(self, monkeypatch):
        monkeypatch.setenv("ANDON_ALLOW_EXTERNAL", "false")
        assert verify_andon_access("1.2.3.4") is False

    def test_none_rejected(self):
        assert verify_andon_access(None) is False
