"""
Shim de compatibilidade Ultralytics — LEGADO.

Envolve ultralytics.YOLO na interface Detector para transição gradual.
Remover quando task-055c (migração completa) for concluída.
AGPL-3.0 — NÃO usar em prod após migração.
"""
from __future__ import annotations

import logging

import numpy as np

from .base import Detector

logger = logging.getLogger(__name__)


class UltralyticsDetector(Detector):
    """Wrapper ultralytics na interface Detector (LEGADO — task-055c remove isso)."""

    def __init__(
        self,
        model_path: str,
        class_names: list[str] | None = None,
        confidence: float = 0.5,
    ) -> None:
        self._model_path = model_path
        self._confidence = confidence
        self._model = None
        self._load()

    def _load(self) -> None:
        try:
            from ultralytics import YOLO  # type: ignore[import]  # noqa: PLC0415
            self._model = YOLO(self._model_path)
            logger.warning(
                "ultralytics_compat: carregado %s — AGPL-3.0 dep (task-055c pendente)",
                self._model_path,
            )
        except ImportError:
            logger.error("ultralytics_compat: ultralytics não instalado")

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def predict(self, frame: np.ndarray) -> list[dict]:
        if self._model is None:
            return []
        results = self._model(frame, conf=self._confidence, verbose=False)
        detections: list[dict] = []
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
