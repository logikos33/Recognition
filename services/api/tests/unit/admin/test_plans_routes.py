"""
Testes — Admin Plans endpoints (WS8).

Endpoints testados:
  GET   /api/v1/admin/modules-registry
  GET   /api/v1/admin/plans           (tenant_count aditivo)
  GET   /api/v1/admin/plans/<id>      (detalhe único, novo)
  POST  /api/v1/admin/plans           (validação slug/name, 409 duplicado)
  PATCH /api/v1/admin/plans/<id>      (404 inexistente, slug imutável,
                                       max_users/module_features/api_rate_per_minute)

Estratégia de mock:
  - DatabasePool mockado via monkeypatch em admin.routes (_pool)
  - log_audit mockado (não toca banco)
  - @require_superadmin exige JWT com role=superadmin
"""
import uuid
from unittest.mock import MagicMock

from flask_jwt_extended import create_access_token
from psycopg2 import errors as pg_errors

SUPERADMIN_TENANT = "00000000-0000-0000-0000-000000000001"
PLAN_ID = str(uuid.uuid4())


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
                "tenant_id": str(uuid.uuid4()),
                "tenant_schema": "tenant_test",
                "role": "operator",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ── Mock helpers ──────────────────────────────────────────────────────────────

def _plan_row(overrides: dict | None = None) -> dict:
    row = {
        "id": PLAN_ID,
        "slug": "standard",
        "name": "Standard",
        "modules_allowed": ["epi", "counting", "basic"],
        "max_cameras": 20,
        "max_users": None,
        "video_retention_days": 15,
        "requires_training_approval": False,
        "price_per_camera": {"epi": 280},
        "module_features": {},
        "api_rate_per_minute": 120,
        "active": True,
        "created_at": None,
        "tenant_count": 3,
    }
    row.update(overrides or {})
    return row


def _mock_pool(monkeypatch, *, fetchone=None, fetchall=None, execute_side_effect=None):
    """Configura pool mockado em admin.routes. Retorna (pool, conn, cur)."""
    import app.api.v1.admin.routes as routes_mod

    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    cur.fetchall.return_value = fetchall if fetchall is not None else []
    if isinstance(fetchone, list):
        cur.fetchone.side_effect = fetchone
    else:
        cur.fetchone.return_value = fetchone
    if execute_side_effect is not None:
        cur.execute.side_effect = execute_side_effect
    pool.get_connection.return_value = conn

    monkeypatch.setattr(routes_mod, "_pool", lambda: pool)
    monkeypatch.setattr(routes_mod, "log_audit", lambda *a, **k: None)
    return pool, conn, cur


# ── GET /api/v1/admin/modules-registry ───────────────────────────────────────

class TestModulesRegistry:
    def test_superadmin_gets_registry(self, app, client):
        resp = client.get("/api/v1/admin/modules-registry", headers=_superadmin_header(app))
        assert resp.status_code == 200
        modules = resp.get_json()["data"]["modules"]
        codes = {m["module_code"] for m in modules}
        assert codes == {"epi", "fueling", "counting", "quality", "basic"}
        for mod in modules:
            assert mod["label"]
            assert isinstance(mod["features"], list)
            assert all("key" in f and "label" in f for f in mod["features"])

    def test_non_superadmin_gets_403(self, app, client):
        resp = client.get("/api/v1/admin/modules-registry", headers=_operator_header(app))
        assert resp.status_code == 403


# ── GET /api/v1/admin/plans ──────────────────────────────────────────────────

class TestListPlans:
    def test_list_includes_tenant_count(self, app, client, monkeypatch):
        _mock_pool(monkeypatch, fetchall=[_plan_row()])
        resp = client.get("/api/v1/admin/plans", headers=_superadmin_header(app))
        assert resp.status_code == 200
        plans = resp.get_json()["data"]["plans"]
        assert plans[0]["tenant_count"] == 3


class TestGetPlan:
    def test_get_plan_found(self, app, client, monkeypatch):
        _mock_pool(monkeypatch, fetchone=_plan_row())
        resp = client.get(f"/api/v1/admin/plans/{PLAN_ID}", headers=_superadmin_header(app))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["plan"]["id"] == PLAN_ID

    def test_get_plan_not_found(self, app, client, monkeypatch):
        _mock_pool(monkeypatch, fetchone=None)
        resp = client.get(f"/api/v1/admin/plans/{uuid.uuid4()}", headers=_superadmin_header(app))
        assert resp.status_code == 404


# ── POST /api/v1/admin/plans ─────────────────────────────────────────────────

class TestCreatePlan:
    def test_missing_slug_returns_400(self, app, client, monkeypatch):
        _mock_pool(monkeypatch)
        resp = client.post(
            "/api/v1/admin/plans",
            json={"name": "Sem Slug"},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400

    def test_invalid_slug_returns_400(self, app, client, monkeypatch):
        _mock_pool(monkeypatch)
        resp = client.post(
            "/api/v1/admin/plans",
            json={"slug": "Slug Inválido!", "name": "X"},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400

    def test_missing_name_returns_400(self, app, client, monkeypatch):
        _mock_pool(monkeypatch)
        resp = client.post(
            "/api/v1/admin/plans",
            json={"slug": "novo-plano"},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400

    def test_duplicate_slug_returns_409(self, app, client, monkeypatch):
        _mock_pool(monkeypatch, execute_side_effect=pg_errors.UniqueViolation())
        resp = client.post(
            "/api/v1/admin/plans",
            json={"slug": "standard", "name": "Duplicado"},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 409
        assert "Slug" in resp.get_json()["error"]

    def test_create_persists_new_fields(self, app, client, monkeypatch):
        _pool, _conn, cur = _mock_pool(monkeypatch, fetchone=_plan_row())
        resp = client.post(
            "/api/v1/admin/plans",
            json={
                "slug": "novo-plano",
                "name": "Novo Plano",
                "max_users": 5,
                "module_features": {"epi": ["vms"]},
                "api_rate_per_minute": 60,
            },
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 201
        insert_sql = cur.execute.call_args_list[0][0][0]
        assert "max_users" in insert_sql
        assert "module_features" in insert_sql
        assert "api_rate_per_minute" in insert_sql

    def test_invalid_module_returns_400(self, app, client, monkeypatch):
        _mock_pool(monkeypatch)
        resp = client.post(
            "/api/v1/admin/plans",
            json={"slug": "novo", "name": "N", "modules_allowed": ["nao-existe"]},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400
        assert "Módulo inválido" in resp.get_json()["error"]


# ── PATCH /api/v1/admin/plans/<id> ───────────────────────────────────────────

class TestUpdatePlan:
    def test_nonexistent_plan_returns_404(self, app, client, monkeypatch):
        # Falha-antes/passa-depois: código antigo retornava {updated: true}
        _mock_pool(monkeypatch, fetchone=None)
        resp = client.patch(
            f"/api/v1/admin/plans/{uuid.uuid4()}",
            json={"name": "Fantasma"},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 404

    def test_update_persists_new_fields(self, app, client, monkeypatch):
        _pool, _conn, cur = _mock_pool(monkeypatch, fetchone={"id": PLAN_ID})
        resp = client.patch(
            f"/api/v1/admin/plans/{PLAN_ID}",
            json={
                "max_users": 5,
                "module_features": {"epi": ["vms"]},
                "api_rate_per_minute": 60,
            },
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 200
        executed = " ".join(str(c[0][0]) for c in cur.execute.call_args_list)
        assert "max_users" in executed
        assert "module_features" in executed
        assert "api_rate_per_minute" in executed

    def test_slug_is_immutable(self, app, client, monkeypatch):
        # slug fora do allowed: payload só com slug → 400 (nenhum campo válido)
        _mock_pool(monkeypatch, fetchone={"id": PLAN_ID})
        resp = client.patch(
            f"/api/v1/admin/plans/{PLAN_ID}",
            json={"slug": "novo-slug"},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400

    def test_slug_ignored_alongside_valid_fields(self, app, client, monkeypatch):
        _pool, _conn, cur = _mock_pool(monkeypatch, fetchone={"id": PLAN_ID})
        resp = client.patch(
            f"/api/v1/admin/plans/{PLAN_ID}",
            json={"slug": "novo-slug", "name": "Renomeado"},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 200
        updates = [str(c[0][0]) for c in cur.execute.call_args_list if "UPDATE" in str(c[0][0])]
        assert updates, "esperava ao menos um UPDATE"
        assert all("slug" not in q for q in updates)

    def test_invalid_module_features_returns_400(self, app, client, monkeypatch):
        _mock_pool(monkeypatch, fetchone={"id": PLAN_ID})
        resp = client.patch(
            f"/api/v1/admin/plans/{PLAN_ID}",
            json={"module_features": {"epi": ["nao-existe"]}},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400

    def test_negative_int_returns_400(self, app, client, monkeypatch):
        _mock_pool(monkeypatch, fetchone={"id": PLAN_ID})
        resp = client.patch(
            f"/api/v1/admin/plans/{PLAN_ID}",
            json={"max_cameras": -1},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400

    def test_max_users_null_means_unlimited(self, app, client, monkeypatch):
        _pool, _conn, cur = _mock_pool(monkeypatch, fetchone={"id": PLAN_ID})
        resp = client.patch(
            f"/api/v1/admin/plans/{PLAN_ID}",
            json={"max_users": None},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 200
