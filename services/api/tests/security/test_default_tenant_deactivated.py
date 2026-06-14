"""
Security tests — ADR-0017 Default Tenant Deactivation.

Verifica que migration 046 está estruturada corretamente e que
a whitelist de schemas exclui 'public'.
"""
import re

import pytest


class TestSchemaWhitelistExcludesPublic:
    """get_schema_whitelist() não deve incluir 'public' como schema de tenant válido."""

    def test_whitelist_excludes_public_with_mocked_pool(self):
        from unittest.mock import MagicMock, patch
        from app.core.tenant import get_schema_whitelist

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [("rvb",), ("admin",)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.get_connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.get_connection.return_value.__exit__ = MagicMock(return_value=False)

        import app.core.tenant as tenant_module
        with patch.object(tenant_module, "_schema_cache", {"schemas": None, "ts": 0}):
            with patch("app.infrastructure.database.connection.DatabasePool") as mock_db_cls:
                mock_db_cls.get_instance.return_value = mock_pool
                schemas = get_schema_whitelist()

        assert "public" not in schemas
        assert "rvb" in schemas
        assert "admin" in schemas

    def test_whitelist_fallback_when_pool_none_is_empty(self):
        """Pool indisponível → fail-closed: set() vazio, nunca {'public'}."""
        from unittest.mock import patch
        from app.core.tenant import get_schema_whitelist

        import app.core.tenant as tenant_module
        with patch.object(tenant_module, "_schema_cache", {"schemas": None, "ts": 0}):
            with patch("app.infrastructure.database.connection.DatabasePool") as mock_db_cls:
                mock_db_cls.get_instance.return_value = None
                schemas = get_schema_whitelist()

        assert "public" not in schemas
        assert schemas == set()


class TestMigration046Structure:
    """Verifica estrutura e idempotência do arquivo de migration 046."""

    @pytest.fixture
    def migration_sql(self):
        import os
        path = os.path.join(
            os.path.dirname(__file__),
            "../../../../infra/migrations/046_deactivate_default_tenant.sql",
        )
        with open(os.path.abspath(path)) as f:
            return f.read()

    def test_migration_targets_correct_tenant_id(self, migration_sql):
        assert "00000000-0000-0000-0000-000000000001" in migration_sql

    def test_migration_deletes_alerts(self, migration_sql):
        assert re.search(r"DELETE FROM public\.alerts", migration_sql)

    def test_migration_deletes_cameras(self, migration_sql):
        assert re.search(r"DELETE FROM public\.cameras", migration_sql)

    def test_migration_deactivates_tenant(self, migration_sql):
        assert re.search(r"UPDATE public\.tenants\s+SET is_active\s*=\s*false", migration_sql)

    def test_migration_uses_do_block_for_idempotency(self, migration_sql):
        assert "DO $$" in migration_sql

    def test_migration_scopes_to_public_schema(self, migration_sql):
        # All DML targets public.* explicitly — no schema-less table references
        dml_lines = [l for l in migration_sql.splitlines() if re.match(r"\s+(DELETE|UPDATE)", l)]
        for line in dml_lines:
            assert "public." in line, f"DML sem schema explícito: {line}"
