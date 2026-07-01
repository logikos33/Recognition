"""
Regression tests — IDOR fixes for video routes (security/audit-hardening-2026-07).

BUG 1 (P1): trigger_extraction — no ownership check before dispatching Celery task.
BUG 2 (P1): finalize_extraction — no ownership check before repo.update_status.
BUG 3 (P1): get_video_frames_handler — returns frames + presigned URLs to any auth user.
BUG 4 (P2): get_video_status — no ownership check on status endpoint.

Each test FAILS before the fix / PASSES after the fix.
"""
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4


OWNER_ID = str(uuid4())
OTHER_USER_ID = str(uuid4())
VIDEO_ID = str(uuid4())
TENANT_ID = str(uuid4())

_VIDEO_SERVICE = "app.api.v1.videos.routes._video_service"
_VIDEO_REPO = "app.api.v1.videos.routes._video_repo"
_TRAINING_VIDEO_SERVICE = "app.api.v1.training.video_handlers.get_video_service"


def _make_video(owner_id: str = OWNER_ID) -> dict:
    return {
        "id": VIDEO_ID,
        "user_id": owner_id,
        "filename": "raw-videos/test/video.mp4",
        "status": "uploaded",
        "frame_count": 0,
        "frames_expected": 0,
    }


def _make_jwt_headers(app, user_id: str) -> dict:
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=user_id,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "email": f"{user_id[:8]}@test.com",
                "role": "operator",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# BUG 1 (P1): POST /api/v1/videos/<video_id>/extract
# ---------------------------------------------------------------------------

class TestTriggerExtractionIDOR:
    """User B must not trigger extraction on user A's video (P1-IDOR)."""

    def test_other_user_gets_403(self, client, app):
        """FAILS before fix (200 returned); PASSES after fix (403)."""
        headers = _make_jwt_headers(app, OTHER_USER_ID)
        service_mock = MagicMock()
        service_mock.get_video.return_value = _make_video(owner_id=OWNER_ID)

        with patch(_VIDEO_SERVICE, return_value=service_mock):
            resp = client.post(
                f"/api/v1/videos/{VIDEO_ID}/extract",
                headers=headers,
            )

        assert resp.status_code == 403

    def test_update_status_not_called_when_not_owner(self, client, app):
        """update_status must NOT be called if ownership check fails."""
        headers = _make_jwt_headers(app, OTHER_USER_ID)
        service_mock = MagicMock()
        service_mock.get_video.return_value = _make_video(owner_id=OWNER_ID)

        with patch(_VIDEO_SERVICE, return_value=service_mock):
            client.post(
                f"/api/v1/videos/{VIDEO_ID}/extract",
                headers=headers,
            )

        service_mock.update_status.assert_not_called()

    def test_owner_triggers_extraction_successfully(self, client, app):
        """Owner CAN trigger extraction — update_status is called."""
        headers = _make_jwt_headers(app, OWNER_ID)
        service_mock = MagicMock()
        service_mock.get_video.return_value = _make_video(owner_id=OWNER_ID)
        service_mock.update_status.return_value = _make_video()

        # Mock the Celery extraction task module (not available in unit test env)
        extraction_mock = MagicMock()
        with (
            patch(_VIDEO_SERVICE, return_value=service_mock),
            patch.dict(
                sys.modules,
                {"app.infrastructure.queue.tasks.extraction": extraction_mock},
            ),
        ):
            client.post(
                f"/api/v1/videos/{VIDEO_ID}/extract",
                headers=headers,
            )

        service_mock.update_status.assert_called_once()


# ---------------------------------------------------------------------------
# BUG 4 (P2): GET /api/v1/videos/<video_id>/status
# ---------------------------------------------------------------------------

class TestGetVideoStatusIDOR:
    """User B must not read processing status of user A's video (P2-IDOR)."""

    def test_other_user_gets_403(self, client, app):
        """FAILS before fix (200 returned); PASSES after fix (403)."""
        headers = _make_jwt_headers(app, OTHER_USER_ID)
        service_mock = MagicMock()
        service_mock.get_video.return_value = _make_video(owner_id=OWNER_ID)

        with patch(_VIDEO_SERVICE, return_value=service_mock):
            resp = client.get(
                f"/api/v1/videos/{VIDEO_ID}/status",
                headers=headers,
            )

        assert resp.status_code == 403

    def test_get_frame_counts_not_called_when_not_owner(self, client, app):
        """get_frame_counts must NOT be called if ownership check fails."""
        headers = _make_jwt_headers(app, OTHER_USER_ID)
        service_mock = MagicMock()
        service_mock.get_video.return_value = _make_video(owner_id=OWNER_ID)

        with patch(_VIDEO_SERVICE, return_value=service_mock):
            client.get(
                f"/api/v1/videos/{VIDEO_ID}/status",
                headers=headers,
            )

        service_mock.get_frame_counts.assert_not_called()

    def test_owner_can_read_status(self, client, app):
        """Owner CAN read status — 200 returned."""
        headers = _make_jwt_headers(app, OWNER_ID)
        service_mock = MagicMock()
        service_mock.get_video.return_value = _make_video(owner_id=OWNER_ID)
        service_mock.get_frame_counts.return_value = {
            "annotated": 0, "pending": 0, "total": 0,
        }

        with patch(_VIDEO_SERVICE, return_value=service_mock):
            resp = client.get(
                f"/api/v1/videos/{VIDEO_ID}/status",
                headers=headers,
            )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# BUG 2 (P1): POST /api/v1/videos/<video_id>/finalize-extraction
# ---------------------------------------------------------------------------

class TestFinalizeExtractionIDOR:
    """User B must not finalize extraction on user A's video (P1-IDOR)."""

    def test_other_user_gets_403(self, client, app):
        """FAILS before fix (200 returned); PASSES after fix (403)."""
        headers = _make_jwt_headers(app, OTHER_USER_ID)
        service_mock = MagicMock()
        service_mock.get_video.return_value = _make_video(owner_id=OWNER_ID)
        repo_mock = MagicMock()

        with (
            patch(_VIDEO_SERVICE, return_value=service_mock),
            patch(_VIDEO_REPO, return_value=repo_mock),
        ):
            resp = client.post(
                f"/api/v1/videos/{VIDEO_ID}/finalize-extraction",
                json={"frame_count": 100},
                headers=headers,
            )

        assert resp.status_code == 403

    def test_repo_update_status_not_called_when_not_owner(self, client, app):
        """Repo update_status must NOT be called when ownership fails."""
        headers = _make_jwt_headers(app, OTHER_USER_ID)
        service_mock = MagicMock()
        service_mock.get_video.return_value = _make_video(owner_id=OWNER_ID)
        repo_mock = MagicMock()

        with (
            patch(_VIDEO_SERVICE, return_value=service_mock),
            patch(_VIDEO_REPO, return_value=repo_mock),
        ):
            client.post(
                f"/api/v1/videos/{VIDEO_ID}/finalize-extraction",
                json={"frame_count": 100},
                headers=headers,
            )

        repo_mock.update_status.assert_not_called()


# ---------------------------------------------------------------------------
# BUG 3 (P1): GET /api/training/videos/<video_id>/frames
# ---------------------------------------------------------------------------

class TestGetVideoFramesIDOR:
    """User B must not list frames + presigned URLs of user A's video (P1-IDOR)."""

    def test_other_user_gets_403(self, client, app):
        """FAILS before fix (200 + presigned URLs); PASSES after fix (403)."""
        from app.core.exceptions import AuthorizationError

        headers = _make_jwt_headers(app, OTHER_USER_ID)
        service_mock = MagicMock()
        service_mock.get_video_frames.side_effect = AuthorizationError("Sem permissao")

        with patch(_TRAINING_VIDEO_SERVICE, return_value=service_mock):
            resp = client.get(
                f"/api/training/videos/{VIDEO_ID}/frames",
                headers=headers,
            )

        assert resp.status_code in (403, 404)

    def test_presigned_urls_not_generated_on_idor_attempt(self, client, app):
        """Storage.generate_presigned_download_url must NOT be called on IDOR attempt."""
        from app.core.exceptions import AuthorizationError

        headers = _make_jwt_headers(app, OTHER_USER_ID)
        service_mock = MagicMock()
        service_mock.get_video_frames.side_effect = AuthorizationError("Sem permissao")
        storage_mock = MagicMock()

        with (
            patch(_TRAINING_VIDEO_SERVICE, return_value=service_mock),
            patch(
                "app.api.v1.training.video_handlers.get_storage",
                return_value=storage_mock,
            ),
        ):
            client.get(
                f"/api/training/videos/{VIDEO_ID}/frames",
                headers=headers,
            )

        storage_mock.generate_presigned_download_url.assert_not_called()

    def test_owner_can_list_frames(self, client, app):
        """Owner CAN list frames — 200 with empty list."""
        headers = _make_jwt_headers(app, OWNER_ID)
        service_mock = MagicMock()
        service_mock.get_video_frames.return_value = []

        with patch(_TRAINING_VIDEO_SERVICE, return_value=service_mock):
            resp = client.get(
                f"/api/training/videos/{VIDEO_ID}/frames",
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["frames"] == []
