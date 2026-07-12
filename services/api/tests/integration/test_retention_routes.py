"""
Integration tests: retention endpoints (task-047).

Cobertura:
  GET /api/cameras/<id>/retention  — retenção efetiva da câmera
  PUT /api/cameras/<id>/retention  — atualizar tier (admin only)
  GET /api/v1/tenant/retention     — retenção padrão do tenant
  PUT /api/v1/tenant/retention     — atualizar padrão do tenant (admin only)

Estratégia: DatabasePool.get_instance() mockado (BaseRepository pattern para
camera_repository; context-manager pattern para routes diretas).
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
CAMERA_ID = str(uuid4())


# ---------------------------------------------------------------------------
# JWT fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "admin",
                "tenant_schema": "test_schema",
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "operator",
                "tenant_schema": "test_schema",
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _camera_row(retention_days=None):
    return {
        "id": CAMERA_ID,
        "tenant_id": TENANT_ID,
        "name": "Cam Test",
        "location": None,
        "retention_days": retention_days,
        "active_module": "epi",
        "schedule_rules": [],
        "site_id": None,
    }


def _mock_camera_pool(camera_row=None, update_ok=True):
    """Pool mock para CameraRepository (BaseRepository — cursor direto, não context manager)."""
    pool = MagicMock()
    conn = MagicMock()
    cur = conn.cursor.return_value  # BaseRepository: conn.cursor() direto

    # get_by_id_and_tenant → fetchone
    cur.fetchone.return_value = camera_row
    # update_retention_days → fetchone do RETURNING
    if update_ok:
        cur.fetchone.side_effect = [camera_row, {"id": CAMERA_ID}]
    else:
        cur.fetchone.side_effect = [None]

    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False
    return pool


def _mock_tenant_pool(plan_days=7, default_days=None, update_ok=True):
    """Pool mock para rotas diretas (context manager para cursor)."""
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()

    row = {"plan_days": plan_days, "default_retention_days": default_days,
           "effective_retention_days": default_days if default_days else plan_days,
           "days": default_days if default_days else plan_days}
    cur.fetchone.return_value = row if update_ok else None

    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False
    return pool


# ---------------------------------------------------------------------------
# GET /api/cameras/<id>/retention
# ---------------------------------------------------------------------------
class TestGetCameraRetention:

    def test_requires_jwt(self, client) -> None:
        res = client.get(f"/api/cameras/{CAMERA_ID}/retention")
        assert res.status_code in (401, 422)

    def test_camera_not_found_returns_404(self, client, operator_headers) -> None:
        pool = _mock_camera_pool(camera_row=None, update_ok=False)
        with (
            patch("app.api.v1.cameras.retention_handler.DatabasePool.get_instance",
                  return_value=pool),
        ):
            res = client.get(f"/api/cameras/{CAMERA_ID}/retention", headers=operator_headers)
        assert res.status_code == 404

    def test_returns_effective_retention_with_camera_override(self, client, operator_headers) -> None:
        cam = _camera_row(retention_days=30)

        # Side effects: first call get_by_id_and_tenant, second call _get_tenant_default
        # We need two different pool contexts
        conn = MagicMock()
        cur_ctx = MagicMock()
        cur_ctx.fetchone.return_value = {"days": 7}
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur_ctx)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Camera repo pool (direct cursor)
        cam_pool = MagicMock()
        cam_conn = MagicMock()
        cam_cur = cam_conn.cursor.return_value
        cam_cur.fetchone.return_value = cam
        cam_pool.get_connection.return_value.__enter__.return_value = cam_conn
        cam_pool.get_connection.return_value.__exit__.return_value = False

        with patch(
            "app.api.v1.cameras.retention_handler.DatabasePool.get_instance",
            return_value=cam_pool,
        ):
            res = client.get(f"/api/cameras/{CAMERA_ID}/retention", headers=operator_headers)

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["retention_days"] == 30
        assert data["data"]["effective_days"] == 30
        assert set(data["data"]["allowed_tiers"]) == {1, 7, 30, 90}

    def test_returns_allowed_tiers(self, client, operator_headers) -> None:
        cam = _camera_row(retention_days=None)
        cam_pool = MagicMock()
        cam_conn = MagicMock()
        cam_cur = cam_conn.cursor.return_value
        cam_cur.fetchone.return_value = cam
        cam_pool.get_connection.return_value.__enter__.return_value = cam_conn
        cam_pool.get_connection.return_value.__exit__.return_value = False

        with patch(
            "app.api.v1.cameras.retention_handler.DatabasePool.get_instance",
            return_value=cam_pool,
        ):
            res = client.get(f"/api/cameras/{CAMERA_ID}/retention", headers=operator_headers)

        assert res.status_code == 200
        tiers = res.get_json()["data"]["allowed_tiers"]
        assert tiers == [1, 7, 30, 90]


# ---------------------------------------------------------------------------
# PUT /api/cameras/<id>/retention
# ---------------------------------------------------------------------------
class TestPutCameraRetention:

    def test_requires_jwt(self, client) -> None:
        res = client.put(f"/api/cameras/{CAMERA_ID}/retention", json={"retention_days": 7})
        assert res.status_code in (401, 422)

    def test_operator_forbidden(self, client, operator_headers) -> None:
        res = client.put(
            f"/api/cameras/{CAMERA_ID}/retention",
            json={"retention_days": 7},
            headers=operator_headers,
        )
        assert res.status_code == 403

    def test_invalid_tier_returns_422(self, client, admin_headers) -> None:
        cam_pool = MagicMock()
        cam_conn = MagicMock()
        cam_cur = cam_conn.cursor.return_value
        cam_cur.fetchone.return_value = _camera_row()
        cam_pool.get_connection.return_value.__enter__.return_value = cam_conn
        cam_pool.get_connection.return_value.__exit__.return_value = False

        with patch(
            "app.api.v1.cameras.retention_handler.DatabasePool.get_instance",
            return_value=cam_pool,
        ):
            res = client.put(
                f"/api/cameras/{CAMERA_ID}/retention",
                json={"retention_days": 15},
                headers=admin_headers,
            )
        assert res.status_code == 422

    def test_valid_tier_updates_camera(self, client, admin_headers) -> None:
        cam_pool = MagicMock()
        cam_conn = MagicMock()
        cam_cur = cam_conn.cursor.return_value
        cam_cur.fetchone.side_effect = [_camera_row(), {"id": CAMERA_ID}]
        cam_pool.get_connection.return_value.__enter__.return_value = cam_conn
        cam_pool.get_connection.return_value.__exit__.return_value = False

        with patch(
            "app.api.v1.cameras.retention_handler.DatabasePool.get_instance",
            return_value=cam_pool,
        ):
            res = client.put(
                f"/api/cameras/{CAMERA_ID}/retention",
                json={"retention_days": 30},
                headers=admin_headers,
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["retention_days"] == 30

    def test_reset_to_null_inherits_tenant(self, client, admin_headers) -> None:
        """retention_days=null → câmera herda do tenant."""
        cam_pool = MagicMock()
        cam_conn = MagicMock()
        cam_cur = cam_conn.cursor.return_value
        cam_cur.fetchone.side_effect = [_camera_row(retention_days=30), {"id": CAMERA_ID}]
        cam_pool.get_connection.return_value.__enter__.return_value = cam_conn
        cam_pool.get_connection.return_value.__exit__.return_value = False

        with patch(
            "app.api.v1.cameras.retention_handler.DatabasePool.get_instance",
            return_value=cam_pool,
        ):
            res = client.put(
                f"/api/cameras/{CAMERA_ID}/retention",
                json={"retention_days": None},
                headers=admin_headers,
            )
        assert res.status_code == 200
        assert res.get_json()["data"]["retention_days"] is None

    def test_camera_not_found_returns_404(self, client, admin_headers) -> None:
        cam_pool = MagicMock()
        cam_conn = MagicMock()
        cam_cur = cam_conn.cursor.return_value
        cam_cur.fetchone.return_value = None
        cam_pool.get_connection.return_value.__enter__.return_value = cam_conn
        cam_pool.get_connection.return_value.__exit__.return_value = False

        with patch(
            "app.api.v1.cameras.retention_handler.DatabasePool.get_instance",
            return_value=cam_pool,
        ):
            res = client.put(
                f"/api/cameras/{CAMERA_ID}/retention",
                json={"retention_days": 7},
                headers=admin_headers,
            )
        assert res.status_code == 404

    @pytest.mark.parametrize("tier", [1, 7, 30, 90])
    def test_all_allowed_tiers(self, client, admin_headers, tier) -> None:
        cam_pool = MagicMock()
        cam_conn = MagicMock()
        cam_cur = cam_conn.cursor.return_value
        cam_cur.fetchone.side_effect = [_camera_row(), {"id": CAMERA_ID}]
        cam_pool.get_connection.return_value.__enter__.return_value = cam_conn
        cam_pool.get_connection.return_value.__exit__.return_value = False

        with patch(
            "app.api.v1.cameras.retention_handler.DatabasePool.get_instance",
            return_value=cam_pool,
        ):
            res = client.put(
                f"/api/cameras/{CAMERA_ID}/retention",
                json={"retention_days": tier},
                headers=admin_headers,
            )
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/tenant/retention
# ---------------------------------------------------------------------------
class TestGetTenantRetention:

    def test_requires_jwt(self, client) -> None:
        res = client.get("/api/v1/tenant/retention")
        assert res.status_code in (401, 422)

    def test_returns_plan_default_when_no_override(self, client, operator_headers) -> None:
        pool = _mock_tenant_pool(plan_days=7, default_days=None)
        with patch("app.api.v1.retention.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/v1/tenant/retention", headers=operator_headers)
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["default_retention_days"] is None
        assert data["plan_retention_days"] == 7

    def test_returns_tenant_override_when_set(self, client, operator_headers) -> None:
        pool = _mock_tenant_pool(plan_days=7, default_days=30)
        with patch("app.api.v1.retention.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/v1/tenant/retention", headers=operator_headers)
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["default_retention_days"] == 30
        assert data["effective_retention_days"] == 30

    def test_returns_allowed_tiers(self, client, operator_headers) -> None:
        pool = _mock_tenant_pool()
        with patch("app.api.v1.retention.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/v1/tenant/retention", headers=operator_headers)
        assert res.status_code == 200
        assert res.get_json()["data"]["allowed_tiers"] == [1, 7, 30, 90]


# ---------------------------------------------------------------------------
# PUT /api/v1/tenant/retention
# ---------------------------------------------------------------------------
class TestPutTenantRetention:

    def test_requires_jwt(self, client) -> None:
        res = client.put("/api/v1/tenant/retention", json={"default_retention_days": 7})
        assert res.status_code in (401, 422)

    def test_operator_forbidden(self, client, operator_headers) -> None:
        res = client.put(
            "/api/v1/tenant/retention",
            json={"default_retention_days": 7},
            headers=operator_headers,
        )
        assert res.status_code == 403

    def test_invalid_tier_returns_422(self, client, admin_headers) -> None:
        pool = _mock_tenant_pool()
        with patch("app.api.v1.retention.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/tenant/retention",
                json={"default_retention_days": 14},
                headers=admin_headers,
            )
        assert res.status_code == 422

    def test_missing_field_returns_422(self, client, admin_headers) -> None:
        pool = _mock_tenant_pool()
        with patch("app.api.v1.retention.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put("/api/v1/tenant/retention", json={}, headers=admin_headers)
        assert res.status_code == 422

    @pytest.mark.parametrize("days", [1, 7, 30, 90])
    def test_all_allowed_tiers_accepted(self, client, admin_headers, days) -> None:
        pool = _mock_tenant_pool(update_ok=True)
        with patch("app.api.v1.retention.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/tenant/retention",
                json={"default_retention_days": days},
                headers=admin_headers,
            )
        assert res.status_code == 200
        assert res.get_json()["data"]["default_retention_days"] == days

    def test_tenant_isolation(self, client, admin_headers) -> None:
        """tenant_id no UPDATE vem sempre do JWT — nunca do body."""
        pool = _mock_tenant_pool()
        with patch("app.api.v1.retention.routes.DatabasePool.get_instance", return_value=pool):
            res = client.put(
                "/api/v1/tenant/retention",
                json={"default_retention_days": 7, "tenant_id": str(uuid4())},
                headers=admin_headers,
            )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["tenant_id"] == TENANT_ID
