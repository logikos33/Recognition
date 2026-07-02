"""Security tests: impersonation "ver como" (WS6).

Cobertura:
  - 403 para admin/operator/analyst/viewer no endpoint de start
  - 403 para alvo superadmin; 403 para alvo inativo; 403 aninhado (claim imp)
  - Token emitido carrega claims do alvo + imp/impersonated_by + exp ≤ 30min
  - NÃO registra em active_sessions (não conta como sessão do alvo)
  - POST /impersonation/stop exige claim imp (400 sem ela) e fecha a sessão
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token, decode_token

_POOL_PATH = "app.api.v1.admin.impersonation_routes.DatabasePool"

SUPERADMIN_ID = str(uuid4())
TARGET_ID = str(uuid4())
TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _auth_header(app, role: str, extra_claims: dict | None = None,
                 identity: str | None = None) -> dict[str, str]:
    claims = {
        "tenant_id": TENANT_ID,
        "tenant_schema": "tenant_test",
        "email": f"{role}@test.dev",
        "role": role,
    }
    if extra_claims:
        claims.update(extra_claims)
    with app.app_context():
        token = create_access_token(
            identity=identity or SUPERADMIN_ID, additional_claims=claims
        )
    return {"Authorization": f"Bearer {token}"}


def _target_row(role: str = "operator", is_active: bool = True) -> dict:
    return {
        "id": TARGET_ID,
        "email": "alvo@cliente.dev",
        "name": "Usuário Alvo",
        "role": role,
        "is_active": is_active,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "tenant_id": TENANT_ID,
        "custom_role_id": None,
        "tenant_schema": "tenant_cliente",
        "modules_enabled": ["epi"],
    }


def _make_pool(fetchone_row=None, executed_queries: list | None = None):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = fetchone_row
        mock_cur.fetchall.return_value = []
        if executed_queries is not None:
            def _record(query, params=None):  # noqa: ARG001
                executed_queries.append(str(query))
            mock_cur.execute.side_effect = _record
        mock_conn.cursor.return_value = mock_cur
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _start(client, app, headers, row=_target_row, executed=None):
    row_value = row() if callable(row) else row
    mock_pool = _make_pool(fetchone_row=row_value, executed_queries=executed)
    with patch(_POOL_PATH) as mock_cls:
        mock_cls.get_instance.return_value = mock_pool
        return client.post(
            f"/api/v1/admin/users/{TARGET_ID}/impersonate", headers=headers
        )


# ── Gate: superadmin-only ─────────────────────────────────────────────────────


class TestImpersonateGate:
    def test_admin_403(self, client, app):
        resp = _start(client, app, _auth_header(app, "admin"))
        assert resp.status_code == 403

    def test_operator_403(self, client, app):
        resp = _start(client, app, _auth_header(app, "operator"))
        assert resp.status_code == 403

    def test_analyst_403(self, client, app):
        resp = _start(client, app, _auth_header(app, "analyst"))
        assert resp.status_code == 403

    def test_viewer_403(self, client, app):
        resp = _start(client, app, _auth_header(app, "viewer"))
        assert resp.status_code == 403

    def test_no_token_401(self, client):
        resp = client.post(f"/api/v1/admin/users/{TARGET_ID}/impersonate")
        assert resp.status_code == 401


# ── Regras do alvo e aninhamento ──────────────────────────────────────────────


class TestImpersonateRules:
    def test_nested_impersonation_403(self, client, app):
        headers = _auth_header(
            app, "superadmin", extra_claims={"imp": True, "impersonated_by": str(uuid4())}
        )
        resp = _start(client, app, headers)
        assert resp.status_code == 403

    def test_target_superadmin_403(self, client, app):
        headers = _auth_header(app, "superadmin")
        resp = _start(client, app, headers, row=_target_row(role="superadmin"))
        assert resp.status_code == 403

    def test_target_inactive_403(self, client, app):
        headers = _auth_header(app, "superadmin")
        resp = _start(client, app, headers, row=_target_row(is_active=False))
        assert resp.status_code == 403

    def test_target_not_found_404(self, client, app):
        headers = _auth_header(app, "superadmin")
        resp = _start(client, app, headers, row=None)
        assert resp.status_code == 404


# ── Token emitido ─────────────────────────────────────────────────────────────


class TestImpersonationToken:
    def test_token_carries_target_claims_and_ttl(self, client, app):
        headers = _auth_header(app, "superadmin")
        resp = _start(client, app, headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "token" in data
        assert data["user"]["email"] == "alvo@cliente.dev"
        assert data["user"]["tenant_schema"] == "tenant_cliente"
        assert data["expires_in_minutes"] == 30

        with app.app_context():
            payload = decode_token(data["token"])
        assert payload["sub"] == TARGET_ID
        assert payload["role"] == "operator"
        assert payload["tenant_id"] == TENANT_ID
        assert payload["tenant_schema"] == "tenant_cliente"
        assert payload["imp"] is True
        assert payload["impersonated_by"] == SUPERADMIN_ID
        # TTL ≤ 30 minutos (margem de 5s para clock do teste)
        assert payload["exp"] - payload["iat"] <= 30 * 60 + 5

    def test_does_not_register_active_session(self, client, app):
        executed: list[str] = []
        headers = _auth_header(app, "superadmin")
        resp = _start(client, app, headers, executed=executed)
        assert resp.status_code == 200
        joined = "\n".join(executed).lower()
        assert "active_sessions" not in joined
        # E registra na tabela forense de impersonation
        assert "impersonation_sessions" in joined


# ── Stop ──────────────────────────────────────────────────────────────────────


class TestImpersonationStop:
    def test_stop_without_imp_claim_400(self, client, app):
        headers = _auth_header(app, "operator", identity=TARGET_ID)
        resp = client.post("/api/v1/impersonation/stop", headers=headers)
        assert resp.status_code == 400

    def test_stop_with_imp_claim_200_and_closes_session(self, client, app):
        headers = _auth_header(
            app,
            "operator",
            identity=TARGET_ID,
            extra_claims={"imp": True, "impersonated_by": SUPERADMIN_ID},
        )
        executed: list[str] = []
        mock_pool = _make_pool(
            fetchone_row={"id": str(uuid4()), "ended_at": datetime.now(timezone.utc)},
            executed_queries=executed,
        )
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.post("/api/v1/impersonation/stop", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["stopped"] is True
        joined = "\n".join(executed).lower()
        assert "ended_at" in joined
