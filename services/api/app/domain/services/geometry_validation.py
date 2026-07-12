"""
Recognition — Validação de geometria de deploy de modelo por câmera (WS-C2).

Campos de `model_deployments.config` (migration 100, JSONB):
  roi: [[x,y], ...]  — zona/polígono, >=3 pontos, mutuamente exclusivo com line
  line: [[x,y],[x,y]] — linha de cruzamento, exatamente 2 pontos
  classes: [str, ...] — não vazio
  thresholds: {class_name: float 0..1} — chaves ⊆ classes

Coordenadas normalizadas 0..1. NÃO confundir com `roi_points`/`line_points`
de ADR-0032 (entidade "Cenário/Operação", schema diferente) — aqui é
config de DEPLOY do modelo na câmera, não uma regra de negócio.
"""
from __future__ import annotations

from typing import Any


def _is_point(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1
            for v in value
        )
    )


def validate_deployment_config(config: Any) -> list[str]:
    """Valida config JSONB de model_deployments. Retorna lista de erros
    (vazia == válido)."""
    if not isinstance(config, dict):
        return ["config deve ser um objeto"]

    errors: list[str] = []
    roi = config.get("roi")
    line = config.get("line")

    if roi is not None and line is not None:
        errors.append("roi e line são mutuamente exclusivos")

    if roi is not None and (
        not isinstance(roi, list) or len(roi) < 3 or not all(_is_point(p) for p in roi)
    ):
        errors.append("roi deve ter >= 3 pontos [x,y] normalizados (0..1)")

    if line is not None and (
        not isinstance(line, list) or len(line) != 2 or not all(_is_point(p) for p in line)
    ):
        errors.append("line deve ter exatamente 2 pontos [x,y] normalizados (0..1)")

    classes = config.get("classes")
    if (
        not isinstance(classes, list)
        or not classes
        or not all(isinstance(c, str) and c for c in classes)
    ):
        errors.append("classes deve ser uma lista não vazia de strings")

    thresholds = config.get("thresholds", {})
    if not isinstance(thresholds, dict):
        errors.append("thresholds deve ser um objeto {classe: limiar}")
    else:
        valid_classes = classes if isinstance(classes, list) else []
        for cls, value in thresholds.items():
            if cls not in valid_classes:
                errors.append(f"thresholds contém classe '{cls}' fora de 'classes'")
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not 0 <= value <= 1
            ):
                errors.append(f"threshold de '{cls}' deve ser numérico entre 0 e 1")

    return errors
