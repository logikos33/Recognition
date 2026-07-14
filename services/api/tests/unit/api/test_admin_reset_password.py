"""
Testes — Admin reset de senha (ADR-0042 Fase 1).

Endpoint testado:
  POST /api/v1/admin/users/<user_id>/reset-password

Gera senha temporária, atualiza o hash bcrypt, marca force_password_reset e
retorna a senha em claro UMA ÚNICA VEZ. Protegido por @require_superadmin.

Estratégia de mock (espelha test_admin_inventory.py):
  - DatabasePool mockado via monkeypatch em admin.routes (_pool)
  - Redis mockado (evita conexão real; o endpoint já tolera falha do redis)
  - JWT real via create_access_token
"""
import uuid
from unittest.mock import MagicMock

from flask_jwt_extended import create_access_token

SUPERADMIN_TENANT = "00000000-0000-0000-0000-000000000001"
TENANT_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
URL = f"/api/v1/admin/users/{USER_ID}/reset-password"


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _superadmin_header(app):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": SUPERADMIN_TENANT,
                "tenant_schema": "admin",
                "role": "superadmin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _operator_header(app):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "tenant_test",
                "role": "operator",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ── Mock helper ───────────────────────────────────────────────────────────────

def _mock_pool(monkeypatch, user_row):
    """Pool mock cujo fetchone retorna `user_row` (dict ou None). Redis mockado."""
    import app.api.v1.admin.routes as routes_mod

    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    cur.fetchone.return_value = user_row
    pool.get_connection.return_value = conn

    monkeypatch.setattr(routes_mod, "_pool", lambda: pool)
    monkeypatch.setattr(routes_mod, "_get_redis", lambda: MagicMock())
    return pool, conn, cur


# ── Testes ────────────────────────────────────────────────────────────────────

class TestResetPassword:
    def test_superadmin_reset_returns_temp_password(self, app, client, monkeypatch):
        _, conn, _ = _mock_pool(
            monkeypatch, {"email": "user@rvb.com", "tenant_id": TENANT_ID}
        )
        resp = client.post(URL, headers=_superadmin_header(app))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["email"] == "user@rvb.com"
        temp = body["data"]["temp_password"]
        assert isinstance(temp, str) and len(temp) >= 12
        conn.commit.assert_called_once()

    def test_update_sets_force_reset_and_stores_bcrypt_hash(self, app, client, monkeypatch):
        """Falha-antes/passa-depois: garante que o UPDATE seta a flag e grava
        um hash bcrypt (não a senha em claro)."""
        _, _, cur = _mock_pool(
            monkeypatch, {"email": "user@rvb.com", "tenant_id": TENANT_ID}
        )
        resp = client.post(URL, headers=_superadmin_header(app))
        assert resp.status_code == 200
        temp = resp.get_json()["data"]["temp_password"]

        update_calls = [
            c for c in cur.execute.call_args_list if "UPDATE users" in c.args[0]
        ]
        assert len(update_calls) == 1
        sql, params = update_calls[0].args[0], update_calls[0].args[1]
        assert "force_password_reset = true" in sql
        assert "password_hash" in sql
        stored_hash = params[0]
        assert stored_hash != temp           # nunca grava senha em claro
        assert stored_hash.startswith("$2")  # bcrypt

    def test_user_not_found_returns_404(self, app, client, monkeypatch):
        _, conn, _ = _mock_pool(monkeypatch, None)
        resp = client.post(URL, headers=_superadmin_header(app))
        assert resp.status_code == 404
        conn.commit.assert_not_called()

    def test_temp_passwords_are_distinct_between_calls(self, app, client, monkeypatch):
        _mock_pool(monkeypatch, {"email": "u@rvb.com", "tenant_id": TENANT_ID})
        p1 = client.post(URL, headers=_superadmin_header(app)).get_json()["data"]["temp_password"]
        p2 = client.post(URL, headers=_superadmin_header(app)).get_json()["data"]["temp_password"]
        assert p1 != p2

    def test_non_superadmin_gets_403(self, app, client, monkeypatch):
        _mock_pool(monkeypatch, {"email": "u@rvb.com", "tenant_id": TENANT_ID})
        resp = client.post(URL, headers=_operator_header(app))
        assert resp.status_code == 403

    def test_unauthenticated_gets_401(self, client):
        resp = client.post(URL)
        assert resp.status_code == 401
