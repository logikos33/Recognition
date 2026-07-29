"""Tests for CollectorLoop: motion->burst->cooldown state machine, target cap,
dedup, and build_collector_loop_from_env's config parsing.

Uses fake RecorderClient/upload_fn/clock — no real ffmpeg/HTTP/camera.
"""

import io
import threading

import pytest
from PIL import Image

from app.collector.collector_loop import CollectorLoop, build_collector_loop_from_env
from app.collector.frame_uploader import FrameUploadError
from app.recorder_client import RecorderError

_CAMERA = "cam-1"
_RECORDER_ID = "recorder-1"


def _solid_jpeg(color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color=color).save(buf, format="JPEG")
    return buf.getvalue()


_BLACK = _solid_jpeg((0, 0, 0))
_WHITE = _solid_jpeg((255, 255, 255))
_GRAY = _solid_jpeg((128, 128, 128))


class _FakeRecorder:
    def __init__(self, frames_by_camera: dict[str, list[bytes]]) -> None:
        self._queues = {cam: list(frames) for cam, frames in frames_by_camera.items()}
        self.calls: list[str] = []

    def capture_frame(self, camera_id: str) -> bytes:
        self.calls.append(camera_id)
        queue = self._queues.get(camera_id, [])
        if not queue:
            raise RecorderError(f"no more fake frames queued for {camera_id}")
        return queue.pop(0)


class _FakeTokenSource:
    def get_bearer(self, ttl_s: int = 300) -> str:
        return "fake-bearer"


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _fake_upload_fn(calls: list):
    def _upload(
        http_client, api_base_url, bearer, camera_id, recorder_id,
        frame_bytes, module_code, captured_at,
    ):
        calls.append(
            {
                "camera_id": camera_id,
                "recorder_id": recorder_id,
                "frame_bytes": frame_bytes,
                "module_code": module_code,
            }
        )
        return f"frame-{len(calls)}"

    return _upload


def _make_loop(recorder, upload_calls, clock=None, **overrides):
    defaults = dict(
        recorder=recorder,
        camera_ids=[_CAMERA],
        api_base_url="https://api.example",
        recorder_id=_RECORDER_ID,
        token_source=_FakeTokenSource(),
        http_client=object(),  # never touched — upload_fn is faked
        upload_fn=_fake_upload_fn(upload_calls),
        clock=clock or _FakeClock(),
        poll_interval_s=0.0,
        burst_count=3,
        burst_interval_s=0.0,
        cooldown_s=30.0,
        target_frames_per_camera=1000,
    )
    defaults.update(overrides)
    return CollectorLoop(**defaults)


def test_first_tick_seeds_detector_without_uploading():
    recorder = _FakeRecorder({_CAMERA: [_BLACK]})
    uploads = []
    loop = _make_loop(recorder, uploads)

    loop.tick(threading.Event())

    assert uploads == []
    assert recorder.calls == [_CAMERA]


def test_motion_triggers_burst_and_uploads():
    # tick 1: seed (BLACK). tick 2: WHITE triggers motion -> burst captures
    # burst_count=3 frames total (the triggering WHITE + 2 more from the
    # queue) — GRAY/BLACK keep each burst frame distinct enough to survive dedup.
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _GRAY, _BLACK]})
    uploads = []
    loop = _make_loop(recorder, uploads, burst_count=3)

    loop.tick(threading.Event())  # seed
    loop.tick(threading.Event())  # motion -> burst

    assert len(uploads) == 3
    assert all(u["camera_id"] == _CAMERA for u in uploads)
    assert all(u["recorder_id"] == _RECORDER_ID for u in uploads)


def test_camera_in_cooldown_is_skipped_entirely():
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _WHITE, _WHITE]})
    uploads = []
    clock = _FakeClock(start=0.0)
    loop = _make_loop(recorder, uploads, clock=clock, burst_count=1, cooldown_s=30.0)

    loop.tick(threading.Event())  # seed
    loop.tick(threading.Event())  # motion -> burst -> cooldown_until = 30.0
    calls_after_burst = len(recorder.calls)

    clock.now = 10.0  # still within cooldown
    loop.tick(threading.Event())

    assert len(recorder.calls) == calls_after_burst


def test_camera_resumes_polling_after_cooldown_expires():
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _BLACK]})
    uploads = []
    clock = _FakeClock(start=0.0)
    loop = _make_loop(recorder, uploads, clock=clock, burst_count=1, cooldown_s=30.0)

    loop.tick(threading.Event())  # seed
    loop.tick(threading.Event())  # motion -> burst -> cooldown_until = 30.0
    calls_after_burst = len(recorder.calls)

    clock.now = 31.0  # cooldown expired
    loop.tick(threading.Event())

    assert len(recorder.calls) == calls_after_burst + 1


def test_camera_at_target_is_skipped_without_capturing():
    recorder = _FakeRecorder({_CAMERA: [_BLACK]})
    uploads = []
    loop = _make_loop(recorder, uploads, target_frames_per_camera=0)

    loop.tick(threading.Event())

    assert recorder.calls == []


def test_burst_stops_once_target_reached_mid_burst():
    # distinct frames (BLACK/WHITE/GRAY) so both burst frames survive dedup
    # and actually count toward the target=2 cap.
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _GRAY]})
    uploads = []
    loop = _make_loop(recorder, uploads, burst_count=10, target_frames_per_camera=2)

    loop.tick(threading.Event())  # seed
    loop.tick(threading.Event())  # motion -> burst capped at target=2

    assert len(uploads) == 2


def test_burst_dedups_near_identical_frames():
    # burst frames: WHITE (trigger), WHITE again (near-identical -> deduped), BLACK (kept)
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _WHITE, _BLACK]})
    uploads = []
    loop = _make_loop(recorder, uploads, burst_count=3)

    loop.tick(threading.Event())  # seed
    loop.tick(threading.Event())  # motion -> burst

    assert len(uploads) == 2  # the duplicate WHITE was skipped


def test_burst_capture_error_is_skipped_not_fatal():
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE]})  # queue runs dry mid-burst
    uploads = []
    loop = _make_loop(recorder, uploads, burst_count=3)

    loop.tick(threading.Event())  # seed
    loop.tick(threading.Event())  # motion -> burst: 1 real frame + 2 failed captures

    assert len(uploads) == 1


def test_upload_failure_does_not_count_toward_target_or_dedup_state():
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _BLACK]})

    def _failing_upload(*args, **kwargs):
        raise FrameUploadError("cloud rejected")

    loop = _make_loop(recorder, [], burst_count=1, upload_fn=_failing_upload)

    loop.tick(threading.Event())  # seed
    loop.tick(threading.Event())  # motion -> burst -> upload fails

    state = loop._states[_CAMERA]
    assert state.frames_uploaded == 0
    assert state.last_uploaded_bytes is None


def test_initial_capture_error_is_logged_and_skipped():
    recorder = _FakeRecorder({})  # every capture_frame call raises
    uploads = []
    loop = _make_loop(recorder, uploads)

    loop.tick(threading.Event())  # should not raise

    assert uploads == []


def test_burst_stops_immediately_when_stop_event_set():
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _WHITE, _WHITE]})
    uploads = []
    loop = _make_loop(recorder, uploads, burst_count=5)

    loop.tick(threading.Event())  # seed

    stop_event = threading.Event()
    stop_event.set()
    loop.tick(stop_event)  # motion triggers, but burst aborts after frame 1

    assert len(uploads) == 1


def test_run_stops_when_stop_event_is_set():
    recorder = _FakeRecorder({_CAMERA: [_BLACK]})
    uploads = []
    loop = _make_loop(recorder, uploads, poll_interval_s=0.0)

    stop_event = threading.Event()
    tick_count = {"n": 0}
    original_tick = loop.tick

    def _counting_tick(se):
        tick_count["n"] += 1
        if tick_count["n"] >= 2:
            stop_event.set()
        original_tick(se)

    loop.tick = _counting_tick
    loop.run(stop_event)

    assert tick_count["n"] == 2


def test_camera_ids_property_returns_a_copy():
    recorder = _FakeRecorder({_CAMERA: []})
    loop = _make_loop(recorder, [])
    ids = loop.camera_ids
    ids.append("mutated")
    assert loop.camera_ids == [_CAMERA]


# ── build_collector_loop_from_env ───────────────────────────────────────────


def test_build_from_env_happy_path():
    recorder = _FakeRecorder({})
    env = {
        "RECORDER_CHANNEL_MAP": '{"cam-1": 1, "cam-2": 2}',
        "RECORDER_CLOUD_ID": "recorder-uuid-1",
        "EDGE_API_URL": "https://api-v3-desenvolvimento.up.railway.app",
    }
    loop = build_collector_loop_from_env(recorder, _FakeTokenSource(), env=env)
    assert sorted(loop.camera_ids) == ["cam-1", "cam-2"]


def test_build_from_env_missing_recorder_cloud_id_raises():
    recorder = _FakeRecorder({})
    env = {"RECORDER_CHANNEL_MAP": '{"cam-1": 1}'}
    with pytest.raises(ValueError, match="RECORDER_CLOUD_ID"):
        build_collector_loop_from_env(recorder, _FakeTokenSource(), env=env)


def test_build_from_env_missing_channel_map_raises():
    recorder = _FakeRecorder({})
    env = {"RECORDER_CLOUD_ID": "recorder-uuid-1"}
    with pytest.raises(ValueError, match="RECORDER_CHANNEL_MAP"):
        build_collector_loop_from_env(recorder, _FakeTokenSource(), env=env)


def test_build_from_env_malformed_channel_map_json_raises():
    recorder = _FakeRecorder({})
    env = {"RECORDER_CHANNEL_MAP": "not-json", "RECORDER_CLOUD_ID": "recorder-uuid-1"}
    with pytest.raises(ValueError):
        build_collector_loop_from_env(recorder, _FakeTokenSource(), env=env)


def test_build_from_env_channel_map_must_be_nonempty_object():
    recorder = _FakeRecorder({})
    env = {"RECORDER_CHANNEL_MAP": "{}", "RECORDER_CLOUD_ID": "recorder-uuid-1"}
    with pytest.raises(ValueError):
        build_collector_loop_from_env(recorder, _FakeTokenSource(), env=env)


def test_build_from_env_applies_tuning_overrides():
    recorder = _FakeRecorder({})
    env = {
        "RECORDER_CHANNEL_MAP": '{"cam-1": 1}',
        "RECORDER_CLOUD_ID": "recorder-uuid-1",
        "COLLECTOR_POLL_INTERVAL_S": "5.0",
        "COLLECTOR_BURST_COUNT": "4",
        "COLLECTOR_TARGET_FRAMES_PER_CAMERA": "50",
    }
    loop = build_collector_loop_from_env(recorder, _FakeTokenSource(), env=env)
    assert loop._poll_interval_s == 5.0
    assert loop._burst_count == 4
    assert loop._target == 50
