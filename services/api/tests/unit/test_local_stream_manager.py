"""
Unit tests for LocalStreamManager guard-rails (task-059, task-061, task-067).

Guard-rails tested:
1. RTSPUrlValidator called BEFORE Popen (RTSP injection prevention)
2. stderr captured and surfaced when process dies
3. stop() kills process AND removes /tmp/hls/{camera_id}/
4. start() is idempotent (2nd call returns already_running, 1 process only)
5. non-UUID camera_id rejected (path traversal prevention)
6. FFmpeg command has low-latency flags and 1s/3-entry HLS config (task-061)
7. task-067: substream → main-stream fallback on fast FFmpeg exit, no retry loop
"""
import logging
import os
import shutil
import subprocess
import threading
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_manager():
    """Return a new (non-singleton) LocalStreamManager instance."""
    # Import lazily to avoid singleton state pollution between tests
    from app.api.v1.cameras.local_stream_manager import LocalStreamManager

    mgr = LocalStreamManager.__new__(LocalStreamManager)
    mgr._processes = {}
    mgr._stderr_tail = {}
    mgr._sequences = {}
    mgr._lock = threading.Lock()
    # Skip starting the watchdog/atexit in unit tests
    return mgr


VALID_RTSP = "rtsp://192.168.1.100:554/cam/realmonitor?channel=1&subtype=0"
VALID_UUID = "11111111-1111-1111-1111-111111111111"


# ---------------------------------------------------------------------------
# Guard-rail 3a — UUID validation (path traversal)
# ---------------------------------------------------------------------------

class TestUUIDValidation:
    def test_non_uuid_camera_id_raises_before_rtsp_check(self):
        """camera_id must be a valid UUID — path traversal prevention."""
        mgr = _fresh_manager()
        with pytest.raises(ValidationError, match="camera_id inválido"):
            mgr.start(camera_id="../etc/passwd", rtsp_url=VALID_RTSP)

    def test_empty_camera_id_raises(self):
        mgr = _fresh_manager()
        with pytest.raises(ValidationError, match="camera_id inválido"):
            mgr.start(camera_id="", rtsp_url=VALID_RTSP)


# ---------------------------------------------------------------------------
# Guard-rail 3b — RTSPUrlValidator called BEFORE Popen
# ---------------------------------------------------------------------------

class TestRTSPValidatedBeforePopen:
    """RTSP injection prevention: Popen must never be called with an invalid URL."""

    def test_invalid_rtsp_scheme_raises_before_popen(self):
        """file:// URL must raise ValidationError; Popen must NOT be called."""
        mgr = _fresh_manager()
        with patch("subprocess.Popen") as mock_popen:
            with pytest.raises(ValidationError):
                mgr.start(camera_id=VALID_UUID, rtsp_url="file:///etc/passwd")
            mock_popen.assert_not_called()

    def test_dangerous_chars_in_rtsp_raise_before_popen(self):
        """Shell metacharacters must be blocked before Popen."""
        mgr = _fresh_manager()
        with patch("subprocess.Popen") as mock_popen:
            with pytest.raises(ValidationError):
                mgr.start(camera_id=VALID_UUID, rtsp_url="rtsp://192.168.1.1:554/;rm -rf /")
            mock_popen.assert_not_called()

    def test_valid_rtsp_reaches_popen(self, tmp_path):
        """A valid RTSP URL should attempt to start FFmpeg (Popen called)."""
        mgr = _fresh_manager()

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = 99999
        mock_proc.poll.return_value = None
        mock_proc.stderr = iter([])

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("os.makedirs"), \
             patch("threading.Thread"):
            result = mgr.start(camera_id=VALID_UUID, rtsp_url=VALID_RTSP)

        mock_popen.assert_called_once()
        assert result["status"] == "started"
        assert result["pid"] == 99999


# ---------------------------------------------------------------------------
# Guard-rail 1 — stderr surfaced when process dies
# ---------------------------------------------------------------------------

class TestStderrSurfaced:
    def test_status_returns_stderr_tail_when_process_dead(self):
        """When FFmpeg exits, stderr_tail must be available in status()."""
        mgr = _fresh_manager()

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = 12345
        mock_proc.poll.return_value = 1  # process exited with code 1

        tail: deque = deque(maxlen=20)
        tail.append("Connection refused: rtsp://192.168.1.100:554")
        tail.append("Error opening input: Connection refused")

        mgr._processes[VALID_UUID] = mock_proc
        mgr._stderr_tail[VALID_UUID] = tail

        st = mgr.status(VALID_UUID)

        assert st["running"] is False
        assert st["returncode"] == 1
        assert "Connection refused" in (st["stderr_tail"] or "")

    def test_status_for_unknown_camera_returns_not_running(self):
        mgr = _fresh_manager()
        st = mgr.status("00000000-0000-0000-0000-000000000000")
        assert st["running"] is False
        assert st["pid"] is None


# ---------------------------------------------------------------------------
# Guard-rail 2 — stop() kills process AND cleans /tmp/hls/
# ---------------------------------------------------------------------------

class TestStopCleansUp:
    def test_stop_kills_process_and_removes_hls_dir(self, tmp_path):
        """stop() must terminate FFmpeg and call shutil.rmtree on the HLS dir."""
        mgr = _fresh_manager()

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None  # still running
        mock_proc.wait.return_value = 0

        hls_dir = tmp_path / "hls" / VALID_UUID
        hls_dir.mkdir(parents=True)
        (hls_dir / "stream.m3u8").write_text("#EXTM3U\n")

        mgr._processes[VALID_UUID] = mock_proc
        mgr._stderr_tail[VALID_UUID] = deque()

        with patch(
            "app.api.v1.cameras.local_stream_manager.os.path.isdir",
            return_value=True,
        ), patch(
            "app.api.v1.cameras.local_stream_manager.shutil.rmtree"
        ) as mock_rmtree:
            result = mgr.stop(VALID_UUID)

        mock_proc.terminate.assert_called_once()
        mock_rmtree.assert_called_once_with(f"/tmp/hls/{VALID_UUID}")
        assert result["status"] == "stopped"
        assert VALID_UUID not in mgr._processes

    def test_stop_not_running_is_safe(self):
        """stop() on an unknown camera_id must not raise."""
        mgr = _fresh_manager()
        result = mgr.stop("00000000-0000-0000-0000-000000000000")
        assert result["status"] == "stopped"


# ---------------------------------------------------------------------------
# Guard-rail 2 — start() is idempotent
# ---------------------------------------------------------------------------

class TestIdempotentStart:
    def test_second_start_returns_already_running(self):
        """Calling start() twice with the same camera_id must not spawn a second FFmpeg."""
        mgr = _fresh_manager()

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = 77777
        mock_proc.poll.return_value = None  # still alive

        mgr._processes[VALID_UUID] = mock_proc

        # RTSPUrlValidator and Popen must NOT be called again
        with patch("subprocess.Popen") as mock_popen, \
             patch("app.api.v1.cameras.local_stream_manager.RTSPUrlValidator.validate"):
            result = mgr.start(camera_id=VALID_UUID, rtsp_url=VALID_RTSP)

        mock_popen.assert_not_called()
        assert result["status"] == "already_running"
        assert result["pid"] == 77777


# ---------------------------------------------------------------------------
# task-061 — Low-latency FFmpeg command structure
# ---------------------------------------------------------------------------

class TestFFmpegLowLatencyCommand:
    """Verify the FFmpeg command emitted by start() has the low-latency config."""

    def _capture_cmd(self, env_overrides: dict) -> list:
        """Spawn start() with patched env and return the Popen cmd list."""
        mgr = _fresh_manager()

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stderr = iter([])

        # Mock Redis so the distributed lock is always acquired (avoids cross-test
        # lock leakage when a real Redis instance is running on the dev machine).
        mock_redis = MagicMock()
        mock_redis.set.return_value = True  # lock acquired

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("os.makedirs"), \
             patch("threading.Thread"), \
             patch("app.api.v1.cameras.local_stream_manager._get_redis_client",
                   return_value=mock_redis), \
             patch.dict("os.environ", env_overrides, clear=False):
            mgr.start(camera_id=VALID_UUID, rtsp_url=VALID_RTSP)

        return mock_popen.call_args[0][0]

    def test_default_hls_time_is_1s(self):
        cmd = self._capture_cmd({"HLS_SEGMENT_TIME": "1", "HLS_LIST_SIZE": "3", "HLS_VIDEO_CODEC": "copy"})
        idx = cmd.index("-hls_time")
        assert cmd[idx + 1] == "1", f"Expected -hls_time 1, got {cmd[idx + 1]}"

    def test_default_hls_list_size_is_3(self):
        cmd = self._capture_cmd({"HLS_SEGMENT_TIME": "1", "HLS_LIST_SIZE": "3", "HLS_VIDEO_CODEC": "copy"})
        idx = cmd.index("-hls_list_size")
        assert cmd[idx + 1] == "3", f"Expected -hls_list_size 3, got {cmd[idx + 1]}"

    def test_hls_list_size_env_override(self):
        """HLS_LIST_SIZE env var must be respected (no min-6 floor)."""
        cmd = self._capture_cmd({"HLS_SEGMENT_TIME": "1", "HLS_LIST_SIZE": "2", "HLS_VIDEO_CODEC": "copy"})
        idx = cmd.index("-hls_list_size")
        assert cmd[idx + 1] == "2"

    def test_low_latency_flags_precede_input(self):
        """nobuffer + low_delay + probesize + analyzeduration must appear before -i."""
        cmd = self._capture_cmd({"HLS_SEGMENT_TIME": "1", "HLS_LIST_SIZE": "3", "HLS_VIDEO_CODEC": "copy"})
        i_idx = cmd.index("-i")
        required = {"-fflags", "-flags", "-probesize", "-analyzeduration"}
        present = set(cmd[:i_idx])
        missing = required - present
        assert not missing, f"Low-latency flags missing before -i: {missing}"

    def test_default_codec_is_copy(self):
        """stream-copy must be the default — no libx264 re-encoding cost."""
        cmd = self._capture_cmd({"HLS_SEGMENT_TIME": "1", "HLS_LIST_SIZE": "3", "HLS_VIDEO_CODEC": "copy"})
        idx = cmd.index("-c:v")
        assert cmd[idx + 1] == "copy"

    def test_libx264_codec_adds_preset_and_tune(self):
        """HLS_VIDEO_CODEC=libx264 must include -preset ultrafast -tune zerolatency."""
        cmd = self._capture_cmd({"HLS_SEGMENT_TIME": "1", "HLS_LIST_SIZE": "3", "HLS_VIDEO_CODEC": "libx264"})
        assert "-preset" in cmd
        assert "ultrafast" in cmd
        assert "-tune" in cmd
        assert "zerolatency" in cmd

    def test_copy_codec_has_no_preset(self):
        """stream-copy must NOT include -preset (no encoder running)."""
        cmd = self._capture_cmd({"HLS_SEGMENT_TIME": "1", "HLS_LIST_SIZE": "3", "HLS_VIDEO_CODEC": "copy"})
        assert "-preset" not in cmd


# ---------------------------------------------------------------------------
# task-068 — Stall detection based on real segment advance (not client polling)
# ---------------------------------------------------------------------------

_STALL_TEST_CAMERA = "22222222-2222-2222-2222-222222222222"


class TestStallDetection:
    """
    The bug: serve_hls renewed the Redis "active" TTL on every client GET, so a
    client stuck polling a dead stream kept the watchdog's inactivity check from
    ever firing (FFmpeg alive but producing no new segments — e.g. RTSP frozen).
    `_check_stall` fixes this by tracking `#EXT-X-MEDIA-SEQUENCE` from the actual
    playlist file: liveness = segments really advancing, not "someone asked".
    """

    def _write_playlist(self, camera_id: str, sequence: int) -> None:
        hls_dir = f"/tmp/hls/{camera_id}"
        os.makedirs(hls_dir, exist_ok=True)
        with open(f"{hls_dir}/stream.m3u8", "w") as fh:
            fh.write(f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-MEDIA-SEQUENCE:{sequence}\n")

    def teardown_method(self) -> None:
        shutil.rmtree(f"/tmp/hls/{_STALL_TEST_CAMERA}", ignore_errors=True)

    def test_first_read_seeds_baseline_not_a_stall(self):
        """First observation of a sequence number is never a stall — no history yet."""
        mgr = _fresh_manager()
        self._write_playlist(_STALL_TEST_CAMERA, sequence=10)

        assert mgr._check_stall(_STALL_TEST_CAMERA) is False
        assert mgr._sequences[_STALL_TEST_CAMERA][0] == 10

    def test_sequence_advancing_is_not_a_stall(self):
        """FAILS BEFORE FIX (no _check_stall existed): sequence moving must never trip a stall."""
        mgr = _fresh_manager()
        self._write_playlist(_STALL_TEST_CAMERA, sequence=10)
        mgr._check_stall(_STALL_TEST_CAMERA)

        self._write_playlist(_STALL_TEST_CAMERA, sequence=11)
        assert mgr._check_stall(_STALL_TEST_CAMERA) is False

    def test_sequence_stuck_past_timeout_is_a_stall(self):
        """Core fix: sequence frozen for > _STALL_TIMEOUT seconds must be reported as stalled."""
        mgr = _fresh_manager()
        self._write_playlist(_STALL_TEST_CAMERA, sequence=10)

        with patch("app.api.v1.cameras.local_stream_manager.time.time", return_value=1_000.0):
            assert mgr._check_stall(_STALL_TEST_CAMERA) is False  # baseline seeded

        with patch("app.api.v1.cameras.local_stream_manager.time.time", return_value=1_000.0 + 13):
            assert mgr._check_stall(_STALL_TEST_CAMERA) is True

    def test_sequence_stuck_below_timeout_is_not_yet_a_stall(self):
        mgr = _fresh_manager()
        self._write_playlist(_STALL_TEST_CAMERA, sequence=10)

        with patch("app.api.v1.cameras.local_stream_manager.time.time", return_value=1_000.0):
            mgr._check_stall(_STALL_TEST_CAMERA)

        with patch("app.api.v1.cameras.local_stream_manager.time.time", return_value=1_000.0 + 5):
            assert mgr._check_stall(_STALL_TEST_CAMERA) is False

    def test_missing_playlist_is_not_a_stall(self):
        """Stream still initialising (no m3u8 yet) must not be reported as stalled."""
        mgr = _fresh_manager()
        assert mgr._check_stall("00000000-0000-0000-0000-000000000000") is False

    def test_watchdog_tick_stops_process_when_stalled(self):
        """
        FAILS BEFORE FIX: previously _watchdog_tick only checked the Redis "active"
        key, which a broken polling client kept renewing forever — the FFmpeg
        process was never stopped. After the fix, the watchdog stops it directly
        from the stalled segment sequence, independent of any Redis/client state.
        """
        mgr = _fresh_manager()
        self._write_playlist(_STALL_TEST_CAMERA, sequence=10)

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = 555
        mock_proc.poll.return_value = None
        mgr._processes[_STALL_TEST_CAMERA] = mock_proc
        mgr._stderr_tail[_STALL_TEST_CAMERA] = deque()

        with patch("app.api.v1.cameras.local_stream_manager.time.time", return_value=2_000.0):
            mgr._check_stall(_STALL_TEST_CAMERA)  # seed baseline

        with patch("app.api.v1.cameras.local_stream_manager.time.time", return_value=2_000.0 + 13), \
             patch("redis.from_url", side_effect=Exception("redis not needed for this test")), \
             patch.object(mgr, "stop", wraps=mgr.stop) as mock_stop:
            mgr._watchdog_tick()

        mock_stop.assert_called_once_with(_STALL_TEST_CAMERA)
        assert _STALL_TEST_CAMERA not in mgr._processes

    def test_watchdog_tick_does_not_stop_process_when_sequence_advancing(self):
        """A healthy, advancing stream must survive the watchdog tick untouched."""
        mgr = _fresh_manager()
        self._write_playlist(_STALL_TEST_CAMERA, sequence=10)

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = 556
        mock_proc.poll.return_value = None
        mgr._processes[_STALL_TEST_CAMERA] = mock_proc
        mgr._stderr_tail[_STALL_TEST_CAMERA] = deque()

        mgr._check_stall(_STALL_TEST_CAMERA)  # seed baseline (seq 10)
        self._write_playlist(_STALL_TEST_CAMERA, sequence=11)  # advanced before next tick

        with patch("redis.from_url", side_effect=Exception("redis not needed for this test")), \
             patch.object(mgr, "stop", wraps=mgr.stop) as mock_stop:
            mgr._watchdog_tick()

        mock_stop.assert_not_called()
        assert _STALL_TEST_CAMERA in mgr._processes


class TestIsStalled:
    """Public, read-only `is_stalled()` — consulted by serve_hls (task-068 GR-2 fix)."""

    def test_is_stalled_false_when_recently_advanced(self):
        mgr = _fresh_manager()
        with patch("app.api.v1.cameras.local_stream_manager.time.time", return_value=3_000.0):
            mgr._sequences[_STALL_TEST_CAMERA] = (5, 3_000.0)
            assert mgr.is_stalled(_STALL_TEST_CAMERA) is False

    def test_is_stalled_true_after_timeout_elapsed(self):
        mgr = _fresh_manager()
        mgr._sequences[_STALL_TEST_CAMERA] = (5, 3_000.0)
        with patch("app.api.v1.cameras.local_stream_manager.time.time", return_value=3_000.0 + 20):
            assert mgr.is_stalled(_STALL_TEST_CAMERA) is True

    def test_is_stalled_unknown_camera_returns_false(self):
        mgr = _fresh_manager()
        assert mgr.is_stalled("00000000-0000-0000-0000-000000000000") is False

    def test_is_stalled_does_not_reparse_playlist_file(self):
        """is_stalled() must be a pure state read — no filesystem access."""
        mgr = _fresh_manager()
        mgr._sequences[_STALL_TEST_CAMERA] = (5, 3_000.0)
        with patch("builtins.open", side_effect=AssertionError("must not open the playlist file")):
            with patch("app.api.v1.cameras.local_stream_manager.time.time", return_value=3_000.0 + 1):
                assert mgr.is_stalled(_STALL_TEST_CAMERA) is False
# task-067 — substream → main-stream runtime fallback
# ---------------------------------------------------------------------------

FALLBACK_RTSP = "rtsp://192.168.1.100:554/cam/realmonitor?channel=1&subtype=0"


class TestStartSpawnsFallbackMonitorOnlyWhenRequested:
    """start() must only arm the early-exit monitor when fallback_rtsp_url is given.

    Mocks _get_redis_client so lock acquisition is deterministic regardless of
    whether a real Redis is reachable in the dev/CI environment (mirrors the
    pattern already used by TestFFmpegLowLatencyCommand._capture_cmd).
    """

    def test_no_fallback_url_no_monitor_thread(self):
        """(a) Substream works, no fallback requested — no monitor thread spawned."""
        mgr = _fresh_manager()

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stderr = iter([])

        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("os.makedirs"), \
             patch("threading.Thread") as mock_thread, \
             patch(
                "app.api.v1.cameras.local_stream_manager._get_redis_client",
                return_value=mock_redis,
             ):
            mgr.start(camera_id=VALID_UUID, rtsp_url=VALID_RTSP)

        names = [kwargs.get("name", "") for _, kwargs in mock_thread.call_args_list]
        assert not any(n.startswith("ffmpeg-fallback-") for n in names)

    def test_fallback_url_spawns_monitor_thread(self):
        """When fallback_rtsp_url is provided, a fallback monitor thread is armed."""
        mgr = _fresh_manager()

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.stderr = iter([])

        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("os.makedirs"), \
             patch("threading.Thread") as mock_thread, \
             patch(
                "app.api.v1.cameras.local_stream_manager._get_redis_client",
                return_value=mock_redis,
             ):
            mgr.start(
                camera_id=VALID_UUID, rtsp_url=VALID_RTSP, fallback_rtsp_url=FALLBACK_RTSP,
            )

        names = [kwargs.get("name", "") for _, kwargs in mock_thread.call_args_list]
        assert any(n.startswith("ffmpeg-fallback-") for n in names)


class TestEarlyExitFallback:
    """Direct tests of _monitor_early_exit (bypasses real thread timing)."""

    def test_process_survives_window_no_fallback(self):
        """(a) Substream keeps running past the early-exit window — no fallback."""
        mgr = _fresh_manager()
        process = MagicMock(spec=subprocess.Popen)
        process.wait.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5)

        with patch.object(mgr, "start") as mock_start:
            mgr._monitor_early_exit(process, VALID_UUID, FALLBACK_RTSP)

        mock_start.assert_not_called()

    def test_clean_exit_no_fallback(self):
        """returncode 0 is not treated as a start failure — no fallback."""
        mgr = _fresh_manager()
        process = MagicMock(spec=subprocess.Popen)
        process.wait.return_value = 0
        mgr._processes[VALID_UUID] = process

        with patch.object(mgr, "start") as mock_start:
            mgr._monitor_early_exit(process, VALID_UUID, FALLBACK_RTSP)

        mock_start.assert_not_called()

    def test_fast_nonzero_exit_triggers_fallback_and_logs(self, caplog):
        """(b) Substream fails fast (non-zero exit) — retries once with fallback, logs GR-1."""
        mgr = _fresh_manager()
        process = MagicMock(spec=subprocess.Popen)
        process.wait.return_value = 1  # died fast with error
        mgr._processes[VALID_UUID] = process

        mock_redis = MagicMock()

        with patch.object(mgr, "start") as mock_start, \
             patch(
                "app.api.v1.cameras.local_stream_manager._get_redis_client",
                return_value=mock_redis,
             ), \
             caplog.at_level(logging.WARNING):
            mgr._monitor_early_exit(process, VALID_UUID, FALLBACK_RTSP)

        mock_start.assert_called_once_with(camera_id=VALID_UUID, rtsp_url=FALLBACK_RTSP)
        mock_redis.delete.assert_called_once_with(f"epi:stream:{VALID_UUID}:ffmpeg_lock")
        assert any("local_stream_fallback_to_main" in r.message for r in caplog.records)

    def test_fallback_retry_omits_fallback_url_no_loop(self):
        """(c) Both substream and fallback fail — the retry call must not request
        another fallback, so a second failure cannot recurse (no infinite loop)."""
        mgr = _fresh_manager()
        process = MagicMock(spec=subprocess.Popen)
        process.wait.return_value = 1
        mgr._processes[VALID_UUID] = process

        with patch.object(mgr, "start") as mock_start, \
             patch("app.api.v1.cameras.local_stream_manager._get_redis_client"):
            mgr._monitor_early_exit(process, VALID_UUID, FALLBACK_RTSP)

        # Retry call has no fallback_rtsp_url kwarg — start() default is None,
        # so even if this retry also fails, no further monitor is armed.
        _, kwargs = mock_start.call_args
        assert "fallback_rtsp_url" not in kwargs

    def test_replaced_process_skips_fallback(self):
        """If another start()/stop() already replaced the tracked process
        (e.g. explicit stop or manual restart raced this monitor), skip fallback."""
        mgr = _fresh_manager()
        dead_process = MagicMock(spec=subprocess.Popen)
        dead_process.wait.return_value = 1
        other_process = MagicMock(spec=subprocess.Popen)
        mgr._processes[VALID_UUID] = other_process  # someone else already reacted

        with patch.object(mgr, "start") as mock_start:
            mgr._monitor_early_exit(dead_process, VALID_UUID, FALLBACK_RTSP)

        mock_start.assert_not_called()

    def test_stopped_process_skips_fallback(self):
        """If stop() already removed the camera entirely, skip fallback."""
        mgr = _fresh_manager()
        dead_process = MagicMock(spec=subprocess.Popen)
        dead_process.wait.return_value = 1
        # camera_id absent from mgr._processes — as if stop() ran already

        with patch.object(mgr, "start") as mock_start:
            mgr._monitor_early_exit(dead_process, VALID_UUID, FALLBACK_RTSP)

        mock_start.assert_not_called()
