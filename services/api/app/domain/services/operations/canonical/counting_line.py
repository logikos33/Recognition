"""
Recognition — CountingLineOperation.

Conta cruzamentos de uma linha virtual por objetos de uma classe.
Estado acumula contagem entre frames. Direção: 'in', 'out' ou 'both'.
Sem DeepSORT — rastreamento por melhor esforço via posição normalizada.

Contenção R6: confirm_samples exige N frames consecutivos no novo lado
antes de confirmar cruzamento; direction_debounce_frames evita dupla
contagem em reversões rápidas (vai-e-volta).
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


def _crossing_debounced(
    debounce: dict,
    obj_key: str,
    crossing_dir: str,
    frame_count: int,
    debounce_frames: int,
) -> bool:
    """Retorna True se cruzamento deve ser ignorado por debounce de direção.

    Debounce ativo quando a direção é oposta à última contada e ainda
    dentro da janela de debounce_frames — evita contar vai-e-volta.
    """
    dbc = debounce.get(obj_key)
    if dbc is None or debounce_frames <= 0:
        return False
    return dbc["last_direction"] != crossing_dir and (frame_count - dbc["frame"]) < debounce_frames


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
            "confirm_samples": {
                "type": "integer",
                "title": "Amostras de confirmação",
                "description": (
                    "Frames consecutivos no novo lado para confirmar cruzamento. "
                    "Default 3 — reduz falsos positivos por ID-switch em oclusão."
                ),
                "minimum": 1,
                "default": 3,
            },
            "direction_debounce_frames": {
                "type": "integer",
                "title": "Debounce de direção (frames)",
                "description": (
                    "Frames a ignorar após cruzamento para evitar dupla contagem "
                    "em reversão rápida (vai-e-volta). Default 5."
                ),
                "minimum": 0,
                "default": 5,
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

        confirm = config.get("confirm_samples")
        if confirm is not None:
            if isinstance(confirm, bool) or not isinstance(confirm, int) or confirm < 1:
                errors.append("confirm_samples deve ser inteiro >= 1")

        debounce_f = config.get("direction_debounce_frames")
        if debounce_f is not None:
            if isinstance(debounce_f, bool) or not isinstance(debounce_f, int) or debounce_f < 0:
                errors.append("direction_debounce_frames deve ser inteiro >= 0")

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
        confirm_samples = max(1, int(self.config.get("confirm_samples", 3)))
        debounce_frames = max(0, int(self.config.get("direction_debounce_frames", 5)))
        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)

        count_in = int(state.get("count_in", 0))
        count_out = int(state.get("count_out", 0))
        prev_sides: dict[str, float] = state.get("prev_sides", {})
        pending: dict[str, dict] = state.get("pending", {})
        debounce: dict[str, dict] = state.get("debounce", {})
        frame_count: int = int(state.get("frame_count", 0)) + 1

        new_sides: dict[str, float] = {}
        new_pending: dict[str, dict] = {}
        new_debounce: dict[str, dict] = dict(debounce)
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

            if obj_key in pending:
                pend = pending[obj_key]
                orig_positive = pend["original_positive"]
                still_on_new_side = (orig_positive and side <= 0) or (not orig_positive and side >= 0)
                if still_on_new_side:
                    new_frames = pend["frames"] + 1
                    if new_frames >= confirm_samples:
                        crossing_dir = pend["direction"]
                        if not _crossing_debounced(new_debounce, obj_key, crossing_dir, frame_count, debounce_frames):
                            if crossing_dir == "in":
                                crossings_in += 1
                            else:
                                crossings_out += 1
                        new_debounce[obj_key] = {"last_direction": crossing_dir, "frame": frame_count}
                    else:
                        new_pending[obj_key] = {**pend, "frames": new_frames}
                # Objeto reverteu antes da confirmação — cancela pending (não adiciona a new_pending)

            elif obj_key in prev_sides:
                prev = prev_sides[obj_key]
                crossing_dir = None
                original_positive = None
                if prev > 0 and side <= 0:
                    crossing_dir = "out"
                    original_positive = True
                elif prev < 0 and side >= 0:
                    crossing_dir = "in"
                    original_positive = False

                if crossing_dir is not None:
                    if confirm_samples == 1:
                        # Confirma imediatamente — comportamento original
                        if not _crossing_debounced(new_debounce, obj_key, crossing_dir, frame_count, debounce_frames):
                            if crossing_dir == "in":
                                crossings_in += 1
                            else:
                                crossings_out += 1
                        new_debounce[obj_key] = {"last_direction": crossing_dir, "frame": frame_count}
                    else:
                        new_pending[obj_key] = {
                            "direction": crossing_dir,
                            "original_positive": original_positive,
                            "frames": 1,
                        }

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
            "state_next": {
                "count_in": count_in,
                "count_out": count_out,
                "prev_sides": new_sides,
                "pending": new_pending,
                "debounce": new_debounce,
                "frame_count": frame_count,
            },
        }
