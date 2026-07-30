"""Tests for LiveViewLoop: supervisão do transcode + push dos segmentos."""

import threading

import pytest

from app.live_view.live_view_loop import (
    LiveViewLoop,
    _resolve_camera_urls,
    build_live_view_loop_from_env,
)
from app.live_view.segment_pusher import SegmentPushError
from app.recorder_client import RecorderError

_CAMERA = "cam-1"
_RTSP = "rtsp://admin:pw@10.0.0.9:554/cam/realmonitor?channel=1&subtype=1"


class _FakeTokenSource:
    def get_bearer(self, ttl_s: int = 300) -> str:
        return "fake-bearer"


class _FakeTranscoder:
    def __init__(self, files=None, running=True, stderr=""):
        self._files = files or []
        self._running = running
        self._stderr = stderr
        self.start_calls = 0
        self.stop_calls = 0

    def is_running(self):
        return self._running

    def start(self):
        self.start_calls += 1
        self._running = True

    def stop(self):
        self.stop_calls += 1

    def stderr_tail(self):
        return self._stderr

    def list_ready_files(self):
        return self._files


def _make_loop(transcoder, pushes, tmp_path):
    def _push(http, base, bearer, camera_id, filename, data):
        pushes.append({"camera_id": camera_id, "filename": filename, "data": data})

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
    )
    loop._transcoders[_CAMERA] = transcoder
    return loop


def test_tick_starts_transcoder_when_not_running(tmp_path):
    t = _FakeTranscoder(running=False)
    loop = _make_loop(t, [], tmp_path)
    loop.tick()
    assert t.start_calls == 1


def test_tick_pushes_playlist_and_segments(tmp_path):
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text("#EXTM3U\nsegment1.ts\n")
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"\x47ts-bytes")

    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[playlist, seg]), pushes, tmp_path)
    loop.tick()

    assert [p["filename"] for p in pushes] == ["stream.m3u8", "segment1.ts"]
    assert pushes[1]["data"] == b"\x47ts-bytes"
    assert all(p["camera_id"] == _CAMERA for p in pushes)


def test_unchanged_segment_not_pushed_twice_but_playlist_is(tmp_path):
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text("#EXTM3U\nsegment1.ts\n")
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")

    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[playlist, seg]), pushes, tmp_path)
    loop.tick()
    loop.tick()

    filenames = [p["filename"] for p in pushes]
    assert filenames.count("segment1.ts") == 1  # dedup
    assert filenames.count("stream.m3u8") == 2  # renova TTL na nuvem


def test_empty_file_is_skipped(tmp_path):
    empty = tmp_path / "segment1.ts"
    empty.write_bytes(b"")
    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[empty]), pushes, tmp_path)
    loop.tick()
    assert pushes == []


def test_vanished_file_is_skipped_without_raising(tmp_path):
    """delete_segments pode apagar o arquivo entre listar e ler."""
    gone = tmp_path / "segment-gone.ts"
    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[gone]), pushes, tmp_path)
    loop.tick()  # não deve levantar
    assert pushes == []


def test_push_failure_does_not_mark_as_pushed(tmp_path):
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")

    attempts = []

    def _failing_push(http, base, bearer, camera_id, filename, data):
        attempts.append(filename)
        raise SegmentPushError("cloud down")

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_failing_push,
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[seg])

    loop.tick()
    loop.tick()

    assert len(attempts) == 2  # retentou, não marcou como enviado


def test_dead_transcoder_forgets_cache_before_restart(tmp_path):
    """Numeração de segmento reinicia com o FFmpeg — um nome reusado precisa
    subir de novo."""
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")
    pushes = []

    alive = _FakeTranscoder(files=[seg], running=True)
    loop = _make_loop(alive, pushes, tmp_path)
    loop.tick()
    assert len(pushes) == 1

    alive._running = False
    loop.tick()  # detecta morte, esquece cache, reinicia
    alive._running = True
    loop.tick()

    assert len(pushes) == 2


def test_start_failure_is_logged_not_fatal(tmp_path):
    class _FailingTranscoder(_FakeTranscoder):
        def start(self):
            raise RecorderError("ffmpeg indisponível")

    loop = _make_loop(_FailingTranscoder(running=False), [], tmp_path)
    loop.tick()  # não deve levantar


def test_run_stops_and_cleans_up_on_stop_event(tmp_path):
    t = _FakeTranscoder(files=[])
    loop = _make_loop(t, [], tmp_path)
    loop._poll_interval_s = 0.0

    stop_event = threading.Event()
    stop_event.set()
    loop.run(stop_event)

    assert t.stop_calls == 1  # stop_all no finally


def test_camera_ids_property(tmp_path):
    loop = _make_loop(_FakeTranscoder(), [], tmp_path)
    assert loop.camera_ids == [_CAMERA]


# ── _resolve_camera_urls / build_from_env ───────────────────────────────────


class _FakeRecorder:
    def __init__(self, channel_map):
        self._channel_map = channel_map

    def _build_live_url(self, channel):
        return f"rtsp://admin:pw@10.0.0.9:554/cam/realmonitor?channel={channel}&subtype=1"


def test_resolve_camera_urls_uses_recorder_live_url():
    urls = _resolve_camera_urls(_FakeRecorder({"cam-a": 1, "cam-b": 2}))
    assert set(urls) == {"cam-a", "cam-b"}
    assert "channel=1" in urls["cam-a"]
    assert "channel=2" in urls["cam-b"]


def test_resolve_camera_urls_empty_when_no_channel_map():
    assert _resolve_camera_urls(_FakeRecorder({})) == {}


def test_resolve_camera_urls_skips_camera_whose_url_fails():
    class _PartiallyFailing(_FakeRecorder):
        def _build_live_url(self, channel):
            if channel == 2:
                raise RecorderError("sem canal mapeado")
            return f"rtsp://10.0.0.9:554/cam/realmonitor?channel={channel}&subtype=1"

    urls = _resolve_camera_urls(_PartiallyFailing({"cam-a": 1, "cam-b": 2}))
    assert set(urls) == {"cam-a"}


def test_build_from_env_happy_path(tmp_path):
    loop = build_live_view_loop_from_env(
        _FakeRecorder({"cam-a": 1}),
        _FakeTokenSource(),
        env={"EDGE_API_URL": "https://api.example", "LIVE_VIEW_WORK_DIR": str(tmp_path)},
    )
    assert loop.camera_ids == ["cam-a"]


def test_build_from_env_no_cameras_raises(tmp_path):
    with pytest.raises(ValueError, match="Nenhuma câmera"):
        build_live_view_loop_from_env(
            _FakeRecorder({}),
            _FakeTokenSource(),
            env={"LIVE_VIEW_WORK_DIR": str(tmp_path)},
        )


def test_build_from_env_applies_overrides(tmp_path):
    loop = build_live_view_loop_from_env(
        _FakeRecorder({"cam-a": 1}),
        _FakeTokenSource(),
        env={
            "LIVE_VIEW_WORK_DIR": str(tmp_path),
            "LIVE_VIEW_POLL_INTERVAL_S": "2.5",
            "LIVE_VIEW_SEGMENT_SECONDS": "4",
        },
    )
    assert loop._poll_interval_s == 2.5
