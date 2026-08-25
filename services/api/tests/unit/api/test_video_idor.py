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

Testes falha-antes/passa-depois: dono → 200; não-dono → 404, sem side effect.

#530: não-dono nunca recebe 403 — 403 confirma que o recurso existe (C-01: não
vazar existência). Padronizado nas 10 rotas irmãs do blueprint, seguindo o que
o PR #525 fez em finalize-extraction. O critério não é o status isolado e sim
a resposta inteira: não-dono e inexistente têm de ser indistinguíveis. Por isso
as 9 rotas levantam o mesmo NotFoundError da busca (404 com o id na mensagem) e
o DELETE cai no 200 idempotente que já respondia para vídeo ausente.
"""
import uuid
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.videos.routes as videos_routes
import app.api.v1.training.video_handlers as video_handlers
from app.core.exceptions import NotFoundError

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
        assert resp.status_code == 404, (
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
        assert resp.status_code == 404, (
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
        assert resp.status_code == 404, (
            f"IDOR: usuario nao-dono listou frames (+ presigned URLs) de video alheio "
            f"(got {resp.status_code})"
        )
        mocked_video_service.get_video_frames.assert_not_called()


# As 10 rotas do #530 — nenhuma pode responder 403 para não-dono.
_ROTAS_IRMAS = [
    ("post", f"/api/v1/videos/{VIDEO_ID}/extract"),
    ("get", f"/api/v1/videos/{VIDEO_ID}/status"),
    ("delete", f"/api/v1/videos/{VIDEO_ID}"),
    ("post", f"/api/v1/videos/{VIDEO_ID}/upload-complete"),
    ("post", f"/api/v1/videos/{VIDEO_ID}/retry-extraction"),
    ("get", f"/api/v1/videos/{VIDEO_ID}/download-url"),
    ("post", f"/api/v1/videos/{VIDEO_ID}/frames/upload"),
    ("get", f"/api/v1/videos/{VIDEO_ID}/blob"),
    ("post", f"/api/v1/videos/{VIDEO_ID}/server-extract"),
    ("get", f"/api/training/videos/{VIDEO_ID}/frames"),
]


@pytest.mark.parametrize(("metodo", "rota"), _ROTAS_IRMAS)
def test_nao_dono_indistinguivel_de_video_inexistente(
    app, client, mocked_video_service, metodo, rota
):
    """C-01 (#530): não-dono recebe resposta IDÊNTICA à de vídeo inexistente.

    403 "Sem permissao" é um oráculo de existência: quem varre ids aprende
    quais existem sem ter acesso a nenhum. Trocar só o status não fecha o
    oráculo — se o corpo diferir (id na mensagem em um caso e não no outro,
    ou 200 idempotente do DELETE em um caso e 404 no outro), o scanner
    continua separando "não é seu" de "não existe".
    """
    nao_dono = getattr(client, metodo)(rota, headers=_auth(app, OTHER_ID))

    # Mesmo requisitante, mesma rota — só o vídeo deixa de existir.
    mocked_video_service.get_video.side_effect = NotFoundError("Vídeo", VIDEO_ID)
    inexistente = getattr(client, metodo)(rota, headers=_auth(app, OTHER_ID))

    assert nao_dono.status_code != 403, (
        f"{metodo.upper()} {rota} respondeu 403 para nao-dono "
        "— 403 confirma que o video existe (C-01)"
    )
    assert (nao_dono.status_code, nao_dono.get_json()) == (
        inexistente.status_code,
        inexistente.get_json(),
    ), (
        f"{metodo.upper()} {rota}: nao-dono {nao_dono.status_code} "
        f"{nao_dono.get_json()} difere de inexistente {inexistente.status_code} "
        f"{inexistente.get_json()} — a diferenca e' o oraculo de existencia"
    )
