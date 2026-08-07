"""
Tests: get_frame_image_handler — StorageError não pode virar 404 (achado:
storage falha alto).

Antes, QUALQUER StorageError vindo do R2 (403 de credencial, timeout,
conexão) virava `NotFoundError("Frame")` — um erro de infraestrutura ficava
indistinguível de "esse frame não existe/não é seu". Agora só objeto
realmente ausente (404/NoSuchKey/NotFound) vira 404; qualquer outro erro do
R2 vira 502 (StorageError) com log ERROR preservando a exceção original.

Cross-tenant (posse) continua 404 — C-01 intacto, esse fix só muda o
tratamento de erro de INFRA, não a regra de posse.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from flask_jwt_extended import create_access_token

import app.api.v1.training.video_handlers as video_handlers

USER_ID = str(uuid.uuid4())
TENANT_ID = str(uuid.uuid4())
FRAME_ID = str(uuid.uuid4())


def _auth(app):
    with app.app_context():
        token = create_access_token(
            identity=USER_ID,
            additional_claims={"tenant_id": TENANT_ID, "role": "operator"},
        )
    return {"Authorization": f"Bearer {token}"}


def _frame_row():
    return {"id": FRAME_ID, "filename": "training-images/t/upload/x.jpg"}


@pytest.fixture
def r2_storage():
    """R2Storage real (boto3 mockado) — preserva o __cause__ genuíno que
    download_bytes() encadeia via `raise StorageError(...) from exc`."""
    with patch("boto3.client"):
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
    return storage


class TestGetFrameImageStorageErrors:
    def test_missing_object_still_returns_404(self, app, client, r2_storage):
        """Objeto de fato ausente no R2 (NoSuchKey) continua 404 — não é o
        que este fix muda."""
        r2_storage._client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )
        repo = MagicMock()
        repo.get_by_id_and_user.return_value = _frame_row()

        with patch.object(video_handlers, "_get_pool", return_value=MagicMock()), \
             patch.object(video_handlers, "FrameRepository", return_value=repo), \
             patch.object(video_handlers, "get_storage", return_value=r2_storage):
            resp = client.get(
                f"/api/training/frames/{FRAME_ID}/image",
                headers=_auth(app),
            )

        assert resp.status_code == 404

    def test_permission_denied_returns_502_not_404(self, app, client, r2_storage):
        """403 de credencial/permissão no R2 NÃO pode virar 404 de frame
        inexistente — essa era a máscara (achado: storage falha alto)."""
        r2_storage._client.get_object.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "GetObject"
        )
        repo = MagicMock()
        repo.get_by_id_and_user.return_value = _frame_row()

        with patch.object(video_handlers, "_get_pool", return_value=MagicMock()), \
             patch.object(video_handlers, "FrameRepository", return_value=repo), \
             patch.object(video_handlers, "get_storage", return_value=r2_storage):
            resp = client.get(
                f"/api/training/frames/{FRAME_ID}/image",
                headers=_auth(app),
            )

        assert resp.status_code == 502, (
            "403 de credencial/permissao do R2 nao pode virar 404 de frame "
            f"inexistente (got {resp.status_code})"
        )
        body = resp.get_json()
        assert body["success"] is False

    def test_generic_storage_error_returns_502_not_404(self, app, client, r2_storage):
        """Timeout/erro de conexão (não 404-family) também não pode virar
        404."""
        r2_storage._client.get_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Error"}}, "GetObject"
        )
        repo = MagicMock()
        repo.get_by_id_and_user.return_value = _frame_row()

        with patch.object(video_handlers, "_get_pool", return_value=MagicMock()), \
             patch.object(video_handlers, "FrameRepository", return_value=repo), \
             patch.object(video_handlers, "get_storage", return_value=r2_storage):
            resp = client.get(
                f"/api/training/frames/{FRAME_ID}/image",
                headers=_auth(app),
            )

        assert resp.status_code == 502

    def test_cross_tenant_still_404(self, app, client):
        """Posse (C-01) continua 404 — esse fix só muda erro de INFRA."""
        repo = MagicMock()
        repo.get_by_id_and_user.return_value = None  # sem posse no tenant

        with patch.object(video_handlers, "_get_pool", return_value=MagicMock()), \
             patch.object(video_handlers, "FrameRepository", return_value=repo), \
             patch.object(video_handlers, "get_storage", return_value=MagicMock()):
            resp = client.get(
                f"/api/training/frames/{FRAME_ID}/image",
                headers=_auth(app),
            )

        assert resp.status_code == 404
