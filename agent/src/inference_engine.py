"""Inference Engine — Optional local YOLOv8 inference."""
import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class InferenceEngine:
    """Runs YOLOv8 on frames locally."""

    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.5) -> None:
        self._confidence = confidence
        self._model = None
        self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        try:
            from ultralytics import YOLO
            self._model = YOLO(model_path)
            logger.info("inference_engine: model loaded from %s", model_path)
        except ImportError:
            logger.warning(
                "inference_engine: ultralytics not installed — inference disabled"
            )
        except Exception as exc:
            logger.error("inference_engine: model load failed %s", exc)

    def infer(self, frame: np.ndarray) -> List[Dict]:
        """Run inference on a frame. Returns list of detections."""
        if self._model is None:
            return []
        try:
            results = self._model(frame, verbose=False)
            detections = []
            for r in results:
                for box in r.boxes:
                    cls = r.names[int(box.cls)]
                    conf = float(box.conf)
                    if conf >= self._confidence:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        detections.append({
                            "class": cls,
                            "confidence": round(conf, 3),
                            "bbox": [x1, y1, x2 - x1, y2 - y1],
                        })
            return detections
        except Exception as exc:
            logger.error("inference_engine: infer error %s", exc)
            return []
