"""
Tests: tasks/nvr_extraction.py — extract_nvr_frames (WS-B1).

Cobre: recorder não encontrado, busca de gravações (client mockado),
FFmpeg mockado (subprocess.run) gerando frames, upload + FrameRepository.create
com source=NVR, teto de _MAX_FRAMES_PER_SEGMENT no comando ffmpeg, erros
parciais por segmento não abortam os demais.
"""
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_TASK_KEY = "app.infrastructure.queue.tasks.nvr_extraction"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_TASK_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue.tasks import nvr_extraction as task_mod  # noqa: E402

_RECORDER_ID = str(uuid4())
_TENANT_ID = "99999999-8888-7777-6666-555555555555"


_UNSET = object()
_DEFAULT_RECORDER = {
    "id": _RECORDER_ID, "host": "10.0.0.5", "port": 80,
    "protocol": "onvif", "password_encrypted": None,
}


def _run(monkeypatch, recorder=_UNSET, segments=None, ffmpeg_returncode=0, glob_files=None):
    mock_recorder_repo = MagicMock()
    mock_recorder_repo.get_by_id.return_value = (
        _DEFAULT_RECORDER if recorder is _UNSET else recorder
    )
    monkeypatch.setattr(task_mod, "_get_recorder_repo", lambda: mock_recorder_repo)

    mock_frame_repo = MagicMock()
    monkeypatch.setattr(task_mod, "_get_frame_repo", lambda: mock_frame_repo)

    mock_storage = MagicMock()
    mock_client = MagicMock()
    mock_client.search_recordings.return_value = segments or []
    mock_client.build_playback_url.return_value = "rtsp://10.0.0.5:554/replay"

    mock_result = MagicMock(returncode=ffmpeg_returncode, stderr="")

    with patch(
        "app.infrastructure.database.connection.DatabasePool"
    ), patch(
        "app.domain.services.recorder_service.RecorderService"
    ) as mock_service_cls, patch(
        "app.infrastructure.nvr.factory.get_nvr_client", return_value=mock_client
    ), patch(
        "app.infrastructure.storage.local_storage.get_storage", return_value=mock_storage
    ), patch(
        "subprocess.run", return_value=mock_result
    ), patch(
        "glob.glob", return_value=glob_files or []
    ), patch(
        "builtins.open", MagicMock()
    ), patch(
        "shutil.rmtree",
    ), patch(
        "tempfile.mkdtemp", return_value="/tmp/nvr_extract_fake"
    ):
        mock_service_cls.return_value.decrypt_password.return_value = "pw"
        result = task_mod.extract_nvr_frames(
            _RECORDER_ID, _TENANT_ID, 1,
            "2026-07-10T09:00:00Z", "2026-07-10T11:00:00Z", 5, "epi",
        )
    return result, mock_frame_repo, mock_storage, mock_client


class TestExtractNvrFrames:
    def test_recorder_not_found_returns_error(self, monkeypatch):
        result, frame_repo, storage, _ = _run(monkeypatch, recorder=None)
        assert result == {"status": "error", "reason": "recorder_not_found"}
        frame_repo.create.assert_not_called()

    def test_no_segments_returns_zero_frames(self, monkeypatch):
        result, frame_repo, storage, _ = _run(monkeypatch, segments=[])
        assert result == {"status": "completed", "segments": 0, "frames": 0}
        frame_repo.create.assert_not_called()
        storage.upload_bytes.assert_not_called()

    def test_search_failure_returns_error_without_raising(self, monkeypatch):
        mock_recorder_repo = MagicMock()
        mock_recorder_repo.get_by_id.return_value = {
            "id": _RECORDER_ID, "host": "10.0.0.5", "port": 80,
            "protocol": "onvif", "password_encrypted": None,
        }
        monkeypatch.setattr(task_mod, "_get_recorder_repo", lambda: mock_recorder_repo)
        monkeypatch.setattr(task_mod, "_get_frame_repo", lambda: MagicMock())

        mock_client = MagicMock()
        mock_client.search_recordings.side_effect = RuntimeError("device offline")

        with patch("app.domain.services.recorder_service.RecorderService") as mock_svc_cls, \
             patch("app.infrastructure.nvr.factory.get_nvr_client", return_value=mock_client):
            mock_svc_cls.return_value.decrypt_password.return_value = "pw"
            result = task_mod.extract_nvr_frames(
                _RECORDER_ID, _TENANT_ID, 1,
                "2026-07-10T09:00:00Z", "2026-07-10T11:00:00Z", 5, "epi",
            )
        assert result["status"] == "error"
        assert result["reason"] == "search_failed"

    def test_extracts_and_creates_frames_from_segment(self, monkeypatch):
        from datetime import datetime
        from app.infrastructure.nvr.base import RecordingSegment

        segment = RecordingSegment(
            channel=1, start=datetime(2026, 7, 10, 10), end=datetime(2026, 7, 10, 10, 5),
            playback_ref="x",
        )
        result, frame_repo, storage, client = _run(
            monkeypatch,
            segments=[segment],
            glob_files=["/tmp/nvr_extract_fake/frame_0001.jpg", "/tmp/nvr_extract_fake/frame_0002.jpg"],
        )
        assert result["status"] == "completed"
        assert result["segments"] == 1
        assert result["frames"] == 2
        assert storage.upload_bytes.call_count == 2
        assert frame_repo.create.call_count == 2

        kwargs = frame_repo.create.call_args.kwargs
        assert kwargs["source"] == "nvr"
        assert str(kwargs["recorder_id"]) == _RECORDER_ID
        assert kwargs["tenant_id"] == _TENANT_ID
        assert kwargs["video_id"] is None

    def test_ffmpeg_failure_on_one_segment_does_not_abort_others(self, monkeypatch):
        from datetime import datetime
        from app.infrastructure.nvr.base import RecordingSegment

        seg1 = RecordingSegment(
            channel=1, start=datetime(2026, 7, 10, 10), end=datetime(2026, 7, 10, 10, 5),
            playback_ref="a",
        )
        seg2 = RecordingSegment(
            channel=1, start=datetime(2026, 7, 10, 10, 10), end=datetime(2026, 7, 10, 10, 15),
            playback_ref="b",
        )
        mock_recorder_repo = MagicMock()
        mock_recorder_repo.get_by_id.return_value = {
            "id": _RECORDER_ID, "host": "10.0.0.5", "port": 80,
            "protocol": "onvif", "password_encrypted": None,
        }
        monkeypatch.setattr(task_mod, "_get_recorder_repo", lambda: mock_recorder_repo)
        mock_frame_repo = MagicMock()
        monkeypatch.setattr(task_mod, "_get_frame_repo", lambda: mock_frame_repo)

        mock_storage = MagicMock()
        mock_client = MagicMock()
        mock_client.search_recordings.return_value = [seg1, seg2]
        mock_client.build_playback_url.return_value = "rtsp://10.0.0.5:554/replay"

        # 1º segmento falha (returncode!=0), 2º sucede
        results = [MagicMock(returncode=1, stderr="ffmpeg boom"), MagicMock(returncode=0, stderr="")]

        with patch(
            "app.infrastructure.database.connection.DatabasePool"
        ), patch(
            "app.domain.services.recorder_service.RecorderService"
        ) as mock_svc_cls, patch(
            "app.infrastructure.nvr.factory.get_nvr_client", return_value=mock_client
        ), patch(
            "app.infrastructure.storage.local_storage.get_storage", return_value=mock_storage
        ), patch(
            "subprocess.run", side_effect=results
        ), patch(
            "glob.glob", return_value=["/tmp/x/frame_0001.jpg"]
        ), patch(
            "builtins.open", MagicMock()
        ), patch(
            "shutil.rmtree",
        ), patch(
            "tempfile.mkdtemp", return_value="/tmp/nvr_extract_fake"
        ):
            mock_svc_cls.return_value.decrypt_password.return_value = "pw"
            result = task_mod.extract_nvr_frames(
                _RECORDER_ID, _TENANT_ID, 1,
                "2026-07-10T09:00:00Z", "2026-07-10T11:00:00Z", 5, "epi",
            )

        assert result["segments"] == 2
        assert result["frames"] == 1  # só o 2o segmento produziu frame
        assert len(result["errors"]) == 1
        assert "ffmpeg" in result["errors"][0]

    def test_ffmpeg_command_includes_frame_cap(self, monkeypatch):
        from datetime import datetime
        from app.infrastructure.nvr.base import RecordingSegment

        segment = RecordingSegment(
            channel=1, start=datetime(2026, 7, 10, 10), end=datetime(2026, 7, 10, 10, 5),
            playback_ref="x",
        )
        captured_cmd = {}

        def _fake_run(cmd, **kwargs):
            captured_cmd["cmd"] = cmd
            return MagicMock(returncode=0, stderr="")

        mock_recorder_repo = MagicMock()
        mock_recorder_repo.get_by_id.return_value = {
            "id": _RECORDER_ID, "host": "10.0.0.5", "port": 80,
            "protocol": "onvif", "password_encrypted": None,
        }
        monkeypatch.setattr(task_mod, "_get_recorder_repo", lambda: mock_recorder_repo)
        monkeypatch.setattr(task_mod, "_get_frame_repo", lambda: MagicMock())
        mock_client = MagicMock()
        mock_client.search_recordings.return_value = [segment]
        mock_client.build_playback_url.return_value = "rtsp://10.0.0.5:554/replay"

        with patch(
            "app.infrastructure.database.connection.DatabasePool"
        ), patch(
            "app.domain.services.recorder_service.RecorderService"
        ) as mock_svc_cls, patch(
            "app.infrastructure.nvr.factory.get_nvr_client", return_value=mock_client
        ), patch(
            "app.infrastructure.storage.local_storage.get_storage", return_value=MagicMock()
        ), patch(
            "subprocess.run", side_effect=_fake_run
        ), patch(
            "glob.glob", return_value=[]
        ), patch(
            "shutil.rmtree",
        ), patch(
            "tempfile.mkdtemp", return_value="/tmp/nvr_extract_fake"
        ):
            mock_svc_cls.return_value.decrypt_password.return_value = "pw"
            task_mod.extract_nvr_frames(
                _RECORDER_ID, _TENANT_ID, 1,
                "2026-07-10T09:00:00Z", "2026-07-10T11:00:00Z", 5, "epi",
            )

        cmd = captured_cmd["cmd"]
        assert "rtsp://10.0.0.5:554/replay" in cmd
        assert "-frames:v" in cmd
        assert str(task_mod._MAX_FRAMES_PER_SEGMENT) in cmd
        assert "fps=1/5" in cmd
