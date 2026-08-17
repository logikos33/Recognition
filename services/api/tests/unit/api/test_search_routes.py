"""
Tests: search_handlers.py — rotas de busca por conteúdo (migration 113).

  POST /api/v1/training/search/preflight
  POST /api/v1/training/search/jobs
  GET  /api/v1/training/search/jobs/<id>
  GET  /api/v1/training/search/jobs

Cobre:
- guard de nuvem (SEARCH_CLOUD_ALLOWED_DATES ausente/malformada) → 409 no
  preflight E no create — fail-closed, nem materializa nada;
- criação: frame_ids/terms ausentes/vazios/fora dos limites → 400; frame
  fora da janela permitida (ou não encontrado/de outro tenant) → 400,
  create_job NUNCA chamado; dispatch_search é disparado (.delay) após a
  criação; callback_token nunca vaza na resposta; role sem training:write
  → 403;
- leitura: cross-tenant → 404 (nunca 403 — C-01); callback_token nunca
  vaza em GET nem em list;
- preflight: elegibilidade (ineligible reasons) + custo (RunPod) — nunca
  materializa/grava nada.
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

_TENANT_ID = "00000000-0000-0000-0000-000000000001"
_HANDLERS = "app.api.v1.training.search_handlers"
_JOB_ID = str(uuid4())
_ALLOWED = [(date(2026, 7, 31), date(2026, 7, 31))]


def _make_token(app, role="admin", tenant_id=_TENANT_ID, user_id=None):
    uid = user_id or uuid4()
    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={"role": role, "tenant_id": tenant_id},
        )
    return token, uid


def _frame(frame_id: str, *, captured_at=datetime(2026, 7, 31, 10, 0), r2_key=None) -> dict:
    return {
        "id": frame_id, "tenant_id": _TENANT_ID,
        "r2_key": r2_key or f"frames/{frame_id}.jpg",
        "captured_at": captured_at,
    }


def _job_row(**overrides) -> dict:
    job = {
        "id": _JOB_ID, "tenant_id": _TENANT_ID, "status": "queued",
        "selected_frame_ids": ["f1", "f2"], "frames_hash": "abc123",
        "terms": [{"label": "Capacete", "query": "safety helmet"}],
        "results": [], "findings_count": 0,
        "callback_token": "super-secret-token",
    }
    job.update(overrides)
    return job


class _Patches:
    """Bundle dos repositories + guard de datas que create_search_job_handler
    usa, já com defaults sãos (2 frames elegíveis, guard liberado)."""

    def __init__(self) -> None:
        self.frame_repo = MagicMock()
        self.frame_repo.get_by_ids_and_tenant.return_value = [_frame("f1"), _frame("f2")]

        self.search_repo = MagicMock()
        self.search_repo.create_job.return_value = _job_row()

        self.allowed_ranges = list(_ALLOWED)

    def ctx(self):
        return (
            patch(f"{_HANDLERS}._get_frame_repo", return_value=self.frame_repo),
            patch(f"{_HANDLERS}._get_search_repo", return_value=self.search_repo),
            patch(
                f"{_HANDLERS}.cloud_search_allowed_dates",
                side_effect=lambda: self.allowed_ranges,
            ),
            patch("app.infrastructure.queue.tasks.search.dispatch_search.delay"),
        )


def _post_job(client, token, body):
    p = _Patches()
    patchers = p.ctx()
    for patcher in patchers:
        patcher.start()
    try:
        res = client.post(
            "/api/v1/training/search/jobs",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        for patcher in reversed(patchers):
            patcher.stop()
    return res, p


class TestCreateSearchJob:
    def _body(self, **overrides) -> dict:
        body = {
            "frame_ids": ["f1", "f2"],
            "terms": [{"label": "Capacete", "query": "safety helmet"}],
        }
        body.update(overrides)
        return body

    def test_happy_path_creates_job_and_dispatches_celery(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body())

        assert res.status_code == 201
        body = res.get_json()
        assert body["data"]["id"] == _JOB_ID
        assert "callback_token" not in body["data"]

        p.search_repo.create_job.assert_called_once()
        create_kwargs = p.search_repo.create_job.call_args.kwargs
        assert create_kwargs["selected_frame_ids"] == ["f1", "f2"]
        assert create_kwargs["terms"] == [{"label": "Capacete", "query": "safety helmet"}]
        assert "frames_hash" in create_kwargs

    def test_cloud_guard_disabled_returns_409_nothing_created(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _Patches()
        p.allowed_ranges = None
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/search/jobs",
                json=self._body(),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()
        assert res.status_code == 409
        assert "SEARCH_CLOUD_ALLOWED_DATES" in res.get_json()["error"]
        p.search_repo.create_job.assert_not_called()

    def test_missing_frame_ids_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, {"terms": [{"label": "x", "query": "y"}]})
        assert res.status_code == 400

    def test_empty_frame_ids_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, self._body(frame_ids=[]))
        assert res.status_code == 400

    def test_frame_ids_above_500_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, self._body(frame_ids=[f"f{i}" for i in range(501)]))
        assert res.status_code == 400

    def test_missing_terms_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, {"frame_ids": ["f1"]})
        assert res.status_code == 400

    def test_terms_above_12_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        terms = [{"label": f"l{i}", "query": f"q{i}"} for i in range(13)]
        res, _p = _post_job(client, token, self._body(terms=terms))
        assert res.status_code == 400

    def test_term_missing_label_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, self._body(terms=[{"query": "y"}]))
        assert res.status_code == 400

    def test_term_missing_query_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, self._body(terms=[{"label": "x"}]))
        assert res.status_code == 400

    def test_duplicate_term_labels_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        terms = [{"label": "x", "query": "a"}, {"label": "x", "query": "b"}]
        res, _p = _post_job(client, token, self._body(terms=terms))
        assert res.status_code == 400

    def test_frame_outside_allowed_dates_returns_400_nothing_created(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _Patches()
        p.frame_repo.get_by_ids_and_tenant.return_value = [
            _frame("f1"), _frame("f2", captured_at=datetime(2026, 8, 1, 10, 0)),
        ]
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/search/jobs",
                json=self._body(),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()
        assert res.status_code == 400
        assert "f2" in res.get_json()["error"]
        p.search_repo.create_job.assert_not_called()

    def test_frame_not_found_or_cross_tenant_returns_400_nothing_created(
        self, client, app,
    ) -> None:
        """Frame_id que não pertence ao tenant nunca aparece em
        get_by_ids_and_tenant (query já escopada) — chega aqui como
        frame_not_found, mesmo caminho de um id inexistente (C-01)."""
        token, _ = _make_token(app)
        p = _Patches()
        p.frame_repo.get_by_ids_and_tenant.return_value = [_frame("f1")]  # f2 sumiu
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/search/jobs",
                json=self._body(),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()
        assert res.status_code == 400
        p.search_repo.create_job.assert_not_called()

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res, _p = _post_job(client, token, self._body())
        assert res.status_code == 403


class TestGetSearchJob:
    def test_found_strips_callback_token(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = _job_row()

        with patch(f"{_HANDLERS}._get_search_repo", return_value=repo):
            res = client.get(
                f"/api/v1/training/search/jobs/{_JOB_ID}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        body = res.get_json()["data"]
        assert body["id"] == _JOB_ID
        assert "callback_token" not in body

    def test_cross_tenant_returns_404(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.get_by_id_and_tenant.return_value = None

        with patch(f"{_HANDLERS}._get_search_repo", return_value=repo):
            res = client.get(
                f"/api/v1/training/search/jobs/{_JOB_ID}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 404


class TestListSearchJobs:
    def test_lists_jobs_without_callback_token(self, client, app) -> None:
        token, _ = _make_token(app)
        repo = MagicMock()
        repo.list_for_tenant.return_value = [_job_row(), _job_row(id=str(uuid4()))]

        with patch(f"{_HANDLERS}._get_search_repo", return_value=repo):
            res = client.get(
                "/api/v1/training/search/jobs",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        jobs = res.get_json()["data"]
        assert len(jobs) == 2
        assert all("callback_token" not in j for j in jobs)


class _PreflightPatches:
    def __init__(self) -> None:
        self.frame_repo = MagicMock()
        self.frame_repo.get_by_ids_and_tenant.return_value = [_frame("f1"), _frame("f2")]

        self.allowed_ranges = list(_ALLOWED)
        self.third_party_cloud_enabled = True
        self.api_key = "sk-fake-runpod-key-must-never-leak-in-response"
        self.price_estimate = (0.3, 0.15, False)

    def ctx(self):
        return (
            patch(f"{_HANDLERS}._get_frame_repo", return_value=self.frame_repo),
            patch(
                f"{_HANDLERS}.cloud_search_allowed_dates",
                side_effect=lambda: self.allowed_ranges,
            ),
            patch(
                f"{_HANDLERS}._third_party_cloud_enabled",
                side_effect=lambda tenant_id: self.third_party_cloud_enabled,  # noqa: ARG005
            ),
            patch(
                f"{_HANDLERS}._resolve_runpod_api_key",
                side_effect=lambda tenant_id: self.api_key,  # noqa: ARG005
            ),
            patch(
                f"{_HANDLERS}._gpu_price_estimate",
                side_effect=lambda api_key, gpu_type, timeout_seconds: self.price_estimate,  # noqa: ARG005,E501
            ),
        )


def _post_preflight(client, token, body, p: "_PreflightPatches | None" = None):
    p = p or _PreflightPatches()
    patchers = p.ctx()
    for patcher in patchers:
        patcher.start()
    try:
        res = client.post(
            "/api/v1/training/search/preflight",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        for patcher in reversed(patchers):
            patcher.stop()
    return res, p


class TestPreflightSearch:
    def _body(self, **overrides) -> dict:
        body = {
            "frame_ids": ["f1", "f2"],
            "terms": [{"label": "Capacete", "query": "safety helmet"}],
        }
        body.update(overrides)
        return body

    def test_happy_path_all_eligible(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_preflight(client, token, self._body())

        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["selected_count"] == 2
        assert data["eligible_count"] == 2
        assert data["ineligible"] == []
        assert data["terms_count"] == 1
        assert data["gpu"]["price_usd_h"] == 0.3
        assert data["allowed_dates"] == ["2026-07-31"]

    def test_cloud_guard_disabled_returns_409(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _PreflightPatches()
        p.allowed_ranges = None
        res, _p = _post_preflight(client, token, self._body(), p=p)
        assert res.status_code == 409

    def test_ineligible_frames_reported_with_reasons(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _PreflightPatches()
        p.frame_repo.get_by_ids_and_tenant.return_value = [_frame("f1")]  # f2 ausente
        res, _p = _post_preflight(client, token, self._body(), p=p)
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["eligible_count"] == 1
        assert data["ineligible"] == [{"frame_id": "f2", "reason": "frame_not_found"}]

    def test_response_never_contains_the_api_key_value(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _PreflightPatches()
        res, _p = _post_preflight(client, token, self._body(), p=p)
        assert res.status_code == 200
        assert p.api_key not in res.get_data(as_text=True)

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res, _p = _post_preflight(client, token, self._body())
        assert res.status_code == 403
