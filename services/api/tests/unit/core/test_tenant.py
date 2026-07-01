"""
Tests: core/tenant.py — get_schema_whitelist, invalidate_schema_cache,
validate_schema, require_superadmin, require_admin, require_permission,
log_audit, log_change, set_search_path.

DatabasePool and JWT are mocked; Flask app context provided via minimal fixture.
"""
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

# Stub flask_jwt_extended before importing tenant.py
_jwt_mock = MagicMock()
sys.modules.setdefault("flask_jwt_extended", _jwt_mock)

from app.core.exceptions import AuthorizationError  # noqa: E402
from app.core.tenant import (                       # noqa: E402
    get_schema_whitelist,
    invalidate_schema_cache,
    log_audit,
    log_change,
    require_admin,
    require_permission,
    require_superadmin,
    set_search_path,
    validate_schema,
)

# DatabasePool is imported lazily inside each function body via
# `from app.infrastructure.database.connection import DatabasePool`.
# Patch at the definition site, not at app.core.tenant (no module attr there).
_POOL_PATH = "app.infrastructure.database.connection.DatabasePool"


def _pool_returning(rows):
    """Build a DatabasePool mock whose cursor.fetchall returns `rows`."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def _conn_ctx():
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool, mock_cursor


# ---------------------------------------------------------------------------
# get_schema_whitelist
# ---------------------------------------------------------------------------

class TestGetSchemaWhitelist:

    def setup_method(self):
        invalidate_schema_cache()

    def test_returns_set_of_schemas(self):
        mock_pool, _ = _pool_returning([("tenant_a",), ("tenant_b",)])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            result = get_schema_whitelist()
        assert result == {"tenant_a", "tenant_b"}

    def test_pool_none_returns_empty_set(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            result = get_schema_whitelist()
        assert result == set()

    def test_db_exception_returns_empty_set(self):
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("DB down")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            result = get_schema_whitelist()
        assert result == set()

    def test_caches_result_on_second_call(self):
        mock_pool, _ = _pool_returning([("s1",)])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            get_schema_whitelist()
            get_schema_whitelist()  # second call — should use cache
        # DB should only be queried once
        assert mock_pool.get_connection.call_count == 1

    def test_invalidate_forces_refresh(self):
        mock_pool, _ = _pool_returning([("s1",)])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            get_schema_whitelist()
            invalidate_schema_cache()
            get_schema_whitelist()
        assert mock_pool.get_connection.call_count == 2


# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------

class TestValidateSchema:

    def setup_method(self):
        invalidate_schema_cache()

    def test_valid_schema_returns_true(self):
        mock_pool, _ = _pool_returning([("my_tenant",)])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            assert validate_schema("my_tenant") is True

    def test_invalid_schema_returns_false(self):
        mock_pool, _ = _pool_returning([("other",)])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            assert validate_schema("unknown") is False


# ---------------------------------------------------------------------------
# require_superadmin
# ---------------------------------------------------------------------------

class TestRequireSuperadmin:

    def _decorate(self, role):
        mock_fn = MagicMock(return_value="ok")
        decorated = require_superadmin(mock_fn)
        with patch("app.core.tenant.verify_jwt_in_request"), \
             patch("app.core.tenant.get_role", return_value=role):
            return decorated(), mock_fn

    def test_superadmin_calls_fn(self):
        result, fn = self._decorate("superadmin")
        fn.assert_called_once()
        assert result == "ok"

    def test_non_superadmin_raises(self):
        decorated = require_superadmin(MagicMock())
        with patch("app.core.tenant.verify_jwt_in_request"), \
             patch("app.core.tenant.get_role", return_value="operator"):
            with pytest.raises(AuthorizationError, match="superadmin"):
                decorated()

    def test_admin_raises(self):
        decorated = require_superadmin(MagicMock())
        with patch("app.core.tenant.verify_jwt_in_request"), \
             patch("app.core.tenant.get_role", return_value="admin"):
            with pytest.raises(AuthorizationError):
                decorated()

    def test_wraps_preserves_name(self):
        def my_view():
            pass
        assert require_superadmin(my_view).__name__ == "my_view"


# ---------------------------------------------------------------------------
# require_admin
# ---------------------------------------------------------------------------

class TestRequireAdmin:

    def test_admin_calls_fn(self):
        mock_fn = MagicMock(return_value="done")
        decorated = require_admin(mock_fn)
        with patch("app.core.tenant.verify_jwt_in_request"), \
             patch("app.core.tenant.get_role", return_value="admin"):
            result = decorated()
        assert result == "done"
        mock_fn.assert_called_once()

    def test_superadmin_calls_fn(self):
        mock_fn = MagicMock(return_value="done")
        decorated = require_admin(mock_fn)
        with patch("app.core.tenant.verify_jwt_in_request"), \
             patch("app.core.tenant.get_role", return_value="superadmin"):
            result = decorated()
        assert result == "done"

    def test_operator_raises(self):
        decorated = require_admin(MagicMock())
        with patch("app.core.tenant.verify_jwt_in_request"), \
             patch("app.core.tenant.get_role", return_value="operator"):
            with pytest.raises(AuthorizationError, match="administradores"):
                decorated()

    def test_wraps_preserves_name(self):
        def my_view():
            pass
        assert require_admin(my_view).__name__ == "my_view"


# ---------------------------------------------------------------------------
# require_permission
# ---------------------------------------------------------------------------

class TestRequirePermission:

    def test_allowed_role_calls_fn(self):
        mock_fn = MagicMock(return_value="yes")
        with patch("app.core.tenant.verify_jwt_in_request"), \
             patch("app.core.tenant.get_role", return_value="annotator"), \
             patch("app.constants.ROLE_PERMISSIONS", {"annotate_frames": ["annotator", "admin"]}):
            result = require_permission("annotate_frames")(mock_fn)()
        assert result == "yes"

    def test_disallowed_role_raises(self):
        mock_fn = MagicMock()
        with patch("app.core.tenant.verify_jwt_in_request"), \
             patch("app.core.tenant.get_role", return_value="viewer"), \
             patch("app.constants.ROLE_PERMISSIONS", {"annotate_frames": ["annotator"]}):
            with pytest.raises(AuthorizationError, match="annotate_frames"):
                require_permission("annotate_frames")(mock_fn)()

    def test_unknown_permission_raises_for_any_role(self):
        mock_fn = MagicMock()
        with patch("app.core.tenant.verify_jwt_in_request"), \
             patch("app.core.tenant.get_role", return_value="superadmin"), \
             patch("app.constants.ROLE_PERMISSIONS", {}):
            with pytest.raises(AuthorizationError):
                require_permission("nonexistent")(mock_fn)()


# ---------------------------------------------------------------------------
# log_audit
# ---------------------------------------------------------------------------

class TestLogAudit:

    def _log(self, **kwargs):
        defaults = dict(
            actor_id="user-1", actor_role="admin", tenant_id="t-1",
            target_type="camera", target_id="cam-1", action="update",
        )
        defaults.update(kwargs)
        log_audit(**defaults)

    def test_pool_none_returns_silently(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            self._log()  # should not raise

    def test_db_exception_silenced(self):
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("crash")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._log()  # should not raise

    def test_action_passed_as_param(self):
        mock_pool, mock_cursor = _pool_returning([])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._log(action="delete")
        params = mock_cursor.execute.call_args[0][1]
        assert "delete" in params

    def test_old_new_value_serialized(self):
        mock_pool, mock_cursor = _pool_returning([])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._log(old_value={"x": 1}, new_value={"x": 2})
        params = mock_cursor.execute.call_args[0][1]
        assert '{"x": 1}' in params
        assert '{"x": 2}' in params

    def test_user_agent_truncated(self):
        mock_pool, mock_cursor = _pool_returning([])
        long_ua = "A" * 600
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._log(user_agent=long_ua)
        params = mock_cursor.execute.call_args[0][1]
        ua_in_params = [p for p in params if isinstance(p, str) and "AAAAA" in p]
        assert any(len(p) <= 500 for p in ua_in_params)


# ---------------------------------------------------------------------------
# log_change
# ---------------------------------------------------------------------------

class TestLogChange:

    def test_pool_none_returns_silently(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            log_change("user-1", "admin", "Test change")  # should not raise

    def test_db_exception_silenced(self):
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("crash")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            log_change("user-1", "admin", "Test")  # should not raise

    def test_title_passed_as_param(self):
        mock_pool, mock_cursor = _pool_returning([])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            log_change("user-1", "admin", "My Title")
        params = mock_cursor.execute.call_args[0][1]
        assert "My Title" in params

    def test_defaults_category_and_importance(self):
        mock_pool, mock_cursor = _pool_returning([])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            log_change("u", "admin", "T")
        params = mock_cursor.execute.call_args[0][1]
        assert "config" in params
        assert "normal" in params


# ---------------------------------------------------------------------------
# set_search_path
# ---------------------------------------------------------------------------

class TestSetSearchPath:

    def setup_method(self):
        invalidate_schema_cache()

    def test_valid_schema_executes_set(self):
        mock_pool, _ = _pool_returning([("my_tenant",)])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            set_search_path(mock_conn, "my_tenant")
        mock_cur.execute.assert_called_once()
        query = mock_cur.execute.call_args[0][0]
        assert "my_tenant" in query
        assert "search_path" in query.lower()

    def test_invalid_schema_raises_authorization_error(self):
        mock_pool, _ = _pool_returning([("other",)])
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            mock_conn = MagicMock()
            with pytest.raises(AuthorizationError, match="inválido"):
                set_search_path(mock_conn, "injected_schema")
