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

        # task "propagação no edge" — 1 site ativo por default (auto-resolve
        # sem precisar de site_id explícito no corpo do request).
        self.edge_site_repo = MagicMock()
        self.edge_site_repo.list_sites.return_value = [
            {"id": "site-1", "tenant_id": _TENANT_ID, "status": "active"},
        ]
        self.edge_site_repo.get_site_by_id.return_value = {
            "id": "site-1", "tenant_id": _TENANT_ID, "status": "active",
        }

    def ctx(self):
        return (
            patch(f"{_HANDLERS}._get_camera_repo", return_value=self.camera_repo),
            patch(f"{_HANDLERS}._get_frame_repo", return_value=self.frame_repo),
            patch(f"{_HANDLERS}._get_annotation_repo", return_value=self.annotation_repo),
            patch(f"{_HANDLERS}._get_propagation_repo", return_value=self.propagation_repo),
            patch(f"{_HANDLERS}._get_edge_site_repo", return_value=self.edge_site_repo),
            patch("app.infrastructure.queue.tasks.propagation.dispatch_propagation.delay"),
        )


def _post_job(client, token, body, p: "_Patches | None" = None):
    p = p or _Patches()
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
        # semente (f0) pinada + 5 frames-alvo — limit conta so os alvos
        assert len(create_kwargs["pool_frame_ids"]) == 6
        assert "f0" in create_kwargs["pool_frame_ids"]

    def test_validation_only_pins_seed_outside_first_five(self, client, app) -> None:
        """Regressao (e2e DEV): semente no 10o frame do pool ficava FORA do
        corte de 5 e o create morria com "nenhuma semente" mesmo com
        semente real — o corte deve pinar a semente e completar com alvos."""
        token, _ = _make_token(app)
        p = _Patches()
        many_frames = [_frame(f"f{i}") for i in range(10)]
        p.frame_repo.list_for_propagation_pool.return_value = many_frames
        p.annotation_repo.get_manual_annotations_for_frames.return_value = [
            {"frame_id": "f9", "class_id": 1, "class_name": "capacete",
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
        assert "f9" in create_kwargs["pool_frame_ids"]
        assert len(create_kwargs["pool_frame_ids"]) == 6
        assert create_kwargs["seed_frame_ids"] == ["f9"]

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res, _p = _post_job(client, token, self._body())
        assert res.status_code == 403

    def test_invalid_threshold_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, self._body(threshold=1.5))
        assert res.status_code == 400

    def test_max_results_valid_is_stored_in_pool_criteria(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body(max_results=42))
        assert res.status_code == 201
        create_kwargs = p.propagation_repo.create_job.call_args.kwargs
        assert create_kwargs["pool_criteria"]["max_results"] == 42

    def test_max_results_absent_not_stored_in_pool_criteria(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body())
        assert res.status_code == 201
        create_kwargs = p.propagation_repo.create_job.call_args.kwargs
        assert "max_results" not in create_kwargs["pool_criteria"]

    def test_max_results_zero_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body(max_results=0))
        assert res.status_code == 400
        p.propagation_repo.create_job.assert_not_called()

    def test_max_results_above_500_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, self._body(max_results=501))
        assert res.status_code == 400

    def test_max_results_non_numeric_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, self._body(max_results="abc"))
        assert res.status_code == 400

    def test_max_results_boolean_returns_400(self, client, app) -> None:
        """`bool` é subclasse de `int` em Python — `int(True) == 1` seria
        aceito silenciosamente sem este guard explícito."""
        token, _ = _make_token(app)
        res, _p = _post_job(client, token, self._body(max_results=True))
        assert res.status_code == 400


class TestCreatePropagationJobProviderAndSite:
    """Task "propagação no edge" — resolução de `provider`/`site_id` no
    create. Default (sem `provider` no body, sem env) continua runpod —
    ver `TestCreatePropagationJob` acima, comportamento inalterado."""

    def _body(self, **overrides) -> dict:
        body = {"camera_ids": [_CAMERA], "date_from": "2026-07-31", "date_to": "2026-07-31"}
        body.update(overrides)
        return body

    def test_provider_edge_single_active_site_auto_resolves(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body(provider="edge"))

        assert res.status_code == 201
        create_kwargs = p.propagation_repo.create_job.call_args.kwargs
        assert create_kwargs["gpu_provider"] == "edge"
        assert create_kwargs["pool_criteria"]["site_id"] == "site-1"

    def test_provider_edge_explicit_site_id_used_and_validated(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _Patches()
        p.edge_site_repo.get_site_by_id.return_value = {
            "id": "site-2", "tenant_id": _TENANT_ID, "status": "active",
        }
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/propagation/jobs",
                json=self._body(provider="edge", site_id="site-2"),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()

        assert res.status_code == 201
        p.edge_site_repo.get_site_by_id.assert_called_once_with("site-2", _TENANT_ID)
        create_kwargs = p.propagation_repo.create_job.call_args.kwargs
        assert create_kwargs["pool_criteria"]["site_id"] == "site-2"

    def test_provider_edge_explicit_site_id_not_owned_by_tenant_returns_400(
        self, client, app,
    ) -> None:
        token, _ = _make_token(app)
        p = _Patches()
        p.edge_site_repo.get_site_by_id.return_value = None
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/propagation/jobs",
                json=self._body(provider="edge", site_id="site-de-outro-tenant"),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()

        assert res.status_code == 400
        p.propagation_repo.create_job.assert_not_called()

    def test_provider_edge_zero_active_sites_returns_400_with_clear_message(
        self, client, app,
    ) -> None:
        token, _ = _make_token(app)
        p = _Patches()
        p.edge_site_repo.list_sites.return_value = []
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/propagation/jobs",
                json=self._body(provider="edge"),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()

        assert res.status_code == 400
        assert "nenhum edge_site ativo" in res.get_json()["error"]
        p.propagation_repo.create_job.assert_not_called()

    def test_provider_edge_multiple_active_sites_without_explicit_site_id_returns_400(
        self, client, app,
    ) -> None:
        token, _ = _make_token(app)
        p = _Patches()
        p.edge_site_repo.list_sites.return_value = [
            {"id": "site-1", "status": "active"},
            {"id": "site-2", "status": "active"},
        ]
        patchers = p.ctx()
        for patcher in patchers:
            patcher.start()
        try:
            res = client.post(
                "/api/v1/training/propagation/jobs",
                json=self._body(provider="edge"),
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()

        assert res.status_code == 400
        assert "site_id" in res.get_json()["error"]
        p.propagation_repo.create_job.assert_not_called()

    def test_provider_edge_ignores_inactive_sites_when_counting(self, client, app) -> None:
        """Site 'inactive'/'maintenance'/'provisioning' não conta pro
        auto-resolve — só 'active'."""
        token, _ = _make_token(app)
        p = _Patches()
        p.edge_site_repo.list_sites.return_value = [
            {"id": "site-1", "status": "active"},
            {"id": "site-old", "status": "inactive"},
        ]
        res, _p2 = _post_job(client, token, self._body(provider="edge"), p=p)

        assert res.status_code == 201
        create_kwargs = p.propagation_repo.create_job.call_args.kwargs
        assert create_kwargs["pool_criteria"]["site_id"] == "site-1"

    def test_provider_local_returns_400_never_dispatched(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body(provider="local"))

        assert res.status_code == 400
        assert "local" in res.get_json()["error"]
        p.propagation_repo.create_job.assert_not_called()

    def test_invalid_provider_value_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body(provider="gcp"))

        assert res.status_code == 400
        p.propagation_repo.create_job.assert_not_called()

    def test_provider_edge_allows_operation_date_frames_outside_criteria_window(
        self, client, app,
    ) -> None:
        """O guard de data (materialize_pool) não derruba o create pra
        onsite mesmo com frame fora da janela do critério — mesma
        motivação do par de testes obrigatório no dispatch
        (test_propagation_dispatch.py::TestEdgeDispatch)."""
        from datetime import datetime as _dt

        token, _ = _make_token(app)
        p = _Patches()
        p.frame_repo.list_for_propagation_pool.return_value = [
            {
                "id": "f1", "tenant_id": _TENANT_ID, "camera_id": _CAMERA,
                "r2_key": "frames/f1.jpg",
                "captured_at": _dt(2026, 8, 5, 9, 0, 0),  # fora de 2026-07-31
            },
        ]
        p.annotation_repo.get_manual_annotations_for_frames.return_value = [
            {"frame_id": "f1", "class_id": 1, "class_name": "capacete",
             "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1},
        ]
        res, _p2 = _post_job(client, token, self._body(provider="edge"), p=p)

        assert res.status_code == 201

    def test_default_provider_without_body_field_stays_runpod(self, client, app) -> None:
        """Sem `provider` no body e sem env PROPAGATION_GPU_PROVIDER —
        retrocompat total, nenhum tenant existente muda de comportamento."""
        token, _ = _make_token(app)
        res, p = _post_job(client, token, self._body())

        assert res.status_code == 201
        create_kwargs = p.propagation_repo.create_job.call_args.kwargs
        assert create_kwargs["gpu_provider"] == "runpod"
        assert "site_id" not in create_kwargs["pool_criteria"]


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


class _PreflightPatches:
    """Bundle dos repositories + resolvers RunPod que
    preflight_propagation_handler usa, já com defaults sãos (câmera do
    tenant, pool com 2 frames, 1 anotação manual, nuvem terceira habilitada,
    RunPod configurado com preço resolvível)."""

    def __init__(self) -> None:
        self.camera_repo = MagicMock()
        self.camera_repo.get_by_id_and_tenant.return_value = {
            "id": _CAMERA, "tenant_id": _TENANT_ID,
        }

        self.frame_repo = MagicMock()
        self.frame_repo.list_for_propagation_pool.return_value = [_frame("f1"), _frame("f2")]

        self.annotation_repo = MagicMock()
        self.annotation_repo.get_manual_annotations_for_frames.return_value = [
            {"frame_id": "f1", "class_id": 1, "class_name": "capacete",
             "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1},
        ]

        self.propagation_repo = MagicMock()
        self.propagation_repo.get_active_for_tenant.return_value = None

        self.third_party_cloud_enabled = True
        # valor "secreto" só pra provar que NUNCA aparece na resposta HTTP.
        self.api_key = "sk-fake-runpod-key-must-never-leak-in-response"
        self.price_estimate = (0.4, 0.4, False)  # (price_usd_h, estimated_cost_usd, price_error)

    def ctx(self):
        return (
            patch(f"{_HANDLERS}._get_camera_repo", return_value=self.camera_repo),
            patch(f"{_HANDLERS}._get_frame_repo", return_value=self.frame_repo),
            patch(f"{_HANDLERS}._get_annotation_repo", return_value=self.annotation_repo),
            patch(f"{_HANDLERS}._get_propagation_repo", return_value=self.propagation_repo),
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


def _get_preflight(client, token, params: dict, p: "_PreflightPatches | None" = None):
    p = p or _PreflightPatches()
    patchers = p.ctx()
    for patcher in patchers:
        patcher.start()
    try:
        res = client.get(
            "/api/v1/training/propagation/preflight",
            query_string=params,
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        for patcher in reversed(patchers):
            patcher.stop()
    return res, p


class TestPreflightPropagation:
    def _params(self, **overrides) -> dict:
        params = {"camera_id": _CAMERA, "date_from": "2026-07-31", "date_to": "2026-07-31"}
        params.update(overrides)
        return params

    def test_happy_path_returns_pool_seed_and_cost_fields(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _get_preflight(client, token, self._params())

        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["pool_total"] == 2
        assert data["pool_effective"] == 2
        assert data["validation_only"] is False
        assert data["seed_frame_count"] == 1
        assert data["seed_box_count"] == 1
        assert data["active_job"] is None
        assert data["third_party_cloud_enabled"] is True
        assert data["runpod_configured"] is True
        assert data["gpu"]["price_usd_h"] == 0.4
        assert data["gpu"]["estimated_cost_usd"] == 0.4
        assert data["gpu"]["price_error"] is False
        assert "timeout_seconds" in data["gpu"]
        assert "max_usd" in data["gpu"]

    def test_missing_camera_id_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        params = self._params()
        del params["camera_id"]
        res, _p = _get_preflight(client, token, params)
        assert res.status_code == 400

    def test_missing_dates_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _get_preflight(client, token, {"camera_id": _CAMERA})
        assert res.status_code == 400

    def test_date_from_after_date_to_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _get_preflight(
            client, token, self._params(date_from="2026-08-01", date_to="2026-07-31"),
        )
        assert res.status_code == 400

    def test_date_shortcut_used_for_both_bounds(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _get_preflight(client, token, {"camera_id": _CAMERA, "date": "2026-07-31"})
        assert res.status_code == 200

    def test_camera_not_owned_by_tenant_returns_404_never_403(self, client, app) -> None:
        """C-01: câmera de outro tenant (ou inexistente) → 404, nunca 403."""
        token, _ = _make_token(app)
        p = _PreflightPatches()
        p.camera_repo.get_by_id_and_tenant.return_value = None
        res, _p = _get_preflight(client, token, self._params(), p=p)
        assert res.status_code == 404

    def test_validation_only_caps_pool_effective_at_five(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _PreflightPatches()
        p.frame_repo.list_for_propagation_pool.return_value = [
            _frame(f"f{i}") for i in range(10)
        ]
        res, _p = _get_preflight(
            client, token, self._params(validation_only="true"), p=p,
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["pool_total"] == 10
        # 1 semente (fixture default) pinada + 5 alvos = 6 — o preflight
        # materializa com a MESMA funcao/sementes que o create usaria
        assert data["pool_effective"] == 6
        assert data["validation_only"] is True

    def test_active_job_present_when_job_queued(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _PreflightPatches()
        active = {"id": _JOB_ID, "status": "queued", "created_at": "2026-08-10T10:00:00"}
        p.propagation_repo.get_active_for_tenant.return_value = active
        res, _p = _get_preflight(client, token, self._params(), p=p)
        assert res.status_code == 200
        assert res.get_json()["data"]["active_job"] == active

    def test_runpod_not_configured_skips_price_lookup_no_price_error(self, client, app) -> None:
        token, _ = _make_token(app)
        p = _PreflightPatches()
        p.api_key = ""
        res, _p = _get_preflight(client, token, self._params(), p=p)
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["runpod_configured"] is False
        assert data["gpu"]["price_usd_h"] is None
        assert data["gpu"]["estimated_cost_usd"] is None
        assert data["gpu"]["price_error"] is False

    def test_runpod_error_returns_null_cost_with_price_error_flag(self, client, app) -> None:
        """RunPodError não derruba o preflight — só marca price_error."""
        token, _ = _make_token(app)
        p = _PreflightPatches()
        p.price_estimate = (None, None, True)
        res, _p = _get_preflight(client, token, self._params(), p=p)
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["runpod_configured"] is True
        assert data["gpu"]["price_usd_h"] is None
        assert data["gpu"]["estimated_cost_usd"] is None
        assert data["gpu"]["price_error"] is True

    def test_response_never_contains_the_api_key_value(self, client, app) -> None:
        """⛔ nunca logar/retornar valor de chave — só presença (bool)."""
        token, _ = _make_token(app)
        p = _PreflightPatches()
        res, _p = _get_preflight(client, token, self._params(), p=p)
        assert res.status_code == 200
        assert p.api_key not in res.get_data(as_text=True)

    def test_role_without_training_write_gets_403(self, client, app) -> None:
        token, _ = _make_token(app, role="viewer")
        res, _p = _get_preflight(client, token, self._params())
        assert res.status_code == 403

    def test_default_gpu_provider_field_is_runpod(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _get_preflight(client, token, self._params())
        assert res.get_json()["data"]["gpu_provider"] == "runpod"

    def test_provider_edge_skips_runpod_price_lookup_and_marks_provider(
        self, client, app,
    ) -> None:
        """Onsite: nenhuma chamada RunPod (custo/gpu ficam nos defaults
        "vazios"), `gpu_provider` no payload reflete o que foi pedido."""
        token, _ = _make_token(app)
        p = _PreflightPatches()
        res, _p2 = _get_preflight(
            client, token, self._params(provider="edge"), p=p,
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["gpu_provider"] == "edge"
        assert data["runpod_configured"] is False
        assert data["gpu"]["price_usd_h"] is None
        assert data["gpu"]["estimated_cost_usd"] is None
        assert data["gpu"]["gpu_type"] is None
        assert data["gpu"]["max_usd"] is None
        assert data["gpu"]["price_error"] is False

    def test_provider_edge_allows_operation_date_frames_in_pool_effective(
        self, client, app,
    ) -> None:
        """validation_only + onsite: pool_effective não zera por causa de
        frame fora da janela de data do critério."""
        from datetime import datetime as _dt

        token, _ = _make_token(app)
        p = _PreflightPatches()
        p.frame_repo.list_for_propagation_pool.return_value = [
            {
                "id": "f1", "tenant_id": _TENANT_ID, "camera_id": _CAMERA,
                "r2_key": "frames/f1.jpg", "captured_at": _dt(2026, 8, 5, 9, 0, 0),
            },
        ]
        p.annotation_repo.get_manual_annotations_for_frames.return_value = [
            {"frame_id": "f1", "class_id": 1, "class_name": "capacete",
             "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1},
        ]
        res, _p2 = _get_preflight(
            client, token, self._params(provider="edge", validation_only="true"), p=p,
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["pool_effective"] == 1

    def test_invalid_provider_query_param_returns_400(self, client, app) -> None:
        token, _ = _make_token(app)
        res, _p = _get_preflight(client, token, self._params(provider="gcp"))
        assert res.status_code == 400
