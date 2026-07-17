"""
Recognition — StageTimerOperation (task-109, ADR-0053).

Cronômetro de etapa (módulo Qualidade, câmeras auxiliares + NvDCF):
mede o tempo em que a peça permanece na zona da etapa — da entrada à saída.
O elapsed_s final alimenta o outbound monofatura (task-108).

Identidade preferencial por det["track_id"] (NvDCF do edge); sem id,
melhor-esforço por presença agregada na zona (uma peça por vez na etapa,
premissa do fluxo de bancada RVB).
"""
import logging

from app.domain.services.operations.base import BaseOperation, _point_in_polygon

logger = logging.getLogger(__name__)


class StageTimerOperation(BaseOperation):
    """Cronometra a permanência da peça na zona da etapa (entrada → saída)."""

    type_id = "stage_timer"
    type_label = "Cronômetro de etapa (Qualidade)"
    available_modules = ["quality"]
    description = (
        "Mede o tempo da peça na zona da etapa via tracker; ao sair, publica "
        "o tempo decorrido (elapsed_s) para a monofatura."
    )
    metric_options = ["elapsed_seconds", "stages_completed"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["zone_points", "target_class"],
        "properties": {
            "zone_points": {
                "type": "array",
                "title": "Zona da etapa (polígono)",
                "items": {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0, "maximum": 1},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "minItems": 3,
            },
            "target_class": {"type": "string", "title": "Classe da peça"},
            "confidence_threshold": {
                "type": "number", "minimum": 0.1, "maximum": 1.0, "default": 0.5,
            },
            "exit_grace_seconds": {
                "type": "number",
                "title": "Tolerância de saída (s)",
                "minimum": 0,
                "default": 2,
                "description": "Ausência menor que isso não conta como saída (oclusão).",
            },
        },
    }

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        if len(config.get("zone_points", [])) < 3:
            errors.append("zone_points precisa ter ao menos 3 pontos")
        if not config.get("target_class"):
            errors.append("target_class é obrigatório")
        return errors

    def evaluate(self, detections: list[dict], frame_meta: dict, state: dict) -> dict:
        zone = self.config["zone_points"]
        target = self.config["target_class"].lower()
        threshold = float(self.config.get("confidence_threshold", 0.5))
        grace = float(self.config.get("exit_grace_seconds", 2))
        now = float(frame_meta.get("timestamp", 0.0))
        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        present = False
        for det in detections:
            if det.get("class", "").lower() != target:
                continue
            if det.get("confidence", 0) < threshold:
                continue
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h
            if _point_in_polygon(cx, cy, zone):
                present = True
                break

        entered_at = state.get("entered_at")
        last_seen = state.get("last_seen")
        completed_elapsed = None

        if present:
            if entered_at is None:
                entered_at = now  # peça entrou na etapa
            last_seen = now
        elif entered_at is not None and last_seen is not None:
            if (now - last_seen) > grace:
                # peça saiu de fato → fecha o cronômetro e publica
                completed_elapsed = round(last_seen - entered_at, 1)
                entered_at = None
                last_seen = None

        running = round(now - entered_at, 1) if entered_at is not None else 0.0
        return {
            "result": {
                "piece_in_stage": entered_at is not None,
                "running_seconds": running,
                "completed_elapsed_s": completed_elapsed,
            },
            "metric_value": completed_elapsed if completed_elapsed is not None else running,
            "condition_satisfied": completed_elapsed is not None,
            "state_next": {**state, "entered_at": entered_at, "last_seen": last_seen},
        }
