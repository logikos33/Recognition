"""
Captura frames de um stream RTSP via OpenCV e publica no Redis.

Canal: frame:{camera_id}
Payload: {camera_id, frame_b64, timestamp}
"""
import base64
import json
import logging
import time
from datetime import datetime, timezone

import cv2

from .redis_client import make_redis
from . import config

logger = logging.getLogger(__name__)


class FramePublisher:
    """Thread daemon que lê frames RTSP e publica no Redis."""

    def __init__(self, camera_id: str, rtsp_url: str) -> None:
        self._camera_id = camera_id
        self._rtsp_url = rtsp_url
        self._running = False
        self._r = make_redis()

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        """Chamado em thread daemon. Reconecta com backoff exponencial."""
        self._running = True
        backoff = 2.0
        while self._running:
            cap = None
            try:
                cap = cv2.VideoCapture(self._rtsp_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    raise ConnectionError(f"Stream não abriu: {self._rtsp_url}")
                logger.info("frame_publisher_connected: camera=%s", self._camera_id)
                backoff = 2.0
                frame_count = 0
                while self._running:
                    ret, frame = cap.read()
                    if not ret:
                        time.sleep(0.05)
                        continue
                    frame_count += 1
                    if frame_count % config.FRAME_EVERY_N != 0:
                        continue
                    self._publish(frame)
            except Exception as exc:
                logger.error(
                    "frame_publisher_error: camera=%s err=%s retry_in=%.0fs",
                    self._camera_id, exc, backoff,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
            finally:
                if cap is not None:
                    cap.release()

    def _publish(self, frame) -> None:
        ok, buf = cv2.imencode(
            ".jpg", frame,
            [cv2.IMWRITE_JPEG_QUALITY, config.FRAME_JPEG_QUALITY],
        )
        if not ok:
            return
        payload = {
            "camera_id": self._camera_id,
            "frame_b64": base64.b64encode(buf.tobytes()).decode(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._r.publish(f"frame:{self._camera_id}", json.dumps(payload))
        except Exception as exc:
            logger.warning("frame_publish_redis_error: %s", exc)
