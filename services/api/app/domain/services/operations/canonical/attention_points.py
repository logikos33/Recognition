"""
Recognition — AttentionPointsOperation (task-109, ADR-0053).

Inspeção multi-atributo por ROI (módulo Qualidade, câmeras principais 4MP):
cada "ponto de atenção" da peça é uma ROI nomeada com critério próprio
(classe esperada presente/ausente). A LISTA de pontos é input do cliente
(pendente) → 100% configurável, nada hard-coded.

O resultado por atributo alimenta o outbound monofatura (task-108):
  result = {"ok": bool, "attributes": [{"name", "ok", "confidence"}, ...]}
"""
import logging

from app.domain.services.operations.base import BaseOperation, _point_in_polygon

logger = logging.getLogger(__name__)

_VALID_OK_WHEN = {"present", "absent"}


class AttentionPointsOperation(BaseOperation):
    """Avalia pontos de atenção (ROIs nomeadas) → OK/falha por atributo."""

    type_id = "attention_points"
    type_label = "Pontos de atenção (Qualidade)"
    available_modules = ["quality"]
    description = (
        "Inspeção multi-atributo: cada ponto de atenção é uma ROI com critério "
        "de classe presente/ausente. Resultado por atributo alimenta a monofatura."
    )
    metric_options = ["attributes_ok", "attributes_failed"]
    output_formats = ["physical", "conditional", "both"]
    config_schema = {
        "type": "object",
        "required": ["points"],
        "properties": {
            "points": {
                "type": "array",
                "title": "Pontos de atenção",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name", "roi", "target_class", "ok_when"],
                    "properties": {
                        "name": {"type": "string", "title": "Nome do atributo"},
                        "roi": {
                            "type": "array",
                            "title": "ROI (polígono normalizado)",
                            "items": {
                                "type": "array",
                                "items": {"type": "number", "minimum": 0, "maximum": 1},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "minItems": 3,
                        },
                        "target_class": {"type": "string"},
                        "ok_when": {
                            "type": "string",
                            "enum": ["present", "absent"],
                            "description": (
                                "present = atributo OK se a classe for detectada na ROI "
                                "(ex.: solda existe); absent = OK se NÃO detectada "
                                "(ex.: defeito ausente)."
                            ),
                        },
                        "min_confidence": {
                            "type": "number", "minimum": 0.1, "maximum": 1.0, "default": 0.5,
                        },
                    },
                },
            },
        },
    }

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        points = config.get("points") or []
        if not points:
            errors.append("points é obrigatório e não pode ser vazio")
        names = set()
        for idx, p in enumerate(points):
            if not p.get("name"):
                errors.append(f"points[{idx}].name é obrigatório")
            elif p["name"] in names:
                errors.append(f"points[{idx}].name duplicado: {p['name']!r}")
            else:
                names.add(p["name"])
            if len(p.get("roi", [])) < 3:
                errors.append(f"points[{idx}].roi precisa ter ao menos 3 pontos")
            if not p.get("target_class"):
                errors.append(f"points[{idx}].target_class é obrigatório")
            if p.get("ok_when") not in _VALID_OK_WHEN:
                errors.append(f"points[{idx}].ok_when deve ser 'present' ou 'absent'")
        return errors

    def evaluate(self, detections: list[dict], frame_meta: dict, state: dict) -> dict:
        frame_w = frame_meta.get("width", 640)
        frame_h = frame_meta.get("height", 360)
        attributes = []
        for point in self.config["points"]:
            target = point["target_class"].lower()
            min_conf = float(point.get("min_confidence", 0.5))
            best = 0.0
            for det in detections:
                if det.get("class", "").lower() != target:
                    continue
                conf = float(det.get("confidence", 0))
                if conf < min_conf:
                    continue
                bbox = det.get("bbox", [0, 0, 0, 0])
                cx = (bbox[0] + bbox[2] / 2) / frame_w
                cy = (bbox[1] + bbox[3] / 2) / frame_h
                if _point_in_polygon(cx, cy, point["roi"]):
                    best = max(best, conf)
            found = best > 0
            ok = found if point["ok_when"] == "present" else not found
            attributes.append({
                "name": point["name"],
                "ok": ok,
                "confidence": round(best, 4) if found else None,
            })
        failed = [a for a in attributes if not a["ok"]]
        return {
            "result": {"ok": not failed, "attributes": attributes},
            "metric_value": len(failed),
            "condition_satisfied": bool(failed),
            "state_next": state,
        }
