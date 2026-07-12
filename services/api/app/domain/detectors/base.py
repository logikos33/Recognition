"""
Detector — interface abstrata.

Todos os backends (YOLOX ONNX, RF-DETR ONNX, …) implementam esta classe.
O contrato de saída é idêntico ao que `inference_loop` publicava com ultralytics:
  [{"class": str, "confidence": float, "bbox": [x, y, w, h], "track_id": None}]
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class Detector(ABC):
    """Interface de inferência para detecção de objetos."""

    @abstractmethod
    def predict(self, frame: "np.ndarray") -> list[dict]:
        """
        Roda inferência num frame BGR (HxWxC uint8).

        Retorna lista de detecções:
          [{"class": str, "confidence": float, "bbox": [x, y, w, h], "track_id": None}]

        "bbox" está em pixels do frame original (antes de qualquer resize).
        "track_id" sempre None aqui; DeepSORT atribui o id depois.
        """

    @property
    def is_ready(self) -> bool:
        """True quando o modelo está carregado e pronto para inferência."""
        return True
