"""Self-check for the DVR replay miner: channel policy table, dedup/blur
filters, and — most important — that the anti-lockout circuit breaker aborts
the WHOLE run (zero retries, zero further recorder access) the instant a
401/403 surfaces, same discipline as snapshot_executor.py's breaker.

No real ffmpeg/ONNX model/network: PersonDetector is stubbed (duck-typed,
same Protocol collector_loop.py already relies on), stream_clip() is a
MockRecorderClient yielding synthetic JPEG bytes, and frame extraction is
injected as the pure `_split_mjpeg` (no subprocess).
"""

from __future__ import annotations

import io
from datetime import date, datetime
from datetime import time as dtime

from PIL import Image, ImageFilter

from app.collector.person_detector import PersonBox, PersonResult
from app.collector.replay_miner import (
    ChannelPolicy,
    MiningTask,
    NearDuplicateFilter,
    ReplayMiner,
    ShiftWindow,
    _split_mjpeg,
    blur_variance,
    build_sampling_plan,
    is_blurry,
    policy_for_channel,
)
from app.recorder_client import RecorderError

_EXCLUDED = {13, 14, 17, 18, 22, 25}
_QUALITY_ONLY = {3, 27}


def _gradient_jpeg(quality: int = 90, flip: bool = False) -> bytes:
    img = Image.new("RGB", (80, 60))
    pixels = img.load()
    for x in range(80):
        for y in range(60):
            v = (x * 3) % 256
            pixels[x, y] = (255 - v, 255 - v, 255 - v) if flip else (v, v, v)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _checkerboard_jpeg() -> bytes:
    """High-frequency pattern — sharp, should NOT be flagged as blurry."""
    img = Image.new("L", (64, 48))
    pixels = img.load()
    for x in range(64):
        for y in range(48):
            pixels[x, y] = 255 if (x + y) % 2 == 0 else 0
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _flat_jpeg() -> bytes:
    """Solid color — zero edge energy, should be flagged as blurry."""
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color=(120, 120, 120)).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ── channel policy table ────────────────────────────────────────────────────


def test_excluded_channels_extract_nothing():
    for ch in _EXCLUDED:
        assert policy_for_channel(ch).policy == ChannelPolicy.EXCLUDED


def test_quality_channels_route_out_of_epi_dataset():
    for ch in _QUALITY_ONLY:
        assert policy_for_channel(ch).policy == ChannelPolicy.QUALITY_ONLY


def test_channel_8_gets_concentration_ceiling():
    rule = policy_for_channel(8)
    assert rule.policy == ChannelPolicy.CEILING
    assert rule.campaign_max_crops is not None and rule.campaign_max_crops > 0


def test_channel_10_is_absence_source():
    assert policy_for_channel(10).policy == ChannelPolicy.ABSENCE


def test_full_priority_channels():
    for ch in (1, 4, 11, 12, 19, 23, 28):
        assert policy_for_channel(ch).policy == ChannelPolicy.FULL


def test_unlisted_channel_is_reduced_not_zeroed():
    rule = policy_for_channel(999)
    assert rule.policy == ChannelPolicy.REDUCED
    assert rule.per_window_cap is not None and rule.per_window_cap > 0


def test_sampling_plan_skips_excluded_and_quality_channels():
    cameras = {ch: f"cam-{ch}" for ch in list(_EXCLUDED) + list(_QUALITY_ONLY) + [1, 8, 10, 999]}
    plan = build_sampling_plan(cameras, days=[date(2026, 8, 3)])
    planned_channels = {t.channel for t in plan}
    assert planned_channels.isdisjoint(_EXCLUDED)
    assert planned_channels.isdisjoint(_QUALITY_ONLY)
    assert {1, 8, 10, 999} <= planned_channels


# ── blur filter (Laplacian variance, PIL-only) ──────────────────────────────


def test_sharp_crop_is_not_blurry():
    assert blur_variance(_checkerboard_jpeg()) > blur_variance(_flat_jpeg())
    assert not is_blurry(_checkerboard_jpeg())


def test_flat_crop_is_blurry():
    assert is_blurry(_flat_jpeg())


def test_defocused_crop_is_blurry():
    """More faithful stand-in for a real out-of-focus crop than a flat
    color block: Gaussian-blur the sharp checkerboard and confirm it drops
    below the sharp image's variance by an order of magnitude."""
    sharp = Image.open(io.BytesIO(_checkerboard_jpeg()))
    buf = io.BytesIO()
    sharp.filter(ImageFilter.GaussianBlur(radius=3)).save(buf, format="JPEG", quality=90)
    defocused = buf.getvalue()

    assert blur_variance(defocused) < blur_variance(_checkerboard_jpeg()) / 5
    assert is_blurry(defocused)


# ── near-duplicate filter (dHash, timeline-aware) ───────────────────────────


def test_near_duplicate_dropped_but_different_crop_kept():
    dedup = NearDuplicateFilter()
    base = _gradient_jpeg(quality=95)
    recompressed = _gradient_jpeg(quality=40)  # same content, different JPEG bytes
    different = _gradient_jpeg(quality=95, flip=True)  # inverted gradient

    assert dedup.is_duplicate("cam-1", base) is False  # first sighting, always kept
    assert dedup.is_duplicate("cam-1", recompressed) is True  # near-identical -> dropped
    assert dedup.is_duplicate("cam-1", different) is False  # genuinely different -> kept


def test_same_camera_same_day_alone_is_not_a_duplicate_reason():
    """Two crops from the same camera on the same day that are NOT visually
    near-identical must both survive — "same day/same camera" alone is never
    the drop reason (task spec)."""
    dedup = NearDuplicateFilter()
    a = _gradient_jpeg(quality=95)
    b = _gradient_jpeg(quality=95, flip=True)

    assert dedup.is_duplicate("cam-1", a) is False
    assert dedup.is_duplicate("cam-1", b) is False


def test_split_mjpeg_pure_byte_split():
    data = b"\xff\xd8AAA\xff\xd9\xff\xd8BBB\xff\xd9"
    frames = _split_mjpeg(data)
    assert frames == [b"\xff\xd8AAA\xff\xd9", b"\xff\xd8BBB\xff\xd9"]


# ── ReplayMiner orchestration: anti-lockout breaker ─────────────────────────


class _FakePersonDetector:
    """Always finds one person covering the whole frame — the gate/crop path
    is exercised without needing the real ONNX model (absent in this env)."""

    def detect(self, frame_bytes: bytes) -> PersonResult:
        img = Image.open(io.BytesIO(frame_bytes))
        w, h = img.size
        box = PersonBox(x=0, y=0, w=w, h=h, confidence=0.9)
        return PersonResult(found=True, boxes=(box,), max_confidence=0.9)


class _FakeTokenSource:
    def get_bearer(self, ttl_s: int = 300) -> str:
        return "fake-bearer"


class _MockRecorderClient:
    """stream_clip() yields one synthetic JPEG "clip" per call; raises a
    401-flavored RecorderError on the call index given by *trip_on_call*
    (None = never). Records every call for the zero-further-access assertion.
    """

    def __init__(self, trip_on_call: int | None = None) -> None:
        self.calls: list[str] = []
        self._trip_on = trip_on_call

    def stream_clip(self, camera_id: str, start: datetime, end: datetime):
        idx = len(self.calls)
        self.calls.append(camera_id)
        if self._trip_on is not None and idx == self._trip_on:
            raise RecorderError("gravador respondeu 401 Unauthorized ao playback")
        yield _gradient_jpeg(quality=90, flip=(idx % 2 == 0))


def _one_window_shift() -> ShiftWindow:
    # 6s de turno == exatamente 1 sub-janela para clip_seconds=6 — mantém o
    # teste determinístico (1 stream_clip() por task) sem depender de
    # aritmética de _sub_windows além do caso trivial.
    return ShiftWindow("teste", dtime(7, 0, 0), dtime(7, 0, 6))


def _make_plan(n_tasks: int) -> list[MiningTask]:
    day = date(2026, 8, 3)
    shift = _one_window_shift()
    channels = [1, 4, 11, 12][:n_tasks]
    return [
        MiningTask(ch, f"cam-{ch}", day, shift, policy_for_channel(ch)) for ch in channels
    ]


def _make_miner(recorder, uploads: list, **overrides) -> ReplayMiner:
    def _upload_fn(http, api_base_url, bearer, camera_id, recorder_id, frame_bytes,
                    module_code, captured_at):
        uploads.append({"camera_id": camera_id, "frame_bytes": frame_bytes})
        return f"frame-{len(uploads)}"

    defaults = dict(
        recorder=recorder,
        api_base_url="https://api.example",
        recorder_id="recorder-1",
        token_source=_FakeTokenSource(),
        person_detector=_FakePersonDetector(),
        http_client=object(),
        upload_fn=_upload_fn,
        frame_extractor=lambda clip, fps: _split_mjpeg(clip),
        disk_check_fn=lambda: True,
        sleep_fn=lambda s: None,
        state_path=None,
        blur_min_variance=0.0,  # blur filter not under test here
        pull_interval_min=60.0,
        clip_seconds=6.0,
    )
    defaults.update(overrides)
    return ReplayMiner(**defaults)


def test_happy_path_uploads_one_crop_per_task():
    recorder = _MockRecorderClient()
    uploads: list = []
    miner = _make_miner(recorder, uploads)
    plan = _make_plan(3)

    stats = miner.mine(plan)

    assert stats.aborted_reason is None
    assert miner.circuit_open is False
    assert stats.crops_kept == 3
    assert len(uploads) == 3
    assert recorder.calls == ["cam-1", "cam-4", "cam-11"]


def test_anti_lockout_breaker_aborts_whole_run_with_zero_retries():
    # Trips on the SECOND stream_clip() call: proves the FIRST task completed
    # normally (breaker doesn't trip preemptively) and that NOTHING after the
    # trip touches the recorder again (zero retries, whole session ends).
    recorder = _MockRecorderClient(trip_on_call=1)
    uploads: list = []
    miner = _make_miner(recorder, uploads)
    plan = _make_plan(4)

    stats = miner.mine(plan)

    assert miner.circuit_open is True
    assert stats.aborted_reason is not None and "auth_circuit_open" in stats.aborted_reason
    # Só a 1a task (cam-1) completou upload; a 2a task disparou o breaker e
    # abortou ANTES de qualquer upload seu; a 3a/4a nunca foram tentadas.
    assert len(uploads) == 1
    assert recorder.calls == ["cam-1", "cam-4"]  # nunca chega em cam-11/cam-12
    assert stats.tasks_attempted == 2
    assert stats.tasks_planned == 4


def test_empty_window_is_not_an_auth_failure_and_does_not_trip_breaker():
    class _EmptyWindowRecorder:
        def __init__(self):
            self.calls: list[str] = []

        def stream_clip(self, camera_id, start, end):
            self.calls.append(camera_id)
            raise RecorderError("ffmpeg não produziu bytes para o clipe: sem sinal no canal")
            yield b""  # pragma: no cover — makes this a generator function

    recorder = _EmptyWindowRecorder()
    uploads: list = []
    miner = _make_miner(recorder, uploads)
    plan = _make_plan(2)

    stats = miner.mine(plan)

    assert miner.circuit_open is False
    assert stats.aborted_reason is None
    assert stats.windows_empty == 2
    assert stats.tasks_attempted == 2  # ambas as tasks tentadas — janela vazia não aborta
