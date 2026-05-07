"""
Recognition — PositionOperation.

Detecta se objetos de uma classe estão dentro de uma área (ROI poligonal).
Output: coordenadas, estado lógico (dentro/fora), ou ambos.
"""
import logging

from app.domain.services.operations.base import BaseOperation, _point_in_polygon

logger = logging.getLogger(__name__)


class PositionOperation(BaseOperation):
    """Monitora posição de objetos em relação a uma ROI poligonal.

    Retorna estado (dentro/fora) e/ou coordenadas do centróide.
    """

    type_id = "position"
    type_label = "Posição"
    available_modules = ["*"]
    description = "Detecta se objetos de uma classe estão dentro de uma área definida."
    metric_options = ["state", "coordinates", "both"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["target_class", "roi_points", "metric"],
        "properties": {
            "target_class": {
                "type": "string",
                "title": "Classe monitorada",
                "description": "Classe YOLO a monitorar (ex: 'person', 'helmet')",
            },
            "roi_points": {
                "type": "array",
                "title": "Pontos do ROI",
                "description": "Lista de pontos [x, y] normalizados [0,1] formando polígono",
                "items": {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0, "maximum": 1},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "minItems": 3,
            },
            "metric": {
                "type": "string",
                "title": "Métrica",
                "enum": ["state", "coordinates", "both"],
                "default": "state",
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
        """Valida configuração da operação de posição."""
        errors: list[str] = []
        if not config.get("target_class"):
            errors.append("target_class é obrigatório")
        roi = config.get("roi_points", [])
        if len(roi) < 3:
            errors.append("roi_points precisa ter ao menos 3 pontos")
        if config.get("metric") not in ("state", "coordinates", "both"):
            errors.append("metric deve ser 'state', 'coordinates' ou 'both'")
        return errors

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        """Avalia se objetos da classe alvo estão dentro do ROI.

        Args:
            detections: Detecções YOLO [{class, confidence, bbox:[x,y,w,h]}, ...]
            frame_meta: Metadados do frame {camera_id, timestamp, width, height}
            state:      Estado anterior (não usado nesta operação)
        """
        target_class = self.config.get("target_class", "")
        roi_points = self.config.get("roi_points", [])
        threshold = self.config.get("confidence_threshold", 0.5)
        metric = self.config.get("metric", "state")

        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        matching = [
            d for d in detections
            if d.get("class", "").lower() == target_class.lower()
            and d.get("confidence", 0) >= threshold
        ]

        objects_in_roi = []
        for det in matching:
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h
            if _point_in_polygon(cx, cy, roi_points):
                objects_in_roi.append({
                    "class": det["class"],
                    "cx": cx,
                    "cy": cy,
                    "confidence": det["confidence"],
                })

        inside = len(objects_in_roi) > 0
        result: dict = {"objects_in_roi": objects_in_roi, "count": len(objects_in_roi)}

        if metric == "state":
            result["metric_value"] = inside
        elif metric == "coordinates":
            result["metric_value"] = objects_in_roi
        else:
            result["metric_value"] = {"inside": inside, "objects": objects_in_roi}

        return {
            "result": result,
            "metric_value": result["metric_value"],
            "condition_satisfied": inside,
            "state_next": state,
        }


