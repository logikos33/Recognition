"""
Motor de inferência YOLO.

Consome frame_b64 (JPEG base64), roda YOLOv8, publica no canal
det:{camera_id} com o schema idêntico ao inference_loop Celery task.

Canal de saída: det:{camera_id}
  {camera_id, timestamp, detections: [{class, confidence, bbox}], has_violation}

O socket_bridge.py na API-V2 já assina det:* e repassa via WebSocket
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
            # Remove modelos anteriores do cache (libera memória)
            _model_cache.clear()
        self._model = _load_model(new_path)
        logger.info("model_reloaded: path=%s ready=%s", new_path, self._model is not None)

    def process_frame(self, camera_id: str, frame_b64: str, timestamp: str) -> None:
        """Decodifica frame, roda YOLO, publica det:{camera_id}."""
        try:
            frame = self._decode_frame(frame_b64)
            if frame is None:
                return
            detections = self._run_yolo(frame)
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
                })
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
