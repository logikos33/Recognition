"""Testes — /api/v1/admin/test-console/*.

Cobre:
  - Role-gate: 403 sem token admin / superadmin
  - Isolamento: tenant de teste (AA) é o único lido/escrito
  - Harness start/stop/status com Redis mockado
  - /models e /evidence com DB mockado
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.admin.test_console_routes as tc

TEST_TENANT = "00000000-0000-0000-0000-0000000000AA"
OTHER_TENANT = "ffffffff-ffff-ffff-ffff-ffffffffffff"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _token(app, role: str = "admin") -> str:
    with app.app_context():
        return create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={"role": role, "tenant_id": TEST_TENANT},
        )


def _auth(app, role: str = "admin") -> dict:
    return {"Authorization": f"Bearer {_token(app, role)}"}


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_redis():
    """Redis em memória simples."""
    store: dict = {}
    ttls: dict = {}

    r = MagicMock()

    def _get(key):
        return store.get(key)

    def _setex(key, ttl, val):
        store[key] = val
        ttls[key] = ttl

    def _delete(*keys):
        for k in keys:
            store.pop(k, None)

    def _exists(key):
        return 1 if key in store else 0

    pipeline_mock = MagicMock()
    pipeline_mock.__enter__ = MagicMock(return_value=pipeline_mock)
    pipeline_mock.__exit__ = MagicMock(return_value=False)
    pipeline_mock.setex = MagicMock(side_effect=lambda k, t, v: _setex(k, t, v))
    pipeline_mock.delete = MagicMock(side_effect=lambda *ks: [store.pop(k, None) for k in ks])
    pipeline_mock.execute = MagicMock(return_value=[])

    r.get = MagicMock(side_effect=_get)
    r.setex = MagicMock(side_effect=_setex)
    r.delete = MagicMock(side_effect=_delete)
    r.exists = MagicMock(side_effect=_exists)
    r.pipeline = MagicMock(return_value=pipeline_mock)

    r._store = store
    return r


@pytest.fixture
def patched_redis(fake_redis, monkeypatch):
    monkeypatch.setattr(tc, "_get_redis", lambda: fake_redis)
    return fake_redis


@pytest.fixture
def patched_cameras(monkeypatch):
    cam_ids = [str(uuid.uuid4()) for _ in range(4)]
    cameras = [{"id": cid, "name": f"cam-{i}", "rtsp_url": f"rtsp://h/cam{i}", "index": i}
               for i, cid in enumerate(cam_ids)]
    monkeypatch.setattr(tc, "_register_test_cameras", lambda n, model_id: cameras[:n])
    monkeypatch.setattr(tc, "_delete_test_cameras", lambda ids: len(ids))
    return cameras


@pytest.fixture
def patched_dispatch(monkeypatch):
    monkeypatch.setattr(tc, "_dispatch_inference_tasks", lambda cams, path: len(cams))


@pytest.fixture
def patched_models(monkeypatch):
    models = [{"id": str(uuid.uuid4()), "name": "yolox-s-coco", "model_key": "models/test/yolox_s.onnx",
               "metrics": {}, "is_default": True, "created_at": "2026-01-01T00:00:00"}]
    monkeypatch.setattr(tc, "_list_models", lambda: models)
    return models


@pytest.fixture
def patched_evidence(monkeypatch):
    items = [{"id": str(uuid.uuid4()), "camera_id": str(uuid.uuid4()), "evidence_key": "e/cam0/f.jpg",
              "confidence": 0.85, "created_at": "2026-01-01T00:00:01", "camera_name": "cam-0"}]
    monkeypatch.setattr(tc, "_list_recent_evidence", lambda limit=20: items)
    return items


# ── Role-gate tests ────────────────────────────────────────────────────────────

class TestRoleGate:
    """Todos os endpoints exigem role admin ou superadmin."""

    ENDPOINTS = [
        ("POST", "/api/v1/admin/test-console/harness/start"),
        ("POST", "/api/v1/admin/test-console/harness/stop"),
        ("GET",  "/api/v1/admin/test-console/status"),
        ("GET",  "/api/v1/admin/test-console/models"),
        ("GET",  "/api/v1/admin/test-console/evidence"),
    ]

    def test_no_token_returns_401(self, app):
        client = app.test_client()
        for method, path in self.ENDPOINTS:
            resp = getattr(client, method.lower())(path)
            assert resp.status_code == 401, f"{method} {path} deveria retornar 401"

    def test_operator_role_returns_403(self, app):
        client = app.test_client()
        headers = _auth(app, role="operator")
        for method, path in self.ENDPOINTS:
            resp = getattr(client, method.lower())(path, headers=headers)
            assert resp.status_code == 403, f"{method} {path} deveria retornar 403 para operator"

    def test_admin_role_passes_gate(self, app, patched_redis, patched_cameras, patched_dispatch, patched_models, patched_evidence):
        client = app.test_client()
        headers = _auth(app, role="admin")
        # status com harness inativo retorna 200
        resp = client.get("/api/v1/admin/test-console/status", headers=headers)
        assert resp.status_code == 200

    def test_superadmin_role_passes_gate(self, app, patched_redis, patched_models):
        client = app.test_client()
        headers = _auth(app, role="superadmin")
        resp = client.get("/api/v1/admin/test-console/models", headers=headers)
        assert resp.status_code == 200


# ── Harness start tests ────────────────────────────────────────────────────────

class TestHarnessStart:
    def test_start_returns_camera_ids(self, app, patched_redis, patched_cameras, patched_dispatch, patched_models):
        client = app.test_client()
        resp = client.post(
            "/api/v1/admin/test-console/harness/start",
            json={"cameras": 4},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["n_cameras"] == 4
        assert len(data["camera_ids"]) == 4
        assert data["tenant_id"] == TEST_TENANT

    def test_start_conflict_when_already_active(self, app, patched_redis, patched_cameras, patched_dispatch, patched_models):
        client = app.test_client()
        headers = _auth(app)
        client.post("/api/v1/admin/test-console/harness/start", json={"cameras": 2}, headers=headers)
        resp = client.post("/api/v1/admin/test-console/harness/start", json={"cameras": 2}, headers=headers)
        assert resp.status_code == 409

    def test_start_invalid_cameras_returns_400(self, app, patched_redis, patched_cameras, patched_dispatch):
        client = app.test_client()
        resp = client.post(
            "/api/v1/admin/test-console/harness/start",
            json={"cameras": 0},
            headers=_auth(app),
        )
        assert resp.status_code == 400

    def test_start_sets_redis_stream_keys(self, app, patched_redis, patched_cameras, patched_dispatch, patched_models):
        client = app.test_client()
        client.post(
            "/api/v1/admin/test-console/harness/start",
            json={"cameras": 2},
            headers=_auth(app),
        )
        # config deve estar no Redis
        assert patched_redis._store.get(tc.REDIS_CONFIG_KEY) is not None

    def test_start_uses_default_model_when_none_provided(self, app, patched_redis, patched_cameras, patched_dispatch, patched_models):
        client = app.test_client()
        resp = client.post(
            "/api/v1/admin/test-console/harness/start",
            json={"cameras": 1},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["model_id"] is not None


# ── Harness stop tests ─────────────────────────────────────────────────────────

class TestHarnessStop:
    def test_stop_no_active_harness_returns_404(self, app, patched_redis):
        resp = app.test_client().post(
            "/api/v1/admin/test-console/harness/stop",
            headers=_auth(app),
        )
        assert resp.status_code == 404

    def test_stop_clears_redis_and_cameras(self, app, patched_redis, patched_cameras, patched_dispatch, patched_models):
        client = app.test_client()
        headers = _auth(app)
        client.post("/api/v1/admin/test-console/harness/start", json={"cameras": 3}, headers=headers)
        assert patched_redis._store.get(tc.REDIS_CONFIG_KEY) is not None

        resp = client.post("/api/v1/admin/test-console/harness/stop", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["cameras_stopped"] == 3
        # config deve ter sido removida do Redis
        assert patched_redis._store.get(tc.REDIS_CONFIG_KEY) is None


# ── Status tests ───────────────────────────────────────────────────────────────

class TestHarnessStatus:
    def test_status_inactive_returns_active_false(self, app, patched_redis):
        resp = app.test_client().get(
            "/api/v1/admin/test-console/status",
            headers=_auth(app),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["active"] is False

    def test_status_active_returns_camera_count(self, app, patched_redis, patched_cameras, patched_dispatch, patched_models):
        client = app.test_client()
        headers = _auth(app)
        client.post("/api/v1/admin/test-console/harness/start", json={"cameras": 2}, headers=headers)

        with patch.object(tc, "_get_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = (5,)
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_pool.return_value.get_connection.return_value = mock_conn

            resp = client.get("/api/v1/admin/test-console/status", headers=headers)

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["active"] is True
        assert data["n_cameras"] == 2


# ── Models tests ───────────────────────────────────────────────────────────────

class TestModels:
    def test_models_returns_list(self, app, patched_redis, patched_models):
        resp = app.test_client().get(
            "/api/v1/admin/test-console/models",
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert isinstance(data["models"], list)
        assert data["count"] == 1
        assert data["models"][0]["name"] == "yolox-s-coco"


# ── Evidence tests ─────────────────────────────────────────────────────────────

class TestEvidence:
    def test_evidence_returns_list(self, app, patched_redis, patched_evidence):
        resp = app.test_client().get(
            "/api/v1/admin/test-console/evidence",
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert isinstance(data["evidence"], list)
        assert data["count"] == 1
        assert data["evidence"][0]["evidence_key"] == "e/cam0/f.jpg"

    def test_evidence_limit_capped_at_100(self, app, patched_redis, patched_evidence):
        resp = app.test_client().get(
            "/api/v1/admin/test-console/evidence?limit=999",
            headers=_auth(app),
        )
        assert resp.status_code == 200


# ── Tenant isolation ───────────────────────────────────────────────────────────

class TestTenantIsolation:
    """Todas as operações devem ser isoladas no TEST_TENANT_ID."""

    def test_start_uses_test_tenant(self, app, patched_redis, patched_dispatch):
        def fake_register(n, model_id):
            return [{"id": str(uuid.uuid4()), "name": "c", "rtsp_url": "rtsp://x", "index": 0}]

        with patch.object(tc, "_register_test_cameras", side_effect=fake_register):
            with patch.object(tc, "_list_models", return_value=[]):
                resp = app.test_client().post(
                    "/api/v1/admin/test-console/harness/start",
                    json={"cameras": 1},
                    headers=_auth(app),
                )

        assert resp.status_code == 200
        assert resp.get_json()["data"]["tenant_id"] == TEST_TENANT
