"""Tests: verification/routes.py — fila de verificação humana de alertas."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
ALERT_ID = str(uuid4())
_SVC_PATH = "app.api.v1.verification.routes._svc"


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "role": "operator",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /api/verification/queue
# ---------------------------------------------------------------------------

class TestGetQueue:

    def test_no_token_returns_401(self, client):
        assert client.get("/api/verification/queue").status_code == 401

    def test_empty_queue_returns_200(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["items"] == []
        assert data["data"]["count"] == 0

    def test_returns_items_with_correct_count(self, client, auth_headers):
        items = [{"id": ALERT_ID, "camera_id": "cam1"}, {"id": str(uuid4()), "camera_id": "cam2"}]
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = items
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue", headers=auth_headers)
        data = resp.get_json()
        assert data["data"]["count"] == 2
        assert len(data["data"]["items"]) == 2

    def test_limit_capped_at_100(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        with patch(_SVC_PATH, mock_svc):
            client.get("/api/verification/queue?limit=9999", headers=auth_headers)
        call_kwargs = mock_svc.get_human_queue.call_args[1]
        assert call_kwargs["limit"] == 100

    def test_default_limit_is_50(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        with patch(_SVC_PATH, mock_svc):
            client.get("/api/verification/queue", headers=auth_headers)
        call_kwargs = mock_svc.get_human_queue.call_args[1]
        assert call_kwargs["limit"] == 50

    def test_camera_id_filter_forwarded(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.return_value = []
        with patch(_SVC_PATH, mock_svc):
            client.get(f"/api/verification/queue?camera_id={ALERT_ID}", headers=auth_headers)
        call_kwargs = mock_svc.get_human_queue.call_args[1]
        assert call_kwargs["camera_id"] == ALERT_ID

    def test_service_error_returns_500(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_human_queue.side_effect = Exception("DB error")
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/verification/queue/count
# ---------------------------------------------------------------------------

class TestQueueCount:

    def test_no_token_returns_401(self, client):
        assert client.get("/api/verification/queue/count").status_code == 401

    def test_returns_count(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_queue_count.return_value = 7
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue/count", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["count"] == 7

    def test_zero_count(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_queue_count.return_value = 0
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue/count", headers=auth_headers)
        assert resp.get_json()["data"]["count"] == 0

    def test_service_error_returns_500(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.get_queue_count.side_effect = Exception("DB error")
        with patch(_SVC_PATH, mock_svc):
            resp = client.get("/api/verification/queue/count", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/verification/<alert_id>/review
# ---------------------------------------------------------------------------

class TestReviewAlert:

    def test_no_token_returns_401(self, client):
        resp = client.post(
            f"/api/verification/{ALERT_ID}/review",
            json={"verdict": "approve"},
        )
        assert resp.status_code == 401

    def test_invalid_verdict_returns_400(self, client, auth_headers):
        mock_svc = MagicMock()
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "invalid"},
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_missing_verdict_returns_400(self, client, auth_headers):
        mock_svc = MagicMock()
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={},
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_approve_returns_200(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.return_value = 1
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "approve"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["verdict"] == "approve"
        assert data["data"]["alert_id"] == ALERT_ID

    def test_reject_returns_200(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.return_value = 1
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "reject"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["verdict"] == "reject"

    def test_not_found_or_already_reviewed_returns_404(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.return_value = 0
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "approve"},
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_value_error_returns_400(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.side_effect = ValueError("Invalid alert state")
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "approve"},
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_generic_exception_returns_500(self, client, auth_headers):
        mock_svc = MagicMock()
        mock_svc.human_review.side_effect = Exception("DB error")
        with patch(_SVC_PATH, mock_svc):
            resp = client.post(
                f"/api/verification/{ALERT_ID}/review",
                json={"verdict": "reject"},
                headers=auth_headers,
            )
        assert resp.status_code == 500
