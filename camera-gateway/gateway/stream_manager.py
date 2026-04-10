"""
Gerencia processos FFmpeg (HLS) e threads FramePublisher por câmera.

Lifecycle:
  start_stream() → FFmpeg subprocess + FramePublisher thread + monitor thread
  stop_stream()  → termina FFmpeg, para threads, deleta chave Redis active
"""
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .frame_publisher import FramePublisher
from .redis_client import make_redis
from . import config

logger = logging.getLogger(__name__)

_HLS_BASE = "/tmp/hls"


@dataclass
class _StreamEntry:
    camera_id: str
    rtsp_url: str
    ffmpeg_proc: Optional[subprocess.Popen]
    publisher: FramePublisher
    pub_thread: threading.Thread
    monitor_thread: threading.Thread
    started_at: float = field(default_factory=time.time)


class StreamManager:
    """Thread-safe manager de streams RTSP → HLS + frame publish."""

    def __init__(self) -> None:
        self._active: dict[str, _StreamEntry] = {}
        self._lock = threading.Lock()
        self._r = make_redis()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_stream(self, camera_id: str, rtsp_url: str, cmd_config: dict) -> None:
        """Idempotente: ignora se câmera já está ativa."""
        with self._lock:
            if camera_id in self._active:
                logger.info("start_stream_already_active: camera=%s", camera_id)
                return

        hls_dir = os.path.join(_HLS_BASE, camera_id)
        os.makedirs(hls_dir, exist_ok=True)

        ffmpeg_proc = self._start_ffmpeg(camera_id, rtsp_url, hls_dir, cmd_config)

        publisher = FramePublisher(camera_id, rtsp_url)
        pub_thread = threading.Thread(
            target=publisher.run,
            daemon=True,
            name=f"pub-{camera_id[:8]}",
        )

        monitor_thread = threading.Thread(
            target=self._monitor_active_key,
            args=(camera_id,),
            daemon=True,
            name=f"mon-{camera_id[:8]}",
        )

        entry = _StreamEntry(
            camera_id=camera_id,
            rtsp_url=rtsp_url,
            ffmpeg_proc=ffmpeg_proc,
            publisher=publisher,
            pub_thread=pub_thread,
            monitor_thread=monitor_thread,
        )

        with self._lock:
            self._active[camera_id] = entry

        pub_thread.start()
        monitor_thread.start()
        logger.info("start_stream_ok: camera=%s", camera_id)

    def stop_stream(self, camera_id: str) -> None:
        with self._lock:
            entry = self._active.pop(camera_id, None)
        if entry is None:
            return

        entry.publisher.stop()

        if entry.ffmpeg_proc and entry.ffmpeg_proc.poll() is None:
            entry.ffmpeg_proc.terminate()
            try:
                entry.ffmpeg_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                entry.ffmpeg_proc.kill()

        try:
            self._r.delete(f"epi:stream:{camera_id}:active")
        except Exception:
            pass

        logger.info("stop_stream_ok: camera=%s", camera_id)

    def is_active(self, camera_id: str) -> bool:
        with self._lock:
            return camera_id in self._active

    def active_camera_ids(self) -> list[str]:
        with self._lock:
            return list(self._active.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _start_ffmpeg(
        self,
        camera_id: str,
        rtsp_url: str,
        hls_dir: str,
        cmd_config: dict,
    ) -> Optional[subprocess.Popen]:
        seg_time = cmd_config.get("hls_segment_time", config.HLS_SEGMENT_TIME)
        list_size = cmd_config.get("hls_list_size", config.HLS_LIST_SIZE)
        out = os.path.join(hls_dir, "stream.m3u8")

        cmd = ["ffmpeg", "-y"]
        if not (rtsp_url.startswith("http://") or rtsp_url.startswith("https://")):
            cmd.extend(["-rtsp_transport", "tcp"])
        cmd.extend([
            "-i", rtsp_url,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-f", "hls",
            "-hls_time", str(seg_time),
            "-hls_list_size", str(list_size),
            "-hls_flags", "delete_segments",
            out,
        ])

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("ffmpeg_started: camera=%s pid=%d", camera_id, proc.pid)
            return proc
        except Exception as exc:
            logger.error("ffmpeg_start_failed: camera=%s err=%s", camera_id, exc)
            return None

    def _monitor_active_key(self, camera_id: str) -> None:
        """Thread que renova TTL e pára o stream se a chave sumir."""
        key = f"epi:stream:{camera_id}:active"
        while self.is_active(camera_id):
            try:
                exists = self._r.exists(key)
                if not exists:
                    logger.info("monitor_key_gone: camera=%s stopping", camera_id)
                    self.stop_stream(camera_id)
                    return
                self._r.expire(key, config.HLS_SEGMENT_TIME * 1800)  # renova TTL
            except Exception as exc:
                logger.warning("monitor_key_error: camera=%s err=%s", camera_id, exc)
            time.sleep(10)
