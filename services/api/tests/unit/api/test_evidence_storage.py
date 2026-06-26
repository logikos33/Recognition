"""Tests: evidence storage endpoints.

POST /api/v1/storage/evidence-upload  — device enrollment token (X-Device-Token)
GET  /api/v1/storage/evidence/<key>   — JWT operator
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
OTHER_TENANT_ID = str(uuid4())
USER_ID = str(uuid4())

_VERIFY_PATH = "app.api.v1.storage.routes.verify_device_token"
_STORAGE_PATH = "app.api.v1.storage.routes.get_storage"
_TENANT_PATH = "app.api.v1.storage.routes.get_tenant_id"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers(app):
    """JWT token for operator of TENANT_ID."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "role": "operator",
                "modules": [],
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_tenant_headers(app):
    """JWT token for operator of OTHER_TENANT_ID."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": OTHER_TENANT_ID,
                "tenant_schema": "public",
                "role": "operator",
                "modules": [],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _valid_claims() -> dict:
    """Simulates claims returned by verify_device_token."""
    return {
        "sub": str(uuid4()),
        "tenant_id": TENANT_ID,
        "token_type": "device_enrollment",
    }


def _mock_storage() -> MagicMock:
    svc = MagicMock()
    svc.generate_presigned_upload_url.return_value = "https://mock-r2.test/upload/key"
    svc.generate_presigned_download_url.return_value = "https://mock-r2.test/download/key"
    return svc


_VALID_BODY = {
    "filename": "frame_001.jpg",
    "content_type": "image/jpeg",
    "camera_id": "cam-abc",
}


# ---------------------------------------------------------------------------
# POST /api/v1/storage/evidence-upload
# ---------------------------------------------------------------------------

class TestEvidenceUpload:

    def test_upload_no_token_returns_401(self, client):
        """Missing X-Device-Token header must return 401."""
        resp = client.post(
            "/api/v1/storage/evidence-upload",
            json=_VALID_BODY,
        )
        assert resp.status_code == 401
        assert resp.get_json()["success"] is False

    def test_upload_invalid_token_returns_401(self, client):
        """Invalid/expired token raises AuthenticationError → 401."""
        from app.core.exceptions import AuthenticationError
        with patch(_VERIFY_PATH, side_effect=AuthenticationError("Token inválido")):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json=_VALID_BODY,
                headers={"X-Device-Token": "bad.token.here"},
            )
        assert resp.status_code == 401

    def test_upload_wrong_token_type_returns_401(self, client):
        """Token that is not device_enrollment type returns 401."""
        from app.core.exceptions import AuthenticationError
        with patch(_VERIFY_PATH, side_effect=AuthenticationError("Token não é de dispositivo")):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json=_VALID_BODY,
                headers={"X-Device-Token": "user.jwt.token"},
            )
        assert resp.status_code == 401

    def test_upload_missing_filename_returns_400(self, client):
        """Missing filename returns 400."""
        with (
            patch(_VERIFY_PATH, return_value=_valid_claims()),
            patch(_STORAGE_PATH, return_value=_mock_storage()),
        ):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json={"content_type": "image/jpeg"},
                headers={"X-Device-Token": "valid.device.token"},
            )
        assert resp.status_code == 400

    def test_upload_valid_token_returns_200_with_upload_url(self, client):
        """Valid device token returns 200 with upload_url, evidence_key, expires_in."""
        mock_svc = _mock_storage()
        with (
            patch(_VERIFY_PATH, return_value=_valid_claims()),
            patch(_STORAGE_PATH, return_value=mock_svc),
        ):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json=_VALID_BODY,
                headers={"X-Device-Token": "valid.device.token"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "upload_url" in data["data"]
        assert "evidence_key" in data["data"]
        assert "expires_in" in data["data"]
        assert data["data"]["expires_in"] == 900

    def test_upload_key_has_tenant_prefix(self, client):
        """evidence_key must start with tenant/<tenant_id>/evidence/."""
        mock_svc = _mock_storage()
        with (
            patch(_VERIFY_PATH, return_value=_valid_claims()),
            patch(_STORAGE_PATH, return_value=mock_svc),
        ):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json=_VALID_BODY,
                headers={"X-Device-Token": "valid.device.token"},
            )
        evidence_key = resp.get_json()["data"]["evidence_key"]
        assert evidence_key.startswith(f"tenant/{TENANT_ID}/evidence/")

    def test_upload_key_contains_camera_id(self, client):
        """evidence_key includes the sanitized camera_id segment."""
        mock_svc = _mock_storage()
        with (
            patch(_VERIFY_PATH, return_value=_valid_claims()),
            patch(_STORAGE_PATH, return_value=mock_svc),
        ):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json={**_VALID_BODY, "camera_id": "cam-abc"},
                headers={"X-Device-Token": "valid.device.token"},
            )
        evidence_key = resp.get_json()["data"]["evidence_key"]
        assert "cam-abc" in evidence_key

    def test_upload_large_filename_is_truncated(self, client):
        """Filenames longer than 200 chars are truncated in the evidence_key."""
        long_name = "a" * 300 + ".jpg"
        mock_svc = _mock_storage()
        with (
            patch(_VERIFY_PATH, return_value=_valid_claims()),
            patch(_STORAGE_PATH, return_value=mock_svc),
        ):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json={**_VALID_BODY, "filename": long_name},
                headers={"X-Device-Token": "valid.device.token"},
            )
        assert resp.status_code == 200
        evidence_key = resp.get_json()["data"]["evidence_key"]
        # The filename portion after the timestamp underscore must be <= 200 chars
        filename_part = evidence_key.rsplit("/", 1)[-1]        # "<TIMESTAMP>_<name>"
        sanitized_name = filename_part.split("_", 1)[-1]
        assert len(sanitized_name) <= 200

    def test_upload_filename_path_traversal_sanitized(self, client):
        """Filename with path-traversal characters is sanitized, not rejected."""
        mock_svc = _mock_storage()
        with (
            patch(_VERIFY_PATH, return_value=_valid_claims()),
            patch(_STORAGE_PATH, return_value=mock_svc),
        ):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json={**_VALID_BODY, "filename": "../../etc/passwd"},
                headers={"X-Device-Token": "valid.device.token"},
            )
        assert resp.status_code == 200
        evidence_key = resp.get_json()["data"]["evidence_key"]
        # No raw ".." must appear after the evidence/ segment
        after_evidence = evidence_key.split("/evidence/", 1)[-1]
        assert ".." not in after_evidence

    def test_upload_tenant_id_from_verified_claims(self, client):
        """tenant_id in evidence_key comes from verified token claims."""
        other_tenant = str(uuid4())
        claims_with_other = {**_valid_claims(), "tenant_id": other_tenant}
        mock_svc = _mock_storage()
        with (
            patch(_VERIFY_PATH, return_value=claims_with_other),
            patch(_STORAGE_PATH, return_value=mock_svc),
        ):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json=_VALID_BODY,
                headers={"X-Device-Token": "valid.device.token"},
            )
        evidence_key = resp.get_json()["data"]["evidence_key"]
        assert evidence_key.startswith(f"tenant/{other_tenant}/")

    def test_upload_storage_error_returns_500(self, client):
        """Storage failure on presigned upload returns 500."""
        mock_svc = MagicMock()
        mock_svc.generate_presigned_upload_url.side_effect = Exception("R2 unavailable")
        with (
            patch(_VERIFY_PATH, return_value=_valid_claims()),
            patch(_STORAGE_PATH, return_value=mock_svc),
        ):
            resp = client.post(
                "/api/v1/storage/evidence-upload",
                json=_VALID_BODY,
                headers={"X-Device-Token": "valid.device.token"},
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/v1/storage/evidence/<key>
# ---------------------------------------------------------------------------

class TestEvidenceDownload:

    def _key_for(self, tenant_id: str, suffix: str = "evidence/cam/20260101T000000Z_frame.jpg") -> str:
        return f"tenant/{tenant_id}/{suffix}"

    def test_download_no_jwt_returns_401(self, client):
        """Missing JWT returns 401."""
        key = self._key_for(TENANT_ID)
        resp = client.get(f"/api/v1/storage/evidence/{key}")
        assert resp.status_code == 401

    def test_download_valid_jwt_own_tenant_returns_200(self, client, auth_headers):
        """Operator can download their own tenant's evidence."""
        key = self._key_for(TENANT_ID)
        mock_svc = _mock_storage()
        with (
            patch(_STORAGE_PATH, return_value=mock_svc),
            patch(_TENANT_PATH, return_value=TENANT_ID),
        ):
            resp = client.get(f"/api/v1/storage/evidence/{key}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "download_url" in data["data"]
        assert data["data"]["expires_in"] == 3600

    def test_download_wrong_tenant_returns_403(self, client, other_tenant_headers):
        """Accessing another tenant's evidence_key returns 403."""
        key = self._key_for(TENANT_ID)          # TENANT_ID's key
        with (
            patch(_STORAGE_PATH, return_value=_mock_storage()),
            patch(_TENANT_PATH, return_value=OTHER_TENANT_ID),   # caller is OTHER_TENANT
        ):
            resp = client.get(
                f"/api/v1/storage/evidence/{key}",
                headers=other_tenant_headers,
            )
        assert resp.status_code == 403
        assert resp.get_json()["success"] is False

    def test_download_path_traversal_in_key_returns_400(self, client, auth_headers):
        """evidence_key containing '..' must be rejected with 400."""
        traversal_key = f"tenant/{TENANT_ID}/evidence/../../../etc/passwd"
        with (
            patch(_STORAGE_PATH, return_value=_mock_storage()),
            patch(_TENANT_PATH, return_value=TENANT_ID),
        ):
            resp = client.get(
                f"/api/v1/storage/evidence/{traversal_key}",
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_download_storage_error_returns_500(self, client, auth_headers):
        """Storage error on presigned download returns 500."""
        key = self._key_for(TENANT_ID)
        mock_svc = MagicMock()
        mock_svc.generate_presigned_download_url.side_effect = Exception("R2 unavailable")
        with (
            patch(_STORAGE_PATH, return_value=mock_svc),
            patch(_TENANT_PATH, return_value=TENANT_ID),
        ):
            resp = client.get(f"/api/v1/storage/evidence/{key}", headers=auth_headers)
        assert resp.status_code == 500

    def test_download_key_without_tenant_prefix_returns_403(self, client, auth_headers):
        """A key that doesn't start with tenant/<id>/ is rejected as cross-tenant."""
        foreign_key = "public/shared/some-frame.jpg"
        with (
            patch(_STORAGE_PATH, return_value=_mock_storage()),
            patch(_TENANT_PATH, return_value=TENANT_ID),
        ):
            resp = client.get(
                f"/api/v1/storage/evidence/{foreign_key}",
                headers=auth_headers,
            )
        assert resp.status_code == 403
