"""Camera Manager — RTSP connection and frame capture.

WS10: cada stream honra um FPS alvo por câmera (frame skipping). O loop de
captura continua lendo TODO frame do RTSP (necessário para esvaziar o buffer
e evitar lag), mas só invoca on_frame quando o intervalo mínimo (1/fps)
passou. set_fps() é thread-safe e aplicável em runtime (comando
update_camera_config vindo da cloud via edge-sync-agent).
"""
import logging
import threading
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_FPS = 5


class CameraStream:
    """Manages a single RTSP camera stream."""

    def __init__(
        self,
        camera_id: str,
        rtsp_url: str,
        on_frame: Callable,
        fps: int = DEFAULT_FPS,
    ) -> None:
        self._id = camera_id
        self._url = rtsp_url
        self._on_frame = on_frame
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._fps_lock = threading.Lock()
        self._fps = max(1, int(fps))
        self._min_interval = 1.0 / self._fps
        self._last_emit = 0.0

    @property
    def fps(self) -> int:
        with self._fps_lock:
            return self._fps

    def set_fps(self, fps: int) -> None:
        """Atualiza o FPS alvo em runtime (thread-safe)."""
        clamped = max(1, int(fps))
        with self._fps_lock:
            self._fps = clamped
            self._min_interval = 1.0 / clamped
        logger.info("camera_stream_fps: %s -> %d fps", self._id, clamped)

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("camera_stream_start: %s (%d fps)", self._id, self.fps)

    def stop(self) -> None:
        self._running = False
        logger.info("camera_stream_stop: %s", self._id)

    def _maybe_emit(self, frame) -> bool:  # type: ignore[no-untyped-def]
        """Emite on_frame se o intervalo mínimo (1/fps) já passou.

        Retorna True quando o frame foi emitido (throttle testável sem cv2).
        """
        now = time.monotonic()
        with self._fps_lock:
            interval = self._min_interval
        # Epsilon: tolera erro de ponto flutuante no limite exato do intervalo
        if (now - self._last_emit) + 1e-6 < interval:
            return False
        self._last_emit = now
        self._on_frame(self._id, frame)
        return True

    def _capture_loop(self) -> None:
        import cv2
        while self._running:
            cap = cv2.VideoCapture(self._url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            try:
                while self._running and cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    # Lê todo frame (buffer RTSP), emite só no rate alvo (WS10)
                    self._maybe_emit(frame)
            except Exception as exc:
                logger.error("camera_capture_error: %s %s", self._id, exc)
            finally:
                cap.release()
            if self._running:
                time.sleep(2)  # reconnect delay


class CameraManager:
    """Manages multiple camera streams."""

    def __init__(self) -> None:
        self._streams: Dict[str, CameraStream] = {}

    def add_camera(
        self,
        camera_id: str,
        rtsp_url: str,
        on_frame: Callable,
        fps: int = DEFAULT_FPS,
    ) -> None:
        if camera_id not in self._streams:
            stream = CameraStream(camera_id, rtsp_url, on_frame, fps=fps)
            stream.start()
            self._streams[camera_id] = stream

    def update_camera_fps(self, camera_id: str, fps: int) -> bool:
        """Aplica novo FPS alvo a um stream em execução (runtime, sem restart)."""
        stream = self._streams.get(camera_id)
        if stream is None:
            return False
        stream.set_fps(fps)
        return True

    def remove_camera(self, camera_id: str) -> None:
        stream = self._streams.pop(camera_id, None)
        if stream:
            stream.stop()

    def stop_all(self) -> None:
        for stream in self._streams.values():
            stream.stop()
        self._streams.clear()
