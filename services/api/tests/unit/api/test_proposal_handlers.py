"""
Tests: proposal_handlers.py — grade de triagem de propostas (migration 118).

  GET  /api/v1/training/proposals
  POST /api/v1/training/proposals/reject-batch
  POST /api/v1/training/propagation/jobs/<job_id>/reject-proposals
  POST /api/v1/training/proposals/<id>/reject
  POST /api/v1/training/proposals/<id>/accept

Cobre: filtros de listagem, rejeição em lote por job/classe/confiança/
seleção (reason derivado + override explícito), guarda "sem filtro → 400",
cap de 5000 ids, item único cross-tenant/inexistente → 404 (nunca 403),
role sem training:write → 403 nas rotas de mutação, GET sem esse guard.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

_TENANT_ID = "00000000-0000-0000-0000-000000000001"
_HANDLERS = "app.api.v1.training.proposal_handlers"


def _make_token(app, role="admin", tenant_id=_TENANT_ID, user_id=None):
    uid = user_id or uuid4()
    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={"role": role, "tenant_id": tenant_id},
        )
    return token, uid


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestListProposals:
    def test_happy_path_returns_proposals_and_facets(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_proposals.return_value = {
            "proposals": [
                {
                    "id": str(uuid4()), "frame_id": str(uuid4()), "job_id": None,
                    "class_name": "capacete", "confidence": 0.4,
                    "bbox": [0.5, 0.5, 0.1, 0.1], "status": "pending",
                    "source": "propagation",
                    "frame": {
                        "r2_key": "frames/a.jpg", "width": 640, "height": 480,
                        "camera_id": None,
                    },
                },
            ],
            "total": 1, "page": 1, "page_size": 60, "total_pages": 1,
            "facets": {"by_class": [{"class_name": "capacete", "count": 1}]},
        }

        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = client.get("/api/v1/training/proposals", headers=_auth(token))

        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["total"] == 1
        assert data["proposals"][0]["frame"]["r2_key"] == "frames/a.jpg"
        assert data["proposals"][0]["frame"]["url"] is not None
        assert data["facets"]["by_class"][0]["class_name"] == "capacete"
        repo.list_proposals.assert_called_once()
        assert repo.list_proposals.call_args.kwargs["status"] == "pending"
        assert repo.list_proposals.call_args.kwargs["sort"] == "confidence"
        assert repo.list_proposals.call_args.kwargs["order"] == "asc"

    def test_get_does_not_require_training_write_role(self, client, app) -> None:
        """GET usa o mesmo guard de leitura dos demais GETs de training —
        só @jwt_required(), sem @require_training_role('write')."""
        token, _ = _make_token(app, role="viewer")
        repo = MagicMock()
        repo.list_proposals.return_value = {
            "proposals": [], "total": 0, "page": 1, "page_size": 60,
            "total_pages": 1, "facets": {"by_class": []},
        }
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = client.get("/api/v1/training/proposals", headers=_auth(token))
        assert res.status_code == 200

    def test_invalid_status_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = client.get(
            "/api/v1/training/proposals?status=bogus", headers=_auth(token),
        )
        assert res.status_code == 400

    def test_invalid_job_id_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = client.get(
            "/api/v1/training/proposals?job_id=not-a-uuid", headers=_auth(token),
        )
        assert res.status_code == 400

    def test_invalid_camera_id_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = client.get(
            "/api/v1/training/proposals?camera_id=not-a-uuid", headers=_auth(token),
        )
        assert res.status_code == 400

    def test_non_numeric_confidence_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = client.get(
            "/api/v1/training/proposals?confidence_min=abc", headers=_auth(token),
        )
        assert res.status_code == 400

    def test_class_name_csv_and_repeated_both_parsed(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_proposals.return_value = {
            "proposals": [], "total": 0, "page": 1, "page_size": 60,
            "total_pages": 1, "facets": {"by_class": []},
        }
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = client.get(
                "/api/v1/training/proposals?class_name=capacete,colete&class_name=luva",
                headers=_auth(token),
            )
        assert res.status_code == 200
        class_names = repo.list_proposals.call_args.kwargs["class_names"]
        assert sorted(class_names) == ["capacete", "colete", "luva"]

    def test_page_size_capped(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_proposals.return_value = {
            "proposals": [], "total": 0, "page": 1, "page_size": 60,
            "total_pages": 1, "facets": {"by_class": []},
        }
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = client.get(
                "/api/v1/training/proposals?page_size=999999", headers=_auth(token),
            )
        assert res.status_code == 200
        assert repo.list_proposals.call_args.kwargs["page_size"] <= 200


class TestRejectBatch:
    def _post(self, client, token, body):
        return client.post(
            "/api/v1/training/proposals/reject-batch",
            json=body,
            headers=_auth(token),
        )

    def test_reject_by_job_derives_reason_job(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.reject_batch.return_value = {
            "rejected_count": 5, "affected_frame_count": 3, "affected_frames": [],
        }
        job_id = str(uuid4())
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = self._post(client, token, {"job_id": job_id})

        assert res.status_code == 200
        assert res.get_json()["data"]["rejected_count"] == 5
        assert repo.reject_batch.call_args.kwargs["reason"] == "job"
        assert repo.reject_batch.call_args.kwargs["job_id"] == job_id

    def test_reject_by_class_names_derives_reason_class(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.reject_batch.return_value = {
            "rejected_count": 2, "affected_frame_count": 2, "affected_frames": [],
        }
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = self._post(client, token, {"class_names": ["capacete"]})

        assert res.status_code == 200
        assert repo.reject_batch.call_args.kwargs["reason"] == "class"

    def test_reject_by_confidence_lt_derives_reason_confidence(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.reject_batch.return_value = {
            "rejected_count": 1, "affected_frame_count": 1, "affected_frames": [],
        }
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = self._post(client, token, {"confidence_lt": 0.3})

        assert res.status_code == 200
        assert repo.reject_batch.call_args.kwargs["reason"] == "confidence"
        assert repo.reject_batch.call_args.kwargs["confidence_lt"] == 0.3

    def test_reject_by_selection_derives_reason_selection(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.reject_batch.return_value = {
            "rejected_count": 1, "affected_frame_count": 1, "affected_frames": [],
        }
        pid = str(uuid4())
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = self._post(client, token, {"proposal_ids": [pid]})

        assert res.status_code == 200
        assert repo.reject_batch.call_args.kwargs["reason"] == "selection"
        assert repo.reject_batch.call_args.kwargs["proposal_ids"] == [pid]

    def test_explicit_reason_overrides_derived(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.reject_batch.return_value = {
            "rejected_count": 1, "affected_frame_count": 1, "affected_frames": [],
        }
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = self._post(
                client, token, {"class_names": ["capacete"], "reason": "custom-note"},
            )

        assert res.status_code == 200
        assert repo.reject_batch.call_args.kwargs["reason"] == "custom-note"

    def test_no_filter_returns_400_never_rejects_all(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = self._post(client, token, {})

        assert res.status_code == 400
        repo.reject_batch.assert_not_called()

    def test_invalid_proposal_id_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = self._post(client, token, {"proposal_ids": ["not-a-uuid"]})
        assert res.status_code == 400

    def test_proposal_ids_over_cap_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = self._post(client, token, {"proposal_ids": [str(uuid4()) for _ in range(5001)]})
        assert res.status_code == 400

    def test_empty_class_names_list_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = self._post(client, token, {"class_names": []})
        assert res.status_code == 400

    def test_non_numeric_confidence_lt_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = self._post(client, token, {"confidence_lt": "abc"})
        assert res.status_code == 400

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res = self._post(client, token, {"job_id": str(uuid4())})
        assert res.status_code == 403


class TestRejectJobProposals:
    def test_wraps_reject_batch_with_job_id_and_reason_job(self, client, app) -> None:
        token, _ = _make_token(app)
        job_id = str(uuid4())
        repo = MagicMock()
        repo.reject_batch.return_value = {
            "rejected_count": 4, "affected_frame_count": 2, "affected_frames": [],
        }
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = client.post(
                f"/api/v1/training/propagation/jobs/{job_id}/reject-proposals",
                json={},
                headers=_auth(token),
            )

        assert res.status_code == 200
        assert repo.reject_batch.call_args.kwargs["job_id"] == job_id
        assert repo.reject_batch.call_args.kwargs["reason"] == "job"

    def test_accepts_optional_class_names_and_confidence_lt(self, client, app) -> None:
        token, _ = _make_token(app)
        job_id = str(uuid4())
        repo = MagicMock()
        repo.reject_batch.return_value = {
            "rejected_count": 1, "affected_frame_count": 1, "affected_frames": [],
        }
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = client.post(
                f"/api/v1/training/propagation/jobs/{job_id}/reject-proposals",
                json={"class_names": ["capacete"], "confidence_lt": 0.5},
                headers=_auth(token),
            )

        assert res.status_code == 200
        assert repo.reject_batch.call_args.kwargs["class_names"] == ["capacete"]
        assert repo.reject_batch.call_args.kwargs["confidence_lt"] == 0.5

    def test_invalid_job_id_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = client.post(
            "/api/v1/training/propagation/jobs/not-a-uuid/reject-proposals",
            json={},
            headers=_auth(token),
        )
        assert res.status_code == 400

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res = client.post(
            f"/api/v1/training/propagation/jobs/{uuid4()}/reject-proposals",
            json={},
            headers=_auth(token),
        )
        assert res.status_code == 403


class TestRejectOne:
    def test_success(self, client, app) -> None:
        token, _ = _make_token(app)
        pid = str(uuid4())
        repo = MagicMock()
        repo.reject_one.return_value = {"id": pid, "status": "rejected"}
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = client.post(
                f"/api/v1/training/proposals/{pid}/reject", headers=_auth(token),
            )

        assert res.status_code == 200
        assert res.get_json()["data"]["status"] == "rejected"
        assert repo.reject_one.call_args.kwargs["reason"] == "selection"

    def test_cross_tenant_or_missing_returns_404_never_403(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.reject_one.return_value = None
        with patch(f"{_HANDLERS}._get_proposal_repo", return_value=repo):
            res = client.post(
                f"/api/v1/training/proposals/{uuid4()}/reject", headers=_auth(token),
            )
        assert res.status_code == 404

    def test_invalid_proposal_id_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = client.post(
            "/api/v1/training/proposals/not-a-uuid/reject", headers=_auth(token),
        )
        assert res.status_code == 400

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res = client.post(
            f"/api/v1/training/proposals/{uuid4()}/reject", headers=_auth(token),
        )
        assert res.status_code == 403


class TestAcceptOne:
    def test_success_without_bbox(self, client, app) -> None:
        token, _ = _make_token(app)
        pid = str(uuid4())
        service = MagicMock()
        service.accept_proposal.return_value = {
            "id": pid, "status": "accepted", "frame_id": str(uuid4()),
        }
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=service):
            res = client.post(
                f"/api/v1/training/proposals/{pid}/accept", headers=_auth(token),
            )

        assert res.status_code == 200
        assert res.get_json()["data"]["status"] == "accepted"
        args = service.accept_proposal.call_args.args
        assert args[2] == pid
        assert args[3] is None

    def test_success_with_corrected_bbox(self, client, app) -> None:
        token, _ = _make_token(app)
        pid = str(uuid4())
        service = MagicMock()
        service.accept_proposal.return_value = {
            "id": pid, "status": "corrected", "frame_id": str(uuid4()),
        }
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=service):
            res = client.post(
                f"/api/v1/training/proposals/{pid}/accept",
                json={"bbox": [0.4, 0.4, 0.2, 0.2]},
                headers=_auth(token),
            )

        assert res.status_code == 200
        assert res.get_json()["data"]["status"] == "corrected"
        args = service.accept_proposal.call_args.args
        assert args[3] == [0.4, 0.4, 0.2, 0.2]

    def test_bbox_wrong_shape_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = client.post(
            f"/api/v1/training/proposals/{uuid4()}/accept",
            json={"bbox": [0.5, 0.5]},
            headers=_auth(token),
        )
        assert res.status_code == 400

    def test_bbox_out_of_range_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = client.post(
            f"/api/v1/training/proposals/{uuid4()}/accept",
            json={"bbox": [1.5, 0.5, 0.1, 0.1]},
            headers=_auth(token),
        )
        assert res.status_code == 400

    def test_invalid_proposal_id_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res = client.post(
            "/api/v1/training/proposals/not-a-uuid/accept", headers=_auth(token),
        )
        assert res.status_code == 400

    def test_service_not_found_propagates_as_404(self, client, app) -> None:
        token, _ = _make_token(app)
        from app.core.exceptions import NotFoundError

        service = MagicMock()
        service.accept_proposal.side_effect = NotFoundError("Proposta", str(uuid4()))
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=service):
            res = client.post(
                f"/api/v1/training/proposals/{uuid4()}/accept", headers=_auth(token),
            )
        assert res.status_code == 404

    def test_service_unmapped_label_propagates_as_400(self, client, app) -> None:
        token, _ = _make_token(app)
        from app.core.exceptions import ValidationError

        service = MagicMock()
        service.accept_proposal.side_effect = ValidationError("label desconhecido")
        with patch(f"{_HANDLERS}.get_annotation_service", return_value=service):
            res = client.post(
                f"/api/v1/training/proposals/{uuid4()}/accept", headers=_auth(token),
            )
        assert res.status_code == 400

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res = client.post(
            f"/api/v1/training/proposals/{uuid4()}/accept", headers=_auth(token),
        )
        assert res.status_code == 403
