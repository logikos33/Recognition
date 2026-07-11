"""
Factory de detectores — task-055a / A1.

Selecionável via env DETECTOR_BACKEND (padrão: yolox_onnx).
Backends disponíveis: yolox_onnx | rfdetr_onnx | ultralytics (legado).

Exemplo de uso:
    detector = get_detector(
        backend=os.environ.get("DETECTOR_BACKEND", "yolox_onnx"),
        model_path="/path/to/model.onnx",
    )
    detections = detector.predict(frame)
"""
from __future__ import annotations

import logging

from .base import Detector

logger = logging.getLogger(__name__)

# ── Backends suportados ────────────────────────────────────────────────────────
BACKEND_YOLOX_ONNX = "yolox_onnx"
BACKEND_RFDETR_ONNX = "rfdetr_onnx"
BACKEND_ULTRALYTICS = "ultralytics"  # legado — mantido p/ transição (task-055c)

SUPPORTED_BACKENDS: tuple[str, ...] = (
    BACKEND_YOLOX_ONNX,
    BACKEND_RFDETR_ONNX,
    BACKEND_ULTRALYTICS,
)


def get_detector(
    backend: str,
    model_path: str,
    class_names: list[str] | None = None,
    confidence: float = 0.5,
    nms_threshold: float = 0.45,
    input_size: tuple[int, int] = (640, 640),
    **kwargs: object,
) -> Detector:
    """
    Instancia e retorna um Detector conforme o backend escolhido.

    Parâmetros:
      backend     — "yolox_onnx" | "rfdetr_onnx" | "ultralytics"
      model_path  — caminho local para o arquivo do modelo (.onnx / .pt)
      class_names — lista de classes (None → padrão do backend)
      confidence  — limiar de confiança mínimo
      nms_threshold — limiar IoU para NMS
      input_size  — (height, width) da entrada do modelo
      **kwargs    — argumentos adicionais repassados ao backend específico

    Lança:
      ValueError  — se backend não é reconhecido
    """
    b = backend.lower().strip()

    if b == BACKEND_YOLOX_ONNX:
        from .onnx_yolox import YoloxOnnxDetector  # noqa: PLC0415
        logger.info("detector_factory: backend=yolox_onnx model=%s", model_path)
        return YoloxOnnxDetector(
            model_path=model_path,
            class_names=class_names,
            confidence=confidence,
            nms_threshold=nms_threshold,
            input_size=input_size,
            raw_output=kwargs.get("raw_output", False),
        )

    if b == BACKEND_RFDETR_ONNX:
        from .onnx_rfdetr import RfDetrOnnxDetector  # noqa: PLC0415
        logger.info("detector_factory: backend=rfdetr_onnx model=%s", model_path)
        return RfDetrOnnxDetector(
            model_path=model_path,
            class_names=class_names,
            confidence=confidence,
            nms_threshold=nms_threshold,
            input_size=input_size,
        )

    if b == BACKEND_ULTRALYTICS:
        # Legado — mantido durante transição; remover em task-055c.
        # AGPL-3.0: não expor em prod após migração concluída.
        logger.warning(
            "detector_factory: backend=ultralytics (AGPL-3.0 — migração pendente task-055c)"
        )
        from .ultralytics_compat import UltralyticsDetector  # noqa: PLC0415
        return UltralyticsDetector(
            model_path=model_path,
            class_names=class_names,
            confidence=confidence,
        )

    raise ValueError(
        f"Backend '{backend}' não reconhecido. "
        f"Suportados: {', '.join(SUPPORTED_BACKENDS)}"
    )
