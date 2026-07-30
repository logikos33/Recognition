"""Tests for HlsTranscoder: wiring do FFmpeg, ciclo de vida, listagem segura.

Fake Popen — nenhum FFmpeg real é invocado (mesma disciplina de
test_rtsp_clip_stream.py / test_rtsp_frame_capture.py).
"""

import io

import pytest

from app.live_view.hls_transcoder import HlsTranscoder, build_output_dir
from app.recorder_client import RecorderError

_RTSP = "rtsp://admin:s3cr3t@10.0.0.9:554/cam/realmonitor?channel=1&subtype=1"
_CAMERA = "cam-1"


class _FakeProc:
    def __init__(self, alive: bool = True, stderr: bytes = b"") -> None:
        self._alive = alive
        self.stderr = io.BytesIO(stderr)
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if self._alive else 1

    def terminate(self):
        self.terminated = True
        self._alive = False

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True
        self._alive = False


def _make(tmp_path, popen=None, **kwargs):
    return HlsTranscoder(
        camera_id=_CAMERA,
        rtsp_url=_RTSP,
        output_dir=str(tmp_path / _CAMERA),
        popen=popen or (lambda cmd, **kw: _FakeProc()),
        **kwargs,
    )


def test_invalid_url_rejected_at_construction(tmp_path):
    with pytest.raises(RecorderError):
        HlsTranscoder(
            camera_id=_CAMERA,
            rtsp_url="ftp://bad-scheme/cam",
            output_dir=str(tmp_path / _CAMERA),
        )


def test_start_builds_low_latency_hls_command(tmp_path):
    captured = {}

    def _popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc()

    t = _make(tmp_path, popen=_popen)
    t.start()

    cmd = captured["cmd"]
    assert cmd[0] == "ffmpeg"
    assert "-rtsp_transport" in cmd and cmd[cmd.index("-rtsp_transport") + 1] == "tcp"
    assert cmd[cmd.index("-hls_time") + 1] == "1"
    assert cmd[cmd.index("-hls_list_size") + 1] == "3"
    assert "delete_segments+omit_endlist" in cmd
    assert "-an" in cmd
    assert cmd[-1].endswith("stream.m3u8")


def test_start_is_idempotent_while_running(tmp_path):
    calls = []

    def _popen(cmd, **kwargs):
        calls.append(cmd)
        return _FakeProc(alive=True)

    t = _make(tmp_path, popen=_popen)
    t.start()
    t.start()
    assert len(calls) == 1


def test_libx264_adds_zerolatency_flags(tmp_path):
    captured = {}

    def _popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc()

    t = _make(tmp_path, popen=_popen, video_codec="libx264")
    t.start()
    assert "-tune" in captured["cmd"]
    assert "zerolatency" in captured["cmd"]


def test_missing_ffmpeg_raises_recorder_error(tmp_path):
    def _popen(cmd, **kwargs):
        raise OSError("No such file or directory: 'ffmpeg'")

    t = _make(tmp_path, popen=_popen)
    with pytest.raises(RecorderError):
        t.start()


def test_credentials_never_leak_in_start_error(tmp_path):
    def _popen(cmd, **kwargs):
        raise OSError("boom")

    t = _make(tmp_path, popen=_popen)
    with pytest.raises(RecorderError) as exc_info:
        t.start()
    assert "s3cr3t" not in str(exc_info.value)


def test_is_running_reflects_process_state(tmp_path):
    proc = _FakeProc(alive=True)
    t = _make(tmp_path, popen=lambda cmd, **kw: proc)
    assert t.is_running() is False  # ainda não iniciou
    t.start()
    assert t.is_running() is True
    proc._alive = False
    assert t.is_running() is False


def test_stop_terminates_and_removes_output_dir(tmp_path):
    proc = _FakeProc(alive=True)
    t = _make(tmp_path, popen=lambda cmd, **kw: proc)
    t.start()
    t.output_dir.mkdir(parents=True, exist_ok=True)
    (t.output_dir / "segment0.ts").write_bytes(b"x")

    t.stop()

    assert proc.terminated is True
    assert not t.output_dir.exists()  # buffer transitório não fica órfão


def test_stderr_tail_empty_while_process_alive(tmp_path):
    t = _make(tmp_path, popen=lambda cmd, **kw: _FakeProc(alive=True, stderr=b"boom"))
    t.start()
    assert t.stderr_tail() == ""  # ler de processo vivo bloquearia


def test_stderr_tail_returns_output_after_death(tmp_path):
    t = _make(tmp_path, popen=lambda cmd, **kw: _FakeProc(alive=False, stderr=b"conn refused"))
    t.start()
    assert "conn refused" in t.stderr_tail()


def test_list_ready_files_empty_without_playlist(tmp_path):
    t = _make(tmp_path)
    assert t.list_ready_files() == []


def test_list_ready_files_returns_playlist_and_listed_segments(tmp_path):
    t = _make(tmp_path)
    t.output_dir.mkdir(parents=True, exist_ok=True)
    t.playlist_path.write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:1.0,\nsegment1.ts\n#EXTINF:1.0,\nsegment2.ts\n"
    )
    (t.output_dir / "segment1.ts").write_bytes(b"a")
    (t.output_dir / "segment2.ts").write_bytes(b"b")

    names = [p.name for p in t.list_ready_files()]

    assert names[0] == "stream.m3u8"
    assert set(names[1:]) == {"segment1.ts", "segment2.ts"}


def test_list_ready_files_skips_segment_not_yet_in_playlist(tmp_path):
    """Segmento sendo escrito AGORA ainda não aparece na playlist — empurrá-lo
    entregaria bytes truncados ao navegador."""
    t = _make(tmp_path)
    t.output_dir.mkdir(parents=True, exist_ok=True)
    t.playlist_path.write_text("#EXTM3U\n#EXTINF:1.0,\nsegment1.ts\n")
    (t.output_dir / "segment1.ts").write_bytes(b"done")
    (t.output_dir / "segment2.ts").write_bytes(b"partial-being-written")

    names = [p.name for p in t.list_ready_files()]

    assert "segment2.ts" not in names


def test_build_output_dir_is_per_camera():
    assert build_output_dir("/tmp/lv", "cam-9").endswith("/cam-9")
