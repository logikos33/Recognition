"""
DOMAIN camera_module_service.py — Resolução de módulo ativo por câmera.

Layer: domain
Pattern: Service (framework-agnostic)

Key exports:
  - resolve_active_module(camera, now) → Optional[str]
      Avalia schedule_rules da câmera para determinar módulo ativo agora.
      Se nenhuma regra fizer match → retorna camera['active_module'] padrão.
      Se módulo for 'none' → retorna None (câmera pausada).

  - get_model_key_for_module(camera, module) → Optional[str]
      Mapeia module → r2_key do .pt correto.
      Retorna None se modelo não estiver vinculado.

schedule_rules formato:
  [
    {"days": [1,2,3,4,5], "start": "08:00", "end": "18:00", "module": "epi"},
    {"days": [1,2,3,4,5], "start": "18:00", "end": "08:00", "module": "basic"},
    {"days": [6,7],        "start": "00:00", "end": "23:59", "module": "none"}
  ]
  days: 1=segunda ... 7=domingo (Python weekday()+1)
  start/end: HH:MM em 24h
  module: epi | quality | counting | basic | none

Related: app/infrastructure/queue/tasks/inference.py, app/api/v1/cameras/module_handler.py
"""
import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Módulos válidos (não incluir "none" aqui — é tratado como pause)
VALID_MODULES = frozenset({"epi", "quality", "counting", "basic"})


def resolve_active_module(camera: dict[str, Any], now: Optional[datetime] = None) -> Optional[str]:
    """
    Determina módulo ativo da câmera no momento 'now'.

    1. Avalia schedule_rules (JSONB) em ordem
    2. Retorna módulo da primeira regra que fizer match
    3. Se módulo da regra for 'none' → retorna None (câmera pausada)
    4. Se nenhuma regra fizer match → retorna camera['active_module'] padrão

    Args:
        camera: dict com campos 'schedule_rules', 'active_module'
        now:    datetime de referência (padrão: datetime.now())

    Returns:
        str com nome do módulo ativo, ou None se câmera pausada
    """
    if now is None:
        now = datetime.now()

    # Carregar schedule_rules
    rules_raw = camera.get("schedule_rules", [])
    if isinstance(rules_raw, str):
        try:
            rules_raw = json.loads(rules_raw)
        except (json.JSONDecodeError, ValueError):
            rules_raw = []

    if not isinstance(rules_raw, list) or not rules_raw:
        # Sem regras: retornar módulo padrão
        return _get_default_module(camera)

    # day_of_week: 1=segunda ... 7=domingo
    day_of_week = now.weekday() + 1
    current_time = now.strftime("%H:%M")

    for rule in rules_raw:
        if not isinstance(rule, dict):
            continue

        days = rule.get("days", [])
        start = rule.get("start", "00:00")
        end = rule.get("end", "23:59")
        module = rule.get("module")

        if not isinstance(days, list) or day_of_week not in days:
            continue

        if _time_in_range(current_time, start, end):
            if module == "none":
                return None  # câmera pausada
            return module if module in VALID_MODULES else _get_default_module(camera)

    return _get_default_module(camera)


def get_model_key_for_module(camera: dict[str, Any], module: str) -> Optional[str]:
    """
    Retorna r2_key do arquivo .pt para o módulo especificado.

    Mapeia module → model_{module}_id → busca r2_key no banco.
    Esta função retorna apenas o UUID do modelo — a busca do r2_key
    deve ser feita pelo caller via CameraRepository.

    Returns:
        UUID do modelo vinculado, ou None se não configurado
    """
    mapping = {
        "epi":      "model_epi_id",
        "quality":  "model_quality_id",
        "counting": "model_counting_id",
    }
    field = mapping.get(module)
    if not field:
        return None
    model_id = camera.get(field)
    return str(model_id) if model_id else None


def validate_schedule_rules(rules: Any) -> tuple[bool, str]:
    """
    Valida estrutura de schedule_rules antes de salvar.

    Returns:
        (True, "") se válido
        (False, "mensagem de erro") se inválido
    """
    if not isinstance(rules, list):
        return False, "schedule_rules deve ser uma lista"

    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            return False, f"Regra {i}: deve ser um objeto"

        days = rule.get("days")
        if not isinstance(days, list) or not days:
            return False, f"Regra {i}: 'days' deve ser lista não-vazia de inteiros (1-7)"
        if not all(isinstance(d, int) and 1 <= d <= 7 for d in days):
            return False, f"Regra {i}: 'days' deve conter inteiros entre 1 (seg) e 7 (dom)"

        start = rule.get("start", "")
        end = rule.get("end", "")
        if not _valid_time_fmt(start):
            return False, f"Regra {i}: 'start' inválido (use HH:MM)"
        if not _valid_time_fmt(end):
            return False, f"Regra {i}: 'end' inválido (use HH:MM)"

        module = rule.get("module")
        valid_with_none = VALID_MODULES | {"none"}
        if module not in valid_with_none:
            return False, f"Regra {i}: módulo '{module}' inválido. Use: {sorted(valid_with_none)}"

    return True, ""


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _get_default_module(camera: dict[str, Any]) -> Optional[str]:
    """Retorna módulo padrão da câmera. None se 'none'."""
    mod = camera.get("active_module", "epi") or "epi"
    return None if mod == "none" else mod


def _time_in_range(current: str, start: str, end: str) -> bool:
    """
    Verifica se 'current' (HH:MM) está no intervalo [start, end].
    Suporta intervalos que cruzam meia-noite (ex: 22:00 → 06:00).
    """
    if start <= end:
        return start <= current <= end
    # Intervalo cruza meia-noite
    return current >= start or current <= end


def _valid_time_fmt(value: str) -> bool:
    """Verifica se string está no formato HH:MM."""
    if not isinstance(value, str) or len(value) != 5:
        return False
    try:
        h, m = value.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except (ValueError, AttributeError):
        return False
