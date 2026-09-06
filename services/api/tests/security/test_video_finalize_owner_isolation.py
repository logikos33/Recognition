"""
Regressão — POST /api/v1/videos/<id>/finalize-extraction sem checagem de posse.

Achado (d) do mapa de migração, grupo VÍDEOS: a rota
(app/api/v1/videos/routes.py::finalize_extraction) ia direto ao
VideoRepository.update_status — qualquer JWT marcava qualquer vídeo como
'extracted' com frame_count arbitrário, sem resolver o vídeo nem comparar o
dono (como fazem as irmãs /<id>/status, /download-url, /frames/upload).

FALHA antes do fix / PASSA depois: não-dono → 404 (C-01 — não vazar
existência) e NENHUMA mutação; dono → 200 e update_status chamado.
"""
import uuid
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.videos.routes as videos_routes

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
                # Grant granular explícito: desde o gate de `training:write`
                # no blueprint (issue #782) o operator não passa por role. O
                # que ESTE teste mede é posse, não permissão — então o token
                # entra COM a chave, e o 404 do não-dono continua sendo do
                # check de posse, não do gate.
                "perms": ["training:write"],
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def video_repo(monkeypatch):
    repo = MagicMock()
    repo.get_by_id.return_value = {
        "id": VIDEO_ID,
        "user_id": OWNER_ID,
        "filename": "raw-videos/x/video.mp4",
        "status": "extracting",
    }
    repo.update_status.return_value = {"id": VIDEO_ID, "status": "extracted"}
    monkeypatch.setattr(videos_routes, "_video_repo", lambda: repo)
    monkeypatch.setattr(
        videos_routes, "_video_service",
        lambda: videos_routes.VideoService(repo, MagicMock()),
    )
    return repo


class TestFinalizeExtractionOwnerIsolation:
    def test_non_owner_cannot_finalize(self, app, client, video_repo):
        resp = client.post(
            f"/api/v1/videos/{VIDEO_ID}/finalize-extraction",
            json={"frame_count": 999},
            headers=_auth(app, OTHER_ID),
        )
        assert resp.status_code == 404, (
            f"IDOR: não-dono finalizou extração de vídeo alheio (got {resp.status_code})"
        )
        video_repo.update_status.assert_not_called()

    def test_owner_finalizes(self, app, client, video_repo):
        resp = client.post(
            f"/api/v1/videos/{VIDEO_ID}/finalize-extraction",
            json={"frame_count": 42},
            headers=_auth(app, OWNER_ID),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"] == {"status": "extracted", "frame_count": 42}
        video_repo.update_status.assert_called_once()
        args, kwargs = video_repo.update_status.call_args
        assert str(args[0]) == VIDEO_ID
        assert kwargs.get("frame_count", args[3] if len(args) > 3 else None) == 42
