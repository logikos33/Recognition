"""
Recognition — Guard fail-closed de datas pra busca por conteúdo (nuvem de
terceiro, RunPod/OWLv2, `training/search_content.py`).

Distinto do guard de pool da propagação semeada (`propagation_pool.py`,
migration 112 — critério câmera+intervalo de data revalidado por ID): a
busca por conteúdo opera sobre frames SELECIONADOS individualmente na
galeria (qualquer câmera, qualquer módulo), então a única trava de "isso
pode ir pra nuvem de terceiro" que faz sentido aqui é uma lista de
DATAS explicitamente liberadas pelo operador — `SEARCH_CLOUD_ALLOWED_DATES`
— não um critério de câmera.

Sem essa env configurada (ausente/vazia/malformada), a busca em nuvem fica
INTEIRAMENTE desabilitada — fail-closed: erro de configuração nunca vira
"libera tudo por engano" (mesmo espírito do ADR-0017 aplicado ao inverso de
onde ele normalmente se aplica, mesmo padrão de
`tasks/training.py::_third_party_cloud_training_enabled`).

Formato de `SEARCH_CLOUD_ALLOWED_DATES` (separado por vírgula):
  "2026-07-31"                    — uma data
  "2026-08-01..2026-08-05"        — intervalo inclusivo
  "2026-07-31,2026-08-01..2026-08-05"  — combinação

Usado em TRÊS pontos do ciclo de vida de um job de busca (nenhum confia no
resultado do anterior — cada um relê a env e revalida os frames do zero):
  1. preflight (`search_handlers.py::preflight_search_handler`) — soft,
     retorna frames inelegíveis em vez de abortar a requisição inteira;
  2. criação (`search_handlers.py::create_search_job_handler`) — fail-closed
     de verdade: QUALQUER frame selecionado fora da janela permitida aborta
     a criação do job inteiro (400, lista os frame_ids recusados);
  3. dispatch (`tasks/search.py::dispatch_search`) — revalidação final,
     relendo a env NA HORA (nunca confia no que foi checado na criação —
     a env pode ter mudado entre os dois momentos).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

_ENV_VAR = "SEARCH_CLOUD_ALLOWED_DATES"

_REASON_NOT_FOUND = "frame_not_found"
_REASON_MISSING_R2_KEY = "missing_r2_key"
_REASON_DATE_NOT_ALLOWED = "date_not_allowed"
_REASON_MISSING_CAPTURED_AT = "missing_captured_at"


@dataclass(frozen=True)
class Ineligible:
    frame_id: str
    reason: str


def parse_allowed_dates(raw: "str | None") -> "list[tuple[date, date]] | None":
    """Parseia `SEARCH_CLOUD_ALLOWED_DATES` pra uma lista de intervalos
    `(date_from, date_to)` inclusivos — uma data solta vira `(d, d)`.

    Retorna `None` se `raw` for ausente/vazio OU malformado (qualquer
    entrada que não parseia, ou intervalo invertido) — os dois casos são
    tratados EXATAMENTE igual pelo caller (`cloud_search_allowed_dates`):
    guard indisponível = busca em nuvem desabilitada, nunca "ignora a
    entrada ruim e libera o resto".
    """
    if not raw or not raw.strip():
        return None

    ranges: list[tuple[date, date]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ".." in part:
            start_raw, _, end_raw = part.partition("..")
            try:
                start = date.fromisoformat(start_raw.strip())
                end = date.fromisoformat(end_raw.strip())
            except ValueError:
                return None
            if start > end:
                return None
            ranges.append((start, end))
        else:
            try:
                single = date.fromisoformat(part)
            except ValueError:
                return None
            ranges.append((single, single))

    if not ranges:
        return None
    return ranges


def cloud_search_allowed_dates() -> "list[tuple[date, date]] | None":
    """Lê `SEARCH_CLOUD_ALLOWED_DATES` do ambiente AGORA (sem cache — o
    dispatch relê no momento do envio pra GPU, nunca confia num valor lido
    minutos antes na criação do job). `None` = guard indisponível
    (ausente/vazia/malformada) = busca em nuvem desabilitada."""
    return parse_allowed_dates(os.environ.get(_ENV_VAR))


def is_date_allowed(value: date, allowed_ranges: "list[tuple[date, date]]") -> bool:
    return any(start <= value <= end for start, end in allowed_ranges)


def _coerce_date(value: Any) -> "date | None":
    if value is None:
        return None
    # `datetime` é subclasse de `date` — checar `datetime` PRIMEIRO é
    # obrigatório, senão `isinstance(value, date)` casa direto e devolve o
    # datetime intacto (hora incluída) em vez de truncar pra data pura.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def classify_frame_eligibility(
    frame: "dict[str, Any] | None",
    allowed_ranges: "list[tuple[date, date]]",
) -> "str | None":
    """Retorna o motivo de inelegibilidade de UM frame já resolvido (ou
    `None` se elegível). `frame=None` (não encontrado OU de outro tenant —
    `FrameRepository.get_by_ids_and_tenant` já filtra por posse, então as
    duas situações chegam aqui indistinguíveis, C-01) → `frame_not_found`.
    """
    if frame is None:
        return _REASON_NOT_FOUND
    if not frame.get("r2_key"):
        return _REASON_MISSING_R2_KEY
    captured_date = _coerce_date(frame.get("captured_at"))
    if captured_date is None:
        return _REASON_MISSING_CAPTURED_AT
    if not is_date_allowed(captured_date, allowed_ranges):
        return _REASON_DATE_NOT_ALLOWED
    return None


def classify_selected_frames(
    selected_frame_ids: "list[str]",
    frames_by_id: "dict[str, dict[str, Any]]",
    allowed_ranges: "list[tuple[date, date]]",
) -> "list[Ineligible]":
    """Classifica CADA frame_id selecionado (não só os que vieram na
    resposta do banco) — um id que nem apareceu em `frames_by_id` é
    `frame_not_found`, o mesmo motivo de um frame de outro tenant (nunca
    vaza a diferença, C-01)."""
    ineligible: list[Ineligible] = []
    for frame_id in selected_frame_ids:
        reason = classify_frame_eligibility(frames_by_id.get(frame_id), allowed_ranges)
        if reason is not None:
            ineligible.append(Ineligible(frame_id=frame_id, reason=reason))
    return ineligible
