"""Camera Manager — RTSP connection and frame capture."""
import logging
import threading
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CameraStream:
    """Manages a single RTSP camera stream."""

    def __init__(self, camera_id: str, rtsp_url: str, on_frame: Callable) -> None:
        self._id = camera_id
        self._url = rtsp_url
        self._on_frame = on_frame
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("camera_stream_start: %s", self._id)

    def stop(self) -> None:
        self._running = False
        logger.info("camera_stream_stop: %s", self._id)

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
                    self._on_frame(self._id, frame)
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

    def add_camera(self, camera_id: str, rtsp_url: str, on_frame: Callable) -> None:
        if camera_id not in self._streams:
            stream = CameraStream(camera_id, rtsp_url, on_frame)
            stream.start()
            self._streams[camera_id] = stream

    def remove_camera(self, camera_id: str) -> None:
        stream = self._streams.pop(camera_id, None)
        if stream:
            stream.stop()

    def stop_all(self) -> None:
        for stream in self._streams.values():
            stream.stop()
        self._streams.clear()
