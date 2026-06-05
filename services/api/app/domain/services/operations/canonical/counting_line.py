"""
Recognition — CountingLineOperation.

Conta cruzamentos de uma linha virtual por objetos de uma classe.
Estado acumula contagem entre frames. Direção: 'in', 'out' ou 'both'.
Sem DeepSORT — rastreamento por melhor esforço via posição normalizada.
"""
import logging

from app.domain.services.operations.base import BaseOperation

logger = logging.getLogger(__name__)

_VALID_DIRECTIONS = {"in", "out", "both"}


def _side_of_line(cx: float, cy: float, p1: list, p2: list) -> float:
    """Produto vetorial para determinar de que lado da linha o ponto está."""
    ax, ay = p1[0], p1[1]
    bx, by = p2[0], p2[1]
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


class CountingLineOperation(BaseOperation):
    """Linha de contagem: conta objetos de uma classe que cruzam a linha virtual."""

    type_id = "counting_line"
    type_label = "Linha de contagem"
    available_modules = ["*"]
    description = "Conta objetos de uma classe que cruzam uma linha virtual definida."
    metric_options = ["count_in", "count_out", "count_total"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["line_points", "direction", "target_class"],
        "properties": {
            "line_points": {
                "type": "array",
                "title": "Pontos da linha",
                "description": "Exatamente 2 pontos [x,y] normalizados [0,1] definindo a linha de contagem",
                "items": {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0, "maximum": 1},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "minItems": 2,
                "maxItems": 2,
            },
            "direction": {
                "type": "string",
                "title": "Direção",
                "enum": ["in", "out", "both"],
                "default": "both",
                "description": "'in' conta entrada, 'out' conta saída, 'both' conta ambos",
            },
            "target_class": {
                "type": "string",
                "title": "Classe alvo",
                "description": "Classe YOLO a contar (ex: 'person')",
                "default": "person",
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
        line = config.get("line_points", [])
        if len(line) != 2:
            errors.append("line_points precisa ter exatamente 2 pontos")
        if config.get("direction") not in _VALID_DIRECTIONS:
            errors.append("direction deve ser 'in', 'out' ou 'both'")
        if not config.get("target_class"):
            errors.append("target_class é obrigatório")
        return errors

    def evaluate(
        self,
        detections: list[dict],
        frame_meta: dict,
        state: dict,
    ) -> dict:
        line = self.config.get("line_points", [[0.0, 0.5], [1.0, 0.5]])
        direction = self.config.get("direction", "both")
        target_class = self.config.get("target_class", "person").lower()
        threshold = self.config.get("confidence_threshold", 0.5)
        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        count_in = int(state.get("count_in", 0))
        count_out = int(state.get("count_out", 0))
        prev_sides: dict[str, float] = state.get("prev_sides", {})

        new_sides: dict[str, float] = {}
        crossings_in = 0
        crossings_out = 0

        for det in detections:
            cls = det.get("class", "").lower()
            if cls != target_class or det.get("confidence", 0) < threshold:
                continue
            bbox = det.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2] / 2) / frame_w
            cy = (bbox[1] + bbox[3] / 2) / frame_h

            # Chave aproximada por posição — sem DeepSORT, melhor esforço
            obj_key = f"{round(cx, 2)},{round(cy, 2)}"
            side = _side_of_line(cx, cy, line[0], line[1])
            new_sides[obj_key] = side

            if obj_key in prev_sides:
                prev = prev_sides[obj_key]
                if prev > 0 and side <= 0:
                    crossings_out += 1
                elif prev < 0 and side >= 0:
                    crossings_in += 1

        count_in += crossings_in
        count_out += crossings_out
        count_total = count_in + count_out

        if direction == "in":
            metric_value = count_in
        elif direction == "out":
            metric_value = count_out
        else:
            metric_value = count_total

        return {
            "result": {"count_in": count_in, "count_out": count_out, "count_total": count_total},
            "metric_value": metric_value,
            "condition_satisfied": metric_value > 0,
            "state_next": {"count_in": count_in, "count_out": count_out, "prev_sides": new_sides},
        }
