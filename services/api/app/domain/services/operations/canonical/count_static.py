"""
Recognition — CountStaticOperation.

Conta objetos de uma classe dentro de uma ROI estática.
Output: número absoluto ou booleano (acima/abaixo de threshold).
"""
import logging

from app.domain.services.operations.base import (
    BaseOperation,
    _effective_threshold,
    _is_in_exclude_zone,
    _point_in_polygon,
    _validate_day_night_profile,
    _validate_exclude_zones,
)

logger = logging.getLogger(__name__)

_EXCLUDE_ZONES_SCHEMA = {
    "type": "array",
    "title": "Zonas de exclusão",
    "description": "Polígonos a ignorar — detecções cujo centro cair nessas zonas são descartadas",
    "items": {
        "type": "array",
        "items": {
            "type": "array",
            "items": {"type": "number", "minimum": 0, "maximum": 1},
            "minItems": 2,
            "maxItems": 2,
        },
        "minItems": 3,
    },
    "default": [],
}

_DAY_NIGHT_PROFILE_SCHEMA = {
    "type": "object",
    "title": "Perfil dia/noite",
    "description": 'Thresholds distintos por período — ex: {"day":{"confidence":0.5},"night":{"confidence":0.7}}',
    "properties": {
        "day": {
            "type": "object",
            "properties": {
                "confidence": {"type": "number", "minimum": 0.1, "maximum": 1.0}
            },
        },
        "night": {
            "type": "object",
            "properties": {
                "confidence": {"type": "number", "minimum": 0.1, "maximum": 1.0}
            },
        },
    },
    "default": {},
}


class CountStaticOperation(BaseOperation):
    """Conta objetos em região de interesse estática.

    Útil para monitoramento de capacidade, presença mínima/máxima de pessoas,
    contagem de paletes, veículos em pátio, etc.
    """

    type_id = "count_static"
    type_label = "Contagem estática"
    available_modules = ["*"]
    description = "Conta objetos de uma classe dentro de uma área definida."
    metric_options = ["count", "boolean_above", "boolean_below"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["target_class", "roi_points", "metric"],
        "properties": {
            "target_class": {"type": "string", "title": "Classe monitorada"},
            "roi_points": {
                "type": "array",
                "title": "Pontos do ROI",
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
                "enum": ["count", "boolean_above", "boolean_below"],
                "default": "count",
            },
            "count_threshold": {
                "type": "integer",
                "title": "Threshold de contagem",
                "description": "Referência para output condicional (acima/abaixo)",
                "minimum": 0,
                "default": 1,
            },
            "confidence_threshold": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 1.0,
                "default": 0.5,
            },
            "exclude_zones": _EXCLUDE_ZONES_SCHEMA,
            "day_night_profile": _DAY_NIGHT_PROFILE_SCHEMA,
        },
    }

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        if not config.get("target_class"):
            errors.append("target_class é obrigatório")
        roi = config.get("roi_points", [])
        if len(roi) < 3:
            errors.append("roi_points precisa ter ao menos 3 pontos")
        if config.get("metric") not in ("count", "boolean_above", "boolean_below"):
            errors.append("metric inválida")
        errors.extend(_validate_exclude_zones(config.get("exclude_zones") or []))
        errors.extend(_validate_day_night_profile(config.get("day_night_profile") or {}))
        return errors

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        target_class = self.config.get("target_class", "")
        roi_points = self.config.get("roi_points", [])
        threshold = _effective_threshold(self.config, frame_meta)
        exclude_zones = self.config.get("exclude_zones") or []
        metric = self.config.get("metric", "count")
        count_threshold = int(self.config.get("count_threshold", 1))

        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        matching = [
            d for d in detections
            if d.get("class", "").lower() == target_class.lower()
            and d.get("confidence", 0) >= threshold
        ]

        count = 0
        for det in matching:
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h
            if _is_in_exclude_zone(cx, cy, exclude_zones):
                continue
            if _point_in_polygon(cx, cy, roi_points):
                count += 1

        if metric == "count":
            metric_value = count
            satisfied = count > 0
        elif metric == "boolean_above":
            metric_value = count > count_threshold
            satisfied = bool(metric_value)
        else:
            metric_value = count < count_threshold
            satisfied = bool(metric_value)

        return {
            "result": {"count": count, "target_class": target_class},
            "metric_value": metric_value,
            "condition_satisfied": satisfied,
            "state_next": state,
        }
