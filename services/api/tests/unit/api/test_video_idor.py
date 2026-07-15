"""
Segurança — IDOR em endpoints de vídeo/frame (achado P1 da auditoria pré-produção).

Bugs corrigidos (mesma classe já corrigida em endpoints irmãos como
delete_video/upload_complete/retry_extraction/get_download_url/upload_frame/
server_extract — mas ausente nestes três):
  1. `POST /api/v1/videos/<id>/extract` disparava extração de qualquer video_id,
     sem checar se pertence ao usuário autenticado.
  2. `GET /api/v1/videos/<id>/status` retornava status/contagem de frames de
     qualquer vídeo, sem checar posse.
  3. `GET /api/training/videos/<id>/frames` listava frames (com presigned URL
     de download do R2) de qualquer vídeo, sem checar posse.

Testes falha-antes/passa-depois: dono → 200; não-dono → 403, sem side effect.
"""
import uuid
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.videos.routes as videos_routes
import app.api.v1.training.video_handlers as video_handlers

OWNER_ID = str(uuid.uuid4())
OTHER_ID = str(uuid.uuid4())
VIDEO_ID = str(uuid.uuid4())


def _auth(app, user_id: str) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=user_id,
            additional_claims={
                "tenant_id": str(uuid.uuid4()),
                "tenant_schema": "tenant_test",
                "role": "operator",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _video_row(user_id: str = OWNER_ID) -> dict:
    return {
        "id": VIDEO_ID,
        "user_id": user_id,
        "filename": "raw-videos/x/video.mp4",
        "status": "extracted",
        "frame_count": 10,
        "frames_expected": 10,
    }


@pytest.fixture()
def mocked_video_service(monkeypatch):
    service = MagicMock()
    service.get_video.return_value = _video_row()
    service.get_frame_counts.return_value = {"approved": 10}
    service.get_video_frames.return_value = []
    monkeypatch.setattr(videos_routes, "_video_service", lambda: service)
    monkeypatch.setattr(video_handlers, "get_video_service", lambda: service)
    return service


class TestExtractIDOR:
    def test_owner_can_trigger_extraction(self, app, client, mocked_video_service, monkeypatch):
        celery_mock = MagicMock()
        monkeypatch.setattr(
            "app.infrastructure.queue.tasks.extraction.extract_frames", celery_mock
        )
        resp = client.post(
            f"/api/v1/videos/{VIDEO_ID}/extract",
            headers=_auth(app, OWNER_ID),
        )
        assert resp.status_code == 200
        celery_mock.delay.assert_called_once()

    def test_non_owner_cannot_trigger_extraction(self, app, client, mocked_video_service, monkeypatch):
        celery_mock = MagicMock()
        monkeypatch.setattr(
            "app.infrastructure.queue.tasks.extraction.extract_frames", celery_mock
        )
        resp = client.post(
            f"/api/v1/videos/{VIDEO_ID}/extract",
            headers=_auth(app, OTHER_ID),
        )
        assert resp.status_code == 403, (
            f"IDOR: usuario nao-dono conseguiu disparar extracao (got {resp.status_code})"
        )
        celery_mock.delay.assert_not_called()
        mocked_video_service.update_status.assert_not_called()


class TestVideoStatusIDOR:
    def test_owner_can_read_status(self, app, client, mocked_video_service):
        resp = client.get(
            f"/api/v1/videos/{VIDEO_ID}/status",
            headers=_auth(app, OWNER_ID),
        )
        assert resp.status_code == 200

    def test_non_owner_cannot_read_status(self, app, client, mocked_video_service):
        resp = client.get(
            f"/api/v1/videos/{VIDEO_ID}/status",
            headers=_auth(app, OTHER_ID),
        )
        assert resp.status_code == 403, (
            f"IDOR: usuario nao-dono leu status de video alheio (got {resp.status_code})"
        )


class TestVideoFramesIDOR:
    def test_owner_can_list_frames(self, app, client, mocked_video_service):
        resp = client.get(
            f"/api/training/videos/{VIDEO_ID}/frames",
            headers=_auth(app, OWNER_ID),
        )
        assert resp.status_code == 200

    def test_non_owner_cannot_list_frames(self, app, client, mocked_video_service):
        resp = client.get(
            f"/api/training/videos/{VIDEO_ID}/frames",
            headers=_auth(app, OTHER_ID),
        )
        assert resp.status_code == 403, (
            f"IDOR: usuario nao-dono listou frames (+ presigned URLs) de video alheio "
            f"(got {resp.status_code})"
        )
        mocked_video_service.get_video_frames.assert_not_called()
