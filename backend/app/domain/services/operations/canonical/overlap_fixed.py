"""
Recognition — OverlapFixedOperation.

Mede tempo de permanência, cobertura percentual ou contagem de entrada/saída
de objetos em uma ROI estática (área fixa desenhada pelo usuário).
"""
import logging
import time as _time

from app.domain.services.operations.base import BaseOperation, _point_in_polygon

logger = logging.getLogger(__name__)


class OverlapFixedOperation(BaseOperation):
    """Monitora sobreposição de objetos com uma ROI estática.

    Acumula tempo de permanência ou conta eventos de entrada/saída.
    Estado entre frames preserva tempos de entrada e contagens.
    """

    type_id = "overlap_fixed"
    type_label = "Sobreposição área fixa"
    available_modules = ["*"]
    description = "Mede tempo, cobertura ou eventos de entrada/saída em área fixa."
    metric_options = ["time_seconds", "coverage_percent", "entry_exit_count"]
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
                "enum": ["time_seconds", "coverage_percent", "entry_exit_count"],
                "default": "time_seconds",
            },
            "threshold_seconds": {
                "type": "number",
                "title": "Threshold (segundos)",
                "description": (
                    "Para output condicional: tempo mínimo para condition_satisfied=True"
                ),
                "default": 5.0,
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
        """Valida configuração da operação de sobreposição fixa."""
        errors: list[str] = []
        if not config.get("target_class"):
            errors.append("target_class é obrigatório")
        roi = config.get("roi_points", [])
        if len(roi) < 3:
            errors.append("roi_points precisa ter ao menos 3 pontos")
        if config.get("metric") not in ("time_seconds", "coverage_percent", "entry_exit_count"):
            errors.append("metric inválida")
        return errors

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        """Calcula sobreposição de objetos com ROI estática.

        Estado preservado: entry_times (dict track→timestamp), total_time, entries, exits.
        """
        target_class = self.config.get("target_class", "")
        roi_points = self.config.get("roi_points", [])
        threshold = self.config.get("confidence_threshold", 0.5)
        metric = self.config.get("metric", "time_seconds")
        threshold_sec = self.config.get("threshold_seconds", 5.0)

        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)
        now = float(frame_meta.get("timestamp_epoch", _time.time()))

        entry_times: dict = state.get("entry_times", {})
        total_time: float = state.get("total_time", 0.0)
        entries: int = state.get("entries", 0)
        exits: int = state.get("exits", 0)

        matching = [
            d for d in detections
            if d.get("class", "").lower() == target_class.lower()
            and d.get("confidence", 0) >= threshold
        ]

        current_ids: set[str] = set()
        for det in matching:
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h
            if _point_in_polygon(cx, cy, roi_points):
                obj_id = det.get("track_id", f"{cx:.2f},{cy:.2f}")
                current_ids.add(str(obj_id))
                if str(obj_id) not in entry_times:
                    entry_times[str(obj_id)] = now
                    entries += 1

        exiting = set(entry_times.keys()) - current_ids
        for obj_id in exiting:
            elapsed = now - entry_times.pop(obj_id)
            total_time += elapsed
            exits += 1

        active_time = sum(now - t for t in entry_times.values())
        cumulative_time = total_time + active_time

        if metric == "time_seconds":
            metric_value = round(cumulative_time, 2)
        elif metric == "coverage_percent":
            metric_value = min(100.0, round(len(current_ids) * 10.0, 1))
        else:
            metric_value = {"entries": entries, "exits": exits}

        return {
            "result": {"metric": metric, "value": metric_value, "objects_in_roi": len(current_ids)},
            "metric_value": metric_value,
            "condition_satisfied": cumulative_time >= threshold_sec,
            "state_next": {
                "entry_times": entry_times,
                "total_time": total_time,
                "entries": entries,
                "exits": exits,
            },
        }


