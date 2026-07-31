"""Tests: storage/routes.py — storage health check e test-upload."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
_STORAGE_PATH = "app.api.v1.storage.routes.get_storage"


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "role": "admin",
                "modules": [],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_storage(exists_return=True, upload_raises=None):
    svc = MagicMock()
    svc.__class__.__name__ = "LocalStorage"
    if upload_raises:
        svc.upload_bytes.side_effect = upload_raises
    else:
        svc.upload_bytes.return_value = None
    svc.exists.return_value = exists_return
    svc.delete.return_value = None
    svc.generate_presigned_download_url.return_value = "https://mock-cdn.test/file.txt"
    return svc


# ---------------------------------------------------------------------------
# GET /api/v1/storage/health — no JWT required
# ---------------------------------------------------------------------------

class TestStorageHealth:

    def test_health_default_does_not_claim_connected(self, client):
        """`connected: true` mentia: era true sempre que get_storage() não
        levantava. Caso real no DEV — dizia connected/R2Storage enquanto TODO
        PutObject dava AccessDenied (token escopado a outro bucket). O modo
        padrão não toca a rede, então não pode afirmar conectividade."""
        mock_svc = _mock_storage()
        with patch(_STORAGE_PATH, return_value=mock_svc):
            resp = client.get("/api/v1/storage/health")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        data = resp.get_json()["data"]
        assert data["connected"] is None
        assert data["checked"] == "config"
        mock_svc.upload_bytes.assert_not_called()  # público: nenhum custo de R2

    def test_health_deep_requires_auth(self, client):
        """?deep=1 sem JWT -> 401. O round-trip já foi removido daqui uma vez
        (task-085) por ser superfície pública capaz de gerar custo real de R2."""
        mock_svc = _mock_storage()
        with patch(_STORAGE_PATH, return_value=mock_svc):
            resp = client.get("/api/v1/storage/health?deep=1")
        assert resp.status_code == 401
        mock_svc.upload_bytes.assert_not_called()

    def test_health_deep_does_real_round_trip(self, client, auth_headers):
        mock_svc = _mock_storage(exists_return=True)
        with patch(_STORAGE_PATH, return_value=mock_svc):
            resp = client.get("/api/v1/storage/health?deep=1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["connected"] is True
        assert data["checked"] == "round_trip"
        mock_svc.upload_bytes.assert_called_once()
        mock_svc.exists.assert_called_once()
        mock_svc.delete.assert_called_once()  # sonda não vira lixo no bucket

    def test_health_deep_reports_failure_when_upload_denied(self, client, auth_headers):
        """Exatamente o cenário do DEV: credencial resolve, mas o PutObject nega."""
        mock_svc = _mock_storage(upload_raises=Exception("AccessDenied"))
        with patch(_STORAGE_PATH, return_value=mock_svc):
            resp = client.get("/api/v1/storage/health?deep=1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["connected"] is False
        assert data["checked"] == "round_trip"
        assert "AccessDenied" in data["error"]

    def test_health_deep_cleanup_failure_does_not_break_result(self, client, auth_headers):
        mock_svc = _mock_storage(exists_return=True)
        mock_svc.delete.side_effect = Exception("delete negado")
        with patch(_STORAGE_PATH, return_value=mock_svc):
            resp = client.get("/api/v1/storage/health?deep=1", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["connected"] is True

    def test_health_not_connected_when_get_storage_raises(self, client):
        with patch(_STORAGE_PATH, side_effect=Exception("bad config")):
            resp = client.get("/api/v1/storage/health")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["connected"] is False

    def test_health_never_touches_storage_io(self, client):
        """Endpoint público sem JWT — nunca deve fazer upload/exists/delete
        real (achado de segurança, task-085: I/O real era abusável sem
        auth). Falha-antes: a implementação anterior chamava os três."""
        mock_svc = _mock_storage()
        with patch(_STORAGE_PATH, return_value=mock_svc):
            resp = client.get("/api/v1/storage/health")
        assert resp.status_code == 200
        mock_svc.upload_bytes.assert_not_called()
        mock_svc.exists.assert_not_called()
        mock_svc.delete.assert_not_called()

    def test_storage_type_in_response(self, client):
        mock_svc = _mock_storage()
        with patch(_STORAGE_PATH, return_value=mock_svc):
            resp = client.get("/api/v1/storage/health")
        assert "storage_type" in resp.get_json()["data"]

    def test_r2_configured_key_in_response(self, client):
        mock_svc = _mock_storage()
        with patch(_STORAGE_PATH, return_value=mock_svc), \
             patch.dict("os.environ", {"R2_ENDPOINT": ""}, clear=False):
            resp = client.get("/api/v1/storage/health")
        assert "r2_configured" in resp.get_json()["data"]

    def test_exception_returns_200_with_error_info(self, client):
        with patch(_STORAGE_PATH, side_effect=Exception("R2 connection failed")):
            resp = client.get("/api/v1/storage/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["connected"] is False
        assert "error" in data["data"]

# ---------------------------------------------------------------------------
# POST /api/v1/storage/test-upload — JWT required
# ---------------------------------------------------------------------------

class TestTestUpload:

    def test_no_token_returns_401(self, client):
        assert client.post("/api/v1/storage/test-upload").status_code == 401

    def test_upload_success_returns_200(self, client, auth_headers):
        mock_svc = _mock_storage(exists_return=True)
        with patch(_STORAGE_PATH, return_value=mock_svc):
            resp = client.post("/api/v1/storage/test-upload", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "key" in data["data"]
        assert data["data"]["exists"] is True
        assert "download_url" in data["data"]
        assert "storage_type" in data["data"]

    def test_upload_key_starts_with_test_prefix(self, client, auth_headers):
        mock_svc = _mock_storage()
        with patch(_STORAGE_PATH, return_value=mock_svc):
            resp = client.post("/api/v1/storage/test-upload", headers=auth_headers)
        key = resp.get_json()["data"]["key"]
        assert key.startswith("test/")

    def test_storage_error_returns_500(self, client, auth_headers):
        with patch(_STORAGE_PATH, side_effect=Exception("Upload failed")):
            resp = client.post("/api/v1/storage/test-upload", headers=auth_headers)
        assert resp.status_code == 500
