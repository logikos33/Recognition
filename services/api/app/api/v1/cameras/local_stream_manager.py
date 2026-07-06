"""
LocalStreamManager — runs FFmpeg in the API container when camera-gateway is offline.

Without this, start_stream dispatches to the Celery/inference container, which writes
HLS segments to its own /tmp/hls/. The API container's serve_hls then reads from its
own /tmp/hls/ (empty) and returns 404.

This class keeps the FFmpeg subprocesses local so that serve_hls can find the files.
"""
import logging
import os
import subprocess
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LocalStreamManager:
    """Singleton that manages in-process FFmpeg subprocesses for HLS streaming."""

    _instance: Optional["LocalStreamManager"] = None
    _class_lock = threading.Lock()

    def __init__(self) -> None:
        self._processes: Dict[str, subprocess.Popen] = {}  # type: ignore[type-arg]
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "LocalStreamManager":
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def start(self, camera_id: str, rtsp_url: str) -> dict:  # type: ignore[type-arg]
        """Start FFmpeg for *camera_id*. Idempotent — returns early if already running."""
        with self._lock:
            existing = self._processes.get(camera_id)
            if existing is not None and existing.poll() is None:
                logger.info("local_stream: already_running camera=%s pid=%d", camera_id, existing.pid)
                return {"camera_id": camera_id, "status": "already_running", "pid": existing.pid}

            hls_dir = f"/tmp/hls/{camera_id}"
            os.makedirs(hls_dir, exist_ok=True)

            hls_segment_time = int(os.environ.get("HLS_SEGMENT_TIME", "2"))
            hls_list_size = int(os.environ.get("HLS_LIST_SIZE", "3"))

            cmd = [
                "ffmpeg", "-y",
                "-rtsp_transport", "tcp",
                "-i", rtsp_url,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-f", "hls",
                "-hls_time", str(hls_segment_time),
                "-hls_list_size", str(hls_list_size),
                "-hls_flags", "delete_segments+omit_endlist",
                f"{hls_dir}/stream.m3u8",
            ]

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                self._processes[camera_id] = process
                logger.info("local_stream_started: camera=%s pid=%d", camera_id, process.pid)
                return {"camera_id": camera_id, "status": "started", "pid": process.pid}
            except FileNotFoundError:
                logger.error("local_stream: ffmpeg_not_found camera=%s", camera_id)
                return {"camera_id": camera_id, "status": "error", "error": "ffmpeg not found"}
            except Exception as exc:
                logger.error("local_stream_start_failed: camera=%s error=%s", camera_id, exc, exc_info=True)
                return {"camera_id": camera_id, "status": "error", "error": str(exc)}

    def stop(self, camera_id: str) -> dict:  # type: ignore[type-arg]
        """Terminate FFmpeg for *camera_id*."""
        with self._lock:
            process = self._processes.pop(camera_id, None)
            if process is None:
                return {"camera_id": camera_id, "status": "not_running"}
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            logger.info("local_stream_stopped: camera=%s", camera_id)
            return {"camera_id": camera_id, "status": "stopped"}

    def is_running(self, camera_id: str) -> bool:
        with self._lock:
            proc = self._processes.get(camera_id)
            return proc is not None and proc.poll() is None

    def cleanup_dead(self) -> None:
        """Remove finished processes from the tracking dict."""
        with self._lock:
            dead = [cid for cid, p in self._processes.items() if p.poll() is not None]
            for cid in dead:
                self._processes.pop(cid, None)
