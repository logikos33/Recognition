"""
Tests: VideoService use cases + _format_bytes helper.

VideoRepository and FrameRepository are injected as mocks — no DB.
"""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.domain.services.video_service import VideoService, _format_bytes


def _svc(video_repo=None, frame_repo=None):
    return VideoService(
        video_repo=video_repo or MagicMock(),
        frame_repo=frame_repo or MagicMock(),
    )


class TestFormatBytes:
    def test_bytes(self):
        assert "B" in _format_bytes(512)
    def test_kilobytes(self):
        assert "KB" in _format_bytes(1024)
    def test_megabytes(self):
        assert "MB" in _format_bytes(1024 * 1024)
    def test_gigabytes(self):
        assert "GB" in _format_bytes(1024 ** 3)
    def test_terabytes(self):
        assert "TB" in _format_bytes(1024 ** 4)


class TestCreateVideo:
    def test_returns_video_with_str_id(self):
        vid_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.create.return_value = {"id": vid_id, "filename": "raw/f.mp4"}
        result = _svc(video_repo=mock_repo).create_video(uuid4(), "raw/f.mp4")
        assert result["id"] == str(vid_id)

    def test_invalid_extension_raises(self):
        with pytest.raises(Exception):
            _svc().create_video(uuid4(), "raw/f.exe")

    def test_original_filename_defaults_to_filename(self):
        mock_repo = MagicMock()
        mock_repo.create.return_value = {"id": uuid4(), "filename": "raw/f.mp4"}
        _svc(video_repo=mock_repo).create_video(uuid4(), "raw/f.mp4")
        assert mock_repo.create.call_args[1]["original_filename"] == "raw/f.mp4"

    def test_explicit_original_filename_passed(self):
        mock_repo = MagicMock()
        mock_repo.create.return_value = {"id": uuid4(), "filename": "raw/f.mp4"}
        _svc(video_repo=mock_repo).create_video(uuid4(), "raw/f.mp4", original_filename="orig.mp4")
        assert mock_repo.create.call_args[1]["original_filename"] == "orig.mp4"


class TestGetVideo:
    def test_returns_video(self):
        vid_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {"id": vid_id, "filename": "f.mp4"}
        result = _svc(video_repo=mock_repo).get_video(vid_id)
        assert result["id"] == str(vid_id)

    def test_not_found_raises(self):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            _svc(video_repo=mock_repo).get_video(uuid4())


class TestListVideos:
    def test_returns_str_ids(self):
        vid_ids = [uuid4(), uuid4()]
        mock_repo = MagicMock()
        mock_repo.get_by_user.return_value = [{"id": v} for v in vid_ids]
        result = _svc(video_repo=mock_repo).list_videos(uuid4())
        assert all(isinstance(v["id"], str) for v in result)

    def test_empty_list(self):
        mock_repo = MagicMock()
        mock_repo.get_by_user.return_value = []
        assert _svc(video_repo=mock_repo).list_videos(uuid4()) == []


class TestGetVideoFrames:
    def test_video_not_found_raises(self):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            _svc(video_repo=mock_repo).get_video_frames(uuid4())

    def test_returns_frames_with_str_ids(self):
        vid_id, frame_id = uuid4(), uuid4()
        mock_vr = MagicMock(); mock_vr.get_by_id.return_value = {"id": vid_id}
        mock_fr = MagicMock(); mock_fr.get_approved_by_video.return_value = [{"id": frame_id}]
        result = _svc(video_repo=mock_vr, frame_repo=mock_fr).get_video_frames(vid_id)
        assert result[0]["id"] == str(frame_id)

    def test_fallback_when_approved_raises(self):
        vid_id, frame_id = uuid4(), uuid4()
        mock_vr = MagicMock(); mock_vr.get_by_id.return_value = {"id": vid_id}
        mock_fr = MagicMock()
        mock_fr.get_approved_by_video.side_effect = Exception("column not found")
        mock_fr.get_by_video.return_value = [{"id": frame_id}]
        result = _svc(video_repo=mock_vr, frame_repo=mock_fr).get_video_frames(vid_id)
        assert result[0]["id"] == str(frame_id)


class TestGetFrameCounts:
    def test_delegates_to_frame_repo(self):
        mock_fr = MagicMock()
        mock_fr.count_by_status.return_value = {"approved": 5}
        vid_id = uuid4()
        result = _svc(frame_repo=mock_fr).get_frame_counts(vid_id)
        assert result == {"approved": 5}
        mock_fr.count_by_status.assert_called_once_with(vid_id)


class TestDeleteVideo:
    def test_not_found_raises(self):
        mock_repo = MagicMock(); mock_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            _svc(video_repo=mock_repo).delete_video(uuid4())

    def test_found_returns_true(self):
        vid_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {"id": vid_id}
        mock_repo.delete.return_value = True
        assert _svc(video_repo=mock_repo).delete_video(vid_id) is True


class TestGetStorageStats:
    def test_returns_expected_keys(self):
        mock_repo = MagicMock(); mock_repo.get_total_storage.return_value = 1024
        result = _svc(video_repo=mock_repo).get_storage_stats(uuid4())
        for key in ("used_bytes", "limit_bytes", "used_formatted", "limit_formatted", "percentage"):
            assert key in result

    def test_percentage_calculation(self):
        limit = 5 * 1024 * 1024 * 1024
        mock_repo = MagicMock(); mock_repo.get_total_storage.return_value = limit // 2
        result = _svc(video_repo=mock_repo).get_storage_stats(uuid4())
        assert result["percentage"] == 50.0

    def test_limit_is_5gb(self):
        mock_repo = MagicMock(); mock_repo.get_total_storage.return_value = 0
        result = _svc(video_repo=mock_repo).get_storage_stats(uuid4())
        assert result["limit_bytes"] == 5 * 1024 * 1024 * 1024


class TestUpdateStatus:
    def test_returns_updated_video(self):
        vid_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.update_status.return_value = {"id": vid_id, "status": "done"}
        result = _svc(video_repo=mock_repo).update_status(vid_id, "done")
        assert result["id"] == str(vid_id)

    def test_not_found_raises(self):
        mock_repo = MagicMock(); mock_repo.update_status.return_value = None
        with pytest.raises(NotFoundError):
            _svc(video_repo=mock_repo).update_status(uuid4(), "done")

    def test_passes_all_params(self):
        vid_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.update_status.return_value = {"id": vid_id, "status": "error"}
        _svc(video_repo=mock_repo).update_status(
            vid_id, "error", error_message="disk full", frame_count=10, frames_expected=20
        )
        call_args = mock_repo.update_status.call_args
        assert "disk full" in str(call_args)
