"""
Tests: core/auth.py — require_training_role (WS-D, pipeline de treinamento).

Cobre: bypass por role via default_roles_for() do registry canônico
(app/core/permissions.py — superadmin/admin/trainer em training:write,
SÓ superadmin em training:approve), override allow=True em
user_permission_overrides (via PermissionOverrideRepository mockado),
override ausente/deny/chave errada → 403, fail-closed em erro de DB,
escopo de tenant na query e nível inválido (ValueError em import-time).

Achado da revisão adversarial corrigido: a versão original usava um tuple
hardcoded ("superadmin","admin") para os dois níveis, divergindo do
registry pré-existente (training:write inclui "trainer"; training:approve
é EXCLUSIVO de "superadmin") — trainers perdiam acesso que já tinham, e
admins ganhavam aprovação que o modelo de permissões da plataforma nega.
Testes usam 'operator' (fora de ambos os default_roles) para exercitar
genuinamente o caminho de override/fail-closed sem bypass acidental por role.

JWT helpers e DatabasePool são mockados; app context Flask mínimo para
o error() (jsonify) do envelope 403.
"""
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from flask import Flask

from app.core.auth import require_training_role

_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
_TENANT_ID = "22222222-2222-2222-2222-222222222222"

# Import lazy dentro de _has_training_override → patch no site de definição
_POOL_PATH = "app.infrastructure.database.connection.DatabasePool"
_REPO_PATH = (
    "app.infrastructure.database.repositories."
    "permission_override_repository.PermissionOverrideRepository"
)


@pytest.fixture
def app_ctx():
    """App context mínimo — necessário para jsonify() dentro de error()."""
    app = Flask(__name__)
    with app.app_context():
        yield app


def _override_row(permission_key: str, allow: bool = True) -> dict:
    return {
        "id": "ov-1",
        "tenant_id": _TENANT_ID,
        "user_id": str(_USER_ID),
        "permission_key": permission_key,
        "allow": allow,
    }


def _call(level: str, role: str, overrides=None, pool_none: bool = False,
          repo_error: bool = False):
    """Executa view decorada com JWT/DB mockados.

    Retorna (resultado, view_mock, repo_mock_cls).
    """
    view = MagicMock(return_value="handler-ok")
    decorated = require_training_role(level)(view)

    mock_pool_cls = MagicMock()
    mock_pool_cls.get_instance.return_value = None if pool_none else MagicMock()

    mock_repo_cls = MagicMock()
    repo_instance = mock_repo_cls.return_value
    if repo_error:
        repo_instance.list_by_user_and_tenant.side_effect = Exception("DB down")
    else:
        repo_instance.list_by_user_and_tenant.return_value = overrides or []

    with patch("app.core.auth.verify_jwt_in_request"), \
         patch("app.core.auth.get_role", return_value=role), \
         patch("app.core.auth.get_current_user_id", return_value=_USER_ID), \
         patch("app.core.auth.get_tenant_id", return_value=_TENANT_ID), \
         patch(_POOL_PATH, mock_pool_cls), \
         patch(_REPO_PATH, mock_repo_cls):
        result = decorated()

    return result, view, mock_repo_cls


def _assert_403(result):
    response, status = result
    assert status == 403
    body = response.get_json()
    assert body["success"] is False
    assert body["error"] == "Permissão de treino insuficiente"


# ---------------------------------------------------------------------------
# Bypass por role
# ---------------------------------------------------------------------------

class TestRoleBypass:

    @pytest.mark.parametrize("level", ["write", "approve"])
    def test_superadmin_always_passes(self, app_ctx, level):
        result, view, _ = _call(level, "superadmin")
        assert result == "handler-ok"
        view.assert_called_once()

    def test_admin_passes_write(self, app_ctx):
        result, view, _ = _call("write", "admin")
        assert result == "handler-ok"
        view.assert_called_once()

    def test_trainer_passes_write_without_override(self, app_ctx):
        """training:write inclui 'trainer' no registry canônico (WS7) —
        trainer não deve precisar de override para o nível 'write'."""
        result, view, repo_cls = _call("write", "trainer")
        assert result == "handler-ok"
        view.assert_called_once()
        repo_cls.assert_not_called()

    def test_admin_does_not_query_overrides(self, app_ctx):
        _, _, repo_cls = _call("write", "admin")
        repo_cls.assert_not_called()

    def test_superadmin_does_not_query_overrides(self, app_ctx):
        _, _, repo_cls = _call("approve", "superadmin")
        repo_cls.assert_not_called()

    def test_admin_denied_approve_without_override(self, app_ctx):
        """training:approve é EXCLUSIVO de superadmin no registry — admin
        sem override não pode ativar/promover modelos (fix da revisão)."""
        result, view, _ = _call("approve", "admin")
        _assert_403(result)
        view.assert_not_called()

    def test_admin_with_approve_override_passes(self, app_ctx):
        """Admin pode ganhar 'approve' via override explícito por usuário."""
        result, view, _ = _call(
            "approve", "admin", overrides=[_override_row("training:approve")]
        )
        assert result == "handler-ok"
        view.assert_called_once()


# ---------------------------------------------------------------------------
# Override em user_permission_overrides
# ---------------------------------------------------------------------------

class TestOverride:
    """'operator' está fora de default_roles_for('training:write'/'approve')
    — exercita genuinamente o caminho de override (role sozinha não basta)."""

    def test_operator_with_write_override_passes(self, app_ctx):
        result, view, _ = _call(
            "write", "operator", overrides=[_override_row("training:write")]
        )
        assert result == "handler-ok"
        view.assert_called_once()

    def test_viewer_with_approve_override_passes(self, app_ctx):
        result, view, _ = _call(
            "approve", "viewer", overrides=[_override_row("training:approve")]
        )
        assert result == "handler-ok"
        view.assert_called_once()

    def test_write_override_does_not_grant_approve(self, app_ctx):
        result, view, _ = _call(
            "approve", "trainer", overrides=[_override_row("training:write")]
        )
        _assert_403(result)
        view.assert_not_called()

    def test_deny_override_does_not_grant(self, app_ctx):
        result, view, _ = _call(
            "write", "operator",
            overrides=[_override_row("training:write", allow=False)],
        )
        _assert_403(result)
        view.assert_not_called()

    def test_unrelated_override_does_not_grant(self, app_ctx):
        result, view, _ = _call(
            "write", "operator", overrides=[_override_row("cameras:write")]
        )
        _assert_403(result)

    def test_query_scoped_by_user_and_tenant(self, app_ctx):
        _, _, repo_cls = _call(
            "write", "operator", overrides=[_override_row("training:write")]
        )
        repo_cls.return_value.list_by_user_and_tenant.assert_called_once_with(
            str(_USER_ID), _TENANT_ID
        )


# ---------------------------------------------------------------------------
# Negação (403) sem override
# ---------------------------------------------------------------------------

class TestDenied:

    @pytest.mark.parametrize("role", ["operator", "analyst", "viewer"])
    def test_non_admin_without_override_403(self, app_ctx, role):
        """'trainer' NÃO entra aqui: está em default_roles_for('training:write')
        e passa sem override (ver TestRoleBypass.test_trainer_passes_write_...)."""
        result, view, _ = _call("write", role)
        _assert_403(result)
        view.assert_not_called()

    @pytest.mark.parametrize("role", ["trainer", "operator", "analyst", "viewer"])
    def test_non_admin_without_override_403_approve(self, app_ctx, role):
        result, view, _ = _call("approve", role)
        _assert_403(result)
        view.assert_not_called()


# ---------------------------------------------------------------------------
# Fail-closed (DB indisponível)
# ---------------------------------------------------------------------------

class TestFailClosed:

    def test_pool_none_denies(self, app_ctx):
        result, view, _ = _call("write", "operator", pool_none=True)
        _assert_403(result)
        view.assert_not_called()

    def test_db_exception_denies(self, app_ctx):
        result, view, _ = _call("write", "operator", repo_error=True)
        _assert_403(result)
        view.assert_not_called()


# ---------------------------------------------------------------------------
# Contrato do decorator
# ---------------------------------------------------------------------------

class TestDecoratorContract:

    def test_invalid_level_raises_value_error(self):
        with pytest.raises(ValueError, match="inválido"):
            require_training_role("delete")

    def test_wraps_preserves_name(self):
        def my_view():
            pass

        assert require_training_role("write")(my_view).__name__ == "my_view"

    def test_args_kwargs_forwarded(self, app_ctx):
        view = MagicMock(return_value="ok")
        decorated = require_training_role("approve")(view)
        with patch("app.core.auth.verify_jwt_in_request"), \
             patch("app.core.auth.get_role", return_value="superadmin"):
            result = decorated("pos", dataset_id="ds-1")
        assert result == "ok"
        view.assert_called_once_with("pos", dataset_id="ds-1")
