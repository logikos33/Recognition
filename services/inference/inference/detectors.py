"""
Inference Service — detectores ONNX (Apache 2.0).

task-055a: substitui ultralytics (AGPL-3.0) no microserviço de inferência.
Suporta YOLOX-S (raw grid) e RF-DETR-N (post-processed ou raw logits).
"""
from __future__ import annotations

import logging
import threading
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── COCO 80 classes ──────────────────────────────────────────────────────────
COCO_CLASSES = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _letterbox(img: np.ndarray, target_h: int, target_w: int,
               pad_value: int = 114) -> tuple[np.ndarray, float]:
    """Redimensiona preservando aspecto e preenche com cinza."""
    h, w = img.shape[:2]
    scale = min(target_h / h, target_w / w)
    new_h, new_w = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    out = np.full((target_h, target_w, 3), pad_value, dtype=np.uint8)
    pad_top = (target_h - new_h) // 2
    pad_left = (target_w - new_w) // 2
    out[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized
    return out, scale


def _preprocess(img: np.ndarray, h: int, w: int) -> tuple[np.ndarray, float]:
    """Letterbox + /255 + CHW + batch dim → (blob[1,3,H,W], scale)."""
    lb, scale = _letterbox(img, h, w)
    blob = lb.astype(np.float32) / 255.0
    blob = blob.transpose(2, 0, 1)[np.newaxis]  # HWC → 1CHW
    return blob, scale


def _nms(boxes_xyxy: np.ndarray, scores: np.ndarray,
         iou_thr: float = 0.45) -> list[int]:
    """Pure-numpy NMS. Retorna índices mantidos."""
    if len(boxes_xyxy) == 0:
        return []
    x1, y1, x2, y2 = boxes_xyxy[:, 0], boxes_xyxy[:, 1], boxes_xyxy[:, 2], boxes_xyxy[:, 3]
    areas = (x2 - x1).clip(0) * (y2 - y1).clip(0)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = (xx2 - xx1).clip(0) * (yy2 - yy1).clip(0)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-7)
        order = order[1:][iou <= iou_thr]
    return keep


# ── YOLOX ONNX ───────────────────────────────────────────────────────────────

def _decode_yolox_positions(raw: np.ndarray, input_h: int,
                             input_w: int) -> np.ndarray:
    """Decodifica grid cx/cy → coordenadas absolutas (para modelos raw)."""
    strides = [8, 16, 32]
    grids, expanded_strides = [], []
    for stride in strides:
        gh, gw = input_h // stride, input_w // stride
        yv, xv = np.meshgrid(np.arange(gh), np.arange(gw), indexing="ij")
        grid = np.stack((xv, yv), axis=-1).reshape(-1, 2)
        grids.append(grid)
        expanded_strides.append(np.full((grid.shape[0], 1), stride))
    grids_np = np.concatenate(grids, axis=0)
    strides_np = np.concatenate(expanded_strides, axis=0)
    decoded = raw.copy()
    decoded[..., :2] = (decoded[..., :2] + grids_np) * strides_np
    decoded[..., 2:4] = np.exp(decoded[..., 2:4]) * strides_np
    return decoded


class YoloxOnnxDetector:
    """YOLOX ONNX detector (Apache 2.0). Suporta output raw e decode_in_inference."""

    def __init__(
        self,
        model_path: str,
        class_names: tuple[str, ...] = COCO_CLASSES,
        confidence: float = 0.5,
        nms_threshold: float = 0.45,
        input_size: tuple[int, int] = (640, 640),
        raw_output: bool = False,
    ) -> None:
        self._model_path = model_path
        self._class_names = class_names
        self._confidence = confidence
        self._nms_threshold = nms_threshold
        self._input_h, self._input_w = input_size
        self._raw_output = raw_output
        self._session = None
        self._load()

    def _load(self) -> None:
        try:
            import onnxruntime as ort  # noqa: PLC0415
            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if "CUDAExecutionProvider" in ort.get_available_providers()
                else ["CPUExecutionProvider"]
            )
            self._session = ort.InferenceSession(self._model_path, providers=providers)
            self._input_name = self._session.get_inputs()[0].name
            logger.info("yolox_onnx_loaded: %s providers=%s", self._model_path, providers)
        except Exception as exc:
            logger.error("yolox_onnx_load_failed: path=%s err=%s", self._model_path, exc)

    @property
    def is_ready(self) -> bool:
        return self._session is not None

    def predict(self, frame: np.ndarray) -> list[dict]:
        if self._session is None:
            return []
        blob, scale = _preprocess(frame, self._input_h, self._input_w)
        raw = self._session.run(None, {self._input_name: blob})[0][0]  # [N,85]

        if self._raw_output:
            raw = _decode_yolox_positions(raw, self._input_h, self._input_w)

        # obj_conf × max_cls_conf
        obj = 1 / (1 + np.exp(-raw[:, 4]))
        cls_logits = raw[:, 5:]
        cls_conf = 1 / (1 + np.exp(-cls_logits))
        cls_ids = cls_conf.argmax(axis=1)
        scores = obj * cls_conf[np.arange(len(raw)), cls_ids]

        mask = scores >= self._confidence
        if not mask.any():
            return []

        boxes_xywh = raw[mask, :4]
        scores_f = scores[mask]
        cls_ids_f = cls_ids[mask]

        # xywh (cx,cy,w,h) → xyxy
        boxes_xyxy = np.zeros_like(boxes_xywh)
        boxes_xyxy[:, 0] = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2
        boxes_xyxy[:, 1] = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2
        boxes_xyxy[:, 2] = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2
        boxes_xyxy[:, 3] = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2

        keep = _nms(boxes_xyxy, scores_f, self._nms_threshold)

        results = []
        for i in keep:
            x1, y1, x2, y2 = (boxes_xyxy[i] / scale).round().astype(int)
            cls_name = (
                self._class_names[cls_ids_f[i]]
                if cls_ids_f[i] < len(self._class_names)
                else str(cls_ids_f[i])
            )
            results.append({
                "class": cls_name,
                "confidence": round(float(scores_f[i]), 3),
                "bbox": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],
                "track_id": None,
            })
        return results


# ── Factory ───────────────────────────────────────────────────────────────────

_detector_lock = threading.Lock()
_detector_cache: dict[str, Any] = {}


def get_detector(
    model_path: str,
    class_names: tuple[str, ...] | None = None,
    confidence: float = 0.5,
) -> YoloxOnnxDetector:
    """Retorna detector singleton por model_path (thread-safe)."""
    with _detector_lock:
        if model_path not in _detector_cache:
            _detector_cache[model_path] = YoloxOnnxDetector(
                model_path=model_path,
                class_names=class_names or COCO_CLASSES,
                confidence=confidence,
            )
        return _detector_cache[model_path]
