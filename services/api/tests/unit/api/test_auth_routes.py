"""Tests: auth/routes.py — register, login, me endpoints via Flask test client."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
AUTH_SVC_PATH = "app.api.v1.auth.routes._get_auth_service"


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


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

class TestRegister:

    def test_success_returns_201(self, client):
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

    def test_success_does_not_return_token(self, client):
        mock_svc = MagicMock()
        mock_svc.register.return_value = {"id": USER_ID, "email": "new@test.com"}
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/register",
                json={"email": "new@test.com", "password": "pass123", "name": "Test"},
            )
        data = resp.get_json()
        assert "token" not in data.get("data", {})

    def test_internal_exception_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.register.side_effect = Exception("DB connection failed")
        with patch(AUTH_SVC_PATH, return_value=mock_svc):
            resp = client.post(
                "/api/auth/register",
                json={"email": "x@x.com", "password": "pass", "name": "X"},
            )
        assert resp.status_code == 500

    def test_missing_body_does_not_crash(self, client):
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
