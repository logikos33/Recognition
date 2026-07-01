"""
Recognition — DefectTriggerOperation.

ROI de esteira: presença do gatilho (trigger_class) na ROI ativa inspeção de defeitos.
OCR e contagem detalhada ficam no edge. Específico do módulo 'quality'.

Tuning por câmera:
  exclude_zones     — lista de polígonos de exclusão; detecções com centro dentro são ignoradas.
  day_night_profile — threshold diferente por período: dia 6h-18h, noite 0h-6h e 18h-24h.
                      Requer frame_meta['hour'] (int 0-23). Sem perfil: usa confidence_threshold fixo.
"""
import logging

from app.domain.services.operations.base import BaseOperation, _point_in_polygon

logger = logging.getLogger(__name__)

# Período de dia: 6h (inclusive) a 18h (exclusive). Fora deste intervalo = noite.
_DAY_HOUR_START = 6
_DAY_HOUR_END = 18


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
            "exclude_zones": {
                "type": "array",
                "title": "Zonas de exclusão",
                "description": (
                    "Lista de polígonos de exclusão. Detecções cujo centro cair dentro de qualquer "
                    "zona são ignoradas. Cada polígono: lista de pontos [x,y] normalizados [0,1], "
                    "mínimo 3 pontos. Default [] (sem exclusão)."
                ),
                "default": [],
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
            },
            "day_night_profile": {
                "type": "object",
                "title": "Perfil dia/noite",
                "description": (
                    "Threshold de confiança diferente por período. "
                    "Dia: 6h-18h; Noite: 0h-6h e 18h-24h. "
                    "Requer frame_meta['hour'] (int 0-23). "
                    "Se ausente ou sem 'hour' no frame: usa confidence_threshold fixo."
                ),
                "default": None,
                "properties": {
                    "day": {
                        "type": "object",
                        "properties": {
                            "confidence": {"type": "number", "minimum": 0.1, "maximum": 1.0}
                        },
                        "required": ["confidence"],
                    },
                    "night": {
                        "type": "object",
                        "properties": {
                            "confidence": {"type": "number", "minimum": 0.1, "maximum": 1.0}
                        },
                        "required": ["confidence"],
                    },
                },
                "required": ["day", "night"],
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

        # Validar exclude_zones
        exclude_zones = config.get("exclude_zones") or []
        for idx, ez in enumerate(exclude_zones):
            if len(ez) < 3:
                errors.append(f"exclude_zones[{idx}] precisa ter ao menos 3 pontos")
                continue
            for pidx, pt in enumerate(ez):
                if len(pt) != 2:
                    errors.append(f"exclude_zones[{idx}][{pidx}] deve ser [x, y]")
                else:
                    x, y = pt
                    if not (0 <= x <= 1) or not (0 <= y <= 1):
                        errors.append(
                            f"exclude_zones[{idx}][{pidx}] coordenadas devem estar em [0,1]"
                        )

        # Validar day_night_profile
        profile = config.get("day_night_profile")
        if profile is not None:
            for period in ("day", "night"):
                p = profile.get(period)
                if p is None:
                    errors.append(f"day_night_profile.{period} é obrigatório")
                else:
                    c = p.get("confidence")
                    if c is None or not (0.1 <= float(c) <= 1.0):
                        errors.append(
                            f"day_night_profile.{period}.confidence deve estar em [0.1, 1.0]"
                        )

        return errors

    def _get_threshold(self, frame_meta: dict) -> float:
        """Retorna threshold de confiança considerando day_night_profile.

        Dia: 6h-18h (inclusive início, exclusive fim).
        Noite: 0h-6h e 18h-24h.
        Sem perfil configurado ou sem 'hour' em frame_meta: usa confidence_threshold fixo.
        """
        profile = self.config.get("day_night_profile")
        hour = frame_meta.get("hour")
        if profile and hour is not None:
            period = "day" if _DAY_HOUR_START <= int(hour) < _DAY_HOUR_END else "night"
            return float(profile[period]["confidence"])
        return float(self.config.get("confidence_threshold", 0.5))

    def _in_any_exclude_zone(self, cx: float, cy: float) -> bool:
        """Retorna True se ponto (cx, cy) está dentro de alguma zona de exclusão."""
        for zone in self.config.get("exclude_zones") or []:
            if _point_in_polygon(cx, cy, zone):
                return True
        return False

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        roi_points = self.config.get("roi_points", [])
        trigger_class = self.config.get("trigger_class", "").lower()
        defect_classes = {c.lower() for c in self.config.get("defect_classes", [])}
        threshold = self._get_threshold(frame_meta)
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
            if self._in_any_exclude_zone(cx, cy):
                continue
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
