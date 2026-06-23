"""
Integration tests: LPR plate endpoints (task-050).

Cobertura:
  PATCH /api/counting/sessions/<id>/plate  — registrar/corrigir placa
  GET   /api/counting/sessions/plates      — listar sessões com placa

Estratégia idêntica à dos testes de branding/events:
  - DatabasePool.get_instance() mockado
  - JWT com additional_claims (tenant_id, role)
  - success() → {"success": True, "data": {...}}
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_row(plate_text=None, plate_confidence=None, plate_review=False, plate_manual=False):
    return {
        "id": str(uuid4()),
        "tenant_id": TENANT_ID,
        "camera_id": str(uuid4()),
        "module_code": "fueling",
        "status": "running",
        "plate_text": plate_text,
        "plate_confidence": plate_confidence,
        "plate_review": plate_review,
        "plate_manual": plate_manual,
        "started_at": "2025-06-01T14:00:00+00:00",
        "ended_at": None,
    }


def _mock_pool(update_returns=None, fetchall_returns=None):
    """
    Cria mock para DatabasePool compatível com BaseRepository.

    BaseRepository usa `conn.cursor()` DIRETAMENTE (não como context manager),
    portanto configuramos `conn.cursor.return_value` — não `__enter__`.
    Apenas `get_connection()` é um context manager.

    Retorna (pool, cur) para que os testes possam inspecionar cur.execute.
    """
    pool = MagicMock()
    conn = MagicMock()
    # cur É o objeto retornado por conn.cursor() (chamada direta)
    cur = conn.cursor.return_value

    cur.fetchone.return_value = update_returns
    cur.fetchall.return_value = fetchall_returns or []

    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False

    return pool, cur


# ---------------------------------------------------------------------------
# PATCH /api/counting/sessions/<id>/plate
# ---------------------------------------------------------------------------
class TestUpdatePlate:

    def test_requires_jwt(self, client) -> None:
        res = client.patch(f"/api/counting/sessions/{SESSION_ID}/plate")
        assert res.status_code in (401, 422)

    def test_missing_plate_text_returns_400(self, client, operator_headers) -> None:
        pool, _ = _mock_pool()
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={},
                headers=operator_headers,
            )
        assert res.status_code == 400

    def test_invalid_plate_format_returns_422(self, client, operator_headers) -> None:
        """Texto que não é placa → 422."""
        pool, _ = _mock_pool()
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={"plate_text": "NOTAPLATE123"},
                headers=operator_headers,
            )
        assert res.status_code == 422

    def test_valid_mercosul_plate_manual_correction(self, client, operator_headers) -> None:
        """Placa Mercosul sem plate_confidence → correção manual."""
        updated_row = _make_session_row("ABC1D23", None, False, True)
        pool, _ = _mock_pool(update_returns=updated_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={"plate_text": "ABC1D23"},
                headers=operator_headers,
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["plate_text"] == "ABC1D23"
        assert data["data"]["plate_manual"] is True
        assert data["data"]["plate_format"] == "mercosul"

    def test_valid_old_format_plate(self, client, operator_headers) -> None:
        """Placa antiga (ABC1234) é aceita."""
        updated_row = _make_session_row("ABC1234", None, False, True)
        pool, _ = _mock_pool(update_returns=updated_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={"plate_text": "ABC1234"},
                headers=operator_headers,
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["plate_format"] == "antiga"

    def test_high_confidence_no_review(self, client, operator_headers) -> None:
        """Confiança >= 0.80 → plate_review=False."""
        updated_row = _make_session_row("ABC1234", 0.92, False, False)
        pool, _ = _mock_pool(update_returns=updated_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={"plate_text": "ABC1234", "plate_confidence": 0.92},
                headers=operator_headers,
            )
        assert res.status_code == 200
        assert res.get_json()["data"]["plate_review"] is False

    def test_low_confidence_triggers_review(self, client, operator_headers) -> None:
        """Confiança < 0.80 → plate_review=True."""
        updated_row = _make_session_row("ABC1234", 0.70, True, False)
        pool, _ = _mock_pool(update_returns=updated_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={"plate_text": "ABC1234", "plate_confidence": 0.70},
                headers=operator_headers,
            )
        assert res.status_code == 200
        assert res.get_json()["data"]["plate_review"] is True

    def test_session_not_found_returns_404(self, client, operator_headers) -> None:
        """update_plate retorna None (tenant não bate) → 404."""
        pool, _ = _mock_pool(update_returns=None)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={"plate_text": "ABC1234"},
                headers=operator_headers,
            )
        assert res.status_code == 404

    def test_lowercase_plate_normalized(self, client, operator_headers) -> None:
        """Placa em minúsculas é normalizada para maiúsculas."""
        updated_row = _make_session_row("ABC1234", None, False, True)
        pool, _ = _mock_pool(update_returns=updated_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={"plate_text": "abc1234"},
                headers=operator_headers,
            )
        assert res.status_code == 200
        assert res.get_json()["data"]["plate_text"] == "ABC1234"

    def test_invalid_confidence_type_returns_400(self, client, operator_headers) -> None:
        """plate_confidence que não é número → 400."""
        pool, _ = _mock_pool()
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={"plate_text": "ABC1234", "plate_confidence": "not-a-number"},
                headers=operator_headers,
            )
        assert res.status_code == 400

    def test_plate_with_hyphen_accepted(self, client, operator_headers) -> None:
        """Placa com hífen (ABC-1234) é aceita e normalizada."""
        updated_row = _make_session_row("ABC1234", None, False, True)
        pool, _ = _mock_pool(update_returns=updated_row)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.patch(
                f"/api/counting/sessions/{SESSION_ID}/plate",
                json={"plate_text": "ABC-1234"},
                headers=operator_headers,
            )
        assert res.status_code == 200
        assert res.get_json()["data"]["plate_text"] == "ABC1234"


# ---------------------------------------------------------------------------
# GET /api/counting/sessions/plates
# ---------------------------------------------------------------------------
class TestListSessionsWithPlates:

    def test_requires_jwt(self, client) -> None:
        res = client.get("/api/counting/sessions/plates")
        assert res.status_code in (401, 422)

    def test_returns_empty_list(self, client, operator_headers) -> None:
        pool, _ = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/counting/sessions/plates", headers=operator_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["sessions"] == []

    def test_returns_sessions_with_plate(self, client, operator_headers) -> None:
        rows = [_make_session_row("ABC1234", 0.92, False, False)]
        pool, _ = _mock_pool(fetchall_returns=rows)
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/counting/sessions/plates", headers=operator_headers)
        assert res.status_code == 200
        sessions = res.get_json()["data"]["sessions"]
        assert len(sessions) == 1

    def test_review_only_flag(self, client, operator_headers) -> None:
        """review_only=true → ainda retorna 200 (filtro aplicado no repositório)."""
        pool, cur = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get(
                "/api/counting/sessions/plates?review_only=true",
                headers=operator_headers,
            )
        assert res.status_code == 200
        # tenant_id do JWT aparece nos params de qualquer execute feito
        assert cur.execute.called
        all_params = [c[0][1] for c in cur.execute.call_args_list]
        assert any(TENANT_ID in p for p in all_params)

    def test_tenant_isolation(self, client, operator_headers) -> None:
        """tenant_id no SQL vem sempre do JWT — nunca de query param."""
        pool, cur = _mock_pool(fetchall_returns=[])
        with patch("app.api.v1.counting.routes.DatabasePool.get_instance", return_value=pool):
            res = client.get("/api/counting/sessions/plates", headers=operator_headers)
        assert res.status_code == 200
        assert cur.execute.called
        all_params = [c[0][1] for c in cur.execute.call_args_list]
        assert any(TENANT_ID in p for p in all_params)
