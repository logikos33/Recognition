"""
Tests: retention_expiry.py helper functions — _get_tenant_rows,
_get_cameras_for_tenant, _expire_camera_evidence, expire_evidence_by_retention (item-24).

celery is not installed in the api venv; celery_app is replaced with a
transparent fake so expire_evidence_by_retention remains the original callable.
"""
import sys
import types
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# ──────────────────────────────────────────────────────────────────
# Transparent celery setup — must run before retention_expiry is imported.
# Always replace celery_app (even if previously set by another test).
# ──────────────────────────────────────────────────────────────────
class _TransparentCelery:
    def task(self, *args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator


_fake_celery_app = types.ModuleType("app.infrastructure.queue.celery_app")
_fake_celery_app.celery = _TransparentCelery()
sys.modules["app.infrastructure.queue.celery_app"] = _fake_celery_app  # unconditional

for _cn in ("celery", "celery.signals", "celery.app", "celery.app.base"):
    if _cn not in sys.modules:
        sys.modules[_cn] = MagicMock()

# Force fresh import (guard against prior test loading with a non-transparent stub)
for _key in list(sys.modules):
    if "queue.tasks.retention_expiry" in _key:
        del sys.modules[_key]

import app.infrastructure.queue.tasks.retention_expiry as _retention_mod  # noqa: F401

_POOL_PATH = "app.infrastructure.database.connection.DatabasePool"
# Patch _get_storage at module level so expire_evidence_by_retention uses mock
_STORAGE_PATH = "app.infrastructure.queue.tasks.retention_expiry._get_storage"


def _make_conn_ctx(rows=None):
    """Return (mock_pool, mock_cursor) where fetchall() returns rows."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows if rows is not None else []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_conn)
    cm.__exit__ = MagicMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.get_connection.return_value = cm
    return mock_pool, mock_cursor


# ---------------------------------------------------------------------------
# _get_tenant_rows
# ---------------------------------------------------------------------------

class TestGetTenantRows:

    def test_returns_active_tenant_rows(self):
        rows = [{"id": uuid4(), "schema_name": "tenant_a", "effective_retention_days": 30}]
        mock_pool, _ = _make_conn_ctx(rows=rows)

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            from app.infrastructure.queue.tasks.retention_expiry import _get_tenant_rows
            result = _get_tenant_rows()

        assert result == rows

    def test_empty_table_returns_empty_list(self):
        mock_pool, _ = _make_conn_ctx(rows=[])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            from app.infrastructure.queue.tasks.retention_expiry import _get_tenant_rows
            result = _get_tenant_rows()
        assert result == []

    def test_pool_none_raises_runtime_error(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            from app.infrastructure.queue.tasks.retention_expiry import _get_tenant_rows
            with pytest.raises(RuntimeError, match="DatabasePool"):
                _get_tenant_rows()


# ---------------------------------------------------------------------------
# _get_cameras_for_tenant
# ---------------------------------------------------------------------------

class TestGetCamerasForTenant:

    def test_returns_cameras_for_tenant(self):
        rows = [{"id": uuid4(), "effective_days": 7}]
        mock_pool, _ = _make_conn_ctx(rows=rows)

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            from app.infrastructure.queue.tasks.retention_expiry import _get_cameras_for_tenant
            result = _get_cameras_for_tenant(str(uuid4()), 30)

        assert result == rows

    def test_no_cameras_returns_empty_list(self):
        mock_pool, _ = _make_conn_ctx(rows=[])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            from app.infrastructure.queue.tasks.retention_expiry import _get_cameras_for_tenant
            result = _get_cameras_for_tenant(str(uuid4()), 7)
        assert result == []


# ---------------------------------------------------------------------------
# _expire_camera_evidence
# ---------------------------------------------------------------------------

class TestExpireCameraEvidence:

    def _pool_with_alerts(self, rows):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=mock_conn)
        cm.__exit__ = MagicMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.get_connection.return_value = cm
        return mock_pool

    def test_deletes_r2_key_returns_count_one(self):
        r2_key = "evidence/tenant_a/alert_123.jpg"
        rows = [{"id": uuid4(), "evidence_r2_key": r2_key}]
        mock_pool = self._pool_with_alerts(rows)
        mock_storage = MagicMock()

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            from app.infrastructure.queue.tasks.retention_expiry import _expire_camera_evidence
            deleted = _expire_camera_evidence("tenant_a", str(uuid4()), 7, mock_storage)

        assert deleted == 1
        mock_storage.delete.assert_called_once_with(r2_key)

    def test_r2_delete_error_skips_alert_continues_next(self):
        rows = [
            {"id": uuid4(), "evidence_r2_key": "evidence/key1.jpg"},
            {"id": uuid4(), "evidence_r2_key": "evidence/key2.jpg"},
        ]
        mock_pool = self._pool_with_alerts(rows)
        mock_storage = MagicMock()
        mock_storage.delete.side_effect = [Exception("R2 error"), None]

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            from app.infrastructure.queue.tasks.retention_expiry import _expire_camera_evidence
            deleted = _expire_camera_evidence("tenant_a", str(uuid4()), 7, mock_storage)

        assert deleted == 1

    def test_no_alerts_returns_zero_without_storage_call(self):
        mock_pool = self._pool_with_alerts([])
        mock_storage = MagicMock()

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            from app.infrastructure.queue.tasks.retention_expiry import _expire_camera_evidence
            deleted = _expire_camera_evidence("tenant_a", str(uuid4()), 7, mock_storage)

        assert deleted == 0
        mock_storage.delete.assert_not_called()

    def test_alert_with_null_r2_key_skipped(self):
        rows = [{"id": uuid4(), "evidence_r2_key": None}]
        mock_pool = self._pool_with_alerts(rows)
        mock_storage = MagicMock()

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            from app.infrastructure.queue.tasks.retention_expiry import _expire_camera_evidence
            deleted = _expire_camera_evidence("tenant_a", str(uuid4()), 7, mock_storage)

        assert deleted == 0
        mock_storage.delete.assert_not_called()

    def test_multiple_alerts_all_deleted(self):
        rows = [
            {"id": uuid4(), "evidence_r2_key": f"evidence/key{i}.jpg"}
            for i in range(3)
        ]
        mock_pool = self._pool_with_alerts(rows)
        mock_storage = MagicMock()

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            from app.infrastructure.queue.tasks.retention_expiry import _expire_camera_evidence
            deleted = _expire_camera_evidence("tenant_a", str(uuid4()), 7, mock_storage)

        assert deleted == 3
        assert mock_storage.delete.call_count == 3


# ---------------------------------------------------------------------------
# expire_evidence_by_retention (task-level integration)
# ---------------------------------------------------------------------------

class TestExpireEvidenceByRetention:

    def test_no_tenants_returns_without_expiry(self):
        mock_storage = MagicMock()

        with patch(_STORAGE_PATH, return_value=mock_storage), \
             patch("app.infrastructure.queue.tasks.retention_expiry._get_tenant_rows",
                   return_value=[]):
            from app.infrastructure.queue.tasks.retention_expiry import expire_evidence_by_retention
            expire_evidence_by_retention()

    def test_tenant_query_error_returns_early(self):
        mock_storage = MagicMock()

        with patch(_STORAGE_PATH, return_value=mock_storage), \
             patch("app.infrastructure.queue.tasks.retention_expiry._get_tenant_rows",
                   side_effect=Exception("DB down")):
            from app.infrastructure.queue.tasks.retention_expiry import expire_evidence_by_retention
            expire_evidence_by_retention()

    def test_camera_query_error_skips_tenant_continues_next(self):
        tenants = [
            {"id": uuid4(), "schema_name": "s1", "effective_retention_days": 7},
            {"id": uuid4(), "schema_name": "s2", "effective_retention_days": 30},
        ]
        cameras_s2 = [{"id": uuid4(), "effective_days": 30}]
        mock_storage = MagicMock()
        expire_mock = MagicMock(return_value=0)

        # side_effect list: first call raises, second returns cameras
        cameras_side_effects = [Exception("cameras fail"), cameras_s2]

        with patch(_STORAGE_PATH, return_value=mock_storage), \
             patch("app.infrastructure.queue.tasks.retention_expiry._get_tenant_rows",
                   return_value=tenants), \
             patch("app.infrastructure.queue.tasks.retention_expiry._get_cameras_for_tenant",
                   side_effect=cameras_side_effects), \
             patch("app.infrastructure.queue.tasks.retention_expiry._expire_camera_evidence",
                   expire_mock):
            from app.infrastructure.queue.tasks.retention_expiry import expire_evidence_by_retention
            expire_evidence_by_retention()

        expire_mock.assert_called_once()

    def test_runs_expire_for_each_camera(self):
        tenant_id = uuid4()
        tenants = [{"id": tenant_id, "schema_name": "tenant_x", "effective_retention_days": 14}]
        cameras = [
            {"id": uuid4(), "effective_days": 14},
            {"id": uuid4(), "effective_days": 7},
        ]
        mock_storage = MagicMock()
        expire_mock = MagicMock(return_value=5)

        with patch(_STORAGE_PATH, return_value=mock_storage), \
             patch("app.infrastructure.queue.tasks.retention_expiry._get_tenant_rows",
                   return_value=tenants), \
             patch("app.infrastructure.queue.tasks.retention_expiry._get_cameras_for_tenant",
                   return_value=cameras), \
             patch("app.infrastructure.queue.tasks.retention_expiry._expire_camera_evidence",
                   expire_mock):
            from app.infrastructure.queue.tasks.retention_expiry import expire_evidence_by_retention
            expire_evidence_by_retention()

        assert expire_mock.call_count == 2
