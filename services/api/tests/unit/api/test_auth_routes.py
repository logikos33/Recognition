"""Tests: auth/routes.py — register, login, me endpoints via Flask test client."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
AUTH_SVC_PATH = "app.api.v1.auth.routes._get_auth_service"
PW_RESET_SVC_PATH = "app.api.v1.auth.routes._get_password_reset_service"


@pytest.fixture
def auth_token(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        return create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "email": "test@test.com",
                "role": "admin",
                "modules": ["epi"],
            },
        )


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def registration_open(monkeypatch):
    """Reabre o auto-registro (fechado por padrão desde o bloco 4)."""
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")


@pytest.fixture
def email_configured(monkeypatch):
    """Simula ambiente com envio de e-mail de fato configurado."""
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("EMAIL_FROM", "no-reply@recognition.test")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")


@pytest.fixture
def email_unconfigured(monkeypatch):
    """Simula o DEV real: nenhuma env de envio de e-mail existe."""
    for var in ("EMAIL_PROVIDER", "EMAIL_FROM", "RESEND_API_KEY",
                "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

class TestRegister:

    def test_disabled_by_default_returns_403(self, client, monkeypatch):
        """Sem ALLOW_PUBLIC_REGISTRATION a rota recusa — não cria conta órfã.

        A conta criada por essa rota nascia com role='operator' e SEM
        tenant_id; o /login depois a recusava ("Usuário sem tenant atribuído")
        e o usuário ficava travado sem entender por quê.
        """
        monkeypatch.delenv("ALLOW_PUBLIC_REGISTRATION", raising=False)
        mock_svc = MagicMock()
        mock_svc.register.return_value = {"id": USER_ID, "email": "orfao@test.com"}
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/register",
                json={"email": "orfao@test.com", "password": "pass123", "name": "Órfão"},
            )
        assert resp.status_code == 403
        body = resp.get_json()
        assert body["success"] is False
        assert body["error_code"] == "registration_disabled"
        assert "administrador" in body["error"].lower()
        # E, principalmente: nenhuma conta foi criada.
        mock_svc.register.assert_not_called()

    def test_success_returns_201(self, client, registration_open):
        mock_svc = MagicMock()
        mock_svc.register.return_value = {"id": USER_ID, "email": "new@test.com"}
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/register",
                json={"email": "new@test.com", "password": "pass123", "name": "Test"},
            )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["success"] is True
        assert "user" in data["data"]

    def test_success_does_not_return_token(self, client, registration_open):
        mock_svc = MagicMock()
        mock_svc.register.return_value = {"id": USER_ID, "email": "new@test.com"}
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/register",
                json={"email": "new@test.com", "password": "pass123", "name": "Test"},
            )
        data = resp.get_json()
        assert "token" not in data.get("data", {})

    def test_internal_exception_returns_500(self, client, registration_open):
        mock_svc = MagicMock()
        mock_svc.register.side_effect = Exception("DB connection failed")
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/register",
                json={"email": "x@x.com", "password": "pass", "name": "X"},
            )
        assert resp.status_code == 500

    def test_missing_body_does_not_crash(self, client, registration_open):
        mock_svc = MagicMock()
        mock_svc.register.return_value = {"id": USER_ID, "email": ""}
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post("/api/auth/register", data="not-json",
                               content_type="application/json")
        assert resp.status_code in (201, 400, 500)


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

class TestLogin:

    def _user_dict(self, **overrides):
        base = {
            "id": USER_ID,
            "email": "user@test.com",
            "tenant_id": TENANT_ID,
            "tenant_schema": "public",
            "role": "admin",
            "modules_enabled": ["epi"],
        }
        base.update(overrides)
        return base

    def test_success_returns_token(self, client):
        mock_svc = MagicMock()
        mock_svc.login.return_value = self._user_dict()
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/login",
                json={"email": "user@test.com", "password": "pass123"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data["data"]

    def test_missing_tenant_schema_returns_401(self, client):
        mock_svc = MagicMock()
        mock_svc.login.return_value = self._user_dict(tenant_schema=None)
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/login",
                json={"email": "user@test.com", "password": "pass123"},
            )
        assert resp.status_code == 401

    def test_missing_tenant_id_returns_401(self, client):
        mock_svc = MagicMock()
        mock_svc.login.return_value = self._user_dict(tenant_id=None)
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/login",
                json={"email": "user@test.com", "password": "pass123"},
            )
        assert resp.status_code == 401

    def test_missing_role_returns_401(self, client):
        mock_svc = MagicMock()
        mock_svc.login.return_value = self._user_dict(role=None)
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/login",
                json={"email": "user@test.com", "password": "pass123"},
            )
        assert resp.status_code == 401

    def test_modules_as_json_string_parsed(self, client):
        import json
        mock_svc = MagicMock()
        mock_svc.login.return_value = self._user_dict(modules_enabled=json.dumps(["epi"]))
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/login",
                json={"email": "user@test.com", "password": "pass123"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data["data"]["user"]["modules"], list)

    def test_modules_as_invalid_json_string_uses_empty_list(self, client):
        mock_svc = MagicMock()
        mock_svc.login.return_value = self._user_dict(modules_enabled="not-json{")
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/login",
                json={"email": "user@test.com", "password": "pass123"},
            )
        assert resp.status_code == 200

    def test_internal_exception_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.login.side_effect = Exception("DB down")
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/login",
                json={"email": "user@test.com", "password": "pass123"},
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

class TestMe:

    def test_without_token_returns_401(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_with_valid_token_returns_user(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_user.return_value = {"id": USER_ID, "email": "test@test.com"}
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_service_exception_returns_500(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_user.side_effect = Exception("DB error")
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/auth/forgot-password
# ---------------------------------------------------------------------------

class TestForgotPassword:

    def test_unconfigured_email_says_so_instead_of_promising(
        self, client, email_unconfigured
    ):
        """Sem envio configurado, a resposta NÃO promete e-mail nenhum.

        Era a mentira medida no DEV: 200 "enviaremos um link de redefinição"
        enquanto resend_client levantava RuntimeError por falta de
        RESEND_API_KEY/EMAIL_FROM e a rota engolia a exceção por desenho.
        """
        mock_svc = MagicMock()
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/forgot-password", json={"email": "user@test.com"}
            )
        assert resp.status_code == 503
        body = resp.get_json()
        assert body["success"] is False
        assert body["error_code"] == "email_delivery_unconfigured"
        assert "não está disponível" in body["error"]
        assert "administrador" in body["error"].lower()
        # Nada prometido: nenhum "enviaremos" na resposta
        assert "enviaremos" not in resp.get_data(as_text=True)
        # E nenhum token de reset é gerado à toa
        mock_svc.request_reset.assert_not_called()

    def test_unconfigured_answer_is_identical_for_known_and_unknown_email(
        self, client, email_unconfigured
    ):
        """A verdade não pode virar oráculo de enumeração de contas."""
        mock_svc = MagicMock()
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            known = client.post(
                "/api/auth/forgot-password", json={"email": "user@test.com"}
            )
            unknown = client.post(
                "/api/auth/forgot-password", json={"email": "nobody@test.com"}
            )
        assert known.status_code == unknown.status_code == 503
        assert known.get_json() == unknown.get_json()

    def test_smtp_provider_without_host_is_also_unconfigured(
        self, client, email_unconfigured, monkeypatch
    ):
        """EMAIL_FROM sozinho não basta: o SMTP ainda erraria por falta de host."""
        monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
        monkeypatch.setenv("EMAIL_FROM", "no-reply@recognition.test")
        mock_svc = MagicMock()
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/forgot-password", json={"email": "user@test.com"}
            )
        assert resp.status_code == 503

    def test_always_returns_200_for_unknown_email(self, client, email_configured):
        mock_svc = MagicMock()
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/forgot-password", json={"email": "nobody@test.com"}
            )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_always_returns_200_for_known_email(self, client, email_configured):
        mock_svc = MagicMock()
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/forgot-password", json={"email": "user@test.com"}
            )
        assert resp.status_code == 200
        mock_svc.request_reset.assert_called_once_with("user@test.com")

    def test_service_exception_still_returns_200(self, client, email_configured):
        """Falha interna nunca pode vazar erro/enumeração ao chamador."""
        mock_svc = MagicMock()
        mock_svc.request_reset.side_effect = Exception("boom")
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/forgot-password", json={"email": "user@test.com"}
            )
        assert resp.status_code == 200

    def test_missing_body_does_not_crash(self, client, email_configured):
        mock_svc = MagicMock()
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            resp = client.post("/api/auth/forgot-password", data="not-json",
                               content_type="application/json")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/auth/reset-password
# ---------------------------------------------------------------------------

class TestResetPassword:

    def test_success_returns_200(self, client):
        mock_svc = MagicMock()
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/reset-password",
                json={"token": "goodtoken", "password": "newpass123"},
            )
        assert resp.status_code == 200
        mock_svc.reset_password.assert_called_once_with(
            token="goodtoken", new_password="newpass123"
        )

    def test_invalid_token_returns_400(self, client):
        from app.core.exceptions import ValidationError
        mock_svc = MagicMock()
        mock_svc.reset_password.side_effect = ValidationError("Token inválido ou expirado")
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/reset-password",
                json={"token": "badtoken", "password": "newpass123"},
            )
        assert resp.status_code == 400

    def test_internal_exception_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.reset_password.side_effect = Exception("DB down")
        with patch(PW_RESET_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/reset-password",
                json={"token": "goodtoken", "password": "newpass123"},
            )
        assert resp.status_code == 500
