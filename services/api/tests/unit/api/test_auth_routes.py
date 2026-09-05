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


# ---------------------------------------------------------------------------
# POST /api/auth/refresh  (issue #667)
# ---------------------------------------------------------------------------
#
# O que se protege aqui não é "a rota responde 200". É que a única rota que
# emite token sem senha NÃO seja uma escada de privilégio:
#
#   · token expirado / ausente não sai daqui com token novo;
#   · as claims saem do BANCO, nunca do token que chegou — token com tenant
#     ou role velho renova para o tenant/role ATUAL, não para o que carregava;
#   · usuário desativado não renova (senão demitir não encerra a sessão);
#   · token de contexto assumido / "ver como" tem TTL curto DE PROPÓSITO e
#     não pode virar 24h de sessão comum por aqui.
#
# Tudo pelo test_client: cruza a fronteira HTTP, com o token indo no header.

USER_REPO_PATH = "app.api.v1.auth.routes._get_user_repository"

OUTRO_TENANT_ID = str(uuid4())


def _db_user(**overrides):
    """Usuário como o BANCO devolve (get_by_id_with_tenant)."""
    base = {
        "id": USER_ID,
        "email": "user@test.com",
        "name": "Usuária",
        "role": "admin",
        "is_active": True,
        "tenant_id": TENANT_ID,
        "tenant_schema": "public",
        "modules_enabled": ["epi"],
    }
    base.update(overrides)
    return base


def _mock_repo(user):
    repo = MagicMock()
    repo.get_by_id_with_tenant.return_value = user
    return repo


def _claims(app, token):
    with app.app_context():
        from flask_jwt_extended import decode_token
        return decode_token(token)


def _token(app, *, claims=None, expires_delta=None, identity=USER_ID):
    from datetime import timedelta  # noqa: F401  (usado pelos chamadores)
    with app.app_context():
        from flask_jwt_extended import create_access_token
        base = {
            "tenant_id": TENANT_ID,
            "tenant_schema": "public",
            "email": "user@test.com",
            "role": "admin",
            "modules": ["epi"],
        }
        base.update(claims or {})
        kwargs = {"identity": identity, "additional_claims": base}
        if expires_delta is not None:
            kwargs["expires_delta"] = expires_delta
        return create_access_token(**kwargs)


class TestRefresh:

    # ── quem NÃO renova ─────────────────────────────────────────────────────

    def test_sem_token_401(self, client):
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401

    def test_token_expirado_401(self, client, app):
        """Um token morto não ressuscita — é o ponto inteiro da rota existir."""
        from datetime import timedelta
        morto = _token(app, expires_delta=timedelta(seconds=-1))
        repo = _mock_repo(_db_user())
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {morto}"}
            )
        assert resp.status_code == 401
        assert "token" not in (resp.get_json().get("data") or {})
        # E nem chegou a consultar o banco: o @jwt_required barrou antes.
        repo.get_by_id_with_tenant.assert_not_called()

    def test_token_adulterado_401(self, client, app):
        bom = _token(app)
        resp = client.post(
            "/api/auth/refresh", headers={"Authorization": f"Bearer {bom}x"}
        )
        assert resp.status_code in (401, 422)

    def test_usuario_desativado_nao_renova(self, client, auth_headers):
        """Desativar a conta tem de encerrar a sessão, não só o próximo login."""
        repo = _mock_repo(_db_user(is_active=False))
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post("/api/auth/refresh", headers=auth_headers)
        assert resp.status_code == 401
        assert "token" not in (resp.get_json().get("data") or {})

    def test_usuario_sumiu_do_banco_nao_renova(self, client, auth_headers):
        repo = _mock_repo(None)
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post("/api/auth/refresh", headers=auth_headers)
        assert resp.status_code == 401

    # ── escada de privilégio ────────────────────────────────────────────────

    def test_token_de_contexto_assumido_403(self, client, app):
        """30 min auditados de contexto assumido não viram 24h de sessão.

        O caminho de renovação dele é /api/admin/tenant-context/renew, que
        preserva o TTL curto e registra auditoria.
        """
        from app.core.tenant_context import TENANT_CTX_CLAIM
        ctx = _token(app, claims={
            TENANT_CTX_CLAIM: True,
            "impersonated_by": USER_ID,
            "role": "superadmin",
        })
        repo = _mock_repo(_db_user())
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {ctx}"}
            )
        assert resp.status_code == 403
        assert resp.get_json()["error_code"] == "refresh_not_allowed"
        assert "token" not in (resp.get_json().get("data") or {})

    def test_token_de_ver_como_403(self, client, app):
        """Impersonation idem: TTL curto é a contenção, não um detalhe."""
        imp = _token(app, claims={"imp": True, "impersonated_by": str(uuid4())})
        repo = _mock_repo(_db_user())
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {imp}"}
            )
        assert resp.status_code == 403

    def test_token_de_enrollment_de_device_403(self, client, app):
        """Token de device não é sessão de gente — não vira uma."""
        dev = _token(app, claims={"token_type": "device_enrollment"})
        repo = _mock_repo(_db_user())
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {dev}"}
            )
        assert resp.status_code == 403

    def test_tenant_do_token_nao_vira_tenant_do_token_novo(self, client, app):
        """Token de OUTRO tenant não vira token deste.

        A claim de tenant que chega é IGNORADA: quem manda é o vínculo do
        usuário no banco. Se o vínculo mudou (ou o token é velho), a renovação
        segue o banco — nunca o papel/tenant que o portador trouxe.
        """
        antigo = _token(app, claims={
            "tenant_id": OUTRO_TENANT_ID, "tenant_schema": "outro_tenant",
        })
        repo = _mock_repo(_db_user(tenant_id=TENANT_ID, tenant_schema="public"))
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {antigo}"}
            )
        assert resp.status_code == 200
        novo = _claims(app, resp.get_json()["data"]["token"])
        assert novo["tenant_id"] == TENANT_ID
        assert novo["tenant_schema"] == "public"
        assert novo["tenant_id"] != OUTRO_TENANT_ID

    def test_role_do_token_nao_amplia_o_token_novo(self, client, app):
        """Rebaixaram a role no banco → o token novo já sai rebaixado."""
        inflado = _token(app, claims={"role": "superadmin"})
        repo = _mock_repo(_db_user(role="operator"))
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {inflado}"}
            )
        assert resp.status_code == 200
        assert _claims(app, resp.get_json()["data"]["token"])["role"] == "operator"

    def test_identidade_vem_do_token_nao_do_corpo(self, client, auth_headers):
        """Corpo da request não escolhe de quem é a sessão renovada."""
        repo = _mock_repo(_db_user())
        outro = str(uuid4())
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post(
                "/api/auth/refresh",
                headers=auth_headers,
                json={"user_id": outro, "role": "superadmin",
                      "tenant_id": OUTRO_TENANT_ID},
            )
        assert resp.status_code == 200
        repo.get_by_id_with_tenant.assert_called_once_with(USER_ID)

    # ── o caminho feliz ─────────────────────────────────────────────────────

    def test_token_valido_devolve_token_novo_com_as_mesmas_claims(
        self, client, app
    ):
        """Renovar não pode TIRAR nada de quem renovou.

        O cenário real é o do aviso de 5 min: token vivo, perto do fim.
        """
        from datetime import timedelta
        quase = _token(app, expires_delta=timedelta(minutes=4))
        repo = _mock_repo(_db_user())
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {quase}"}
            )
        assert resp.status_code == 200

        antes = _claims(app, quase)
        depois = _claims(app, resp.get_json()["data"]["token"])
        for claim in ("sub", "tenant_id", "tenant_schema", "role", "modules", "email"):
            assert depois[claim] == antes[claim], f"claim {claim} mudou na renovação"

    def test_token_novo_e_outro_token_com_prazo_maior(self, client, app):
        """Renovar que devolve o MESMO prazo é o bug antigo do `reload()`:
        mesmo token, mesmo `exp`, aviso de volta em segundos."""
        from datetime import timedelta
        quase = _token(app, expires_delta=timedelta(minutes=4))
        repo = _mock_repo(_db_user())
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post(
                "/api/auth/refresh", headers={"Authorization": f"Bearer {quase}"}
            )
        body = resp.get_json()["data"]
        antes, depois = _claims(app, quase), _claims(app, body["token"])
        assert depois["jti"] != antes["jti"]
        assert depois["exp"] > antes["exp"]
        # O prazo vai pronto no corpo: o front não decodifica JWT.
        assert body["expires_at"] == depois["exp"]

    def test_devolve_o_usuario_sem_campo_interno(self, client, auth_headers):
        repo = _mock_repo(_db_user())
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post("/api/auth/refresh", headers=auth_headers)
        user = resp.get_json()["data"]["user"]
        assert "password_hash" not in user
        assert "modules_enabled" not in user
        assert user["modules"] == ["epi"]
        assert "permissions" in user

    def test_usuario_sem_tenant_nao_renova(self, client, auth_headers):
        """ADR-0017: sem fallback silencioso de tenant, nem na renovação."""
        repo = _mock_repo(_db_user(tenant_schema=None))
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post("/api/auth/refresh", headers=auth_headers)
        assert resp.status_code == 401

    def test_falha_interna_nao_devolve_token(self, client, auth_headers):
        repo = MagicMock()
        repo.get_by_id_with_tenant.side_effect = Exception("DB down")
        with patch(USER_REPO_PATH, return_value=repo):
            resp = client.post("/api/auth/refresh", headers=auth_headers)
        assert resp.status_code == 500
        assert "token" not in (resp.get_json().get("data") or {})
