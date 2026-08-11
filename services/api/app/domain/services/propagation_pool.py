"""
Recognition — Guard fail-closed do pool de propagação semeada.

Sem "sessão de coleta" no domínio (verificado no banco DEV: a encenação é
tenant RVB, captured_at 2026-07-31, UMA câmera, 662 frames todos com
r2_key — `recorder_id` é o NVR físico, igual em TODOS os frames de TODOS
os dias, não identifica um lote), a única trava confiável contra vazamento
de imagem de operação pra uma nuvem de terceiro é a LISTA MATERIALIZADA de
frame_ids gravada no próprio job (`propagation_jobs.pool_frame_ids`) —
nunca um critério (câmeras + intervalo de data) reavaliado às cegas no
momento do dispatch, que poderia devolver um conjunto DIFERENTE (frame
novo inserido depois, frame reatribuído a outra câmera) sem ninguém notar.

`validate_pool_frames` roda em DOIS momentos do ciclo de vida de um job:
  1. na CRIAÇÃO (`api/v1/training/propagation_handlers.py::
     create_propagation_job_handler`, via `materialize_pool`) — materializa
     a lista pela primeira vez a partir do critério pedido pelo usuário;
  2. no DISPATCH (`infrastructure/queue/tasks/propagation.py::
     dispatch_propagation`, via `revalidate_pool`) — REFETCHA os mesmos
     frames POR ID (nunca por critério de novo) e confirma que nada mudou:
     nenhum frame sumiu/apareceu, nenhum ainda viola o critério original,
     e o `pool_hash` recomputado bate com o gravado na criação.

QUALQUER violação (frame fora do critério, r2_key ausente, pool mudou)
levanta `PoolGuardError` — o caller (handler HTTP ou task Celery) NUNCA
prossegue parcialmente (nunca "pula o frame ofensor e segue com os
outros"): o job inteiro falha com o motivo legível.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any


class PoolGuardError(ValueError):
    """Um ou mais frames do pool violam `pool_criteria`, ou o pool mudou
    entre a criação do job e o dispatch — job NUNCA prossegue (nem
    parcialmente). Mensagem sempre inclui o motivo legível (vira
    `propagation_jobs.error_reason`)."""


def compute_pool_hash(frame_ids: list[str]) -> str:
    """sha256 da lista de frame_ids ORDENADA — determinístico
    independente da ordem em que a query devolveu as linhas."""
    ordered = sorted(str(fid) for fid in frame_ids)
    digest = hashlib.sha256("|".join(ordered).encode("utf-8"))
    return digest.hexdigest()


def validate_pool_frames(
    frames: list[dict[str, Any]],
    *,
    tenant_id: "str",
    camera_ids: list[str],
    date_from: date,
    date_to: date,
) -> None:
    """Valida frame a frame contra o critério — levanta `PoolGuardError`
    na PRIMEIRA violação encontrada (fail-closed: não faz sentido reportar
    "3 de 662 frames ruins" e seguir com os outros 659 — o pool inteiro é
    rejeitado, motivo legível, nada é enviado pra GPU).
    """
    if not frames:
        raise PoolGuardError(
            "pool vazio — nenhum frame casa com o critério pedido "
            f"(camera_ids={sorted(str(c) for c in camera_ids)}, "
            f"{date_from}..{date_to})"
        )

    camera_id_set = {str(c) for c in camera_ids}
    for frame in frames:
        frame_id = frame.get("id")

        if str(frame.get("tenant_id")) != str(tenant_id):
            raise PoolGuardError(
                f"frame {frame_id} pertence a outro tenant "
                f"(esperado={tenant_id}, obtido={frame.get('tenant_id')})"
            )

        if str(frame.get("camera_id")) not in camera_id_set:
            raise PoolGuardError(
                f"frame {frame_id} tem camera_id fora do critério "
                f"(camera_id={frame.get('camera_id')}, "
                f"critério={sorted(camera_id_set)})"
            )

        captured_at = frame.get("captured_at")
        if captured_at is None:
            raise PoolGuardError(
                f"frame {frame_id} sem captured_at — não é possível "
                "validar contra o intervalo de data do critério"
            )
        captured_date = (
            captured_at.date() if hasattr(captured_at, "date") else captured_at
        )
        if not (date_from <= captured_date <= date_to):
            raise PoolGuardError(
                f"frame {frame_id} com captured_at fora do intervalo "
                f"({captured_date} não está entre {date_from} e {date_to})"
            )

        if not frame.get("r2_key"):
            raise PoolGuardError(
                f"frame {frame_id} sem r2_key — imagem não existe no storage"
            )


def materialize_pool(
    frames: list[dict[str, Any]],
    *,
    tenant_id: str,
    camera_ids: list[str],
    date_from: date,
    date_to: date,
    limit: int | None = None,
    must_include: list[str] | None = None,
) -> tuple[list[str], str]:
    """Valida `frames` (já buscados por critério —
    `FrameRepository.list_for_propagation_pool`) e retorna
    `(frame_ids ordenados, pool_hash)`.

    `limit` trunca DETERMINISTICAMENTE (após ordenar por id) — é o que
    implementa `validation_only` (pool pequeno pra validar o fluxo ponta a
    ponta antes de comprometer o pool inteiro numa GPU paga). Quando há
    `must_include` (os frames-SEMENTE), eles são pinados no corte e o
    `limit` passa a contar só os frames-ALVO além deles — sem isso, uma
    semente fora dos primeiros N ids ficaria fora do pool de validação e o
    job morreria com "nenhuma semente disponível" mesmo com semente real.
    Ids de `must_include` fora de `frames` são ignorados (o create valida
    semente-fora-do-pool com 400 antes de chegar aqui). O hash é calculado
    sobre a lista JÁ truncada — é essa, e só essa, que o dispatch vai
    revalidar depois.
    """
    validate_pool_frames(
        frames, tenant_id=tenant_id, camera_ids=camera_ids,
        date_from=date_from, date_to=date_to,
    )
    frame_ids = sorted(str(f["id"]) for f in frames)
    if limit is not None:
        pinned = {str(fid) for fid in (must_include or [])} & set(frame_ids)
        targets = [fid for fid in frame_ids if fid not in pinned]
        frame_ids = sorted(pinned | set(targets[:limit]))
    return frame_ids, compute_pool_hash(frame_ids)


def revalidate_pool(
    frames: list[dict[str, Any]],
    *,
    tenant_id: str,
    camera_ids: list[str],
    date_from: date,
    date_to: date,
    expected_frame_ids: list[str],
    expected_pool_hash: str,
) -> None:
    """Revalida o pool NO DISPATCH — chamado com os frames REFETCHADOS POR
    ID (`FrameRepository.get_by_ids(job['pool_frame_ids'])`), nunca
    reconsultados por critério de novo (isso poderia silenciosamente
    trocar o conjunto). Levanta `PoolGuardError` em QUALQUER divergência:

      1. frame sumiu (deletado/movido) ou um id inesperado apareceu —
         comparação de CONJUNTOS entre o que foi refetchado e
         `expected_frame_ids` (o que o job registrou na criação);
      2. algum frame, hoje, viola o critério original (câmera reatribuída,
         captured_at alterado, r2_key removido) — reusa `validate_pool_
         frames`, a MESMA validação da criação;
      3. o `pool_hash` recomputado não bate com `expected_pool_hash` —
         checagem final, redundante com (1) por desenho (defesa em
         profundidade: um bug futuro em qualquer um dos dois lados ainda
         seria pego pelo outro).

    Nenhum frame "ofensor" é silenciosamente descartado — a primeira
    violação aborta o job inteiro.
    """
    fetched_ids = {str(f["id"]) for f in frames}
    expected_ids = {str(fid) for fid in expected_frame_ids}
    if fetched_ids != expected_ids:
        missing = sorted(expected_ids - fetched_ids)
        extra = sorted(fetched_ids - expected_ids)
        raise PoolGuardError(
            "pool mudou desde a criação do job — "
            f"faltando={missing} inesperados={extra}"
        )

    validate_pool_frames(
        frames, tenant_id=tenant_id, camera_ids=camera_ids,
        date_from=date_from, date_to=date_to,
    )

    recomputed = compute_pool_hash(list(fetched_ids))
    if recomputed != expected_pool_hash:
        raise PoolGuardError(
            f"pool_hash divergente no dispatch (esperado={expected_pool_hash} "
            f"recomputado={recomputed}) — abortando sem enviar nada pra GPU"
        )


def _coerce_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def parse_pool_criteria(criteria: dict[str, Any]) -> tuple[list[str], date, date]:
    """Normaliza `pool_criteria` (dict cru — do body do request na criação
    OU da coluna JSONB lida de volta no dispatch) pra
    `(camera_ids, date_from, date_to)`.

    MESMA função nos dois momentos do ciclo de vida (criação e dispatch) —
    nunca duas implementações que poderiam divergir sutilmente (ex.: uma
    aceitando bordas exclusivas e a outra inclusivas). Malformado
    (`camera_ids` vazio, datas ausentes/invertidas) levanta
    `PoolGuardError` — no request isso vira 400; no dispatch (não deveria
    acontecer, já validado na criação) viraria job 'failed' com motivo
    legível, nunca um crash sem contexto.
    """
    camera_ids = criteria.get("camera_ids") if isinstance(criteria, dict) else None
    if not isinstance(camera_ids, list) or not camera_ids:
        raise PoolGuardError("pool_criteria.camera_ids ausente ou vazio")

    date_from_raw = criteria.get("date_from")
    date_to_raw = criteria.get("date_to")
    if not date_from_raw or not date_to_raw:
        raise PoolGuardError("pool_criteria.date_from/date_to ausentes")

    try:
        date_from = _coerce_date(date_from_raw)
        date_to = _coerce_date(date_to_raw)
    except ValueError as exc:
        raise PoolGuardError(f"pool_criteria com data inválida: {exc}") from exc

    if date_from > date_to:
        raise PoolGuardError("pool_criteria.date_from posterior a date_to")

    return [str(c) for c in camera_ids], date_from, date_to
