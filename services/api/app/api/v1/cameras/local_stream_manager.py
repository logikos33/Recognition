"""
LocalStreamManager — runs FFmpeg in the API container when camera-gateway is offline.

Without this, start_stream dispatches to the Celery/inference container, which writes
HLS segments to its own /tmp/hls/. The API container's serve_hls then reads from its
own /tmp/hls/ (empty) and returns 404.

This class keeps the FFmpeg subprocesses local so that serve_hls can find the files.

⚠️  SCOPE: DEV / SINGLE-REPLICA ONLY — see ADR-0030.
    With 2+ API replicas, replica-B's serve_hls cannot find segments written by
    replica-A (same cross-container 404 resurfaces between replicas). For production
    multi-replica deployments, use task-060 (dedicated transcode service).
"""
import atexit
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid as _uuid
from collections import deque
from typing import Deque, Dict, Optional, Tuple

from app.core.redact import redact_bytes
from app.core.exceptions import ValidationError
from app.core.validators import RTSPUrlValidator

logger = logging.getLogger(__name__)


def _get_redis_client():  # type: ignore[no-untyped-def]
    """Short-timeout Redis client for the ffmpeg_lock distributed lock and the
    epi:stream:*:active watchdog check — both epi:stream:* keys.

    Uses SEGMENTS_REDIS_URL when set (isolates this high-frequency traffic
    from the security Redis holding revoked_jti:*, see
    docs/runbooks/REDIS_SEGMENTS_SEPARATION.md); falls back to the same
    REDIS_URL/timeout as before when unset — behavior unchanged.
    """
    import redis as _redis
    from app.core.segments_redis import segments_redis_url  # noqa: PLC0415
    return _redis.from_url(
        segments_redis_url(),
        socket_timeout=2,
        decode_responses=True,
    )


# How long (seconds) a stream may be inactive before the watchdog kills it.
_INACTIVITY_TIMEOUT = int(os.environ.get("HLS_INACTIVITY_TIMEOUT", "30"))
# Watchdog polling interval (seconds).
_WATCHDOG_INTERVAL = 5
# Maximum stderr lines kept per camera (ring buffer).
_STDERR_TAIL_SIZE = 20
# task-068: how long (seconds) the HLS segment sequence may stay unchanged
# before the stream is considered stalled (camera offline / RTSP frozen but
# the FFmpeg process itself never exited). Liveness must be based on real
# segment production, not on the client still polling — see task spec.
_STALL_TIMEOUT = int(os.environ.get("HLS_STALL_TIMEOUT", "12"))
_MEDIA_SEQUENCE_RE = re.compile(r"#EXT-X-MEDIA-SEQUENCE:(\d+)")
# task-067: how long (seconds) after Popen we still treat an FFmpeg exit as a
# "failed to start" signal (vs. a later runtime failure, e.g. network drop).
# Only within this window do we retry once with fallback_rtsp_url.
_EARLY_EXIT_WINDOW = float(os.environ.get("LOCAL_STREAM_FALLBACK_WINDOW", "5"))


class LocalStreamManager:
    """Singleton that manages in-process FFmpeg subprocesses for HLS streaming.

    Guard-rails enforced here (task-059):
    1. RTSPUrlValidator.validate() called before any Popen.
    2. stderr captured non-blockingly; last _STDERR_TAIL_SIZE lines available in status().
    3. Watchdog thread stops idle streams (no viewer for _INACTIVITY_TIMEOUT seconds).
    4. stop() kills FFmpeg and removes /tmp/hls/{camera_id}/ entirely.
    5. atexit handler cleans all streams on shutdown.
    6. camera_id must be a valid UUID — prevents path traversal in /tmp/hls/.
    """

    _instance: Optional["LocalStreamManager"] = None
    _class_lock = threading.Lock()

    def __init__(self) -> None:
        # {camera_id: Popen}
        self._processes: Dict[str, subprocess.Popen] = {}  # type: ignore[type-arg]
        # {camera_id: Deque[str]} — last N stderr lines (ring buffer)
        self._stderr_tail: Dict[str, Deque[str]] = {}
        # {camera_id: (last_media_sequence, last_change_timestamp)} — task-068 stall detection.
        # Updated only when the HLS playlist's #EXT-X-MEDIA-SEQUENCE actually advances,
        # so it reflects real segment production instead of client polling activity.
        self._sequences: Dict[str, Tuple[int, float]] = {}
        self._lock = threading.Lock()

        self._watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog.start()

        atexit.register(self._shutdown_all)

    @classmethod
    def get_instance(cls) -> "LocalStreamManager":
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        camera_id: str,
        rtsp_url: str,
        fallback_rtsp_url: Optional[str] = None,
    ) -> dict:  # type: ignore[type-arg]
        """Start FFmpeg for *camera_id*. Idempotent — returns early if already running.

        Guard-rails:
        - camera_id validated as UUID (path traversal prevention).
        - rtsp_url validated by RTSPUrlValidator before Popen.
        - stderr captured by a daemon reader thread.

        task-067: if *fallback_rtsp_url* is given and FFmpeg dies within
        _EARLY_EXIT_WINDOW seconds of starting (typical of a camera without a
        configured substream), a background monitor retries once with
        fallback_rtsp_url (no further fallback is attempted on that retry —
        prevents an infinite loop). Pass None (default) to disable fallback.
        """
        # Guard-rail 3a — UUID validation (path traversal prevention)
        try:
            _uuid.UUID(camera_id)
        except ValueError:
            raise ValidationError(f"camera_id inválido: {camera_id!r}")

        # Guard-rail 3b — RTSP validation before any subprocess call
        RTSPUrlValidator.validate(rtsp_url)

        # Fast path: check in-process dict before going to Redis (same-worker dedup).
        with self._lock:
            existing = self._processes.get(camera_id)
            if existing is not None and existing.poll() is None:
                logger.info("local_stream: already_running camera=%s pid=%d", camera_id, existing.pid)
                return {"camera_id": camera_id, "status": "already_running", "pid": existing.pid}

        # Flag A — Redis distributed lock (cross-worker dedup).
        # Gunicorn spawns N worker processes; each has its own LocalStreamManager
        # singleton. Without this lock, two workers handling simultaneous requests
        # for the same .m3u8 will both call Popen → two FFmpeg processes per camera.
        try:
            r_lock = _get_redis_client()
            lock_key = f"epi:stream:{camera_id}:ffmpeg_lock"
            acquired = r_lock.set(lock_key, "1", nx=True, ex=60)
            if not acquired:
                logger.info("local_stream: lock_held by another worker camera=%s", camera_id)
                return {"camera_id": camera_id, "status": "already_starting"}
        except Exception as exc:
            logger.warning("local_stream: redis_lock_unavailable camera=%s error=%s", camera_id, exc)

        with self._lock:
            # Double-check after lock acquisition — another thread may have started in the interim.
            existing = self._processes.get(camera_id)
            if existing is not None and existing.poll() is None:
                logger.info("local_stream: already_running camera=%s pid=%d", camera_id, existing.pid)
                return {"camera_id": camera_id, "status": "already_running", "pid": existing.pid}

            hls_dir = f"/tmp/hls/{camera_id}"
            os.makedirs(hls_dir, exist_ok=True)

            # task-061: 1s segments + 3-entry playlist → ~2-3s live latency.
            # Default codec=copy (stream-copy): camera MUST output H.264 + GOP ≤ hls_time.
            # Set HLS_VIDEO_CODEC=libx264 for H.265 cameras (adds CPU cost + ~1s enc latency).
            hls_segment_time = int(os.environ.get("HLS_SEGMENT_TIME", "1"))
            hls_list_size = int(os.environ.get("HLS_LIST_SIZE", "3"))
            video_codec = os.environ.get("HLS_VIDEO_CODEC", "copy")

            # Guard-rail 3c — args as list, shell=False (implicit default)
            # Low-latency input flags MUST precede -i to affect the RTSP decoder.
            cmd = [
                "ffmpeg", "-y",
                "-fflags", "nobuffer",    # no demuxer buffering
                "-flags", "low_delay",    # low-delay decode mode
                "-probesize", "32",       # minimal stream probing (bytes)
                "-analyzeduration", "0",  # no pre-analysis delay
                "-rtsp_transport", "tcp",
                "-rtbufsize", os.environ.get("FFMPEG_RTBUFSIZE", "4M"),  # cap receive buffer
                "-i", rtsp_url,
                "-c:v", video_codec,
            ]
            if video_codec == "libx264":
                cmd.extend(["-preset", "ultrafast", "-tune", "zerolatency"])
            cmd.append("-an")  # no audio — video-only HLS (cameras rarely need audio; skip reduces bitrate)
            cmd.extend([
                "-f", "hls",
                "-hls_time", str(hls_segment_time),
                "-hls_list_size", str(hls_list_size),
                # delete_segments — old segments removed automatically (playlist stays bounded)
                # omit_endlist  — keeps playlist open (live stream, no VOD EXT-X-ENDLIST)
                "-hls_flags", "delete_segments+omit_endlist",
                f"{hls_dir}/stream.m3u8",
            ])

            tail: Deque[str] = deque(maxlen=_STDERR_TAIL_SIZE)
            self._stderr_tail[camera_id] = tail

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                self._processes[camera_id] = process

                # Guard-rail 1 — non-blocking stderr reader (daemon thread)
                reader = threading.Thread(
                    target=self._read_stderr,
                    args=(process, tail, camera_id),
                    daemon=True,
                    name=f"ffmpeg-stderr-{camera_id[:8]}",
                )
                reader.start()

                # task-067 — early-exit fallback monitor (substream → main).
                # Only spawned when a fallback URL was provided; the retry call
                # omits fallback_rtsp_url so it can't recurse.
                if fallback_rtsp_url:
                    monitor = threading.Thread(
                        target=self._monitor_early_exit,
                        args=(process, camera_id, fallback_rtsp_url),
                        daemon=True,
                        name=f"ffmpeg-fallback-{camera_id[:8]}",
                    )
                    monitor.start()

                logger.info("local_stream_started: camera=%s pid=%d", camera_id, process.pid)
                return {"camera_id": camera_id, "status": "started", "pid": process.pid}

            except FileNotFoundError:
                logger.error("local_stream: ffmpeg_not_found camera=%s", camera_id)
                return {"camera_id": camera_id, "status": "error", "error": "ffmpeg not found"}
            except Exception as exc:
                logger.error("local_stream_start_failed: camera=%s error=%s", camera_id, exc, exc_info=True)
                return {"camera_id": camera_id, "status": "error", "error": str(exc)}

    def stop(self, camera_id: str) -> dict:  # type: ignore[type-arg]
        """Terminate FFmpeg for *camera_id* and remove HLS directory."""
        # Release the distributed lock so another worker can restart the stream immediately.
        # Without this, the lock would only expire after 60s (TTL), blocking restarts.
        try:
            r_lock = _get_redis_client()
            r_lock.delete(f"epi:stream:{camera_id}:ffmpeg_lock")
        except Exception:
            pass

        with self._lock:
            process = self._processes.pop(camera_id, None)
            self._stderr_tail.pop(camera_id, None)
            self._sequences.pop(camera_id, None)

        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        # Guard-rail 2 — clean up segment files on stop
        hls_dir = f"/tmp/hls/{camera_id}"
        if os.path.isdir(hls_dir):
            try:
                shutil.rmtree(hls_dir)
                logger.info("local_stream_cleaned: camera=%s dir=%s", camera_id, hls_dir)
            except OSError as exc:
                logger.warning("local_stream_cleanup_failed: camera=%s error=%s", camera_id, exc)

        logger.info("local_stream_stopped: camera=%s", camera_id)
        return {"camera_id": camera_id, "status": "stopped"}

    def status(self, camera_id: str) -> dict:  # type: ignore[type-arg]
        """Return runtime status including stderr tail for error surfacing."""
        with self._lock:
            process = self._processes.get(camera_id)
            tail = self._stderr_tail.get(camera_id)

        if process is None:
            return {"camera_id": camera_id, "running": False, "pid": None,
                    "returncode": None, "stderr_tail": None}

        rc = process.poll()
        stderr_lines = list(tail) if tail else []
        return {
            "camera_id": camera_id,
            "running": rc is None,
            "pid": process.pid,
            "returncode": rc,
            # Guard-rail 1 — last stderr lines surfaced for diagnostics
            "stderr_tail": "\n".join(stderr_lines) if stderr_lines else None,
        }

    def is_running(self, camera_id: str) -> bool:
        with self._lock:
            proc = self._processes.get(camera_id)
        return proc is not None and proc.poll() is None

    def is_stalled(self, camera_id: str) -> bool:
        """Read-only check: has the last known segment sequence stopped advancing?

        task-068 defense in depth. This does NOT re-parse the playlist file (that's
        `_check_stall`, called by the watchdog); it only consults the state the
        watchdog already maintains, so `serve_hls` can cheaply skip renewing the
        Redis TTL once a stall is known — letting the process die instead of being
        kept alive by client polling.
        """
        with self._lock:
            entry = self._sequences.get(camera_id)
        if entry is None:
            return False
        _seq, last_change = entry
        return (time.time() - last_change) > _STALL_TIMEOUT

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_stall(self, camera_id: str) -> bool:
        """Parse the HLS playlist and detect whether the segment sequence is stuck.

        Liveness is based on the *real* `#EXT-X-MEDIA-SEQUENCE` advancing in
        /tmp/hls/{camera_id}/stream.m3u8 — not on whether a client is still
        polling serve_hls. A camera that drops off the network (RTSP hangs)
        often leaves the FFmpeg process alive but producing no new segments;
        this is exactly the case the client-driven Redis TTL cannot catch.
        """
        playlist_path = f"/tmp/hls/{camera_id}/stream.m3u8"
        try:
            with open(playlist_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            # Playlist not written yet (stream still initialising) — not a stall.
            return False

        match = _MEDIA_SEQUENCE_RE.search(content)
        if match is None:
            return False
        sequence = int(match.group(1))

        now = time.time()
        with self._lock:
            previous = self._sequences.get(camera_id)
            if previous is None or previous[0] != sequence:
                self._sequences[camera_id] = (sequence, now)
                return False
            _prev_seq, last_change = previous

        return (now - last_change) > _STALL_TIMEOUT

    @staticmethod
    def _read_stderr(
        process: "subprocess.Popen[bytes]",
        tail: "Deque[str]",
        camera_id: str,
    ) -> None:
        """Read stderr line-by-line into the ring buffer (daemon thread)."""
        try:
            assert process.stderr is not None
            for raw in process.stderr:
                # Redigido na ORIGEM: o ffmpeg ecoa a URL de entrada inteira em
                # erro de conexão, com a senha do gravador do cliente em texto
                # puro. Vazava pro log do Railway e pro `ffmpeg_error` que
                # /stream/status devolve na API. Redigir aqui garante que o
                # segredo nunca entra no ring buffer nem em lugar nenhum
                # depois — não adianta redigir só na hora de logar.
                line = redact_bytes(raw).rstrip()
                tail.append(line)
                if "error" in line.lower() or "fail" in line.lower():
                    logger.warning("ffmpeg_stderr: camera=%s | %s", camera_id, line)
        except Exception:
            pass  # process already dead or pipe closed

    def _monitor_early_exit(
        self,
        process: "subprocess.Popen[bytes]",
        camera_id: str,
        fallback_rtsp_url: str,
    ) -> None:
        """task-067 — retry once with fallback_rtsp_url if FFmpeg dies fast.

        Blocks (in its own daemon thread) on process.wait(timeout=_EARLY_EXIT_WINDOW).
        Three outcomes:
        - Timeout (process still running past the window): treat as a healthy
          start, do nothing.
        - Clean exit (returncode 0): not a start failure signal, do nothing.
        - Non-zero exit within the window: this camera's substream likely
          isn't configured on the hardware. Release the Redis dedup lock (the
          original start() holds it with a 60s TTL) and retry once against
          fallback_rtsp_url (main stream). No fallback is passed on the retry,
          so a second failure surfaces as a normal stream error — no loop.
        """
        try:
            returncode = process.wait(timeout=_EARLY_EXIT_WINDOW)
        except subprocess.TimeoutExpired:
            return  # survived past the early-exit window — healthy start

        if returncode == 0:
            return  # clean exit isn't a start-failure signal

        # Only fall back if this process is still the one tracked for camera_id —
        # an explicit stop() (process removed from dict) or a concurrent manual
        # restart (dict entry replaced) means someone already reacted; don't race it.
        with self._lock:
            current = self._processes.get(camera_id)
        if current is not process:
            return

        logger.warning(
            "local_stream_fallback_to_main: camera=%s reason=substream_start_failed returncode=%s",
            camera_id, returncode,
        )

        # The failed attempt's lock is still held (60s TTL) — release it so the
        # fallback retry (a fresh start() call) can acquire it immediately.
        try:
            r_lock = _get_redis_client()
            r_lock.delete(f"epi:stream:{camera_id}:ffmpeg_lock")
        except Exception as exc:
            logger.warning("local_stream_fallback_lock_release_failed: camera=%s error=%s", camera_id, exc)

        try:
            self.start(camera_id=camera_id, rtsp_url=fallback_rtsp_url)
        except Exception as exc:
            logger.error(
                "local_stream_fallback_start_failed: camera=%s error=%s", camera_id, exc, exc_info=True
            )

    def _watchdog_loop(self) -> None:
        """Daemon thread: stops streams with no active viewer."""
        while True:
            time.sleep(_WATCHDOG_INTERVAL)
            try:
                self._watchdog_tick()
            except Exception as exc:
                logger.error("local_stream_watchdog_error: %s", exc, exc_info=True)

    def _watchdog_tick(self) -> None:
        """Check each stream for stall/inactivity; stop + clean if detected.

        task-068: stall detection (segment sequence not advancing) runs FIRST
        and independently of the Redis "active" key, because a client stuck
        polling a dead stream would otherwise keep renewing that key forever
        (GR-2 bug — liveness tied to "client asked" instead of "stream produced").
        """
        with self._lock:
            camera_ids = list(self._processes.keys())

        for camera_id in camera_ids:
            try:
                if self._check_stall(camera_id):
                    logger.warning(
                        "local_stream_watchdog: stall detected (segment not advancing) "
                        "camera=%s — stopping",
                        camera_id,
                    )
                    self.stop(camera_id)
            except Exception as exc:
                logger.debug("local_stream_watchdog_stall_check_failed: camera=%s error=%s", camera_id, exc)

        try:
            r = _get_redis_client()
        except Exception:
            return

        with self._lock:
            camera_ids = list(self._processes.keys())

        for camera_id in camera_ids:
            try:
                active = r.exists(f"epi:stream:{camera_id}:active")
                if not active:
                    logger.info("local_stream_watchdog: inactivity detected camera=%s — stopping", camera_id)
                    self.stop(camera_id)
            except Exception as exc:
                logger.debug("local_stream_watchdog_check_failed: camera=%s error=%s", camera_id, exc)

    def _shutdown_all(self) -> None:
        """atexit handler — stop all running streams on process exit."""
        with self._lock:
            camera_ids = list(self._processes.keys())
        for camera_id in camera_ids:
            try:
                self.stop(camera_id)
            except Exception:
                pass


def _get_local_stream_manager() -> LocalStreamManager:
    """Module-level helper for use in route handlers."""
    return LocalStreamManager.get_instance()
