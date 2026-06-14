"""
Security tests — ADR-0017 Tenant Isolation Enforcement.

Verifica que claims JWT sem fallback silencioso levantam AuthenticationError,
e que login rejeita usuários sem tenant atribuído.

Nota: usa patch em flask_jwt_extended.get_jwt porque as funções importam
get_jwt() dentro do corpo da função (não no topo do módulo).
"""
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

from app.core.exceptions import AuthenticationError


@pytest.fixture(scope="module")
def security_app():
    """Minimal Flask app sem SocketIO para testes de auth."""
    app = Flask(__name__)
    app.config.update({
        "TESTING": True,
        "JWT_SECRET_KEY": "test-key-for-security-tests",
        "JWT_ACCESS_TOKEN_EXPIRES": False,
    })
    JWTManager(app)
    from app.api.v1.auth.routes import auth_bp
    app.register_blueprint(auth_bp)
    from app.core.middleware import register_error_handlers
    register_error_handlers(app)
    return app


@pytest.fixture
def security_client(security_app):
    return security_app.test_client()


class TestJwtClaimEnforcement:
    """get_tenant_schema / get_tenant_id / get_role — sem fallback silencioso."""

    def test_get_tenant_schema_raises_when_missing(self):
        with patch("flask_jwt_extended.get_jwt", return_value={}):
            from app.core.auth import get_tenant_schema
            with pytest.raises(AuthenticationError, match="tenant_schema"):
                get_tenant_schema()

    def test_get_tenant_schema_returns_value_when_present(self):
        with patch("flask_jwt_extended.get_jwt", return_value={"tenant_schema": "rvb"}):
            from app.core.auth import get_tenant_schema
            assert get_tenant_schema() == "rvb"

    def test_get_tenant_id_raises_when_missing(self):
        with patch("flask_jwt_extended.get_jwt", return_value={}):
            from app.core.auth import get_tenant_id
            with pytest.raises(AuthenticationError, match="tenant_id"):
                get_tenant_id()

    def test_get_tenant_id_returns_value_when_present(self):
        tid = "11111111-0000-0000-0000-000000000002"
        with patch("flask_jwt_extended.get_jwt", return_value={"tenant_id": tid}):
            from app.core.auth import get_tenant_id
            assert get_tenant_id() == tid

    def test_get_role_raises_when_missing(self):
        with patch("flask_jwt_extended.get_jwt", return_value={}):
            from app.core.auth import get_role
            with pytest.raises(AuthenticationError, match="role"):
                get_role()

    def test_get_role_returns_value_when_present(self):
        with patch("flask_jwt_extended.get_jwt", return_value={"role": "admin"}):
            from app.core.auth import get_role
            assert get_role() == "admin"

    def test_get_modules_enabled_returns_empty_list_when_missing(self):
        """modules_enabled mantém fallback [] — lista vazia é estado legítimo."""
        with patch("flask_jwt_extended.get_jwt", return_value={}):
            from app.core.auth import get_modules_enabled
            assert get_modules_enabled() == []

    def test_get_modules_enabled_returns_list_when_present(self):
        with patch("flask_jwt_extended.get_jwt", return_value={"modules": ["epi", "quality"]}):
            from app.core.auth import get_modules_enabled
            assert get_modules_enabled() == ["epi", "quality"]


class TestLoginTenantValidation:
    """Login deve rejeitar usuários sem tenant atribuído (sem fallback silencioso)."""

    def _make_user(self, **overrides):
        base = {
            "id": "aaaaaaaa-0000-0000-0000-000000000001",
            "email": "test@example.com",
            "role": "operator",
            "tenant_id": "bbbbbbbb-0000-0000-0000-000000000001",
            "tenant_schema": "test_schema",
            "modules_enabled": ["epi"],
        }
        base.update(overrides)
        return base

    def test_login_returns_401_when_tenant_schema_missing(self, security_client):
        user_without_schema = self._make_user(tenant_schema=None)
        with patch("app.api.v1.auth.routes._get_auth_service") as mock_factory:
            mock_svc = MagicMock()
            mock_svc.login.return_value = user_without_schema
            mock_factory.return_value = mock_svc

            resp = security_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "pw"},
            )
            assert resp.status_code == 401

    def test_login_returns_401_when_tenant_id_missing(self, security_client):
        user_without_tenant = self._make_user(tenant_id=None)
        with patch("app.api.v1.auth.routes._get_auth_service") as mock_factory:
            mock_svc = MagicMock()
            mock_svc.login.return_value = user_without_tenant
            mock_factory.return_value = mock_svc

            resp = security_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "pw"},
            )
            assert resp.status_code == 401

    def test_login_returns_401_when_role_missing(self, security_client):
        user_without_role = self._make_user(role=None)
        with patch("app.api.v1.auth.routes._get_auth_service") as mock_factory:
            mock_svc = MagicMock()
            mock_svc.login.return_value = user_without_role
            mock_factory.return_value = mock_svc

            resp = security_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "pw"},
            )
            assert resp.status_code == 401


class TestRegisterNoToken:
    """Register não deve emitir access_token — ADR-0017 Camada 2."""

    def test_register_response_has_no_token(self, security_client):
        user_data = {
            "id": "cccccccc-0000-0000-0000-000000000001",
            "email": "new@example.com",
            "name": "Test User",
        }
        with patch("app.api.v1.auth.routes._get_auth_service") as mock_factory:
            mock_svc = MagicMock()
            mock_svc.register.return_value = user_data
            mock_factory.return_value = mock_svc

            resp = security_client.post(
                "/api/auth/register",
                json={"email": "new@example.com", "password": "pw", "name": "Test User"},
            )
            assert resp.status_code == 201
            body = resp.get_json()
            assert "token" not in body.get("data", {})

    def test_register_response_contains_message(self, security_client):
        user_data = {"id": "cccccccc-0000-0000-0000-000000000001", "email": "new@example.com"}
        with patch("app.api.v1.auth.routes._get_auth_service") as mock_factory:
            mock_svc = MagicMock()
            mock_svc.register.return_value = user_data
            mock_factory.return_value = mock_svc

            resp = security_client.post(
                "/api/auth/register",
                json={"email": "new@example.com", "password": "pw", "name": "New"},
            )
            body = resp.get_json()
            assert "message" in body.get("data", {})
