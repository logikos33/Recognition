"""
Recognition — CrowdZoneOperation (task-110, ADR-0053).

Regra de aglomeração do módulo Estacionamento: dispara quando N ou mais
objetos da classe-alvo permanecem dentro da zona por M frames consecutivos.
Sem necessidade de track id — conta presença por frame e exige persistência.
"""
import logging

from app.domain.services.operations.base import BaseOperation, _point_in_polygon

logger = logging.getLogger(__name__)


class CrowdZoneOperation(BaseOperation):
    """Aglomeração: >= min_count objetos na zona por >= min_frames consecutivos."""

    type_id = "crowd_zone"
    type_label = "Aglomeração em zona"
    available_modules = ["counting", "epi"]
    description = (
        "Dispara quando N+ objetos da classe permanecem na zona por M frames "
        "consecutivos (ex.: aglomeração de pessoas no estacionamento)."
    )
    metric_options = ["count_in_zone", "consecutive_frames"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["zone_points", "target_class", "min_count"],
        "properties": {
            "zone_points": {
                "type": "array",
                "title": "Zona (polígono)",
                "items": {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0, "maximum": 1},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "minItems": 3,
            },
            "target_class": {"type": "string", "title": "Classe alvo", "default": "person"},
            "min_count": {"type": "integer", "title": "Mínimo de objetos", "minimum": 2, "default": 3},
            "min_frames": {
                "type": "integer",
                "title": "Frames consecutivos",
                "minimum": 1,
                "default": 5,
                "description": "Persistência mínima antes de disparar (anti-flicker).",
            },
            "confidence_threshold": {
                "type": "number", "minimum": 0.1, "maximum": 1.0, "default": 0.5,
            },
        },
    }

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        if len(config.get("zone_points", [])) < 3:
            errors.append("zone_points precisa ter ao menos 3 pontos")
        if not config.get("target_class"):
            errors.append("target_class é obrigatório")
        if int(config.get("min_count", 0) or 0) < 2:
            errors.append("min_count deve ser >= 2")
        return errors

    def evaluate(self, detections: list[dict], frame_meta: dict, state: dict) -> dict:
        zone = self.config["zone_points"]
        target = self.config["target_class"].lower()
        threshold = float(self.config.get("confidence_threshold", 0.5))
        min_count = int(self.config["min_count"])
        min_frames = int(self.config.get("min_frames", 5))
        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        in_zone = 0
        for det in detections:
            if det.get("class", "").lower() != target:
                continue
            if det.get("confidence", 0) < threshold:
                continue
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h
            if _point_in_polygon(cx, cy, zone):
                in_zone += 1

        consecutive = state.get("consecutive", 0) + 1 if in_zone >= min_count else 0
        satisfied = consecutive >= min_frames
        return {
            "result": {"count_in_zone": in_zone, "consecutive_frames": consecutive},
            "metric_value": in_zone,
            "condition_satisfied": satisfied,
            "state_next": {**state, "consecutive": consecutive},
        }
