"""Tests: Camera hardening fields — task-041.

Covers: detection_stream_url, video_codec, max_auth_failures
in CameraService.create_camera() and CameraService.update_camera().
"""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from cryptography.fernet import Fernet

from app.core.exceptions import ValidationError
from app.domain.services.camera_service import CameraService


def _make_service() -> tuple[CameraService, MagicMock]:
    repo = MagicMock()
    fernet_key = Fernet.generate_key().decode()
    service = CameraService(repo, fernet_key)
    return service, repo


def _base_cam(uid: object, cam_id: object) -> dict:
    return {"id": cam_id, "tenant_id": uid, "name": "Cam", "host": "10.0.0.1"}


# ---------------------------------------------------------------------------
# create_camera — hardening fields
# ---------------------------------------------------------------------------

class TestCreateCameraHardeningFields:
    """CameraService.create_camera() com campos de hardening."""

    def test_create_camera_with_hardening_fields(self) -> None:
        """Repo.create() recebe os 3 novos campos."""
        service, repo = _make_service()
        uid = uuid4()
        cam_id = uuid4()
        repo.create.return_value = {"id": cam_id, "name": "Cam"}

        service.create_camera(uid, {
            "name": "Cam",
            "host": "10.1.2.3",
            "detection_stream_url": "rtsp://admin:pass@10.1.2.3:554/sub",
            "video_codec": "h265",
            "max_auth_failures": 3,
        })

        call_args = repo.create.call_args[0][0]
        assert call_args["detection_stream_url"] == "rtsp://admin:pass@10.1.2.3:554/sub"
        assert call_args["video_codec"] == "h265"
        assert call_args["max_auth_failures"] == 3

    def test_max_auth_failures_default(self) -> None:
        """max_auth_failures usa default 5 quando não fornecido."""
        service, repo = _make_service()
        uid = uuid4()
        repo.create.return_value = {"id": uuid4(), "name": "Cam"}

        service.create_camera(uid, {"name": "Cam", "host": "10.1.2.3"})

        call_args = repo.create.call_args[0][0]
        assert call_args["max_auth_failures"] == 5

    def test_create_camera_video_codec_none(self) -> None:
        """video_codec=None é aceito."""
        service, repo = _make_service()
        uid = uuid4()
        repo.create.return_value = {"id": uuid4(), "name": "Cam"}

        service.create_camera(uid, {"name": "Cam", "host": "10.1.2.3", "video_codec": None})

        call_args = repo.create.call_args[0][0]
        assert call_args["video_codec"] is None

    def test_create_camera_video_codec_h264(self) -> None:
        """video_codec='h264' é aceito."""
        service, repo = _make_service()
        uid = uuid4()
        repo.create.return_value = {"id": uuid4(), "name": "Cam"}

        service.create_camera(uid, {"name": "Cam", "host": "10.1.2.3", "video_codec": "h264"})

        call_args = repo.create.call_args[0][0]
        assert call_args["video_codec"] == "h264"

    def test_create_camera_video_codec_invalid(self) -> None:
        """video_codec com valor inválido lança ValidationError."""
        service, repo = _make_service()

        with pytest.raises(ValidationError, match="video_codec"):
            service.create_camera(uuid4(), {
                "name": "Cam", "host": "10.1.2.3", "video_codec": "hevc",
            })

    def test_create_camera_max_auth_failures_zero_raises(self) -> None:
        """max_auth_failures=0 é rejeitado (mínimo 1)."""
        service, repo = _make_service()

        with pytest.raises(ValidationError, match="max_auth_failures"):
            service.create_camera(uuid4(), {
                "name": "Cam", "host": "10.1.2.3", "max_auth_failures": 0,
            })

    def test_create_camera_max_auth_failures_negative_raises(self) -> None:
        """max_auth_failures negativo é rejeitado."""
        service, repo = _make_service()

        with pytest.raises(ValidationError, match="max_auth_failures"):
            service.create_camera(uuid4(), {
                "name": "Cam", "host": "10.1.2.3", "max_auth_failures": -1,
            })

    def test_create_detection_stream_url_valid(self) -> None:
        """detection_stream_url válida passa pelo RTSPUrlValidator."""
        service, repo = _make_service()
        uid = uuid4()
        repo.create.return_value = {"id": uuid4(), "name": "Cam"}

        # 10.x.x.x é endereço privado — validator aceita (não é loopback/multicast)
        service.create_camera(uid, {
            "name": "Cam",
            "host": "10.1.2.3",
            "detection_stream_url": "rtsp://user:pass@10.1.2.3:554/substream",
        })

        call_args = repo.create.call_args[0][0]
        assert call_args["detection_stream_url"] == "rtsp://user:pass@10.1.2.3:554/substream"

    def test_create_detection_stream_url_ssrf_loopback_rejected(self) -> None:
        """detection_stream_url com loopback é rejeitada pelo RTSPUrlValidator."""
        service, repo = _make_service()

        with pytest.raises(ValidationError):
            service.create_camera(uuid4(), {
                "name": "Cam",
                "host": "10.1.2.3",
                "detection_stream_url": "rtsp://admin:pass@127.0.0.1:554/stream",
            })


# ---------------------------------------------------------------------------
# update_camera — hardening fields
# ---------------------------------------------------------------------------

class TestUpdateCameraHardeningFields:
    """CameraService.update_camera() com campos de hardening."""

    def _setup(self) -> tuple[CameraService, MagicMock, object, object]:
        service, repo = _make_service()
        uid = uuid4()
        cam_id = uuid4()
        repo.get_by_id.return_value = _base_cam(uid, cam_id)
        repo.update.return_value = {"id": cam_id, "name": "Cam"}
        return service, repo, uid, cam_id

    def test_update_camera_video_codec_h264(self) -> None:
        """update_camera aceita video_codec='h264'."""
        service, repo, uid, cam_id = self._setup()

        service.update_camera(cam_id, uid, {"video_codec": "h264"})

        call_args = repo.update.call_args[0][1]
        assert call_args["video_codec"] == "h264"

    def test_update_camera_video_codec_h265(self) -> None:
        """update_camera aceita video_codec='h265'."""
        service, repo, uid, cam_id = self._setup()

        service.update_camera(cam_id, uid, {"video_codec": "h265"})

        call_args = repo.update.call_args[0][1]
        assert call_args["video_codec"] == "h265"

    def test_update_camera_video_codec_invalid(self) -> None:
        """update_camera rejeita video_codec='hevc'."""
        service, repo, uid, cam_id = self._setup()

        with pytest.raises(ValidationError, match="video_codec"):
            service.update_camera(cam_id, uid, {"video_codec": "hevc"})

    def test_update_detection_stream_url_valid(self) -> None:
        """update_camera aceita detection_stream_url válida."""
        service, repo, uid, cam_id = self._setup()

        service.update_camera(cam_id, uid, {
            "detection_stream_url": "rtsp://admin:pw@10.0.0.5:554/sub",
        })

        call_args = repo.update.call_args[0][1]
        assert call_args["detection_stream_url"] == "rtsp://admin:pw@10.0.0.5:554/sub"

    def test_update_detection_stream_url_ssrf_rejected(self) -> None:
        """update_camera rejeita detection_stream_url com loopback (SSRF)."""
        service, repo, uid, cam_id = self._setup()

        with pytest.raises(ValidationError):
            service.update_camera(cam_id, uid, {
                "detection_stream_url": "rtsp://admin:pw@127.0.0.1:554/stream",
            })

    def test_update_max_auth_failures_valid(self) -> None:
        """update_camera aceita max_auth_failures >= 1."""
        service, repo, uid, cam_id = self._setup()

        service.update_camera(cam_id, uid, {"max_auth_failures": 10})

        call_args = repo.update.call_args[0][1]
        assert call_args["max_auth_failures"] == 10

    def test_update_max_auth_failures_zero_raises(self) -> None:
        """update_camera rejeita max_auth_failures=0."""
        service, repo, uid, cam_id = self._setup()

        with pytest.raises(ValidationError, match="max_auth_failures"):
            service.update_camera(cam_id, uid, {"max_auth_failures": 0})
