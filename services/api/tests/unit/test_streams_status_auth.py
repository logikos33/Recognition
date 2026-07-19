"""
Unit — S4: GET /api/streams/status deixou de ser público (expunha topologia
dos workers Celery). Agora exige role admin/superadmin.
"""
import uuid

from flask_jwt_extended import create_access_token

TENANT = "11111111-1111-1111-1111-111111111111"


def _auth(app, role: str) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": TENANT,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def test_no_token_returns_401(client):
    assert client.get("/api/streams/status").status_code == 401


def test_operator_returns_403(app, client):
    resp = client.get("/api/streams/status", headers=_auth(app, "operator"))
    assert resp.status_code == 403


def test_admin_allowed(app, client, monkeypatch):
    # Sem REDIS_URL → caminho curto redis_unavailable (não precisa de Celery)
    monkeypatch.delenv("REDIS_URL", raising=False)
    resp = client.get("/api/streams/status", headers=_auth(app, "admin"))
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "redis_unavailable"
