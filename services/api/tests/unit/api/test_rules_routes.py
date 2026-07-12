"""Tests: rules/routes.py — CRUD de regras de alerta."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
RULE_ID = str(uuid4())
_POOL_PATH = "app.api.v1.rules.routes.DatabasePool"

_SAMPLE_RULE = {
    "id": RULE_ID,
    "tenant_id": TENANT_ID,
    "violation_type": "no_helmet",
    "min_duration_seconds": 5,
    "min_occurrences": None,
    "time_window_seconds": None,
    "create_alert": True,
    "enabled": True,
}


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "role": "admin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _make_pool(fetchone_row=None, fetchall_rows=None):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = fetchone_row
        mock_cur.fetchall.return_value = fetchall_rows or []
        mock_conn.cursor.return_value = mock_cur
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


# ---------------------------------------------------------------------------
# GET /api/rules
# ---------------------------------------------------------------------------

class TestListRules:

    def test_no_token_returns_401(self, client):
        assert client.get("/api/rules").status_code == 401

    def test_empty_list(self, client, auth_headers):
        mock_pool = _make_pool(fetchall_rows=[])
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.get("/api/rules", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["rules"] == []

    def test_returns_rules(self, client, auth_headers):
        mock_pool = _make_pool(fetchall_rows=[_SAMPLE_RULE])
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.get("/api/rules", headers=auth_headers)
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["data"]["rules"]) == 1
        assert data["data"]["rules"][0]["violation_type"] == "no_helmet"

    def test_db_error_returns_500(self, client, auth_headers):
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            resp = client.get("/api/rules", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/rules
# ---------------------------------------------------------------------------

class TestCreateRule:

    def test_no_token_returns_401(self, client):
        assert client.post("/api/rules", json={}).status_code == 401

    def test_missing_violation_type_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/rules",
            json={"min_duration_seconds": 5},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_missing_duration_and_occurrences_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/rules",
            json={"violation_type": "no_helmet"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_valid_rule_with_duration_returns_201(self, client, auth_headers):
        mock_pool = _make_pool(fetchone_row=_SAMPLE_RULE)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.post(
                "/api/rules",
                json={"violation_type": "no_helmet", "min_duration_seconds": 5},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["rule"]["violation_type"] == "no_helmet"

    def test_valid_rule_with_occurrences_returns_201(self, client, auth_headers):
        mock_pool = _make_pool(fetchone_row=_SAMPLE_RULE)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.post(
                "/api/rules",
                json={"violation_type": "no_vest", "min_occurrences": 3},
                headers=auth_headers,
            )
        assert resp.status_code == 201

    def test_db_error_returns_500(self, client, auth_headers):
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            resp = client.post(
                "/api/rules",
                json={"violation_type": "no_helmet", "min_duration_seconds": 5},
                headers=auth_headers,
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/rules/<rule_id>
# ---------------------------------------------------------------------------

class TestGetRule:

    def test_no_token_returns_401(self, client):
        assert client.get(f"/api/rules/{RULE_ID}").status_code == 401

    def test_rule_found_returns_200(self, client, auth_headers):
        mock_pool = _make_pool(fetchone_row=_SAMPLE_RULE)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.get(f"/api/rules/{RULE_ID}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["rule"]["id"] == RULE_ID

    def test_rule_not_found_returns_404(self, client, auth_headers):
        mock_pool = _make_pool(fetchone_row=None)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.get(f"/api/rules/{RULE_ID}", headers=auth_headers)
        assert resp.status_code == 404

    def test_db_error_returns_500(self, client, auth_headers):
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            resp = client.get(f"/api/rules/{RULE_ID}", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PUT /api/rules/<rule_id>
# ---------------------------------------------------------------------------

class TestUpdateRule:

    def test_no_token_returns_401(self, client):
        assert client.put(f"/api/rules/{RULE_ID}", json={}).status_code == 401

    def test_rule_not_found_returns_404(self, client, auth_headers):
        mock_pool = _make_pool(fetchone_row=None)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.put(
                f"/api/rules/{RULE_ID}",
                json={"enabled": False},
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_rule_updated_returns_200(self, client, auth_headers):
        updated = {**_SAMPLE_RULE, "enabled": False}
        mock_pool = _make_pool(fetchone_row=updated)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.put(
                f"/api/rules/{RULE_ID}",
                json={"enabled": False},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["rule"]["enabled"] is False

    def test_db_error_returns_500(self, client, auth_headers):
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            resp = client.put(
                f"/api/rules/{RULE_ID}",
                json={"enabled": False},
                headers=auth_headers,
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /api/rules/<rule_id>
# ---------------------------------------------------------------------------

class TestDeleteRule:

    def test_no_token_returns_401(self, client):
        assert client.delete(f"/api/rules/{RULE_ID}").status_code == 401

    def test_rule_not_found_returns_404(self, client, auth_headers):
        mock_pool = _make_pool(fetchone_row=None)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.delete(f"/api/rules/{RULE_ID}", headers=auth_headers)
        assert resp.status_code == 404

    def test_rule_deleted_returns_200(self, client, auth_headers):
        mock_pool = _make_pool(fetchone_row=_SAMPLE_RULE)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.delete(f"/api/rules/{RULE_ID}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["deleted"] is True

    def test_db_error_returns_500(self, client, auth_headers):
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            resp = client.delete(f"/api/rules/{RULE_ID}", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/rules/<rule_id>/toggle
# ---------------------------------------------------------------------------

class TestToggleRule:

    def test_no_token_returns_401(self, client):
        assert client.post(f"/api/rules/{RULE_ID}/toggle").status_code == 401

    def test_toggle_returns_updated_rule(self, client, auth_headers):
        toggled = {**_SAMPLE_RULE, "enabled": False}
        mock_pool = _make_pool(fetchone_row=toggled)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.post(f"/api/rules/{RULE_ID}/toggle", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["rule"]["enabled"] is False

    def test_toggle_rule_not_found_returns_404(self, client, auth_headers):
        mock_pool = _make_pool(fetchone_row=None)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.post(f"/api/rules/{RULE_ID}/toggle", headers=auth_headers)
        assert resp.status_code == 404

    def test_db_error_returns_500(self, client, auth_headers):
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            resp = client.post(f"/api/rules/{RULE_ID}/toggle", headers=auth_headers)
        assert resp.status_code == 500
