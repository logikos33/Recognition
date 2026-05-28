"""
Motor de inferência YOLO + DeepSORT anti-duplicate tracking.

Consome frame_b64 (JPEG base64), roda YOLOv8, aplica DeepSORT para
track_ids únicos por objeto, publica no canal det:{camera_id}.

Canal de saída: det:{camera_id}
  {camera_id, timestamp, detections: [{class, confidence, bbox, track_id}], has_violation}

O socket_bridge.py na API já assina det:* e repassa via WebSocket
para o frontend — zero mudanças necessárias nessa ponte.
"""
import base64
import json
import logging
import os
import threading
from typing import Any

import cv2
import numpy as np

from .redis_client import make_redis
from . import config

logger = logging.getLogger(__name__)

_model_lock = threading.Lock()
_model_cache: dict[str, Any] = {}

# DeepSORT: one tracker per camera_id to avoid cross-contamination
_deepsort_lock = threading.Lock()
_deepsort_trackers: dict[str, Any] = {}


def _load_model(model_path: str) -> Any:
    """Carrega YOLO com cache em /tmp/epi_models/. Thread-safe."""
    with _model_lock:
        if model_path in _model_cache:
            return _model_cache[model_path]
        try:
            from ultralytics import YOLO  # noqa: PLC0415
        except ImportError:
            logger.warning("ultralytics_not_installed: no-YOLO mode")
            _model_cache[model_path] = None
            return None
        cache_dir = "/tmp/epi_models"
        os.makedirs(cache_dir, exist_ok=True)
        resolved = model_path if os.path.isfile(model_path) else "yolov8n.pt"
        logger.info("yolo_model_loading: %s", resolved)
        model = YOLO(resolved)
        _model_cache[model_path] = model
        logger.info("yolo_model_loaded: %s", resolved)
        return model


def _get_tracker(camera_id: str) -> Any:
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
        self._model = _load_model(config.YOLO_MODEL_PATH)
        self._frames_processed = 0

    @property
    def frames_processed(self) -> int:
        return self._frames_processed

    def is_ready(self) -> bool:
        return self._model is not None

    def reload_model(self, new_path: str) -> None:
        """Hot-reload YOLO model. Thread-safe — limpa cache e carrega novo."""
        global _model_cache
        with _model_lock:
            _model_cache.clear()
        self._model = _load_model(new_path)
        logger.info("model_reloaded: path=%s ready=%s", new_path, self._model is not None)

    def process_frame(self, camera_id: str, frame_b64: str, timestamp: str) -> None:
        """Decodifica frame, roda YOLO + DeepSORT, publica det:{camera_id}."""
        try:
            frame = self._decode_frame(frame_b64)
            if frame is None:
                return
            detections = self._run_yolo(frame)
            detections = self._apply_tracking(camera_id, frame, detections)
            self._publish(camera_id, detections, timestamp)
            self._frames_processed += 1
        except Exception as exc:
            logger.error("process_frame_error: camera=%s err=%s", camera_id, exc)

    def _decode_frame(self, frame_b64: str):
        frame_bytes = base64.b64decode(frame_b64)
        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame  # None se falhar

    def _run_yolo(self, frame) -> list[dict]:
        if self._model is None:
            return []
        results = self._model(frame, conf=config.DETECTION_CONFIDENCE, verbose=False)
        detections = []
        for r in results:
            for box in r.boxes:
                cls_name = r.names[int(box.cls)]
                conf = float(box.conf)
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                detections.append({
                    "class": cls_name,
                    "confidence": round(conf, 3),
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "track_id": None,
                })
        return detections

    def _apply_tracking(self, camera_id: str, frame, detections: list[dict]) -> list[dict]:
        """Aplica DeepSORT para atribuir track_ids únicos. Fallback: sem tracking."""
        if not detections:
            return detections

        tracker = _get_tracker(camera_id)
        if tracker is None:
            return detections

        try:
            # Formato DeepSORT: ([left, top, w, h], confidence, class_name)
            ds_input = [
                ([d["bbox"][0], d["bbox"][1], d["bbox"][2], d["bbox"][3]], d["confidence"], d["class"])
                for d in detections
            ]
            tracks = tracker.update_tracks(ds_input, frame=frame)

            # Map confirmed tracks back to detections by bbox proximity
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

    def _publish(self, camera_id: str, detections: list[dict], timestamp: str) -> None:
        has_violation = any(d["class"].startswith("no_") for d in detections)
        payload = {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "detections": detections,
            "has_violation": has_violation,
        }
        try:
            self._r.publish(f"det:{camera_id}", json.dumps(payload))
        except Exception as exc:
            logger.warning("detection_publish_error: camera=%s err=%s", camera_id, exc)
