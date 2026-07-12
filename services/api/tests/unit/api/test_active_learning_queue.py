"""
Tests: GET /api/training/active-learning/queue (WS-B2, ADR-0031).

Cobre: auth obrigatória, filtros ?module=/?limit=, shape da resposta,
serialização de UUIDs, e que qualquer erro interno vira 500 sem stack trace.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

TENANT_ID = "00000000-0000-0000-0000-000000000001"


def _auth_header(app, role="operator", tenant_id=TENANT_ID):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": tenant_id, "tenant_schema": None, "role": role},
        )
    return {"Authorization": f"Bearer {token}"}


class TestActiveLearningQueue:
    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/training/active-learning/queue")
        assert resp.status_code == 401

    def test_returns_queue_ordered_by_uncertainty(self, app, client):
        frame_id = uuid4()
        camera_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.list_unlabeled_by_uncertainty.return_value = [
            {
                "id": frame_id, "video_id": None, "frame_number": 0,
                "filename": "training-images/t/auto/x.jpg", "r2_key": "training-images/t/auto/x.jpg",
                "source": "auto", "width": 640, "height": 480, "camera_id": camera_id,
                "model_confidence": 0.31, "created_at": None,
            }
        ]
        with patch(
            "app.api.v1.training.image_handlers._get_frame_repo", return_value=mock_repo
        ):
            resp = client.get(
                "/api/training/active-learning/queue?module=epi&limit=5",
                headers=_auth_header(app),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert body["data"]["module"] == "epi"
        frame = body["data"]["frames"][0]
        assert frame["id"] == str(frame_id)
        assert frame["camera_id"] == str(camera_id)
        assert frame["video_id"] is None
        mock_repo.list_unlabeled_by_uncertainty.assert_called_once_with(
            TENANT_ID, "epi", 5
        )

    def test_limit_is_clamped_to_100(self, app, client):
        mock_repo = MagicMock()
        mock_repo.list_unlabeled_by_uncertainty.return_value = []
        with patch(
            "app.api.v1.training.image_handlers._get_frame_repo", return_value=mock_repo
        ):
            client.get(
                "/api/training/active-learning/queue?limit=9999",
                headers=_auth_header(app),
            )
        args = mock_repo.list_unlabeled_by_uncertainty.call_args.args
        assert args[2] == 100

    def test_default_module_is_epi(self, app, client):
        mock_repo = MagicMock()
        mock_repo.list_unlabeled_by_uncertainty.return_value = []
        with patch(
            "app.api.v1.training.image_handlers._get_frame_repo", return_value=mock_repo
        ):
            resp = client.get(
                "/api/training/active-learning/queue", headers=_auth_header(app)
            )
        assert resp.get_json()["data"]["module"] == "epi"

    def test_internal_error_returns_500_without_stacktrace(self, app, client):
        mock_repo = MagicMock()
        mock_repo.list_unlabeled_by_uncertainty.side_effect = RuntimeError("db down")
        with patch(
            "app.api.v1.training.image_handlers._get_frame_repo", return_value=mock_repo
        ):
            resp = client.get(
                "/api/training/active-learning/queue", headers=_auth_header(app)
            )
        assert resp.status_code == 500
        assert "RuntimeError" not in resp.get_json().get("error", "")
