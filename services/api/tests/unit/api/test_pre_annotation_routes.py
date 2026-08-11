"""
Tests: POST /api/training/frames/<id>/pre-annotate e /accept-suggestions
(WS-B4). Gate @require_training_role('write'); 403 quando o backend está
desligado (default); delegação correta pro AnnotationService.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

TENANT_ID = "00000000-0000-0000-0000-000000000001"
_HANDLERS = "app.api.v1.training.annotation_handlers"


def _auth_header(app, role="admin", tenant_id=TENANT_ID):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": tenant_id, "tenant_schema": None, "role": role},
        )
    return {"Authorization": f"Bearer {token}"}


class TestPreAnnotateFrameRoute:
    def test_no_auth_returns_401(self, client):
        frame_id = str(uuid4())
        resp = client.post(f"/api/training/frames/{frame_id}/pre-annotate")
        assert resp.status_code == 401

    def test_operator_without_write_role_returns_403(self, app, client):
        frame_id = str(uuid4())
        resp = client.post(
            f"/api/training/frames/{frame_id}/pre-annotate",
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403

    def test_disabled_backend_returns_403(self, app, client):
        frame_id = str(uuid4())
        mock_service = MagicMock()
        from app.core.exceptions import AuthorizationError
        mock_service.pre_annotate_frame.side_effect = AuthorizationError(
            "Pré-anotação desabilitada para este tenant"
        )
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=mock_service):
            resp = client.post(
                f"/api/training/frames/{frame_id}/pre-annotate",
                headers=_auth_header(app),
            )
        assert resp.status_code == 403

    def test_enabled_backend_returns_annotations_count(self, app, client):
        frame_id = str(uuid4())
        mock_service = MagicMock()
        mock_service.pre_annotate_frame.return_value = 5
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=mock_service):
            resp = client.post(
                f"/api/training/frames/{frame_id}/pre-annotate",
                json={"module_code": "epi"},
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["annotations_count"] == 5


class TestAcceptSuggestionsRoute:
    def test_no_auth_returns_401(self, client):
        frame_id = str(uuid4())
        resp = client.post(f"/api/training/frames/{frame_id}/accept-suggestions")
        assert resp.status_code == 401

    def test_accepts_all_by_default(self, app, client):
        frame_id = str(uuid4())
        mock_service = MagicMock()
        mock_service.accept_suggestions.return_value = 3
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=mock_service):
            resp = client.post(
                f"/api/training/frames/{frame_id}/accept-suggestions",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["accepted"] == 3
        mock_service.accept_suggestions.assert_called_once()
        assert mock_service.accept_suggestions.call_args.kwargs["indices"] is None

    def test_accepts_specific_indices(self, app, client):
        frame_id = str(uuid4())
        mock_service = MagicMock()
        mock_service.accept_suggestions.return_value = 1
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=mock_service):
            resp = client.post(
                f"/api/training/frames/{frame_id}/accept-suggestions",
                json={"indices": [1]},
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert mock_service.accept_suggestions.call_args.kwargs["indices"] == [1]

    def test_invalid_indices_type_returns_400(self, app, client):
        frame_id = str(uuid4())
        resp = client.post(
            f"/api/training/frames/{frame_id}/accept-suggestions",
            json={"indices": "not-a-list"},
            headers=_auth_header(app),
        )
        assert resp.status_code == 400


class TestPreAnnotationReviewRoute:
    """POST /api/training/frames/<id>/pre-annotation-review (migration 111).

    Fila de aprovação de propostas: fecha o buraco de modelo onde uma
    proposta rejeitada não tinha onde pousar e a fila nunca esvaziava.
    """

    def test_no_auth_returns_401(self, client):
        frame_id = str(uuid4())
        resp = client.post(f"/api/training/frames/{frame_id}/pre-annotation-review")
        assert resp.status_code == 401

    def test_operator_without_write_role_returns_403(self, app, client):
        frame_id = str(uuid4())
        resp = client.post(
            f"/api/training/frames/{frame_id}/pre-annotation-review",
            json={"status": "accepted"},
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403

    def test_missing_status_returns_400(self, app, client):
        frame_id = str(uuid4())
        resp = client.post(
            f"/api/training/frames/{frame_id}/pre-annotation-review",
            json={},
            headers=_auth_header(app),
        )
        assert resp.status_code == 400

    def test_invalid_status_returns_400(self, app, client):
        frame_id = str(uuid4())
        resp = client.post(
            f"/api/training/frames/{frame_id}/pre-annotation-review",
            json={"status": "maybe"},
            headers=_auth_header(app),
        )
        assert resp.status_code == 400

    def test_cross_tenant_or_missing_frame_returns_404(self, app, client):
        """FALHA-ANTES/PASSA-DEPOIS (C-01): frame de outro tenant ou
        inexistente → 404, nunca 403 (não vaza existência)."""
        frame_id = str(uuid4())
        mock_service = MagicMock()
        from app.core.exceptions import NotFoundError
        mock_service.review_pre_annotation.side_effect = NotFoundError(
            "Frame", frame_id
        )
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=mock_service):
            resp = client.post(
                f"/api/training/frames/{frame_id}/pre-annotation-review",
                json={"status": "rejected"},
                headers=_auth_header(app),
            )
        assert resp.status_code == 404

    def test_rejected_status_returns_200(self, app, client):
        frame_id = str(uuid4())
        mock_service = MagicMock()
        mock_service.review_pre_annotation.return_value = {
            "frame_id": frame_id, "status": "rejected", "reviewed_at": None,
        }
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=mock_service):
            resp = client.post(
                f"/api/training/frames/{frame_id}/pre-annotation-review",
                json={"status": "rejected"},
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "rejected"
        mock_service.review_pre_annotation.assert_called_once()
        assert mock_service.review_pre_annotation.call_args.args[2] == "rejected"

    def test_accepted_status_returns_200(self, app, client):
        frame_id = str(uuid4())
        mock_service = MagicMock()
        mock_service.review_pre_annotation.return_value = {
            "frame_id": frame_id, "status": "accepted", "reviewed_at": None,
        }
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=mock_service):
            resp = client.post(
                f"/api/training/frames/{frame_id}/pre-annotation-review",
                json={"status": "accepted"},
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "accepted"

    def test_calling_twice_is_idempotent(self, app, client):
        frame_id = str(uuid4())
        mock_service = MagicMock()
        mock_service.review_pre_annotation.return_value = {
            "frame_id": frame_id, "status": "rejected", "reviewed_at": None,
        }
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=mock_service):
            first = client.post(
                f"/api/training/frames/{frame_id}/pre-annotation-review",
                json={"status": "rejected"},
                headers=_auth_header(app),
            )
            second = client.post(
                f"/api/training/frames/{frame_id}/pre-annotation-review",
                json={"status": "rejected"},
                headers=_auth_header(app),
            )
        assert first.status_code == 200
        assert second.status_code == 200
        assert mock_service.review_pre_annotation.call_count == 2
