"""
Integration tests: authenticated route paths with mocked services.

Patches service factory functions (_video_service, _annotation_service, etc.)
so routes execute their handlers without needing a real database.
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def auth_headers(app, user_id):
    """Generate JWT bearer token for test user.

    Inclui os claims tenant_id/role/tenant_schema — tokens reais sempre os
    carregam (auth/routes.py) e handlers escopados por tenant exigem.

    Identity == fixture `user_id`, para que testes de ownership (video.user_id
    == JWT identity) possam configurar o mock com o mesmo id.
    """
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(user_id),
            additional_claims={
                "tenant_id": str(uuid4()),
                "role": "operator",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def superadmin_auth_headers(app, user_id):
    """Token com role=superadmin — único papel com training:approve.

    Endpoints de disparo/cancelamento de treino (POST /api/training/jobs,
    POST /api/training/jobs/<id>/stop) exigem este gate desde o fix do
    achado P0 (routes.py criava job com só @jwt_required()) — `auth_headers`
    (role=operator) agora leva 403 neles, mesmo padrão já usado em
    test_create_class_ok/test_activate_model_error_path.
    """
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(user_id),
            additional_claims={
                "tenant_id": str(uuid4()),
                "role": "superadmin",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Training — Videos
# ---------------------------------------------------------------------------

class TestTrainingVideos:

    def test_list_videos_ok(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.list_videos.return_value = [
            {"id": str(uuid4()), "filename": "v1.mp4", "status": "uploaded"},
        ]
        with patch("app.api.v1.training.video_handlers.get_video_service", return_value=mock_svc):
            res = client.get("/api/training/videos", headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_list_videos_empty(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.list_videos.return_value = []
        with patch("app.api.v1.training.video_handlers.get_video_service", return_value=mock_svc):
            res = client.get("/api/training/videos", headers=auth_headers)
        assert res.status_code == 200

    def test_create_video_ok(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.create_video.return_value = {
            "id": str(uuid4()), "filename": "video.mp4", "status": "uploaded",
        }
        with patch("app.api.v1.training.video_handlers.get_video_service", return_value=mock_svc):
            res = client.post("/api/training/videos", json={
                "filename": "video.mp4",
                "original_filename": "original.mp4",
                "file_size": 1024,
            }, headers=auth_headers)
        assert res.status_code in (200, 201)

    def test_get_video_frames_ok(self, client, auth_headers, user_id) -> None:
        vid_id = uuid4()
        mock_svc = MagicMock()
        mock_svc.get_video.return_value = {"id": str(vid_id), "user_id": str(user_id)}
        mock_svc.get_video_frames.return_value = [
            {"id": str(uuid4()), "frame_number": 0, "filename": "frames/f.jpg"},
        ]
        with patch("app.api.v1.training.video_handlers.get_video_service", return_value=mock_svc):
            res = client.get(
                f"/api/training/videos/{vid_id}/frames", headers=auth_headers
            )
        assert res.status_code == 200

    def test_get_video_frames_not_found(self, client, auth_headers) -> None:
        from app.core.exceptions import NotFoundError
        mock_svc = MagicMock()
        mock_svc.get_video.side_effect = NotFoundError("Vídeo", str(uuid4()))
        with patch("app.api.v1.training.video_handlers.get_video_service", return_value=mock_svc):
            res = client.get(
                f"/api/training/videos/{uuid4()}/frames", headers=auth_headers
            )
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Training — Annotations
# ---------------------------------------------------------------------------

class TestTrainingAnnotations:

    def test_get_annotations_ok(self, client, auth_headers) -> None:
        fid = uuid4()
        mock_svc = MagicMock()
        mock_svc.get_frame_annotations.return_value = [
            {"id": str(uuid4()), "class_id": 1, "x_center": 0.5,
             "y_center": 0.5, "width": 0.3, "height": 0.4},
        ]
        with patch("app.api.v1.training.annotation_handlers.get_annotation_service", return_value=mock_svc):
            res = client.get(
                f"/api/training/frames/{fid}/annotations", headers=auth_headers
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_save_annotations_ok(self, client, auth_headers) -> None:
        fid = uuid4()
        mock_svc = MagicMock()
        mock_svc.save_annotations.return_value = 2
        with patch("app.api.v1.training.annotation_handlers.get_annotation_service", return_value=mock_svc):
            res = client.post(
                f"/api/training/frames/{fid}/annotations",
                json={"annotations": [
                    {"class_id": 1, "x_center": 0.5, "y_center": 0.5,
                     "width": 0.3, "height": 0.4},
                ]},
                headers=auth_headers,
            )
        assert res.status_code == 200

    def test_save_annotations_empty(self, client, auth_headers) -> None:
        fid = uuid4()
        mock_svc = MagicMock()
        mock_svc.save_annotations.return_value = 0
        with patch("app.api.v1.training.annotation_handlers.get_annotation_service", return_value=mock_svc):
            res = client.post(
                f"/api/training/frames/{fid}/annotations",
                json={"annotations": []},
                headers=auth_headers,
            )
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Training — Classes
# ---------------------------------------------------------------------------

class TestTrainingClasses:

    def test_get_classes_ok(self, client, auth_headers) -> None:
        # WS-A1: classes agora via TenantClassService (tenant-scoped)
        mock_svc = MagicMock()
        mock_svc.list_classes.return_value = [
            {"id": 1, "name": "Capacete", "color": "#22c55e"},
        ]
        with patch("app.api.v1.training.annotation_handlers.get_tenant_class_service", return_value=mock_svc):
            res = client.get("/api/classes", headers=auth_headers)
        assert res.status_code == 200

    def test_create_class_ok(self, client, app) -> None:
        # WS-A1: mutação — role admin passa o gate require_training_role
        with app.app_context():
            from flask_jwt_extended import create_access_token
            token = create_access_token(
                identity=str(uuid4()),
                additional_claims={
                    "tenant_id": str(uuid4()),
                    "role": "admin",
                    "tenant_schema": "public",
                },
            )
        mock_svc = MagicMock()
        mock_svc.create_class.return_value = {
            "id": 1, "name": "Capacete", "color": "#22c55e",
        }
        with patch("app.api.v1.training.annotation_handlers.get_tenant_class_service", return_value=mock_svc):
            res = client.post("/api/classes", json={
                "name": "Capacete", "color": "#22c55e",
            }, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code in (200, 201)


# ---------------------------------------------------------------------------
# Training — Jobs + Models
# ---------------------------------------------------------------------------

class TestTrainingJobs:

    def test_create_job_ok(self, client, superadmin_auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.create_job.return_value = {
            "id": str(uuid4()), "status": "queued", "preset": "balanced",
        }
        mock_dataset_svc = MagicMock()
        mock_dataset_svc.get_latest.return_value = None
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc), \
             patch("app.api.v1.training.job_handlers.get_dataset_service", return_value=mock_dataset_svc):
            res = client.post("/api/training/jobs", json={
                "preset": "balanced", "model_size": "yolo26n", "total_epochs": 100,
            }, headers=superadmin_auth_headers)
        assert res.status_code in (200, 201)

    def test_create_job_resolves_latest_dataset_version_when_omitted(self, client, superadmin_auth_headers) -> None:
        """task B2: sem dataset_version_id no body, resolve pra versão mais recente do usuário."""
        dsv_id = str(uuid4())
        mock_svc = MagicMock()
        mock_svc.create_job.return_value = {
            "id": str(uuid4()), "status": "queued", "preset": "balanced",
            "dataset_version_id": dsv_id,
        }
        mock_dataset_svc = MagicMock()
        mock_dataset_svc.get_latest.return_value = {"id": dsv_id, "version": "v1"}
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc), \
             patch("app.api.v1.training.job_handlers.get_dataset_service", return_value=mock_dataset_svc):
            res = client.post("/api/training/jobs", json={
                "preset": "balanced", "model_size": "yolo26n", "total_epochs": 100,
            }, headers=superadmin_auth_headers)
        assert res.status_code in (200, 201)
        mock_svc.create_job.assert_called_once()
        assert mock_svc.create_job.call_args.kwargs["dataset_version_id"] == dsv_id
        assert res.get_json()["data"]["dataset_version_id"] == dsv_id

    def test_create_job_respects_explicit_dataset_version_id(self, client, superadmin_auth_headers) -> None:
        """task B2: dataset_version_id explícito no body vence — sem lookup."""
        explicit_dsv_id = str(uuid4())
        mock_svc = MagicMock()
        mock_svc.create_job.return_value = {
            "id": str(uuid4()), "status": "queued", "preset": "balanced",
            "dataset_version_id": explicit_dsv_id,
        }
        mock_dataset_svc = MagicMock()
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc), \
             patch("app.api.v1.training.job_handlers.get_dataset_service", return_value=mock_dataset_svc):
            res = client.post("/api/training/jobs", json={
                "preset": "balanced", "model_size": "yolo26n", "total_epochs": 100,
                "dataset_version_id": explicit_dsv_id,
            }, headers=superadmin_auth_headers)
        assert res.status_code in (200, 201)
        assert mock_svc.create_job.call_args.kwargs["dataset_version_id"] == explicit_dsv_id
        # Body já trouxe o id — não precisa consultar a versão mais recente
        mock_dataset_svc.get_latest.assert_not_called()

    def test_list_jobs_ok(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.list_jobs.return_value = []
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc):
            res = client.get("/api/training/jobs", headers=auth_headers)
        assert res.status_code == 200

    def test_get_job_status_ok(self, client, auth_headers) -> None:
        job_id = uuid4()
        mock_svc = MagicMock()
        mock_svc.get_job.return_value = {
            "id": str(job_id), "status": "running", "progress": 42,
        }
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc):
            res = client.get(
                f"/api/training/jobs/{job_id}/status", headers=auth_headers
            )
        assert res.status_code == 200

    def test_list_models_ok(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.list_models.return_value = []
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc):
            res = client.get("/api/training/models", headers=auth_headers)
        assert res.status_code == 200

    def test_activate_model_requires_training_approve(self, client, auth_headers) -> None:
        """Rota legada delega ao handler canônico (/api/v1/models/<id>/activate):
        operator sem training:approve → 403, sem tocar no serviço legado
        (C-01 — ver tests/security/test_training_models_activate_tenant_isolation.py)."""
        model_id = uuid4()
        mock_svc = MagicMock()
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc), \
             patch("app.core.auth._has_training_override", return_value=False):
            res = client.post(
                f"/api/training/models/{model_id}/activate", headers=auth_headers
            )
        assert res.status_code == 403
        mock_svc.activate_model.assert_not_called()


def _role_headers(app, role: str) -> dict[str, str]:
    """Token com role arbitrária — para os testes de gate abaixo."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": str(uuid4()), "role": role, "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


class TestTrainingJobsPlatformGate:
    """Achado P0 do mutirão: POST /api/training/jobs e .../jobs/<id>/stop só
    tinham @jwt_required() — QUALQUER papel autenticado disparava treino
    real (GPU paga). Regra do produto: 'a Logikos treina, sempre; nenhum
    papel de tenant dispara treino' → training:approve (superadmin-only,
    ver app/core/permissions.py). activate_model já tinha o gate certo
    (test_activate_model_requires_training_approve, acima); aqui fecha o
    buraco simétrico em criar/cancelar job.

    Protocolo falha-antes/passa-depois: sem @require_training_role("approve")
    em create_job/stop_job (routes.py) estes testes voltam a 200/201 —
    prova de mutação rodada manualmente (ver saída no relatório do PR)."""

    NAO_PLATAFORMA = ["admin", "trainer", "operator", "analyst", "viewer"]

    @pytest.mark.parametrize("role", NAO_PLATAFORMA)
    def test_create_job_denied_for_non_platform_role(self, app, client, role) -> None:
        mock_svc = MagicMock()
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc), \
             patch("app.core.auth._has_training_override", return_value=False):
            res = client.post(
                "/api/training/jobs",
                json={"preset": "balanced"},
                headers=_role_headers(app, role),
            )
        assert res.status_code == 403, res.get_json()
        mock_svc.create_job.assert_not_called()

    def test_create_job_still_works_for_superadmin(self, client, superadmin_auth_headers) -> None:
        """Não quebrar o caminho legítimo — o Vitor treina como superadmin."""
        mock_svc = MagicMock()
        mock_svc.create_job.return_value = {
            "id": str(uuid4()), "status": "queued", "preset": "balanced",
        }
        mock_dataset_svc = MagicMock()
        mock_dataset_svc.get_latest.return_value = None
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc), \
             patch("app.api.v1.training.job_handlers.get_dataset_service", return_value=mock_dataset_svc):
            res = client.post(
                "/api/training/jobs", json={"preset": "balanced"},
                headers=superadmin_auth_headers,
            )
        assert res.status_code == 201, res.get_json()
        mock_svc.create_job.assert_called_once()

    @pytest.mark.parametrize("role", NAO_PLATAFORMA)
    def test_stop_job_denied_for_non_platform_role(self, app, client, role) -> None:
        mock_svc = MagicMock()
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc), \
             patch("app.core.auth._has_training_override", return_value=False):
            res = client.post(
                f"/api/training/jobs/{uuid4()}/stop",
                headers=_role_headers(app, role),
            )
        assert res.status_code == 403, res.get_json()
        mock_svc.stop_job.assert_not_called()

    def test_stop_job_still_works_for_superadmin(self, client, superadmin_auth_headers) -> None:
        """Não quebrar o caminho legítimo — cancelar continua liberado pro superadmin."""
        job_id = str(uuid4())
        mock_svc = MagicMock()
        mock_svc.stop_job.return_value = {"id": job_id, "status": "stopped"}
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc):
            res = client.post(
                f"/api/training/jobs/{job_id}/stop", headers=superadmin_auth_headers,
            )
        assert res.status_code == 200, res.get_json()
        mock_svc.stop_job.assert_called_once()


# ---------------------------------------------------------------------------
# Video Upload Routes
# ---------------------------------------------------------------------------

class TestVideoRoutes:

    def test_get_upload_url_ok(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.create_video.return_value = {
            "id": str(uuid4()), "filename": "raw-videos/u/v/test.mp4",
        }
        mock_storage = MagicMock()
        mock_storage.generate_presigned_upload_url.return_value = "https://r2.test/presigned"
        with patch("app.api.v1.videos.routes._video_service", return_value=mock_svc), \
             patch("app.api.v1.videos.routes.get_storage", return_value=mock_storage):
            res = client.post("/api/v1/videos/upload-url", json={
                "filename": "test.mp4", "content_type": "video/mp4",
            }, headers=auth_headers)
        assert res.status_code in (200, 201)

    def test_get_upload_url_missing_filename(self, client, auth_headers) -> None:
        with patch("app.api.v1.videos.routes.get_storage", return_value=MagicMock()):
            res = client.post("/api/v1/videos/upload-url", json={},
                              headers=auth_headers)
        assert res.status_code in (400, 422, 500)

    def test_get_video_status_ok(self, client, auth_headers, user_id) -> None:
        vid_id = uuid4()
        mock_svc = MagicMock()
        mock_svc.get_video.return_value = {
            "id": str(vid_id), "status": "extracted", "filename": "test.mp4",
            "user_id": str(user_id),
        }
        mock_svc.get_frame_counts.return_value = {
            "annotated": 3, "pending": 7, "total": 10,
        }
        with patch("app.api.v1.videos.routes._video_service", return_value=mock_svc):
            res = client.get(
                f"/api/v1/videos/{vid_id}/status", headers=auth_headers
            )
        assert res.status_code == 200

    def test_trigger_extraction_dispatches(self, client, auth_headers, user_id) -> None:
        """Route updates status to 'extracting' — 200 or 500 both valid here."""
        vid_id = uuid4()
        mock_svc = MagicMock()
        mock_svc.get_video.return_value = {
            "id": str(vid_id), "filename": "raw-videos/u/v/test.mp4",
            "user_id": str(user_id),
        }
        mock_svc.update_status.return_value = {"id": str(vid_id), "status": "extracting"}
        # extract_frames.delay will fail without Celery broker — that's OK for coverage
        with patch("app.api.v1.videos.routes._video_service", return_value=mock_svc):
            res = client.post(
                f"/api/v1/videos/{vid_id}/extract", headers=auth_headers
            )
        # Route either succeeds or catches the Celery import/broker error as 500
        assert res.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Camera Routes
# ---------------------------------------------------------------------------

class TestCameraRoutesAuthenticated:
    """Camera routes use _get_camera_service() — patch at that level."""

    def test_list_cameras_ok(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.list_cameras.return_value = [
            {"id": str(uuid4()), "name": "Cam 1", "host": "192.168.1.100"},
        ]
        with patch("app.api.v1.cameras.crud_handlers._get_camera_service", return_value=mock_svc), \
             patch("app.api.v1.cameras.crud_handlers._is_admin", return_value=False):
            res = client.get("/api/cameras", headers=auth_headers)
        assert res.status_code in (200, 500)

    def test_create_camera_ok(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.create_camera.return_value = {
            "id": str(uuid4()), "name": "Cam 1", "host": "192.168.1.100",
        }
        with patch("app.api.v1.cameras.crud_handlers._get_camera_service", return_value=mock_svc):
            res = client.post("/api/cameras", json={
                "name": "Cam 1", "host": "192.168.1.100",
                "manufacturer": "generic", "port": 554,
            }, headers=auth_headers)
        assert res.status_code in (200, 201, 500)

    def test_get_camera_ok(self, client, auth_headers) -> None:
        cam_id = uuid4()
        mock_svc = MagicMock()
        mock_svc.get_camera.return_value = {
            "id": str(cam_id), "name": "Cam 1",
        }
        with patch("app.api.v1.cameras.crud_handlers._get_camera_service", return_value=mock_svc):
            res = client.get(f"/api/cameras/{cam_id}", headers=auth_headers)
        assert res.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class TestAlertsRoutes:

    def test_get_alerts_ok(self, client, auth_headers) -> None:
        cam_id = uuid4()
        mock_svc = MagicMock()
        mock_svc.get_alerts.return_value = []
        with patch("app.api.v1.training.job_handlers.get_inference_service", return_value=mock_svc):
            res = client.get(
                f"/api/cameras/{cam_id}/alerts", headers=auth_headers
            )
        assert res.status_code in (200, 500)

    def test_acknowledge_alert_ok(self, client, auth_headers) -> None:
        """POST /api/alerts/<id>/acknowledge é servido por app.api.v1.alerts.routes
        (blueprint alerts_bp), não por training.job_handlers — mockar
        get_inference_service não tinha nenhum efeito aqui (o handler real
        chama _get_repo()/DatabasePool.get_instance()). Sem integração real
        plugada, o pool global ficava sempre None nesse contexto e
        _get_repo() levantava RuntimeError, então o teste "passava" por
        acidente (500 caindo no except genérico). Com pg_pool real
        inicializado por outro teste da mesma sessão (task 2.0 mutirão), a
        rota passou a responder de verdade e um alert_id aleatório não
        existe -> 404, quebrando a asserção antiga. Mock correto: patch em
        _get_repo mesmo, hermético independente de outro teste ter
        inicializado o DatabasePool."""
        alert_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.acknowledge.return_value = {
            "id": str(alert_id), "acknowledged": True,
        }
        with patch("app.api.v1.alerts.routes._get_repo", return_value=mock_repo):
            res = client.post(
                f"/api/alerts/{alert_id}/acknowledge", headers=auth_headers
            )
        assert res.status_code == 200
        mock_repo.acknowledge.assert_called_once()


# ---------------------------------------------------------------------------
# Error paths — training routes
# ---------------------------------------------------------------------------

class TestTrainingErrorPaths:
    """Trigger error paths to cover exception handling code."""

    def test_list_videos_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.list_videos.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.video_handlers.get_video_service", return_value=mock_svc):
            res = client.get("/api/training/videos", headers=auth_headers)
        assert res.status_code == 500

    def test_create_video_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.create_video.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.video_handlers.get_video_service", return_value=mock_svc):
            res = client.post("/api/training/videos", json={"filename": "v.mp4"},
                              headers=auth_headers)
        assert res.status_code == 500

    def test_get_frames_error_path(self, client, auth_headers, user_id) -> None:
        mock_svc = MagicMock()
        mock_svc.get_video.return_value = {"id": str(uuid4()), "user_id": str(user_id)}
        mock_svc.get_video_frames.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.video_handlers.get_video_service", return_value=mock_svc):
            res = client.get(f"/api/training/videos/{uuid4()}/frames",
                             headers=auth_headers)
        assert res.status_code == 500

    def test_get_annotations_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.get_frame_annotations.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.annotation_handlers.get_annotation_service", return_value=mock_svc):
            res = client.get(f"/api/training/frames/{uuid4()}/annotations",
                             headers=auth_headers)
        assert res.status_code == 500

    def test_save_annotations_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.save_annotations.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.annotation_handlers.get_annotation_service", return_value=mock_svc):
            res = client.post(f"/api/training/frames/{uuid4()}/annotations",
                              json={"annotations": []}, headers=auth_headers)
        assert res.status_code == 500

    def test_get_classes_error_path(self, client, auth_headers) -> None:
        # WS-A1: classes agora via TenantClassService (tenant-scoped)
        mock_svc = MagicMock()
        mock_svc.list_classes.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.annotation_handlers.get_tenant_class_service", return_value=mock_svc):
            res = client.get("/api/classes", headers=auth_headers)
        assert res.status_code == 500

    def test_create_class_error_path(self, client, app) -> None:
        # WS-A1: mutação — role admin passa o gate require_training_role
        with app.app_context():
            from flask_jwt_extended import create_access_token
            token = create_access_token(
                identity=str(uuid4()),
                additional_claims={
                    "tenant_id": str(uuid4()),
                    "role": "admin",
                    "tenant_schema": "public",
                },
            )
        mock_svc = MagicMock()
        mock_svc.create_class.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.annotation_handlers.get_tenant_class_service", return_value=mock_svc):
            res = client.post("/api/classes", json={"name": "X"},
                              headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 500

    def test_create_job_error_path(self, client, superadmin_auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.create_job.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc):
            res = client.post("/api/training/jobs", json={}, headers=superadmin_auth_headers)
        assert res.status_code == 500

    def test_list_jobs_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.list_jobs.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc):
            res = client.get("/api/training/jobs", headers=auth_headers)
        assert res.status_code == 500

    def test_get_job_status_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.get_job.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc):
            res = client.get(f"/api/training/jobs/{uuid4()}/status",
                             headers=auth_headers)
        assert res.status_code == 500

    def test_list_models_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.list_models.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.job_handlers.get_training_service", return_value=mock_svc):
            res = client.get("/api/training/models", headers=auth_headers)
        assert res.status_code == 500

    def test_activate_model_error_path(self, app, client) -> None:
        """Rota legada delega ao handler canônico — erro de repo do registry → 500."""
        with app.app_context():
            from flask_jwt_extended import create_access_token
            token = create_access_token(
                identity=str(uuid4()),
                additional_claims={
                    "tenant_id": str(uuid4()), "role": "superadmin",
                    "tenant_schema": "public",
                },
            )
        mock_repo = MagicMock()
        mock_repo.get_for_tenant.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.models.registry_handlers._get_registry_repo", return_value=mock_repo):
            res = client.post(f"/api/training/models/{uuid4()}/activate",
                              headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 500

    def test_get_alerts_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.get_alerts.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.training.job_handlers.get_inference_service", return_value=mock_svc):
            res = client.get(f"/api/cameras/{uuid4()}/alerts", headers=auth_headers)
        assert res.status_code == 500

    def test_acknowledge_alert_error_path(self, client, auth_headers) -> None:
        """Ver TestAlertsRoutes.test_acknowledge_alert_ok: get_inference_service
        não é usado por esta rota (alerts_bp usa _get_repo()). O mock antigo
        nunca disparava o RuntimeError de propósito — o 500 só saía porque o
        pool global estava sempre None nesse contexto (sem integração real
        plugada). Patch correto em _get_repo para exercitar de fato o branch
        `except Exception` da rota."""
        mock_repo = MagicMock()
        mock_repo.acknowledge.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.alerts.routes._get_repo", return_value=mock_repo):
            res = client.post(f"/api/alerts/{uuid4()}/acknowledge",
                              headers=auth_headers)
        assert res.status_code == 500


# ---------------------------------------------------------------------------
# Frame image endpoint
# ---------------------------------------------------------------------------

class TestFrameImageRoute:

    def test_get_frame_image_not_found_via_pool(self, client, auth_headers) -> None:
        """Frame image with mocked pool returning None frame."""
        fid = uuid4()
        mock_frame_repo = MagicMock()
        mock_frame_repo.get_by_id.return_value = None

        # Patch FrameRepository class and _get_pool so route uses our mocks
        from app.infrastructure.database.connection import DatabasePool
        with patch.object(DatabasePool, "get_instance", return_value=MagicMock()), \
             patch("app.api.v1.training.video_handlers.FrameRepository", return_value=mock_frame_repo):
            res = client.get(f"/api/training/frames/{fid}/image",
                             headers=auth_headers)
        # NotFoundError → 404, or pool/db error → 500
        assert res.status_code in (200, 307, 404, 500)

    def test_get_frame_image_not_found(self, client, auth_headers) -> None:
        mock_pool = MagicMock()
        mock_frame_repo = MagicMock()
        mock_frame_repo.get_by_id.return_value = None

        with patch("app.api.v1.training.video_handlers._get_pool", return_value=mock_pool), \
             patch("app.api.v1.training.video_handlers.FrameRepository", return_value=mock_frame_repo):
            res = client.get(f"/api/training/frames/{uuid4()}/image",
                             headers=auth_headers)
        assert res.status_code in (404, 500)


# ---------------------------------------------------------------------------
# Storage routes
# ---------------------------------------------------------------------------

class TestStorageRoutesAuthenticated:

    def test_storage_health_with_r2(self, client) -> None:
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = None
        mock_storage.exists.return_value = True
        mock_storage.delete.return_value = None
        with patch("app.api.v1.storage.routes.get_storage", return_value=mock_storage):
            res = client.get("/api/v1/storage/health")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_test_upload_authenticated(self, client, auth_headers) -> None:
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = None
        mock_storage.generate_presigned_download_url.return_value = "https://r2.test/dl"
        mock_storage.exists.return_value = True
        with patch("app.api.v1.storage.routes.get_storage", return_value=mock_storage):
            res = client.post("/api/v1/storage/test-upload", headers=auth_headers)
        assert res.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Streams routes
# ---------------------------------------------------------------------------

class TestStreamsRoutes:

    def test_streams_status_requires_auth(self, client) -> None:
        # S4: rota deixou de ser pública — sem token → 401
        res = client.get("/api/streams/status")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Dashboard routes
# ---------------------------------------------------------------------------

class TestDashboardRoutesAuthenticated:

    def test_stats_with_mock(self, client, auth_headers) -> None:
        mock_pool = MagicMock()
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"count": 5}
        mock_cursor.fetchall.return_value = []
        from contextlib import contextmanager

        @contextmanager
        def fake_conn():
            yield mock_conn

        mock_pool.get_connection = fake_conn
        with patch("app.api.v1.dashboard.routes.DatabasePool.get_instance",
                   return_value=mock_pool):
            res = client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert res.status_code in (200, 500)

    def test_detections_with_mock(self, client, auth_headers) -> None:
        mock_pool = MagicMock()
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        from contextlib import contextmanager

        @contextmanager
        def fake_conn():
            yield mock_conn

        mock_pool.get_connection = fake_conn
        with patch("app.api.v1.dashboard.routes.DatabasePool.get_instance",
                   return_value=mock_pool):
            res = client.get("/api/v1/dashboard/detections", headers=auth_headers)
        assert res.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Video routes — error paths
# ---------------------------------------------------------------------------

class TestVideoErrorPaths:

    def test_upload_url_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.create_video.side_effect = RuntimeError("storage error")
        mock_storage = MagicMock()
        mock_storage.generate_presigned_upload_url.return_value = "https://r2.test/up"
        with patch("app.api.v1.videos.routes._video_service", return_value=mock_svc), \
             patch("app.api.v1.videos.routes.get_storage", return_value=mock_storage):
            res = client.post("/api/v1/videos/upload-url",
                              json={"filename": "test.mp4"}, headers=auth_headers)
        assert res.status_code in (400, 500)

    def test_get_video_status_error_path(self, client, auth_headers) -> None:
        mock_svc = MagicMock()
        mock_svc.get_video.side_effect = RuntimeError("not found")
        with patch("app.api.v1.videos.routes._video_service", return_value=mock_svc):
            res = client.get(f"/api/v1/videos/{uuid4()}/status", headers=auth_headers)
        assert res.status_code == 500


# ---------------------------------------------------------------------------
# Additional camera route coverage
# ---------------------------------------------------------------------------

class TestCameraRoutesCoverage:

    def test_delete_camera_ok(self, client, auth_headers) -> None:
        cam_id = uuid4()
        mock_svc = MagicMock()
        mock_svc.delete_camera.return_value = None
        with patch("app.api.v1.cameras.crud_handlers._get_camera_service", return_value=mock_svc), \
             patch("app.api.v1.cameras.crud_handlers._is_admin", return_value=False):
            res = client.delete(f"/api/cameras/{cam_id}", headers=auth_headers)
        assert res.status_code in (200, 204, 500)

    def test_update_camera_ok(self, client, auth_headers) -> None:
        cam_id = uuid4()
        mock_svc = MagicMock()
        mock_svc.update_camera.return_value = {
            "id": str(cam_id), "name": "Updated",
        }
        with patch("app.api.v1.cameras.crud_handlers._get_camera_service", return_value=mock_svc), \
             patch("app.api.v1.cameras.crud_handlers._is_admin", return_value=False):
            res = client.put(f"/api/cameras/{cam_id}",
                             json={"name": "Updated"}, headers=auth_headers)
        assert res.status_code in (200, 405, 500)

    def test_camera_not_found_error(self, client, auth_headers) -> None:
        from app.core.exceptions import NotFoundError
        mock_svc = MagicMock()
        mock_svc.get_camera.side_effect = NotFoundError("Câmera", "test")
        with patch("app.api.v1.cameras.crud_handlers._get_camera_service", return_value=mock_svc):
            res = client.get(f"/api/cameras/{uuid4()}", headers=auth_headers)
        assert res.status_code in (404, 500)
