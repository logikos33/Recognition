"""
Backend RF-DETR ONNX — Apache 2.0.

RF-DETR (Roboflow Detection Transformer) — github.com/roboflow/rf-detr
Licença: Apache 2.0.

Saída esperada do ONNX (formato padrão de export DETR):
  output_0 ("pred_logits") : [batch, num_queries, num_classes]   — logits pré-softmax
  output_1 ("pred_boxes")  : [batch, num_queries, 4]             — cx, cy, w, h norm. [0,1]

Alternativamente alguns exports têm saída já pós-processada:
  output_0 ("scores")      : [batch, num_queries]
  output_1 ("labels")      : [batch, num_queries]
  output_2 ("boxes")       : [batch, num_queries, 4]  — cx, cy, w, h norm. [0,1]

O código detecta o formato automaticamente pelo número de saídas.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np
from PIL import Image as _PIL_Image

from .base import Detector

logger = logging.getLogger(__name__)

# Quantos pares (query, classe) considerar. 300 = o número de queries do
# RF-DETR: mesmo teto do postprocess de referência.
_TOPK_QUERY_CLASSE = 300

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


# ── Pré-processamento ─────────────────────────────────────────────────────────

def _preprocess_rfdetr(
    img: np.ndarray,
    target_h: int = 640,
    target_w: int = 640,
) -> tuple[np.ndarray, float, float]:
    """
    Pré-processa frame BGR para RF-DETR.

    RF-DETR usa normalização ImageNet (mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
    Retorna blob [1,3,H,W] float32 e (scale_x, scale_y) para reverter coords.
    """
    orig_h, orig_w = img.shape[:2]

    pil_img = _PIL_Image.fromarray(img[..., ::-1]).resize(
        (target_w, target_h), _PIL_Image.BILINEAR
    )
    rgb = np.array(pil_img, dtype=np.float32) / 255.0
    # Normalização ImageNet
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    rgb = (rgb - mean) / std
    blob = rgb.transpose(2, 0, 1)[np.newaxis]  # [1, 3, H, W]

    scale_x = orig_w / target_w
    scale_y = orig_h / target_h
    return np.ascontiguousarray(blob, dtype=np.float32), scale_x, scale_y


# ── NMS ───────────────────────────────────────────────────────────────────────

def _nms(
    boxes_xyxy: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float,
) -> list[int]:
    """Non-maximum suppression (numpy puro). boxes_xyxy: [N,4], scores: [N]."""
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

class RfDetrOnnxDetector(Detector):
    """
    Detector RF-DETR via ONNXRuntime (Apache 2.0).

    Suporta dois formatos de saída ONNX detectados automaticamente:
    - "logits+boxes" (raw): 2 saídas [logits, boxes]
    - "post-processed": 3 saídas [scores, labels, boxes]

    Parâmetros:
      model_path   — caminho para o arquivo .onnx
      class_names  — lista de classes; None → COCO_CLASSES_91
      confidence   — limiar mínimo de confiança [0, 1]
      nms_threshold — limiar IoU para NMS (apenas no modo raw)
      input_size   — (height, width) da entrada do modelo
    """

    def __init__(
        self,
        model_path: str,
        class_names: list[str] | None = None,
        confidence: float = 0.5,
        nms_threshold: float = 0.5,
        input_size: tuple[int, int] = (640, 640),
    ) -> None:
        self._model_path = model_path
        self._class_names = list(class_names) if class_names else list(COCO_CLASSES_91)
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

            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            self._session = ort.InferenceSession(
                self._model_path, sess_options=opts, providers=providers,
            )
            self._input_name = self._session.get_inputs()[0].name
            self._adotar_lado_do_modelo(self._session.get_inputs()[0].shape)

            n_outputs = len(self._session.get_outputs())
            self._output_mode = "post" if n_outputs >= 3 else "raw"

            logger.info(
                "rfdetr_onnx_loaded: path=%s output_mode=%s providers=%s",
                self._model_path, self._output_mode,
                self._session.get_providers(),
            )
        except Exception as exc:
            logger.error("rfdetr_onnx_load_failed: path=%s err=%s", self._model_path, exc)
            self._session = None

    def _adotar_lado_do_modelo(self, shape: list) -> None:
        """Adota o lado que o ONNX declara, em vez do input_size pedido.

        RF-DETR exporta em 560×560; o default deste backend é 640×640. Alimentar
        um modelo 560 com um blob 640 faz `session.run` levantar shape mismatch,
        que `predict` engole devolvendo `[]` — e o resultado é um detector que
        não detecta NADA sem uma linha de erro por imagem. Foi assim que uma
        avaliação inteira saiu com tp=0 e fp=0 (issue #417).

        Só dimensão estática entra: eixo dinâmico (str ou None) fica com o
        pedido, porque aí o modelo aceita qualquer lado.
        """
        if len(shape) != 4:
            return
        h, w = shape[2], shape[3]
        if not (isinstance(h, int) and isinstance(w, int) and h > 0 and w > 0):
            return
        if (h, w) != (self._input_h, self._input_w):
            logger.info(
                "rfdetr_onnx_input_size_do_modelo: pedido=%dx%d modelo=%dx%d — "
                "adotando o do modelo",
                self._input_h, self._input_w, h, w,
            )
        self._input_h, self._input_w = h, w

    @property
    def is_ready(self) -> bool:
        return self._session is not None and os.path.isfile(self._model_path)

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
            # `[]` aqui NÃO é "não vi nada" — é "não consegui olhar". Quem
            # chama distingue os dois por `ultimo_erro` (ver Detector.base).
            self.ultimo_erro = f"{type(exc).__name__}: {exc}"
            logger.error("rfdetr_onnx_predict_error: %s", exc)
            return []

    def _postprocess_raw(
        self,
        outputs: list[np.ndarray],
        scale_x: float,
        scale_y: float,
    ) -> list[dict]:
        """
        Saída raw (2 tensores), identificados por FORMA — não por posição.

        O RF-DETR exporta `dets [1,Q,4]` PRIMEIRO e `labels [1,Q,C]` depois;
        este código assumia o contrário. O produto rodava softmax sobre
        COORDENADAS, tirava argmax de 4 "classes" e usava 12 logits como
        geometria — não é imprecisão, é ler o modelo de cabeça para baixo.

        Medido no `.onnx` do TREINO 2:
            outputs[0] = dets   [1, 300, 4]   <- CAIXAS
            outputs[1] = labels [1, 300, 12]  <- LOGITS

        A identificação passa a ser pela última dimensão (4 = caixa), porque
        ordem de saída é detalhe do export e já mudou uma vez. Forma não mente.
        """
        a, b = outputs[0][0], outputs[1][0]
        if a.shape[-1] == 4 and b.shape[-1] != 4:
            boxes_norm, logits = a, b
        elif b.shape[-1] == 4 and a.shape[-1] != 4:
            boxes_norm, logits = b, a
        else:
            logger.error(
                "rfdetr_onnx_saidas_ambiguas: formas %s e %s — nenhuma tem "
                "última dimensão 4, ou ambas têm. Sem palpite: zero detecções.",
                a.shape, b.shape,
            )
            return []

        # Sigmoid, não softmax: RF-DETR treina com FOCAL LOSS, onde as classes
        # são independentes. Softmax força as probabilidades a somarem 1 e
        # distorce todo o score — é a mesma escolha do harness calibrado
        # (training/eval/per_class_eval.py), que reproduz o baseline exato.
        probs = 1.0 / (1.0 + np.exp(-logits))  # [Q, C]

        # topk sobre query x classe, não argmax por query: uma query PODE
        # emitir mais de uma classe, e o argmax descartava todas menos a maior.
        # Mesmo postprocess do RF-DETR e do harness.
        plano = probs.ravel()
        n_classes = probs.shape[1]
        k = min(_TOPK_QUERY_CLASSE, plano.size)
        idx = np.argpartition(plano, -k)[-k:]
        idx = idx[np.argsort(-plano[idx])]

        query_ids, class_ids = np.divmod(idx, n_classes)
        scores = plano[idx]
        boxes_norm = boxes_norm[query_ids]

        mask = scores >= self._confidence
        if not np.any(mask):
            return []

        boxes_f = boxes_norm[mask]
        scores_f = scores[mask]
        class_ids_f = class_ids[mask]

        # cx, cy, w, h (norm) → x1, y1, x2, y2 (pixels orig)
        cx_p = boxes_f[:, 0] * self._input_w * scale_x
        cy_p = boxes_f[:, 1] * self._input_h * scale_y
        bw_p = boxes_f[:, 2] * self._input_w * scale_x
        bh_p = boxes_f[:, 3] * self._input_h * scale_y
        x1 = cx_p - bw_p / 2
        y1 = cy_p - bh_p / 2
        x2 = cx_p + bw_p / 2
        y2 = cy_p + bh_p / 2

        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)
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

        scores_f = scores_all[mask]
        class_ids_f = labels_all[mask]
        boxes_f = boxes_all[mask]

        cx_p = boxes_f[:, 0] * self._input_w * scale_x
        cy_p = boxes_f[:, 1] * self._input_h * scale_y
        bw_p = boxes_f[:, 2] * self._input_w * scale_x
        bh_p = boxes_f[:, 3] * self._input_h * scale_y
        x1 = cx_p - bw_p / 2
        y1 = cy_p - bh_p / 2
        x2 = cx_p + bw_p / 2
        y2 = cy_p + bh_p / 2

        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)
        keep = _nms(boxes_xyxy, scores_f, self._nms_threshold)

        return self._build_results(keep, boxes_xyxy, scores_f, class_ids_f)

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
