"""
Motor de inferência ONNX + DeepSORT anti-duplicate tracking.

task-055a: ultralytics (AGPL-3.0) removido. Usa onnxruntime (Apache 2.0)
via detectors.YoloxOnnxDetector.

Consome frame_b64 (JPEG base64), roda YOLOX ONNX, aplica DeepSORT para
track_ids únicos por objeto, publica no canal det:{camera_id}.

Canal de saída: det:{camera_id}
  {camera_id, timestamp, detections: [{class, confidence, bbox, track_id}], has_violation}

O socket_bridge.py na API já assina det:* e repassa via WebSocket
para o frontend — zero mudanças necessárias nessa ponte.
"""
import base64
import json
import logging
import threading

import cv2
import numpy as np

from .redis_client import make_redis
from . import config
from .detectors import get_detector, YoloxOnnxDetector

logger = logging.getLogger(__name__)

# DeepSORT: one tracker per camera_id to avoid cross-contamination
_deepsort_lock = threading.Lock()
_deepsort_trackers: dict[str, object] = {}

# Classes que geram alerta de violação (configurável via env VIOLATION_CLASSES)
_VIOLATION_CLASSES: set[str] = {
    c.strip()
    for c in config.VIOLATION_CLASSES.split(",")
    if c.strip()
}


def _get_tracker(camera_id: str) -> object:
    """Retorna (ou cria) instância DeepSORT para a câmera. Thread-safe."""
    with _deepsort_lock:
        if camera_id not in _deepsort_trackers:
            try:
                from deep_sort_realtime.deepsort_tracker import DeepSort  # noqa: PLC0415
                _deepsort_trackers[camera_id] = DeepSort(max_age=30, n_init=3)
                logger.info("deepsort_tracker_created: camera=%s", camera_id)
            except ImportError:
                logger.warning("deep_sort_realtime_not_installed: tracking disabled")
                _deepsort_trackers[camera_id] = None
        return _deepsort_trackers.get(camera_id)


class InferenceEngine:
    """Processa frames e publica detecções no Redis."""

    def __init__(self) -> None:
        self._r = make_redis()
        self._detector: YoloxOnnxDetector = get_detector(
            model_path=config.YOLO_MODEL_PATH,
            confidence=config.DETECTION_CONFIDENCE,
        )
        self._frames_processed = 0

    @property
    def frames_processed(self) -> int:
        return self._frames_processed

    def is_ready(self) -> bool:
        return self._detector.is_ready

    def reload_model(self, new_path: str) -> None:
        """Hot-reload ONNX model. Thread-safe — substitui detector singleton."""
        from .detectors import _detector_cache, _detector_lock  # noqa: PLC0415
        with _detector_lock:
            _detector_cache.pop(new_path, None)
        self._detector = get_detector(
            model_path=new_path,
            confidence=config.DETECTION_CONFIDENCE,
        )
        logger.info(
            "model_reloaded: path=%s ready=%s", new_path, self._detector.is_ready
        )

    def process_frame(self, camera_id: str, frame_b64: str, timestamp: str) -> None:
        """Decodifica frame, roda YOLOX ONNX + DeepSORT, publica det:{camera_id}."""
        try:
            frame = self._decode_frame(frame_b64)
            if frame is None:
                return
            detections = self._run_detector(frame)
            detections = self._apply_tracking(camera_id, frame, detections)
            self._publish(camera_id, detections, timestamp)
            self._frames_processed += 1
        except Exception as exc:
            logger.error("process_frame_error: camera=%s err=%s", camera_id, exc)

    def _decode_frame(self, frame_b64: str) -> np.ndarray | None:
        frame_bytes = base64.b64decode(frame_b64)
        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)  # None se falhar

    def _run_detector(self, frame: np.ndarray) -> list[dict]:
        if not self._detector.is_ready:
            return []
        return self._detector.predict(frame)

    def _apply_tracking(
        self, camera_id: str, frame: np.ndarray, detections: list[dict]
    ) -> list[dict]:
        """Aplica DeepSORT para atribuir track_ids únicos. Fallback: sem tracking."""
        if not detections:
            return detections

        tracker = _get_tracker(camera_id)
        if tracker is None:
            return detections

        try:
            # Formato DeepSORT: ([left, top, w, h], confidence, class_name)
            ds_input = [
                (
                    [d["bbox"][0], d["bbox"][1], d["bbox"][2], d["bbox"][3]],
                    d["confidence"],
                    d["class"],
                )
                for d in detections
            ]
            tracks = tracker.update_tracks(ds_input, frame=frame)

            # Map confirmed tracks back to detections by class
            tracked_by_class: dict[str, list] = {}
            for track in tracks:
                if not track.is_confirmed():
                    continue
                cls = track.det_class or ""
                tracked_by_class.setdefault(cls, []).append(track)

            for det in detections:
                candidates = tracked_by_class.get(det["class"], [])
                if candidates:
                    det["track_id"] = candidates[0].track_id
                    candidates.pop(0)

        except Exception as exc:
            logger.warning("deepsort_error: camera=%s err=%s", camera_id, exc)

        return detections

    def _publish(
        self, camera_id: str, detections: list[dict], timestamp: str
    ) -> None:
        has_violation = any(d["class"] in _VIOLATION_CLASSES for d in detections)
        payload = {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "detections": detections,
            "has_violation": has_violation,
        }
        try:
            self._r.publish(f"det:{camera_id}", json.dumps(payload))
        except Exception as exc:
            logger.warning(
                "detection_publish_error: camera=%s err=%s", camera_id, exc
            )
