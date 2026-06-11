"""
Recognition — EpiZoneOperation.

Zona de vigilância EPI: alerta quando classe de não-conformidade (no_*) é detectada
dentro de um polígono configurado. Específico do módulo 'epi'.
"""
import logging

from app.constants import EpiClass
from app.domain.services.operations.base import (
    BaseOperation,
    _effective_threshold,
    _is_in_exclude_zone,
    _point_in_polygon,
    _validate_day_night_profile,
    _validate_exclude_zones,
)

logger = logging.getLogger(__name__)

_VALID_EPI_CLASSES = {e.value for e in EpiClass}

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


class EpiZoneOperation(BaseOperation):
    """Zona EPI: alerta se classe de não-conformidade for detectada dentro da zona."""

    type_id = "epi_zone"
    type_label = "Zona EPI"
    available_modules = ["epi"]
    description = "Alerta quando classe de EPI negativo é detectada dentro de uma zona definida."
    metric_options = ["violation_detected", "violation_count"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["zone_points", "watch_classes"],
        "properties": {
            "zone_points": {
                "type": "array",
                "title": "Pontos da zona",
                "description": "Polígono da zona de vigilância — mínimo 3 pontos [x,y] normalizados [0,1]",
                "items": {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0, "maximum": 1},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "minItems": 3,
            },
            "watch_classes": {
                "type": "array",
                "title": "Classes a vigiar",
                "description": "Subset de classes EPI a monitorar (ex: ['no_helmet', 'no_vest'])",
                "items": {"type": "string", "enum": sorted(_VALID_EPI_CLASSES)},
                "minItems": 1,
            },
            "confidence_threshold": {
                "type": "number",
                "title": "Confiança mínima",
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
        zone = config.get("zone_points", [])
        if len(zone) < 3:
            errors.append("zone_points precisa ter ao menos 3 pontos")
        watch = config.get("watch_classes") or []
        if not watch:
            errors.append("watch_classes é obrigatório e não pode ser vazio")
        for cls in watch:
            if cls not in _VALID_EPI_CLASSES:
                errors.append(f"classe inválida: {cls!r} não pertence ao módulo epi")
        errors.extend(_validate_exclude_zones(config.get("exclude_zones") or []))
        errors.extend(_validate_day_night_profile(config.get("day_night_profile") or {}))
        return errors

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        zone_points = self.config.get("zone_points", [])
        watch_classes = set(self.config.get("watch_classes", []))
        threshold = _effective_threshold(self.config, frame_meta)
        exclude_zones = self.config.get("exclude_zones") or []
        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        violations = []
        for det in detections:
            cls = det.get("class", "").lower()
            if cls not in watch_classes or det.get("confidence", 0) < threshold:
                continue
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h
            if _is_in_exclude_zone(cx, cy, exclude_zones):
                continue
            if _point_in_polygon(cx, cy, zone_points):
                violations.append({"class": cls, "cx": cx, "cy": cy, "confidence": det["confidence"]})

        detected = len(violations) > 0
        return {
            "result": {"violations": violations, "count": len(violations)},
            "metric_value": len(violations),
            "condition_satisfied": detected,
            "state_next": state,
        }
