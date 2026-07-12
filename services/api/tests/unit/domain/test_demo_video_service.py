"""
Tests: demo_video_service — upload, list_videos, get_for_camera, delete.

DB (via _get_repo) and storage are mocked throughout.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import AuthorizationError, ValidationError
from app.domain.services import demo_video_service

_POOL_PATH = "app.domain.services.demo_video_service.DatabasePool"
_REPO_PATH = "app.domain.services.demo_video_service._get_repo"
_STORAGE_PATH = "app.domain.services.demo_video_service.get_storage"

_VALID_MP4 = b"x" * 1024  # 1 KB, well under limit
_VALID_MIME = "video/mp4"


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------

class TestUpload:

    def _upload(self, role="superadmin", mime=_VALID_MIME, data=_VALID_MP4, **kwargs):
        mock_repo = MagicMock()
        mock_repo.create.return_value = {"id": 1, "module": "epi"}
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = None
        mock_storage.generate_presigned_download_url.return_value = "https://r2/v.mp4"

        with patch(_POOL_PATH), \
             patch(_REPO_PATH, return_value=mock_repo), \
             patch(_STORAGE_PATH, return_value=mock_storage):
            return demo_video_service.upload(
                file_data=data,
                content_type=mime,
                module=kwargs.get("module", "epi"),
                user_role=role,
                user_id=kwargs.get("user_id", "user-1"),
                camera_id=kwargs.get("camera_id"),
                label=kwargs.get("label"),
            )

    def test_non_superadmin_raises_authorization_error(self):
        with pytest.raises(AuthorizationError):
            self._upload(role="operator")

    def test_invalid_mime_raises_validation_error(self):
        with pytest.raises(ValidationError, match="mp4"):
            self._upload(mime="video/avi")

    def test_oversized_file_raises_validation_error(self):
        big = b"x" * (100 * 1024 * 1024 + 1)
        with pytest.raises(ValidationError, match="grande"):
            self._upload(data=big)

    def test_valid_upload_returns_record(self):
        result = self._upload()
        assert result["id"] == 1

    def test_r2_key_contains_module(self):
        mock_repo = MagicMock()
        mock_repo.create.return_value = {"id": 2, "module": "fueling"}
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.return_value = "https://r2/v.mp4"
        captured = {}

        def _create(**kwargs):
            captured.update(kwargs)
            return {"id": 2, "module": "fueling"}

        mock_repo.create.side_effect = lambda **kw: (captured.update(kw), {"id": 2})[1]

        with patch(_POOL_PATH), \
             patch(_REPO_PATH, return_value=mock_repo), \
             patch(_STORAGE_PATH, return_value=mock_storage):
            demo_video_service.upload(
                file_data=_VALID_MP4, content_type=_VALID_MIME,
                module="fueling", user_role="superadmin",
            )
        # r2_key should include "fueling"
        create_call_args = mock_repo.create.call_args
        assert "fueling" in create_call_args[1]["r2_key"]

    def test_storage_upload_called(self):
        mock_repo = MagicMock()
        mock_repo.create.return_value = {"id": 1, "module": "epi"}
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.return_value = "https://r2/v.mp4"

        with patch(_POOL_PATH), \
             patch(_REPO_PATH, return_value=mock_repo), \
             patch(_STORAGE_PATH, return_value=mock_storage):
            demo_video_service.upload(
                file_data=_VALID_MP4, content_type=_VALID_MIME,
                module="epi", user_role="superadmin",
            )
        mock_storage.upload_bytes.assert_called_once()


# ---------------------------------------------------------------------------
# list_videos
# ---------------------------------------------------------------------------

class TestListVideos:

    def test_delegates_to_repo(self):
        mock_repo = MagicMock()
        mock_repo.list_active.return_value = [{"id": 1}]
        with patch(_POOL_PATH), patch(_REPO_PATH, return_value=mock_repo):
            result = demo_video_service.list_videos(module="epi")
        assert result == [{"id": 1}]
        mock_repo.list_active.assert_called_once_with(module="epi", camera_id=None)

    def test_passes_camera_id(self):
        mock_repo = MagicMock()
        mock_repo.list_active.return_value = []
        with patch(_POOL_PATH), patch(_REPO_PATH, return_value=mock_repo):
            demo_video_service.list_videos(module="epi", camera_id="cam-1")
        mock_repo.list_active.assert_called_once_with(module="epi", camera_id="cam-1")


# ---------------------------------------------------------------------------
# get_for_camera
# ---------------------------------------------------------------------------

class TestGetForCamera:

    def test_non_superadmin_returns_none(self):
        with patch(_POOL_PATH), patch(_REPO_PATH):
            result = demo_video_service.get_for_camera("cam-1", user_role="operator")
        assert result is None

    def test_superadmin_no_record_returns_none(self):
        mock_repo = MagicMock()
        mock_repo.get_for_camera.return_value = None
        with patch(_POOL_PATH), patch(_REPO_PATH, return_value=mock_repo):
            result = demo_video_service.get_for_camera("cam-1", user_role="superadmin")
        assert result is None

    def test_superadmin_returns_record_with_refreshed_url(self):
        mock_repo = MagicMock()
        mock_repo.get_for_camera.return_value = {"id": 5, "r2_key": "k/v.mp4", "r2_url": "old"}
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.return_value = "https://r2/fresh.mp4"

        with patch(_POOL_PATH), \
             patch(_REPO_PATH, return_value=mock_repo), \
             patch(_STORAGE_PATH, return_value=mock_storage):
            result = demo_video_service.get_for_camera("cam-1", user_role="superadmin")

        assert result is not None
        assert result["r2_url"] == "https://r2/fresh.mp4"

    def test_url_refresh_exception_returns_stale_record(self):
        mock_repo = MagicMock()
        mock_repo.get_for_camera.return_value = {"id": 5, "r2_key": "k/v.mp4", "r2_url": "stale"}
        mock_storage = MagicMock()
        mock_storage.generate_presigned_download_url.side_effect = Exception("R2 down")

        with patch(_POOL_PATH), \
             patch(_REPO_PATH, return_value=mock_repo), \
             patch(_STORAGE_PATH, return_value=mock_storage):
            result = demo_video_service.get_for_camera("cam-1", user_role="superadmin")

        # Should return the stale record, not raise
        assert result is not None
        assert result["r2_url"] == "stale"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestDelete:

    def test_non_superadmin_raises_authorization_error(self):
        with patch(_POOL_PATH), patch(_REPO_PATH):
            with pytest.raises(AuthorizationError):
                demo_video_service.delete(1, user_role="operator")

    def test_superadmin_found_returns_true(self):
        mock_repo = MagicMock()
        mock_repo.soft_delete.return_value = True
        with patch(_POOL_PATH), patch(_REPO_PATH, return_value=mock_repo):
            result = demo_video_service.delete(5, user_role="superadmin")
        assert result is True

    def test_superadmin_not_found_returns_false(self):
        mock_repo = MagicMock()
        mock_repo.soft_delete.return_value = False
        with patch(_POOL_PATH), patch(_REPO_PATH, return_value=mock_repo):
            result = demo_video_service.delete(99, user_role="superadmin")
        assert result is False

    def test_video_id_passed_to_repo(self):
        mock_repo = MagicMock()
        mock_repo.soft_delete.return_value = True
        with patch(_POOL_PATH), patch(_REPO_PATH, return_value=mock_repo):
            demo_video_service.delete(42, user_role="superadmin")
        mock_repo.soft_delete.assert_called_once_with(42)
