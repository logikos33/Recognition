"""
Backend YOLOX ONNX — Apache 2.0.

Compatível com modelos exportados via:
    python tools/export_onnx.py --decode_in_inference
ou sem decode (mode raw=True).

Referência: github.com/Megvii-BaseDetection/YOLOX
  demo/ONNXRuntime/onnx_inference.py
"""
from __future__ import annotations

import logging
import os
from typing import Any

import cv2
import numpy as np

from .base import Detector

logger = logging.getLogger(__name__)

# ── Classes COCO (80 classes, índice 0-based) ─────────────────────────────────
COCO_CLASSES: tuple[str, ...] = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
)


# ── Pré-processamento ─────────────────────────────────────────────────────────

def _letterbox(
    img: np.ndarray,
    target_h: int,
    target_w: int,
    pad_value: int = 114,
) -> tuple[np.ndarray, float]:
    """
    Redimensiona mantendo aspecto com padding.

    Retorna (imagem padded float32 [H,W,3], scale).
    scale é o fator de escala aplicado (para reverter coords depois).
    """
    h, w = img.shape[:2]
    scale = min(target_h / h, target_w / w)
    new_h = int(round(h * scale))
    new_w = int(round(w * scale))

    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    padded = np.full((target_h, target_w, 3), pad_value, dtype=np.float32)
    padded[:new_h, :new_w] = resized
    return padded, scale


def _preprocess(img: np.ndarray, input_h: int, input_w: int) -> tuple[np.ndarray, float]:
    """BGR frame → float32 [1, 3, H, W] /255, retorna também o scale."""
    padded, scale = _letterbox(img, input_h, input_w)
    # BGR → RGB, HWC → CHW, /255
    blob = padded[:, :, ::-1].transpose(2, 0, 1)
    blob = np.ascontiguousarray(blob, dtype=np.float32) / 255.0
    return blob[np.newaxis], scale  # [1, 3, H, W]


# ── Decode de posições (para modelos sem decode embutido) ─────────────────────

def _decode_positions(
    raw: np.ndarray,
    input_h: int,
    input_w: int,
) -> np.ndarray:
    """
    Decodifica posições YOLOX: adiciona offsets de grid e aplica stride.

    Entrada: raw [1, N, 5+C] onde :2 são raw cx/cy, 2:4 são raw w/h.
    Saída: mesma shape com posições em pixels do input (pre-resize).

    Usar apenas em modelos exportados SEM decode_in_inference.
    """
    strides = [8, 16, 32]
    grids: list[np.ndarray] = []
    expanded_strides: list[np.ndarray] = []

    for stride in strides:
        hs, ws = input_h // stride, input_w // stride
        xv, yv = np.meshgrid(np.arange(ws), np.arange(hs))
        grid = np.stack([xv, yv], axis=2).reshape(1, -1, 2)
        grids.append(grid)
        expanded_strides.append(np.full((1, hs * ws, 1), stride, dtype=np.float32))

    all_grids = np.concatenate(grids, axis=1)
    all_strides = np.concatenate(expanded_strides, axis=1)

    out = raw.copy()
    out[..., :2] = (out[..., :2] + all_grids) * all_strides
    out[..., 2:4] = np.exp(np.clip(out[..., 2:4], -10, 10)) * all_strides
    return out


# ── NMS ───────────────────────────────────────────────────────────────────────

def _nms(
    boxes_xyxy: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float,
) -> list[int]:
    """
    Non-maximum suppression (numpy puro, sem dependência de cv2.dnn).

    boxes_xyxy: [N, 4] float — (x1, y1, x2, y2)
    scores:     [N] float
    """
    if len(boxes_xyxy) == 0:
        return []

    x1, y1, x2, y2 = (
        boxes_xyxy[:, 0], boxes_xyxy[:, 1],
        boxes_xyxy[:, 2], boxes_xyxy[:, 3],
    )
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = scores.argsort()[::-1]

    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        union = areas[i] + areas[order[1:]] - inter
        iou = np.where(union > 0, inter / union, 0.0)

        order = order[1:][iou <= iou_threshold]

    return keep


# ── Backend principal ─────────────────────────────────────────────────────────

class YoloxOnnxDetector(Detector):
    """
    Detector YOLOX via ONNXRuntime (Apache 2.0).

    Parâmetros:
      model_path   — caminho para o arquivo .onnx
      class_names  — lista de classes; None → COCO_CLASSES (80 classes)
      confidence   — limiar mínimo de confiança [0, 1]
      nms_threshold — limiar IoU para NMS
      input_size   — (height, width) da entrada do modelo
      raw_output   — True se o modelo NÃO inclui decode de posições no grafo
                     (exportado sem --decode_in_inference). Padrão: False.
    """

    def __init__(
        self,
        model_path: str,
        class_names: list[str] | None = None,
        confidence: float = 0.5,
        nms_threshold: float = 0.45,
        input_size: tuple[int, int] = (640, 640),
        raw_output: bool = False,
    ) -> None:
        self._model_path = model_path
        self._class_names = list(class_names) if class_names else list(COCO_CLASSES)
        self._confidence = confidence
        self._nms_threshold = nms_threshold
        self._input_h, self._input_w = input_size
        self._raw_output = raw_output
        self._session: Any = None
        self._input_name: str = ""
        self._load()

    def _load(self) -> None:
        try:
            import onnxruntime as ort  # noqa: PLC0415

            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            # Suprimir logs verbosos do ORT
            opts = ort.SessionOptions()
            opts.log_severity_level = 3  # ERROR only
            self._session = ort.InferenceSession(
                self._model_path, sess_options=opts, providers=providers,
            )
            self._input_name = self._session.get_inputs()[0].name
            logger.info(
                "yolox_onnx_loaded: path=%s input=%s providers=%s",
                self._model_path, self._input_name,
                self._session.get_providers(),
            )
        except Exception as exc:
            logger.error("yolox_onnx_load_failed: path=%s err=%s", self._model_path, exc)
            self._session = None

    @property
    def is_ready(self) -> bool:
        return self._session is not None and os.path.isfile(self._model_path)

    def predict(self, frame: np.ndarray) -> list[dict]:
        if self._session is None:
            return []

        try:
            blob, scale = _preprocess(frame, self._input_h, self._input_w)
            raw_output = self._session.run(None, {self._input_name: blob})[0]
            # raw_output: [1, N, 5+C]

            if self._raw_output:
                raw_output = _decode_positions(raw_output, self._input_h, self._input_w)

            preds = raw_output[0]  # [N, 5+C]

            # scores = obj_conf × max_class_conf
            obj_conf = preds[:, 4]          # [N]
            cls_conf = preds[:, 5:]         # [N, C]
            class_ids = np.argmax(cls_conf, axis=1)  # [N]
            max_cls = cls_conf[np.arange(len(cls_conf)), class_ids]  # [N]
            scores = obj_conf * max_cls     # [N]

            mask = scores >= self._confidence
            if not np.any(mask):
                return []

            preds_f = preds[mask]
            scores_f = scores[mask]
            class_ids_f = class_ids[mask]

            # cx, cy, w, h → x1, y1, x2, y2 (em coords do input após letterbox)
            cx, cy, bw, bh = (
                preds_f[:, 0], preds_f[:, 1],
                preds_f[:, 2], preds_f[:, 3],
            )
            x1 = (cx - bw / 2) / scale
            y1 = (cy - bh / 2) / scale
            x2 = (cx + bw / 2) / scale
            y2 = (cy + bh / 2) / scale

            boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)
            keep = _nms(boxes_xyxy, scores_f, self._nms_threshold)

            results: list[dict] = []
            for i in keep:
                cls_idx = int(class_ids_f[i])
                cls_name = (
                    self._class_names[cls_idx]
                    if cls_idx < len(self._class_names)
                    else f"cls_{cls_idx}"
                )
                bx1, by1 = max(0, int(boxes_xyxy[i, 0])), max(0, int(boxes_xyxy[i, 1]))
                bx2, by2 = int(boxes_xyxy[i, 2]), int(boxes_xyxy[i, 3])
                results.append({
                    "class": cls_name,
                    "confidence": round(float(scores_f[i]), 3),
                    "bbox": [bx1, by1, bx2 - bx1, by2 - by1],
                    "track_id": None,
                })
            return results

        except Exception as exc:
            logger.error("yolox_onnx_predict_error: %s", exc)
            return []
