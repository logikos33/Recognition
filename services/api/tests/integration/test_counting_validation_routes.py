"""
Integration tests: rotas de validação/aceite CD-07 (task-057).

Cobertura:
  PATCH /api/counting/sessions/<id>            — atualização parcial (manual_count, acceptance_status...)
  GET   /api/counting/sessions/validation-report — relatório sistema vs manual

Contexto (bug P0 corrigido): apps/frontend/src/pages/fueling/FuelingValidationPage.tsx
chamava esses dois endpoints via countingService.ts, mas nenhum existia em
counting/routes.py — a tela de validação de abastecimento retornava 404/405 em
produção. O domain service (CountingService.update_session /
get_validation_report) e o whitelist do repository já existiam e já tinham
cobertura unitária (tests/unit/domain/test_counting_loading_sessions.py);
faltava só a rota Flask + as queries SQL reais no repository
(get_validation_sessions / get_validation_daily).

Estratégia idêntica à dos testes de LPR (test_counting_plate_routes.py):
  - DatabasePool.get_instance() mockado
  - JWT com additional_claims (tenant_id, role)
  - success() → {"success": True, "data": {...}}
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
SESSION_ID = str(uuid4())


@pytest.fixture
def operator_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "operator",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_pool(fetchone_returns=None, fetchall_returns=None):
    """
    BaseRepository usa `conn.cursor()` diretamente (não como context manager);
    apenas `get_connection()` é um context manager.
    """
    pool = MagicMock()
    conn = MagicMock()
    cur = conn.cursor.return_value

    cur.fetchone.return_value = fetchone_returns
    cur.fetchall.return_value = fetchall_returns or []

    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False

    return pool, cur


def _session_row(**overrides):
    row = {
        "id": SESSION_ID,
        "tenant_id": TENANT_ID,
        "camera_id": str(uuid4()),
        "module_code": "fueling",
        "status": "stopped",
        "manual_count": 10,
        "acceptance_status": "pending",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# PATCH /api/counting/sessions/<id>
# ---------------------------------------------------------------------------
class TestUpdateSession:

    def test_requires_jwt(self, client) -> None:
        res = client.patch(f"/api/counting/sessions/{SESSION_ID}")
        assert res.status_code in (401, 422)

    def test_empty_body_returns_400(self, client, operator_headers) -> None:
        pool, _ = _mock_pool()
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}",
                json={},
                headers=operator_headers,
            )
        assert res.status_code == 400

    def test_updates_manual_count(self, client, operator_headers) -> None:
        """Regressão: era 404 (rota inexistente) antes deste fix."""
        session_row = _session_row()
        pool, cur = _mock_pool(fetchone_returns=session_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}",
                json={"manual_count": 12},
                headers=operator_headers,
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["session"]["manual_count"] == 10  # eco da row mockada (get_session)

    def test_updates_acceptance_status(self, client, operator_headers) -> None:
        session_row = _session_row(acceptance_status="accepted")
        pool, _ = _mock_pool(fetchone_returns=session_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}",
                json={"acceptance_status": "accepted"},
                headers=operator_headers,
            )
        assert res.status_code == 200
        assert res.get_json()["data"]["session"]["acceptance_status"] == "accepted"

    def test_invalid_acceptance_status_returns_400(self, client, operator_headers) -> None:
        session_row = _session_row()
        pool, _ = _mock_pool(fetchone_returns=session_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}",
                json={"acceptance_status": "maybe"},
                headers=operator_headers,
            )
        assert res.status_code == 400

    def test_negative_manual_count_returns_400(self, client, operator_headers) -> None:
        session_row = _session_row()
        pool, _ = _mock_pool(fetchone_returns=session_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}",
                json={"manual_count": -5},
                headers=operator_headers,
            )
        assert res.status_code == 400

    def test_session_not_found_returns_404(self, client, operator_headers) -> None:
        pool, _ = _mock_pool(fetchone_returns=None)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}",
                json={"manual_count": 5},
                headers=operator_headers,
            )
        assert res.status_code == 404

    def test_invalid_session_id_returns_400(self, client, operator_headers) -> None:
        pool, _ = _mock_pool()
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                "/api/counting/sessions/not-a-uuid",
                json={"manual_count": 5},
                headers=operator_headers,
            )
        assert res.status_code == 400

    def test_unknown_field_returns_400(self, client, operator_headers) -> None:
        session_row = _session_row()
        pool, _ = _mock_pool(fetchone_returns=session_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}",
                json={"status": "stopped"},
                headers=operator_headers,
            )
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/counting/sessions/validation-report
# ---------------------------------------------------------------------------
class TestValidationReport:

    def test_requires_jwt(self, client) -> None:
        res = client.get("/api/counting/sessions/validation-report")
        assert res.status_code in (401, 422)

    def test_empty_period_returns_empty_report(self, client, operator_headers) -> None:
        """Regressão: era 404 (rota inexistente) antes deste fix."""
        pool, _ = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                "/api/counting/sessions/validation-report",
                headers=operator_headers,
            )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["summary"]["sessions_validated"] == 0
        assert data["sessions"] == []
        assert data["daily"] == []
        assert data["threshold_pct"] == 5.0
        assert "period" in data

    def test_default_threshold_and_period_shape(self, client, operator_headers) -> None:
        pool, _ = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                "/api/counting/sessions/validation-report",
                headers=operator_headers,
            )
        data = res.get_json()["data"]
        assert set(data["period"].keys()) == {"start", "end"}

    def test_custom_threshold_and_dates(self, client, operator_headers) -> None:
        pool, _ = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                "/api/counting/sessions/validation-report"
                "?start=2026-06-01&end=2026-06-08&threshold=2.5",
                headers=operator_headers,
            )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["threshold_pct"] == 2.5

    def test_invalid_date_returns_400(self, client, operator_headers) -> None:
        pool, _ = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                "/api/counting/sessions/validation-report?start=not-a-date",
                headers=operator_headers,
            )
        assert res.status_code == 400

    def test_invalid_bay_id_returns_400(self, client, operator_headers) -> None:
        pool, _ = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                "/api/counting/sessions/validation-report?bay_id=not-a-uuid",
                headers=operator_headers,
            )
        assert res.status_code == 400

    def test_negative_threshold_returns_400(self, client, operator_headers) -> None:
        pool, _ = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                "/api/counting/sessions/validation-report?threshold=-1",
                headers=operator_headers,
            )
        assert res.status_code == 400

    def test_tenant_isolation(self, client, operator_headers) -> None:
        """tenant_id no SQL vem sempre do JWT — nunca de query param."""
        pool, cur = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                "/api/counting/sessions/validation-report",
                headers=operator_headers,
            )
        assert res.status_code == 200
        assert cur.execute.called
        all_params = [c[0][1] for c in cur.execute.call_args_list]
        assert any(TENANT_ID in p for p in all_params)
