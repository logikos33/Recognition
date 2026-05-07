"""
Recognition — OverlapDynamicOperation.

Mede intersecção, distância mínima ou tempo de overlap entre 2+ objetos em movimento.
Útil para detectar interações (pessoa+veículo, operador+máquina, etc.).
"""
import logging
import time as _time

from app.domain.services.operations.base import BaseOperation

logger = logging.getLogger(__name__)


class OverlapDynamicOperation(BaseOperation):
    """Monitora sobreposição dinâmica entre dois tipos de objetos.

    Calcula IoU (Intersection over Union) entre bounding boxes de classes distintas.
    """

    type_id = "overlap_dynamic"
    type_label = "Sobreposição dinâmica"
    available_modules = ["*"]
    description = "Detecta interação entre dois tipos de objetos em movimento."
    metric_options = ["iou_percent", "min_distance", "overlap_time_seconds"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["class_a", "class_b", "metric"],
        "properties": {
            "class_a": {"type": "string", "title": "Classe A"},
            "class_b": {"type": "string", "title": "Classe B"},
            "metric": {
                "type": "string",
                "enum": ["iou_percent", "min_distance", "overlap_time_seconds"],
                "default": "iou_percent",
            },
            "iou_threshold": {
                "type": "number",
                "title": "Threshold IoU (%)",
                "minimum": 0,
                "maximum": 100,
                "default": 10.0,
            },
            "confidence_threshold": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 1.0,
                "default": 0.5,
            },
        },
    }

    def validate_config(self, config: dict) -> list[str]:
        """Valida configuração da operação de sobreposição dinâmica."""
        errors: list[str] = []
        if not config.get("class_a"):
            errors.append("class_a é obrigatório")
        if not config.get("class_b"):
            errors.append("class_b é obrigatório")
        if config.get("class_a") == config.get("class_b"):
            errors.append("class_a e class_b devem ser diferentes")
        if config.get("metric") not in ("iou_percent", "min_distance", "overlap_time_seconds"):
            errors.append("metric inválida")
        return errors

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        """Calcula IoU ou distância mínima entre objetos das classes A e B."""
        class_a = self.config.get("class_a", "")
        class_b = self.config.get("class_b", "")
        threshold = self.config.get("confidence_threshold", 0.5)
        metric = self.config.get("metric", "iou_percent")
        iou_threshold = self.config.get("iou_threshold", 10.0)

        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)
        now = float(frame_meta.get("timestamp_epoch", _time.time()))

        objs_a = [
            d for d in detections
            if d.get("class", "").lower() == class_a.lower()
            and d.get("confidence", 0) >= threshold
        ]
        objs_b = [
            d for d in detections
            if d.get("class", "").lower() == class_b.lower()
            and d.get("confidence", 0) >= threshold
        ]

        overlap_time: float = state.get("overlap_time", 0.0)
        overlap_start: float | None = state.get("overlap_start")
        best_iou = 0.0
        min_dist = float("inf")
        has_overlap = False

        for a in objs_a:
            for b in objs_b:
                iou = _compute_iou(a["bbox"], b["bbox"], frame_w, frame_h)
                best_iou = max(best_iou, iou)
                dist = _compute_distance(a["bbox"], b["bbox"], frame_w, frame_h)
                min_dist = min(min_dist, dist)
                if iou * 100 >= iou_threshold:
                    has_overlap = True

        if has_overlap and overlap_start is None:
            overlap_start = now
        elif not has_overlap and overlap_start is not None:
            overlap_time += now - overlap_start
            overlap_start = None

        if metric == "iou_percent":
            metric_value = round(best_iou * 100, 2)
        elif metric == "min_distance":
            metric_value = round(min_dist, 4) if min_dist < float("inf") else None
        else:
            active = (now - overlap_start) if overlap_start is not None else 0
            metric_value = round(overlap_time + active, 2)

        return {
            "result": {
                "iou": best_iou,
                "min_distance": min_dist if min_dist < float("inf") else None,
            },
            "metric_value": metric_value,
            "condition_satisfied": has_overlap,
            "state_next": {"overlap_time": overlap_time, "overlap_start": overlap_start},
        }


def _compute_iou(bbox_a: list, bbox_b: list, fw: int, fh: int) -> float:
    """Calcula IoU normalizado entre dois bounding boxes [x, y, w, h]."""
    ax1, ay1 = bbox_a[0] / fw, bbox_a[1] / fh
    ax2, ay2 = (bbox_a[0] + bbox_a[2]) / fw, (bbox_a[1] + bbox_a[3]) / fh
    bx1, by1 = bbox_b[0] / fw, bbox_b[1] / fh
    bx2, by2 = (bbox_b[0] + bbox_b[2]) / fw, (bbox_b[1] + bbox_b[3]) / fh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _compute_distance(bbox_a: list, bbox_b: list, fw: int, fh: int) -> float:
    """Distância Euclidiana entre centróides normalizados."""
    cx_a = (bbox_a[0] + bbox_a[2] / 2) / fw
    cy_a = (bbox_a[1] + bbox_a[3] / 2) / fh
    cx_b = (bbox_b[0] + bbox_b[2] / 2) / fw
    cy_b = (bbox_b[1] + bbox_b[3] / 2) / fh
    return ((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2) ** 0.5
