"""
Recognition — DefectTriggerOperation.

ROI de esteira: presença do gatilho (trigger_class) na ROI ativa inspeção de defeitos.
OCR e contagem detalhada ficam no edge. Específico do módulo 'quality'.
"""
import logging

from app.domain.services.operations.base import BaseOperation, _point_in_polygon

logger = logging.getLogger(__name__)


class DefectTriggerOperation(BaseOperation):
    """Gatilho de defeito: detecta trigger na ROI e sinaliza presença de defeitos."""

    type_id = "defect_trigger"
    type_label = "Gatilho de defeito"
    available_modules = ["quality"]
    description = "Detecta gatilho na ROI da esteira e sinaliza presença de classes de defeito."
    metric_options = ["defect_detected", "defect_count"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["roi_points", "trigger_class", "defect_classes"],
        "properties": {
            "roi_points": {
                "type": "array",
                "title": "ROI da esteira",
                "description": "Polígono da região de inspeção — mínimo 3 pontos [x,y] normalizados [0,1]",
                "items": {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0, "maximum": 1},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "minItems": 3,
            },
            "trigger_class": {
                "type": "string",
                "title": "Classe gatilho",
                "description": "Classe YOLO cuja presença na ROI ativa a inspeção",
            },
            "defect_classes": {
                "type": "array",
                "title": "Classes de defeito",
                "description": "Classes YOLO que representam defeitos a inspecionar",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "confidence_threshold": {
                "type": "number",
                "title": "Confiança mínima",
                "minimum": 0.1,
                "maximum": 1.0,
                "default": 0.5,
            },
        },
    }

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        roi = config.get("roi_points", [])
        if len(roi) < 3:
            errors.append("roi_points precisa ter ao menos 3 pontos")
        if not config.get("trigger_class"):
            errors.append("trigger_class é obrigatório")
        if not config.get("defect_classes"):
            errors.append("defect_classes é obrigatório e não pode ser vazio")
        return errors

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        roi_points = self.config.get("roi_points", [])
        trigger_class = self.config.get("trigger_class", "").lower()
        defect_classes = {c.lower() for c in self.config.get("defect_classes", [])}
        threshold = self.config.get("confidence_threshold", 0.5)
        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        trigger_in_roi = False
        defects_found = []

        for det in detections:
            cls = det.get("class", "").lower()
            conf = det.get("confidence", 0)
            if conf < threshold:
                continue
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h
            in_roi = _point_in_polygon(cx, cy, roi_points)

            if cls == trigger_class and in_roi:
                trigger_in_roi = True
            if cls in defect_classes and in_roi:
                defects_found.append({"class": cls, "cx": cx, "cy": cy, "confidence": conf})

        defect_detected = trigger_in_roi and len(defects_found) > 0
        return {
            "result": {
                "trigger_in_roi": trigger_in_roi,
                "defects": defects_found,
                "defect_count": len(defects_found),
            },
            "metric_value": len(defects_found) if trigger_in_roi else 0,
            "condition_satisfied": defect_detected,
            "state_next": state,
        }
