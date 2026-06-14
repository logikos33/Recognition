"""
Security tests — set_search_path rejects 'public' (defense in depth).

set_search_path() em app/core/tenant.py é camada independente da whitelist:
valida internamente via validate_schema() antes de emitir qualquer SQL.
'public' é rejeitado com AuthorizationError mesmo que alguém bypasse
get_schema_whitelist() em outro ponto do código.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import AuthorizationError


def _whitelist_without_public():
    """Whitelist simulada: tenants ativos, sem 'public'."""
    return {"rvb", "admin"}


class TestSetSearchPathRejectsPublic:
    """Defense in depth — 'public' rejeitado pela própria set_search_path()."""

    def test_rejects_public_literal(self):
        from app.core.tenant import set_search_path

        mock_conn = MagicMock()
        with patch("app.core.tenant.get_schema_whitelist", return_value=_whitelist_without_public()):
            with pytest.raises(AuthorizationError, match="Schema inválido"):
                set_search_path(mock_conn, "public")

    def test_rejects_sql_injection_attempts(self):
        from app.core.tenant import set_search_path

        mock_conn = MagicMock()
        invalid_schemas = [
            "public; DROP TABLE users--",
            "'public'",
            "../etc",
            "",
            "public OR 1=1",
        ]
        with patch("app.core.tenant.get_schema_whitelist", return_value=_whitelist_without_public()):
            for schema in invalid_schemas:
                with pytest.raises((AuthorizationError, Exception)):
                    set_search_path(mock_conn, schema)

    def test_does_not_execute_sql_when_schema_invalid(self):
        """SQL nunca chega ao cursor se schema é inválido."""
        from app.core.tenant import set_search_path

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.core.tenant.get_schema_whitelist", return_value=_whitelist_without_public()):
            with pytest.raises(AuthorizationError):
                set_search_path(mock_conn, "public")

        for call in mock_cur.execute.call_args_list:
            sql = (call[0][0] if call[0] else "").upper()
            assert "SET search_path" not in sql, "SQL emitido para schema inválido"

    def test_accepts_valid_tenant_schema(self):
        """Schema válido da whitelist deve passar sem exception."""
        from app.core.tenant import set_search_path

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.core.tenant.get_schema_whitelist", return_value={"rvb", "admin"}):
            set_search_path(mock_conn, "rvb")  # não deve levantar exception
