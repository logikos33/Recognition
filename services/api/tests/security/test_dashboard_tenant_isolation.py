"""
Regression tests — BUG-5/BUG-6 (mutirão WS3): vazamento cross-tenant no dashboard.

FALHA antes do fix:
  - GET /api/v1/dashboard/stats      — nenhuma query filtrava tenant_id
  - GET /api/v1/dashboard/detections — contagem global de alertas
  - GET /api/v1/reports/export       — exportava alertas de todos os tenants
  - GET /api/alerts/stats            — count_by_camera/get_unacknowledged sem tenant

PASSA após o fix: toda query executada por essas rotas inclui o tenant_id
extraído do JWT (via get_tenant_id) como parâmetro SQL (%s) — nunca interpolado.

Estratégia: DatabasePool mockado; inspecionamos cada cursor.execute() e
exigimos que (a) o SQL mencione tenant_id e (b) o tenant do JWT esteja nos params.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_A = str(uuid4())
TENANT_B = str(uuid4())
CAM_ID = str(uuid4())


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_headers(app, tenant_id: str) -> dict:
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "role": "admin",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def tenant_a_headers(app):
    return _make_headers(app, TENANT_A)


def _mock_pool(fetchone=None, fetchall=None):
    """Pool mockado: fetchone/fetchall fixos para todas as queries."""
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = fetchone if fetchone is not None else {"total": 0, "count": 0}
    cur.fetchall.return_value = fetchall if fetchall is not None else []
    conn.cursor.return_value = cur
    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False
    return pool, cur


def _assert_all_executes_tenant_scoped(cur, tenant_id: str) -> None:
    """Toda query executada deve filtrar por tenant_id com o valor do JWT nos params."""
    calls = cur.execute.call_args_list
    assert len(calls) >= 1, "Nenhuma query executada — rota não chegou ao banco"
    for call in calls:
        args = call[0]
        sql = args[0]
        assert "tenant_id" in sql.lower(), (
            f"Cross-tenant leak: SQL sem filtro tenant_id → {sql[:120]!r}"
        )
        assert len(args) >= 2, (
            f"Cross-tenant leak: SQL executado sem params (tenant não passado) → {sql[:120]!r}"
        )
        params = args[1]
        assert tenant_id in [str(p) for p in params], (
            f"Cross-tenant leak: tenant do JWT ausente nos params → {sql[:120]!r}"
        )


_DASH_POOL = "app.api.v1.dashboard.routes.DatabasePool.get_instance"
_ALERTS_POOL = "app.api.v1.alerts.routes.DatabasePool.get_instance"


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/stats (BUG-5)
# ---------------------------------------------------------------------------
class TestDashboardStatsTenantIsolation:

    def test_requires_jwt(self, client) -> None:
        res = client.get("/api/v1/dashboard/stats")
        assert res.status_code in (401, 422)

    def test_all_queries_tenant_scoped(self, client, tenant_a_headers) -> None:
        """FALHA antes do fix (queries globais). PASSA após: tenant em toda query."""
        pool, cur = _mock_pool(fetchone={"total": 0})
        with patch(_DASH_POOL, return_value=pool):
            res = client.get("/api/v1/dashboard/stats", headers=tenant_a_headers)

        assert res.status_code == 200
        _assert_all_executes_tenant_scoped(cur, TENANT_A)

    def test_tenant_b_never_appears_in_params(self, client, tenant_a_headers) -> None:
        """Token do tenant A jamais produz queries com tenant B."""
        pool, cur = _mock_pool(fetchone={"total": 0})
        with patch(_DASH_POOL, return_value=pool):
            client.get("/api/v1/dashboard/stats", headers=tenant_a_headers)

        for call in cur.execute.call_args_list:
            params = call[0][1] if len(call[0]) >= 2 else ()
            assert TENANT_B not in [str(p) for p in params]


# ---------------------------------------------------------------------------
# GET /api/v1/dashboard/detections (BUG-5)
# ---------------------------------------------------------------------------
class TestDashboardDetectionsTenantIsolation:

    def test_requires_jwt(self, client) -> None:
        res = client.get("/api/v1/dashboard/detections")
        assert res.status_code in (401, 422)

    def test_query_tenant_scoped(self, client, tenant_a_headers) -> None:
        """FALHA antes do fix (alerts globais por dia). PASSA após o fix."""
        pool, cur = _mock_pool(fetchall=[])
        with patch(_DASH_POOL, return_value=pool):
            res = client.get(
                "/api/v1/dashboard/detections?days=30", headers=tenant_a_headers
            )

        assert res.status_code == 200
        _assert_all_executes_tenant_scoped(cur, TENANT_A)


# ---------------------------------------------------------------------------
# GET /api/v1/reports/export (BUG-5)
# ---------------------------------------------------------------------------
class TestReportsExportTenantIsolation:

    def test_requires_jwt(self, client) -> None:
        res = client.get("/api/v1/reports/export")
        assert res.status_code in (401, 422)

    def test_query_tenant_scoped(self, client, tenant_a_headers) -> None:
        """FALHA antes do fix (xlsx com alertas de todos os tenants). PASSA após."""
        pool, cur = _mock_pool(fetchall=[])
        with patch(_DASH_POOL, return_value=pool):
            res = client.get("/api/v1/reports/export?days=7", headers=tenant_a_headers)

        assert res.status_code == 200
        _assert_all_executes_tenant_scoped(cur, TENANT_A)


# ---------------------------------------------------------------------------
# GET /api/alerts/stats (BUG-6)
# ---------------------------------------------------------------------------
class TestAlertStatsTenantIsolation:

    def test_requires_jwt(self, client) -> None:
        res = client.get("/api/alerts/stats")
        assert res.status_code in (401, 422)

    def test_unacknowledged_tenant_scoped(self, client, tenant_a_headers) -> None:
        """FALHA antes do fix (get_unacknowledged global). PASSA após o fix."""
        pool, cur = _mock_pool(fetchall=[])
        with patch(_ALERTS_POOL, return_value=pool):
            res = client.get("/api/alerts/stats", headers=tenant_a_headers)

        assert res.status_code == 200
        _assert_all_executes_tenant_scoped(cur, TENANT_A)

    def test_count_by_camera_tenant_scoped(self, client, tenant_a_headers) -> None:
        """FALHA antes do fix (count_by_camera sem tenant). PASSA após o fix."""
        pool, cur = _mock_pool(fetchone={"count": 0}, fetchall=[])
        with patch(_ALERTS_POOL, return_value=pool):
            res = client.get(
                f"/api/alerts/stats?camera_id={CAM_ID}", headers=tenant_a_headers
            )

        assert res.status_code == 200
        _assert_all_executes_tenant_scoped(cur, TENANT_A)
