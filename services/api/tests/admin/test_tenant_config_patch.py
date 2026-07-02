"""Tests: PATCH /api/v1/admin/tenants/<id> — políticas de plataforma (WS6).

Cobertura:
  - Novos campos aceitos: max_seats, single_session, rate_limit_per_minute,
    default_retention_days (colunas já existiam — migrations 051/079)
  - Valores inválidos → 400 com mensagem pt-BR
  - Campos antigos continuam aceitos (paridade — zero regressão)
  - GET /api/v1/admin/modules/catalog — catálogo canônico superadmin-only
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

_POOL_PATH = "app.api.v1.admin.routes.DatabasePool"

TENANT_ID = str(uuid4())


def _auth_header(app, role: str = "superadmin") -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "admin",
                "role": role,
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _make_pool(executed: list | None = None):
    """Pool mock: fetchone devolve tenant-base p/ o SELECT de estado anterior."""
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = {
            "plan": "standard",
            "modules_enabled": ["epi"],
            "is_active": True,
        }
        mock_cur.fetchall.return_value = []
        if executed is not None:
            def _record(query, params=None):
                executed.append((str(query), params))
            mock_cur.execute.side_effect = _record
        mock_conn.cursor.return_value = mock_cur
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _patch_tenant(client, app, body, role="superadmin", executed=None):
    with patch(_POOL_PATH) as mock_cls:
        mock_cls.get_instance.return_value = _make_pool(executed)
        return client.patch(
            f"/api/v1/admin/tenants/{TENANT_ID}",
            json=body,
            headers=_auth_header(app, role),
        )


# ── Gate ──────────────────────────────────────────────────────────────────────


class TestTenantPatchGate:
    def test_admin_403(self, client, app):
        resp = _patch_tenant(client, app, {"max_seats": 5}, role="admin")
        assert resp.status_code == 403

    def test_no_token_401(self, client):
        resp = client.patch(f"/api/v1/admin/tenants/{TENANT_ID}", json={"max_seats": 5})
        assert resp.status_code == 401


# ── Novos campos (WS6) ────────────────────────────────────────────────────────


class TestTenantPolicyFields:
    def test_max_seats_persisted(self, client, app):
        executed: list = []
        resp = _patch_tenant(client, app, {"max_seats": 10}, executed=executed)
        assert resp.status_code == 200
        updates = [q for q, _ in executed if "max_seats" in q]
        assert updates, "UPDATE de max_seats não executado"

    def test_single_session_persisted(self, client, app):
        executed: list = []
        resp = _patch_tenant(client, app, {"single_session": True}, executed=executed)
        assert resp.status_code == 200
        assert any("single_session" in q for q, _ in executed)

    def test_rate_limit_persisted(self, client, app):
        executed: list = []
        resp = _patch_tenant(
            client, app, {"rate_limit_per_minute": 120}, executed=executed
        )
        assert resp.status_code == 200
        assert any("rate_limit_per_minute" in q for q, _ in executed)

    def test_default_retention_days_persisted(self, client, app):
        executed: list = []
        resp = _patch_tenant(
            client, app, {"default_retention_days": 30}, executed=executed
        )
        assert resp.status_code == 200
        assert any("default_retention_days" in q for q, _ in executed)

    def test_null_clears_override(self, client, app):
        resp = _patch_tenant(client, app, {"max_seats": None, "rate_limit_per_minute": None})
        assert resp.status_code == 200


# ── Validação (400 pt-BR) ─────────────────────────────────────────────────────


class TestTenantPolicyValidation:
    def test_max_seats_zero_400(self, client, app):
        resp = _patch_tenant(client, app, {"max_seats": 0})
        assert resp.status_code == 400

    def test_max_seats_string_400(self, client, app):
        resp = _patch_tenant(client, app, {"max_seats": "dez"})
        assert resp.status_code == 400

    def test_single_session_non_bool_400(self, client, app):
        resp = _patch_tenant(client, app, {"single_session": "sim"})
        assert resp.status_code == 400

    def test_rate_limit_negative_400(self, client, app):
        resp = _patch_tenant(client, app, {"rate_limit_per_minute": -5})
        assert resp.status_code == 400

    def test_retention_invalid_tier_400(self, client, app):
        resp = _patch_tenant(client, app, {"default_retention_days": 45})
        assert resp.status_code == 400
        assert "tiers" in resp.get_json()["error"]


# ── Paridade: campos antigos continuam aceitos ────────────────────────────────


class TestTenantPatchParity:
    def test_legacy_fields_still_accepted(self, client, app):
        executed: list = []
        resp = _patch_tenant(
            client,
            app,
            {"internal_notes": "nota", "contract_cameras": 4, "active": True},
            executed=executed,
        )
        assert resp.status_code == 200

    def test_empty_body_400(self, client, app):
        resp = _patch_tenant(client, app, {})
        assert resp.status_code == 400


# ── Catálogo de módulos ───────────────────────────────────────────────────────


class TestModulesCatalog:
    def test_superadmin_gets_catalog(self, client, app):
        resp = client.get(
            "/api/v1/admin/modules/catalog", headers=_auth_header(app)
        )
        assert resp.status_code == 200
        modules = resp.get_json()["data"]["modules"]
        codes = {m["code"] for m in modules}
        assert {"epi", "fueling", "counting", "quality", "basic", "analytics"} <= codes
        for m in modules:
            assert m["label"], f"módulo {m['code']} sem label"
            assert m["description"], f"módulo {m['code']} sem descrição"
            assert m["status"] in ("active", "beta", "coming_soon")

    def test_admin_403(self, client, app):
        resp = client.get(
            "/api/v1/admin/modules/catalog", headers=_auth_header(app, "admin")
        )
        assert resp.status_code == 403
