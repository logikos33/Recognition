"""
Testes — Admin Software Channels (OTA bare-metal, ADR-0057 item 10).

Endpoints:
  GET /api/v1/admin/software-channels           listagem
  PUT /api/v1/admin/software-channels/<channel>  publica target_ref (upsert)

Estratégia de mock: mesmo padrão de test_plans_routes.py — DatabasePool
mockado via monkeypatch em admin.routes (_pool), log_audit mockado.
"""
import uuid
from unittest.mock import MagicMock

from flask_jwt_extended import create_access_token

SUPERADMIN_TENANT = "00000000-0000-0000-0000-000000000001"


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
                "tenant_id": str(uuid.uuid4()),
                "tenant_schema": "tenant_test",
                "role": "operator",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_pool(monkeypatch, *, fetchone=None, fetchall=None):
    import app.api.v1.admin.routes as routes_mod

    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    cur.fetchall.return_value = fetchall if fetchall is not None else []
    cur.fetchone.return_value = fetchone
    pool.get_connection.return_value = conn

    monkeypatch.setattr(routes_mod, "_pool", lambda: pool)
    monkeypatch.setattr(routes_mod, "log_audit", lambda *a, **k: None)
    return pool, conn, cur


class TestListSoftwareChannels:
    def test_superadmin_lists_channels(self, app, client, monkeypatch):
        _mock_pool(
            monkeypatch,
            fetchall=[
                {"channel": "dev", "target_ref": "abc123", "updated_at": None, "updated_by": None},
            ],
        )
        resp = client.get("/api/v1/admin/software-channels", headers=_superadmin_header(app))
        assert resp.status_code == 200
        channels = resp.get_json()["data"]["channels"]
        assert channels[0]["channel"] == "dev"
        assert channels[0]["target_ref"] == "abc123"

    def test_non_superadmin_gets_403(self, app, client):
        resp = client.get("/api/v1/admin/software-channels", headers=_operator_header(app))
        assert resp.status_code == 403

    def test_no_token_gets_401(self, client):
        resp = client.get("/api/v1/admin/software-channels")
        assert resp.status_code == 401


class TestSetSoftwareChannelTarget:
    def test_superadmin_publishes_target_ref(self, app, client, monkeypatch):
        _mock_pool(
            monkeypatch,
            fetchone={
                "channel": "dev", "target_ref": "new-sha", "updated_at": None, "updated_by": None,
            },
        )
        resp = client.put(
            "/api/v1/admin/software-channels/dev",
            headers=_superadmin_header(app),
            json={"target_ref": "new-sha"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["target_ref"] == "new-sha"

    def test_missing_target_ref_returns_422(self, app, client, monkeypatch):
        _mock_pool(monkeypatch)
        resp = client.put(
            "/api/v1/admin/software-channels/dev",
            headers=_superadmin_header(app),
            json={},
        )
        assert resp.status_code == 422

    def test_blank_target_ref_returns_422(self, app, client, monkeypatch):
        _mock_pool(monkeypatch)
        resp = client.put(
            "/api/v1/admin/software-channels/dev",
            headers=_superadmin_header(app),
            json={"target_ref": "   "},
        )
        assert resp.status_code == 422

    def test_non_superadmin_gets_403(self, app, client):
        resp = client.put(
            "/api/v1/admin/software-channels/dev",
            headers=_operator_header(app),
            json={"target_ref": "sha"},
        )
        assert resp.status_code == 403

    def test_query_uses_upsert(self, app, client, monkeypatch):
        _pool, _conn, cur = _mock_pool(
            monkeypatch, fetchone={"channel": "dev", "target_ref": "r"}
        )
        client.put(
            "/api/v1/admin/software-channels/dev",
            headers=_superadmin_header(app),
            json={"target_ref": "r"},
        )
        query = cur.execute.call_args[0][0]
        assert "ON CONFLICT" in query
