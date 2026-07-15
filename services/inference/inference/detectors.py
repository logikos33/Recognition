"""
Inference Service — detectores ONNX (Apache 2.0).

task-055a: substitui ultralytics (AGPL-3.0) no microserviço de inferência.
task-082: implementa RfDetrOnnxDetector (decode DETR portado de
  services/api/app/domain/detectors/onnx_rfdetr.py — referência canônica)
  e seleção de backend por arquitetura do modelo em get_detector().

Backends: yolox_onnx | rfdetr_onnx — 100% ONNX Apache 2.0.
"ultralytics" (AGPL-3.0) resulta em ValueError dedicado (ADR-0043/task-080).
"""
from __future__ import annotations

import json
import logging
import os
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

# ── Classes COCO (RF-DETR pré-treinado usa COCO 91 classes, índice 1-based) ──
# Para modelos COCO, a classe 0 é "N/A" (background DETR-style).
COCO_CLASSES_91: tuple[str, ...] = (
    "N/A", "person", "bicycle", "car", "motorcycle", "airplane", "bus",
    "train", "truck", "boat", "traffic light", "fire hydrant", "N/A",
    "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse",
    "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "N/A", "backpack",
    "umbrella", "N/A", "N/A", "handbag", "tie", "suitcase", "frisbee", "skis",
    "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "N/A", "wine glass",
    "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich",
    "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "N/A", "dining table", "N/A",
    "N/A", "toilet", "N/A", "tv", "laptop", "mouse", "remote", "keyboard",
    "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "N/A", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
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


# ── RF-DETR ONNX ─────────────────────────────────────────────────────────────
# Decode/post-proc portado de services/api/app/domain/detectors/onnx_rfdetr.py
# (referência canônica — task-082). Única diferença deliberada: resize bilinear
# via cv2 (já é dependência deste serviço) em vez de PIL — a matemática de
# decode (normalização ImageNet, softmax, cxcywh→xyxy, NMS) é idêntica.

def _preprocess_rfdetr(
    img: np.ndarray,
    target_h: int = 640,
    target_w: int = 640,
) -> tuple[np.ndarray, float, float]:
    """
    Pré-processa frame BGR para RF-DETR.

    RF-DETR usa normalização ImageNet (mean=[0.485,0.456,0.406],
    std=[0.229,0.224,0.225]) e resize direto (sem letterbox).
    Retorna blob [1,3,H,W] float32 e (scale_x, scale_y) para reverter coords.
    """
    orig_h, orig_w = img.shape[:2]

    rgb = cv2.resize(
        img[..., ::-1], (target_w, target_h), interpolation=cv2.INTER_LINEAR
    ).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    rgb = (rgb - mean) / std
    blob = rgb.transpose(2, 0, 1)[np.newaxis]  # [1, 3, H, W]

    scale_x = orig_w / target_w
    scale_y = orig_h / target_h
    return np.ascontiguousarray(blob, dtype=np.float32), scale_x, scale_y


class RfDetrOnnxDetector:
    """
    Detector RF-DETR via ONNXRuntime (Apache 2.0).

    Suporta dois formatos de saída ONNX detectados automaticamente:
    - "raw" (2 saídas): pred_logits [1,Q,C] + pred_boxes [1,Q,4] cxcywh norm.
    - "post" (3+ saídas): scores [1,Q] + labels [1,Q] + boxes [1,Q,4]
    """

    def __init__(
        self,
        model_path: str,
        class_names: tuple[str, ...] = COCO_CLASSES_91,
        confidence: float = 0.5,
        nms_threshold: float = 0.5,
        input_size: tuple[int, int] = (640, 640),
    ) -> None:
        self._model_path = model_path
        self._class_names = class_names
        self._confidence = confidence
        self._nms_threshold = nms_threshold
        self._input_h, self._input_w = input_size
        self._session: Any = None
        self._input_name: str = ""
        self._output_mode: str = "unknown"  # "raw" | "post"
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

            n_outputs = len(self._session.get_outputs())
            self._output_mode = "post" if n_outputs >= 3 else "raw"

            logger.info(
                "rfdetr_onnx_loaded: path=%s output_mode=%s providers=%s",
                self._model_path, self._output_mode, providers,
            )
        except Exception as exc:
            logger.error("rfdetr_onnx_load_failed: path=%s err=%s", self._model_path, exc)
            self._session = None

    @property
    def is_ready(self) -> bool:
        return self._session is not None

    def predict(self, frame: np.ndarray) -> list[dict]:
        if self._session is None:
            return []

        try:
            blob, scale_x, scale_y = _preprocess_rfdetr(
                frame, self._input_h, self._input_w,
            )
            outputs = self._session.run(None, {self._input_name: blob})

            if self._output_mode == "post":
                return self._postprocess_post(outputs, scale_x, scale_y)
            return self._postprocess_raw(outputs, scale_x, scale_y)

        except Exception as exc:
            logger.error("rfdetr_onnx_predict_error: %s", exc)
            return []

    def _postprocess_raw(
        self,
        outputs: list[np.ndarray],
        scale_x: float,
        scale_y: float,
    ) -> list[dict]:
        """
        Saída raw (2 tensores):
          outputs[0] = logits  [1, Q, num_classes]
          outputs[1] = boxes   [1, Q, 4]  cx, cy, w, h — normalizados [0,1]
        """
        logits = outputs[0][0]  # [Q, C]
        boxes_norm = outputs[1][0]  # [Q, 4]

        # Softmax e classe com maior prob
        exp_l = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp_l / exp_l.sum(axis=1, keepdims=True)  # [Q, C]

        class_ids = np.argmax(probs, axis=1)
        scores = probs[np.arange(len(probs)), class_ids]

        mask = scores >= self._confidence
        if not np.any(mask):
            return []

        boxes_xyxy = self._boxes_to_xyxy(boxes_norm[mask], scale_x, scale_y)
        scores_f = scores[mask]
        class_ids_f = class_ids[mask]

        keep = _nms(boxes_xyxy, scores_f, self._nms_threshold)
        return self._build_results(keep, boxes_xyxy, scores_f, class_ids_f)

    def _postprocess_post(
        self,
        outputs: list[np.ndarray],
        scale_x: float,
        scale_y: float,
    ) -> list[dict]:
        """
        Saída pós-processada (3+ tensores):
          outputs[0] = scores  [1, Q]
          outputs[1] = labels  [1, Q]
          outputs[2] = boxes   [1, Q, 4]  cx, cy, w, h norm.
        """
        scores_all = outputs[0][0]   # [Q]
        labels_all = outputs[1][0].astype(int)  # [Q]
        boxes_all = outputs[2][0]    # [Q, 4]

        mask = scores_all >= self._confidence
        if not np.any(mask):
            return []

        boxes_xyxy = self._boxes_to_xyxy(boxes_all[mask], scale_x, scale_y)
        scores_f = scores_all[mask]
        class_ids_f = labels_all[mask]

        keep = _nms(boxes_xyxy, scores_f, self._nms_threshold)
        return self._build_results(keep, boxes_xyxy, scores_f, class_ids_f)

    def _boxes_to_xyxy(
        self, boxes_norm: np.ndarray, scale_x: float, scale_y: float
    ) -> np.ndarray:
        """cx, cy, w, h (norm [0,1]) → x1, y1, x2, y2 (pixels da imagem orig)."""
        cx_p = boxes_norm[:, 0] * self._input_w * scale_x
        cy_p = boxes_norm[:, 1] * self._input_h * scale_y
        bw_p = boxes_norm[:, 2] * self._input_w * scale_x
        bh_p = boxes_norm[:, 3] * self._input_h * scale_y
        x1 = cx_p - bw_p / 2
        y1 = cy_p - bh_p / 2
        x2 = cx_p + bw_p / 2
        y2 = cy_p + bh_p / 2
        return np.stack([x1, y1, x2, y2], axis=1)

    def _build_results(
        self,
        keep: list[int],
        boxes_xyxy: np.ndarray,
        scores: np.ndarray,
        class_ids: np.ndarray,
    ) -> list[dict]:
        results: list[dict] = []
        for i in keep:
            cls_idx = int(class_ids[i])
            cls_name = (
                self._class_names[cls_idx]
                if cls_idx < len(self._class_names)
                else f"cls_{cls_idx}"
            )
            if cls_name == "N/A":
                continue  # Pular classe background DETR

            x1, y1, x2, y2 = (
                max(0, int(boxes_xyxy[i, 0])),
                max(0, int(boxes_xyxy[i, 1])),
                int(boxes_xyxy[i, 2]),
                int(boxes_xyxy[i, 3]),
            )
            results.append({
                "class": cls_name,
                "confidence": round(float(scores[i]), 3),
                "bbox": [x1, y1, x2 - x1, y2 - y1],
                "track_id": None,
            })
        return results


# ── Factory ───────────────────────────────────────────────────────────────────

BACKEND_YOLOX_ONNX = "yolox_onnx"
BACKEND_RFDETR_ONNX = "rfdetr_onnx"

SUPPORTED_BACKENDS: tuple[str, ...] = (
    BACKEND_YOLOX_ONNX,
    BACKEND_RFDETR_ONNX,
)

# Mapa trained_models.framework → backend do detector (mesma semântica da
# factory do monolito: services/api/app/domain/detectors/factory.py).
# "ultralytics" NÃO tem mapa — modelo legado falha alto (ADR-0043/task-080).
FRAMEWORK_TO_BACKEND: dict[str, str] = {
    "rfdetr": BACKEND_RFDETR_ONNX,
    "yolox": BACKEND_YOLOX_ONNX,
}

_detector_lock = threading.Lock()
_detector_cache: dict[str, Any] = {}


def evict_detector(model_path: str, backend: str = BACKEND_YOLOX_ONNX) -> None:
    """Remove detector do cache (hot-reload força nova instância)."""
    b = normalize_backend(backend)
    with _detector_lock:
        _detector_cache.pop(f"{b}:{model_path}", None)


def normalize_backend(backend: str) -> str:
    """
    Normaliza backend/framework para um backend suportado.

    Aceita aliases de trained_models.framework ("yolox", "rfdetr").
    Lança ValueError para "ultralytics" (removido — AGPL-3.0) e para
    qualquer valor não reconhecido. Sem fallback silencioso (ADR-0017).
    """
    b = backend.lower().strip()
    b = FRAMEWORK_TO_BACKEND.get(b, b)

    if b == "ultralytics":
        # Mensagem dedicada para o caso legado — consistente com a factory
        # do monolito (task-080), sem reintroduzir o caminho AGPL.
        raise ValueError(
            "Backend 'ultralytics' foi removido (AGPL-3.0 — ADR-0043/task-080). "
            "Re-treine ou re-exporte o modelo para ONNX (yolox/rfdetr)."
        )

    if b not in SUPPORTED_BACKENDS:
        raise ValueError(
            f"Backend '{backend}' não reconhecido. "
            f"Suportados: {', '.join(SUPPORTED_BACKENDS)}"
        )
    return b


def resolve_backend_for_model(
    model_path: str,
    explicit: str | None = None,
    default: str = BACKEND_YOLOX_ONNX,
) -> str:
    """
    Resolve a arquitetura do modelo (task-082 — registry carrega arquitetura
    junto do peso). Ordem de precedência:

    1. `explicit` — framework/backend vindo do payload model:reload
       (trained_models.framework propagado pelo publisher);
    2. sidecar JSON ao lado do peso (`<modelo>.json`, campo "framework"
       ou "backend") — para modelos pré-provisionados em disco;
    3. `default` — env DETECTOR_BACKEND do serviço.

    Valores inválidos (inclusive "ultralytics") falham alto via
    normalize_backend — nunca caem silenciosamente no default.
    """
    if explicit:
        return normalize_backend(explicit)

    sidecar = os.path.splitext(model_path)[0] + ".json"
    if os.path.isfile(sidecar):
        try:
            with open(sidecar, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Sidecar de metadata inválido: {sidecar} ({exc})"
            ) from exc
        declared = meta.get("framework") or meta.get("backend")
        if declared:
            return normalize_backend(str(declared))
        logger.warning(
            "model_sidecar_sem_framework: %s — usando default %s", sidecar, default
        )

    return normalize_backend(default)


def get_detector(
    model_path: str,
    class_names: tuple[str, ...] | None = None,
    confidence: float = 0.5,
    backend: str = BACKEND_YOLOX_ONNX,
) -> YoloxOnnxDetector | RfDetrOnnxDetector:
    """
    Retorna detector singleton por (backend, model_path) — thread-safe.

    backend: "yolox_onnx" | "rfdetr_onnx" (aliases "yolox"/"rfdetr" aceitos).
    Lança ValueError para backend não reconhecido, incluindo "ultralytics"
    (removido — ADR-0043/task-080).
    """
    b = normalize_backend(backend)
    cache_key = f"{b}:{model_path}"
    with _detector_lock:
        if cache_key not in _detector_cache:
            if b == BACKEND_RFDETR_ONNX:
                logger.info("detector_factory: backend=rfdetr_onnx model=%s", model_path)
                _detector_cache[cache_key] = RfDetrOnnxDetector(
                    model_path=model_path,
                    class_names=class_names or COCO_CLASSES_91,
                    confidence=confidence,
                )
            else:
                logger.info("detector_factory: backend=yolox_onnx model=%s", model_path)
                _detector_cache[cache_key] = YoloxOnnxDetector(
                    model_path=model_path,
                    class_names=class_names or COCO_CLASSES,
                    confidence=confidence,
                )
        return _detector_cache[cache_key]
