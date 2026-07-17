"""
Recognition — DwellZoneOperation (task-110, ADR-0053).

Permanência atípica em zona (módulo Estacionamento): dispara quando um objeto
da classe-alvo permanece na zona por mais de max_dwell_seconds.

⚠️ v1 FASEADO: esta regra sinaliza "permanência atípica em zona" — a
plataforma NÃO alega detecção de furto/intenção. Terminologia neutra por
decisão de produto (ADR-0053).

Identidade do objeto: usa det["track_id"] quando presente (edge NvDCF já
fornece); fallback melhor-esforço por posição quantizada (sem id estável,
oclusões podem resetar o cronômetro — limitação documentada).
"""
import logging

from app.domain.services.operations.base import BaseOperation, _point_in_polygon

logger = logging.getLogger(__name__)


class DwellZoneOperation(BaseOperation):
    """Permanência: objeto na zona além de max_dwell_seconds → alerta neutro."""

    type_id = "dwell_zone"
    type_label = "Permanência em zona"
    available_modules = ["counting", "epi"]
    description = (
        "Sinaliza permanência atípica: objeto da classe fica na zona por mais "
        "de N segundos (terminologia neutra de zona/permanência — v1 faseado ADR-0053)."
    )
    metric_options = ["max_dwell_seconds", "objects_over_limit"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["zone_points", "target_class", "max_dwell_seconds"],
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
            "max_dwell_seconds": {
                "type": "number", "title": "Permanência máxima (s)", "minimum": 1, "default": 120,
            },
            "confidence_threshold": {
                "type": "number", "minimum": 0.1, "maximum": 1.0, "default": 0.5,
            },
            "grace_seconds": {
                "type": "number",
                "title": "Tolerância de ausência (s)",
                "minimum": 0,
                "default": 3,
                "description": "Oclusão curta não reseta o cronômetro.",
            },
        },
    }

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        if len(config.get("zone_points", [])) < 3:
            errors.append("zone_points precisa ter ao menos 3 pontos")
        if not config.get("target_class"):
            errors.append("target_class é obrigatório")
        if float(config.get("max_dwell_seconds", 0) or 0) < 1:
            errors.append("max_dwell_seconds deve ser >= 1")
        return errors

    def _obj_key(self, det: dict, cx: float, cy: float) -> str:
        track_id = det.get("track_id")
        if track_id is not None:
            return f"t{track_id}"
        # fallback: posição quantizada (grade 20x20) — melhor esforço sem id
        return f"p{int(cx * 20)}_{int(cy * 20)}"

    def evaluate(self, detections: list[dict], frame_meta: dict, state: dict) -> dict:
        zone = self.config["zone_points"]
        target = self.config["target_class"].lower()
        threshold = float(self.config.get("confidence_threshold", 0.5))
        max_dwell = float(self.config["max_dwell_seconds"])
        grace = float(self.config.get("grace_seconds", 3))
        now = float(frame_meta.get("timestamp", 0.0))
        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        dwell: dict = dict(state.get("dwell", {}))
        seen_now: set[str] = set()
        for det in detections:
            if det.get("class", "").lower() != target:
                continue
            if det.get("confidence", 0) < threshold:
                continue
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h
            if not _point_in_polygon(cx, cy, zone):
                continue
            key = self._obj_key(det, cx, cy)
            seen_now.add(key)
            entry = dwell.get(key, {"entered_at": now})
            entry["last_seen"] = now
            dwell[key] = entry

        # expira quem sumiu além da tolerância (grace cobre oclusão curta)
        dwell = {
            k: v for k, v in dwell.items()
            if k in seen_now or (now - v.get("last_seen", now)) <= grace
        }

        over_limit = [
            {"key": k, "dwell_seconds": round(now - v["entered_at"], 1)}
            for k, v in dwell.items()
            if (now - v["entered_at"]) > max_dwell
        ]
        max_seconds = max(
            [now - v["entered_at"] for v in dwell.values()], default=0.0
        )
        return {
            "result": {
                "objects_in_zone": len(dwell),
                "objects_over_limit": over_limit,
                "max_dwell_seconds": round(max_seconds, 1),
            },
            "metric_value": round(max_seconds, 1),
            "condition_satisfied": len(over_limit) > 0,
            "state_next": {**state, "dwell": dwell},
        }
