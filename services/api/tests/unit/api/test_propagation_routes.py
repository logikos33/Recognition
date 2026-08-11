"""
Tests: propagation_handlers.py — rotas de propagação semeada (migration 112).

  POST /api/v1/training/propagation/jobs
  GET  /api/v1/training/propagation/jobs/<id>
  GET  /api/v1/training/propagation/jobs

Cobre:
- criação: câmera fora do tenant → 404 (C-01, sem vazar existência); pool
  vazio/critério malformado → 400 (PoolGuardError propagado como texto);
  sementes default resolvidas via anotações humanas do pool; sementes
  explícitas fora do pool → 400; sem sementes nenhuma → 400;
  validation_only trunca o pool ANTES de criar o job; dispatch_propagation
  é disparado (.delay) após a criação; callback_token nunca vaza na
  resposta; role sem training:write → 403.
- leitura: cross-tenant → 404 (nunca 403 — C-01); callback_token nunca
  vaza em GET nem em list.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

_TENANT_ID = "00000000-0000-0000-0000-000000000001"
_HANDLERS = "app.api.v1.training.propagation_handlers"
_CAMERA = str(uuid4())
_JOB_ID = str(uuid4())


def _make_token(app, role="admin", tenant_id=_TENANT_ID, user_id=None):
    uid = user_id or uuid4()
    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={"role": role, "tenant_id": tenant_id},
        )
    return token, uid


def _frame(frame_id: str, camera_id: str = _CAMERA) -> dict:
    from datetime import datetime
    return {
        "id": frame_id, "tenant_id": _TENANT_ID, "camera_id": camera_id,
        "r2_key": f"frames/{frame_id}.jpg",
        "captured_at": datetime(2026, 7, 31, 10, 0, 0),
    }


def _job_row(**overrides) -> dict:
    job = {
        "id": _JOB_ID, "tenant_id": _TENANT_ID, "status": "queued",
        "pool_criteria": {"camera_ids": [_CAMERA], "date_from": "2026-07-31", "date_to": "2026-07-31"},
        "pool_frame_ids": ["f1", "f2"], "pool_hash": "abc123",
        "seed_frame_ids": ["f1"], "seed_count": 1, "proposals_count": 0,
        "callback_token": "super-secret-token",
    }
    job.update(overrides)
    return job


class _Patches:
    """Bundle dos 4 repositories que create_propagation_job_handler usa,
    já com defaults sãos (câmera pertence ao tenant, pool com 2 frames,
    1 anotação manual)."""

    def __init__(self) -> None:
        self.camera_repo = MagicMock()
        self.camera_repo.get_by_id_and_tenant.return_value = {"id": _CAMERA, "tenant_id": _TENANT_ID}

        self.frame_repo = MagicMock()
        self.frame_repo.list_for_propagation_pool.return_value = [_frame("f1"), _frame("f2")]

        self.annotation_repo = MagicMock()
        self.annotation_repo.get_manual_annotations_for_frames.return_value = [
            {"frame_id": "f1", "class_id": 1, "class_name": "capacete",
             "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1},
        ]

        self.propagation_repo = MagicMock()
        self.propagation_repo.create_job.return_value = _job_row()

    def ctx(self):
        return (
            patch(f"{_HANDLERS}._get_camera_repo", return_value=self.camera_repo),
            patch(f"{_HANDLERS}._get_frame_repo", return_value=self.frame_repo),
            patch(f"{_HANDLERS}._get_annotation_repo", return_value=self.annotation_repo),
            patch(f"{_HANDLERS}._get_propagation_repo", return_value=self.propagation_repo),
            patch("app.infrastructure.queue.tasks.propagation.dispatch_propagation.delay"),
        )


def _post_job(client, token, body):
    p = _Patches()
    patchers = p.ctx()
    for patcher in patchers:
        patcher.start()
    try:
        res = client.post(
            "/api/v1/training/propagation/jobs",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        for patcher in reversed(patchers):
            patcher.stop()
    return res, p


class TestCreatePropagationJob:
    def _body(self, **overrides) -> dict:
        body = {"camera_ids": [_CAMERA], "date_from": "2026-07-31", "date_to": "2026-07-31"}
        body.update(overrides)
        return body

    def test_happy_path_creates_job_and_dispatches_celery(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body())

        assert res.status_code == 201
        body = res.get_json()
        assert body["data"]["id"] == _JOB_ID
        assert "callback_token" not in body["data"]

        p.propagation_repo.create_job.assert_called_once()
        create_kwargs = p.propagation_repo.create_job.call_args.kwargs
        assert create_kwargs["pool_frame_ids"] == ["f1", "f2"]
        assert create_kwargs["seed_frame_ids"] == ["f1"]  # default: anotações manuais do pool

    def test_missing_camera_ids_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, {"date_from": "2026-07-31", "date_to": "2026-07-31"})
        assert res.status_code == 400

    def test_missing_dates_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, {"camera_ids": [_CAMERA]})
        assert res.status_code == 400

    def test_date_from_after_date_to_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(
            client, token, self._body(date_from="2026-08-01", date_to="2026-07-31"),
        )
        assert res.status_code == 400

    def test_camera_not_owned_by_tenant_returns_404_never_403(self, client, app) -> None:
        """C-01: câmera de outro tenant (ou inexistente) → 404, nunca 403
        (não vaza existência)."""
        token, _ = _make_token(app)
        p = _Patches()
        p.camera_repo.get_by_id_and_tenant.return_value = None
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/propagation/jobs",
                json=self._body(),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()
        assert res.status_code == 404
        p.propagation_repo.create_job.assert_not_called()

    def test_empty_pool_returns_400_with_guard_reason(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _Patches()
        p.frame_repo.list_for_propagation_pool.return_value = []
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/propagation/jobs",
                json=self._body(),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()
        assert res.status_code == 400
        assert "pool vazio" in res.get_json()["error"]
        p.propagation_repo.create_job.assert_not_called()

    def test_explicit_seed_outside_pool_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(
            client, token, self._body(seed_frame_ids=["frame-nao-esta-no-pool"]),
        )
        assert res.status_code == 400
        assert "fora do pool" in res.get_json()["error"]
        p.propagation_repo.create_job.assert_not_called()

    def test_explicit_seed_inside_pool_is_accepted(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body(seed_frame_ids=["f2"]))
        assert res.status_code == 201
        create_kwargs = p.propagation_repo.create_job.call_args.kwargs
        assert create_kwargs["seed_frame_ids"] == ["f2"]

    def test_no_seeds_available_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _Patches()
        p.annotation_repo.get_manual_annotations_for_frames.return_value = []
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/propagation/jobs",
                json=self._body(),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()
        assert res.status_code == 400
        assert "semente" in res.get_json()["error"]

    def test_validation_only_truncates_pool_before_creating_job(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _Patches()
        many_frames = [_frame(f"f{i}") for i in range(10)]
        p.frame_repo.list_for_propagation_pool.return_value = many_frames
        p.annotation_repo.get_manual_annotations_for_frames.return_value = [
            {"frame_id": "f0", "class_id": 1, "class_name": "capacete",
             "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1},
        ]
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/propagation/jobs",
                json=self._body(validation_only=True),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()
        assert res.status_code == 201
        create_kwargs = p.propagation_repo.create_job.call_args.kwargs
        assert len(create_kwargs["pool_frame_ids"]) == 5

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res, _p = _post_job(client, token, self._body())
        assert res.status_code == 403

    def test_invalid_threshold_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, self._body(threshold=1.5))
        assert res.status_code == 400


class TestGetPropagationJob:
    def test_found_strips_callback_token(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_row()

        with patch(f"{_HANDLERS}._get_propagation_repo", return_value=repo):
            res = client.get(
                f"/api/v1/training/propagation/jobs/{_JOB_ID}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        body = res.get_json()["data"]
        assert body["id"] == _JOB_ID
        assert "callback_token" not in body

    def test_cross_tenant_returns_404(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = None  # outro tenant, ou inexistente

        with patch(f"{_HANDLERS}._get_propagation_repo", return_value=repo):
            res = client.get(
                f"/api/v1/training/propagation/jobs/{_JOB_ID}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 404


class TestListPropagationJobs:
    def test_lists_jobs_without_callback_token(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_for_tenant.return_value = [_job_row(), _job_row(id=str(uuid4()))]

        with patch(f"{_HANDLERS}._get_propagation_repo", return_value=repo):
            res = client.get(
                "/api/v1/training/propagation/jobs",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        jobs = res.get_json()["data"]
        assert len(jobs) == 2
        assert all("callback_token" not in j for j in jobs)
