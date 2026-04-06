"""Tests: VideoService."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.video_service import VideoService


class TestVideoService:
    """Testes para VideoService."""

    def setup_method(self) -> None:
        self.video_repo = MagicMock()
        self.frame_repo = MagicMock()
        self.service = VideoService(self.video_repo, self.frame_repo)

    def test_create_video_success(self) -> None:
        vid = uuid4()
        uid = uuid4()
        self.video_repo.create.return_value = {
            "id": vid, "user_id": uid, "filename": "test.mp4",
            "status": "uploaded", "frame_count": 0,
        }
        result = self.service.create_video(uid, "test.mp4")
        assert result["filename"] == "test.mp4"
        assert result["id"] == str(vid)

    def test_create_video_invalid_extension(self) -> None:
        with pytest.raises(ValidationError, match="não permitida"):
            self.service.create_video(uuid4(), "test.exe")

    def test_get_video_success(self) -> None:
        vid = uuid4()
        self.video_repo.get_by_id.return_value = {
            "id": vid, "filename": "test.mp4",
        }
        result = self.service.get_video(vid)
        assert result["id"] == str(vid)

    def test_get_video_not_found(self) -> None:
        self.video_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_video(uuid4())

    def test_list_videos(self) -> None:
        uid = uuid4()
        self.video_repo.get_by_user.return_value = [
            {"id": uuid4(), "filename": "v1.mp4"},
            {"id": uuid4(), "filename": "v2.mp4"},
        ]
        result = self.service.list_videos(uid)
        assert len(result) == 2

    def test_get_video_frames(self) -> None:
        vid = uuid4()
        self.video_repo.get_by_id.return_value = {"id": vid}
        self.frame_repo.get_by_video.return_value = [
            {"id": uuid4(), "frame_number": 1},
            {"id": uuid4(), "frame_number": 2},
        ]
        result = self.service.get_video_frames(vid)
        assert len(result) == 2

    def test_get_video_frames_not_found(self) -> None:
        self.video_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_video_frames(uuid4())

    def test_update_status(self) -> None:
        vid = uuid4()
        self.video_repo.update_status.return_value = {
            "id": vid, "status": "processing",
        }
        result = self.service.update_status(vid, "processing")
        assert result["status"] == "processing"
