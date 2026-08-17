"""
Recognition — Search Job handlers (busca por conteúdo, RunPod/OWLv2).

Rotas (routes.py):
  POST /api/v1/training/search/preflight          insumos ANTES de criar o
                                                    job (elegibilidade dos
                                                    frames selecionados,
                                                    custo) — só leitura
  POST /api/v1/training/search/jobs                cria job — materializa +
                                                    valida a seleção
                                                    (domain/services/
                                                    search_cloud_guard.py),
                                                    dispara Celery
  GET  /api/v1/training/search/jobs/<id>            status do job
                                                    (cross-tenant → 404)
  GET  /api/v1/training/search/jobs                lista jobs do tenant
  POST /api/v1/training/search/jobs/<id>/callback   callback da GPU remota —
                                                    SEM jwt (X-Callback-Token)
  POST /api/v1/training/search/jobs/<id>/promote    promove achado(s) a
                                                    proposta(s) pendente(s)

O guard fail-closed de datas (`SEARCH_CLOUD_ALLOWED_DATES`,
`domain/services/search_cloud_guard.py`) roda no preflight (soft — retorna
`ineligible`) e no create (fail-closed — 400 se QUALQUER frame selecionado
não for elegível); o dispatch (`tasks/search.py`) revalida de novo do zero,
nunca confiando no que foi checado aqui.

Resultado de um job de busca é ACHADO (`results`/`findings_count`), não
proposta de anotação — só vira `pre_annotations` pendente via
POST .../jobs/<id>/promote (merge, nunca sobrescreve propostas pendentes
de outro job — `FrameRepository.append_pre_annotations`).
"""
import hmac
import logging
from typing import Any

from flask import request

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.domain.services.propagation_pool import compute_pool_hash
from app.domain.services.search_cloud_guard import (
    classify_selected_frames,
    cloud_search_allowed_dates,
)

logger = logging.getLogger(__name__)

_MIN_FRAME_IDS = 1
_MAX_FRAME_IDS = 500
_MIN_TERMS = 1
_MAX_TERMS = 12
_ERROR_MAX_LEN = 2000
_CLOUD_DISABLED_MESSAGE = (
    "busca em nuvem desabilitada — SEARCH_CLOUD_ALLOWED_DATES não configurada"
)


def _get_pool():
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415

    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _get_search_repo():
    from app.infrastructure.database.repositories.search_repository import (  # noqa: PLC0415
        SearchRepository,
    )

    return SearchRepository(_get_pool())


def _get_frame_repo():
    from app.infrastructure.database.repositories.frame_repository import (  # noqa: PLC0415
        FrameRepository,
    )

    return FrameRepository(_get_pool())


def _strip_callback_token(job: "dict[str, Any] | None") -> "dict[str, Any] | None":
    """Nunca expor `callback_token` (mesmo revogado) numa resposta HTTP —
    mesmo padrão de `propagation_handlers.py::_strip_callback_token`."""
    if job is not None:
        job.pop("callback_token", None)
    return job


def _third_party_cloud_enabled(tenant_id: str) -> bool:
    """Reusa o MESMO gate ADR-0047/0060 do treino/propagação — lazy
    import, mesmo padrão dos `_get_*_repo` deste módulo."""
    from app.infrastructure.queue.tasks.training import (  # noqa: PLC0415
        _third_party_cloud_training_enabled,
    )

    return _third_party_cloud_training_enabled(tenant_id)


def _resolve_runpod_api_key(tenant_id: str) -> str:
    from app.infrastructure.gpu.runpod_client import resolve_runpod_api_key  # noqa: PLC0415

    return resolve_runpod_api_key(tenant_id)


def _gpu_job_limits() -> "tuple[str, int, float]":
    """(gpu_type, timeout_seconds, max_usd) do tipo de carga SEARCH — só
    leitura de env/defaults, SEM chamada de rede."""
    from app.infrastructure.gpu.runpod_runner import (  # noqa: PLC0415
        JobKind,
        gpu_type_default,
        max_usd_for_kind,
        timeout_seconds_for_kind,
    )

    return (
        gpu_type_default(),
        timeout_seconds_for_kind(JobKind.SEARCH),
        max_usd_for_kind(JobKind.SEARCH),
    )


def _gpu_price_estimate(
    api_key: str, gpu_type: str, timeout_seconds: int,
) -> "tuple[float | None, float | None, bool]":
    """(price_usd_h, estimated_cost_usd, price_error) — mesmo padrão de
    `propagation_handlers.py::_gpu_price_estimate`. `RunPodError` nunca
    derruba o preflight inteiro. ⛔ `api_key` só instancia o client — nunca
    logada, nunca volta no retorno."""
    from app.infrastructure.gpu.runpod_client import RunPodClient, RunPodError  # noqa: PLC0415
    from app.infrastructure.gpu.runpod_runner import estimate_cost_usd  # noqa: PLC0415

    try:
        client = RunPodClient(api_key)
        price = client.get_gpu_price(gpu_type)
    except RunPodError as exc:
        logger.warning("search_preflight_price_lookup_failed: err=%s", exc)
        return None, None, True
    return price, estimate_cost_usd(price, timeout_seconds), False


# --------------------------------------------------------------------------
# Validação de entrada (frame_ids / terms) — compartilhada preflight+create
# --------------------------------------------------------------------------

def _parse_frame_ids(raw: Any) -> "tuple[list[str] | None, str | None]":
    if not isinstance(raw, list) or not raw:
        return None, "frame_ids é obrigatório e não pode ser vazio"
    seen: set[str] = set()
    frame_ids: list[str] = []
    for item in raw:
        fid = str(item)
        if fid not in seen:
            seen.add(fid)
            frame_ids.append(fid)
    if not (_MIN_FRAME_IDS <= len(frame_ids) <= _MAX_FRAME_IDS):
        return None, (
            f"frame_ids deve ter entre {_MIN_FRAME_IDS} e {_MAX_FRAME_IDS} "
            f"itens (recebido: {len(frame_ids)})"
        )
    return frame_ids, None


def _parse_terms(raw: Any) -> "tuple[list[dict[str, str]] | None, str | None]":
    if not isinstance(raw, list) or not raw:
        return None, "terms é obrigatório e não pode ser vazio"
    if not (_MIN_TERMS <= len(raw) <= _MAX_TERMS):
        return None, (
            f"terms deve ter entre {_MIN_TERMS} e {_MAX_TERMS} itens "
            f"(recebido: {len(raw)})"
        )
    terms: list[dict[str, str]] = []
    seen_labels: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            return None, f"term inválido (não é objeto): {item!r}"
        label = str(item.get("label") or "").strip()
        query = str(item.get("query") or "").strip()
        if not label:
            return None, f"term.label inválido/ausente: {item!r}"
        if not query:
            return None, f"term.query inválido/ausente: {item!r}"
        if label in seen_labels:
            return None, f"term.label duplicado: {label!r}"
        seen_labels.add(label)
        terms.append({"label": label, "query": query})
    return terms, None


def _format_date_ranges(ranges: "list[tuple]") -> list[str]:
    formatted = []
    for start, end in ranges:
        formatted.append(start.isoformat() if start == end else f"{start.isoformat()}..{end.isoformat()}")
    return formatted


# --------------------------------------------------------------------------
# POST /api/v1/training/search/preflight
# --------------------------------------------------------------------------

def preflight_search_handler():
    """Preflight da busca por conteúdo — elegibilidade dos frames
    SELECIONADOS (posse por tenant, r2_key, data permitida) + custo
    estimado (RunPod). Só leitura — não materializa nem grava nada.
    ---
    tags:
      - training
    summary: Preflight de busca por conteúdo (elegibilidade + custo, sem criar job)
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          properties:
            frame_ids: {type: array, items: {type: string}}
            terms:
              type: array
              items:
                type: object
                properties:
                  label: {type: string}
                  query: {type: string}
    responses:
      200:
        description: Elegibilidade dos frames + custo estimado (RunPod)
      409:
        description: Busca em nuvem desabilitada (SEARCH_CLOUD_ALLOWED_DATES não configurada)
    """
    try:
        tenant_id = get_tenant_id()
        data = request.get_json() or {}

        allowed_ranges = cloud_search_allowed_dates()
        if allowed_ranges is None:
            return error(_CLOUD_DISABLED_MESSAGE, 409)

        frame_ids, frame_ids_error = _parse_frame_ids(data.get("frame_ids"))
        if frame_ids_error:
            return error(frame_ids_error, 400)

        terms, terms_error = _parse_terms(data.get("terms"))
        if terms_error:
            return error(terms_error, 400)

        frame_repo = _get_frame_repo()
        frames = frame_repo.get_by_ids_and_tenant(frame_ids, tenant_id)
        frames_by_id = {str(f["id"]): f for f in frames}

        ineligible = classify_selected_frames(frame_ids, frames_by_id, allowed_ranges)
        ineligible_ids = {item.frame_id for item in ineligible}
        eligible_count = len(frame_ids) - len(ineligible_ids)

        third_party_cloud_enabled = _third_party_cloud_enabled(str(tenant_id))

        # ⛔ nunca logar/retornar o valor da chave — só presença (bool).
        api_key = _resolve_runpod_api_key(str(tenant_id))
        runpod_configured = bool(api_key)

        gpu_type, timeout_seconds, max_usd = _gpu_job_limits()
        price_usd_h: float | None = None
        estimated_cost_usd: float | None = None
        price_error = False
        if runpod_configured:
            price_usd_h, estimated_cost_usd, price_error = _gpu_price_estimate(
                api_key, gpu_type, timeout_seconds,
            )

        return success({
            "selected_count": len(frame_ids),
            "eligible_count": eligible_count,
            "ineligible": [
                {"frame_id": item.frame_id, "reason": item.reason} for item in ineligible
            ],
            "terms_count": len(terms),
            "third_party_cloud_enabled": third_party_cloud_enabled,
            "runpod_configured": runpod_configured,
            "gpu": {
                "gpu_type": gpu_type,
                "price_usd_h": price_usd_h,
                "estimated_cost_usd": estimated_cost_usd,
                "max_usd": max_usd,
                "timeout_seconds": timeout_seconds,
                "price_error": price_error,
            },
            "allowed_dates": _format_date_ranges(allowed_ranges),
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("preflight_search_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --------------------------------------------------------------------------
# POST /api/v1/training/search/jobs
# --------------------------------------------------------------------------

def create_search_job_handler():
    """Cria um job de busca por conteúdo.
    ---
    tags:
      - training
    summary: Cria job de busca por conteúdo (OWLv2 no RunPod)
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          properties:
            frame_ids: {type: array, items: {type: string}}
            terms:
              type: array
              items:
                type: object
                properties:
                  label: {type: string}
                  query: {type: string}
    responses:
      201:
        description: Job criado (queued) e despachado pro Celery
      409:
        description: Busca em nuvem desabilitada (SEARCH_CLOUD_ALLOWED_DATES não configurada)
    """
    try:
        tenant_id = get_tenant_id()
        user_id = get_current_user_id()
        data = request.get_json() or {}

        allowed_ranges = cloud_search_allowed_dates()
        if allowed_ranges is None:
            return error(_CLOUD_DISABLED_MESSAGE, 409)

        frame_ids, frame_ids_error = _parse_frame_ids(data.get("frame_ids"))
        if frame_ids_error:
            return error(frame_ids_error, 400)

        terms, terms_error = _parse_terms(data.get("terms"))
        if terms_error:
            return error(terms_error, 400)

        frame_repo = _get_frame_repo()
        frames = frame_repo.get_by_ids_and_tenant(frame_ids, tenant_id)
        frames_by_id = {str(f["id"]): f for f in frames}

        # Fail-closed de verdade (ao contrário do preflight, que só
        # informa): QUALQUER frame selecionado inelegível aborta a criação
        # do job inteiro — nunca "cria com os elegíveis e ignora o resto".
        ineligible = classify_selected_frames(frame_ids, frames_by_id, allowed_ranges)
        if ineligible:
            return error(
                "frames recusados pelo guard de nuvem (posse/r2_key/data fora de "
                f"SEARCH_CLOUD_ALLOWED_DATES): "
                f"{[{'frame_id': item.frame_id, 'reason': item.reason} for item in ineligible]}",
                400,
            )

        selected_frame_ids = sorted(frame_ids)
        frames_hash = compute_pool_hash(selected_frame_ids)

        repo = _get_search_repo()
        job = repo.create_job(
            tenant_id=tenant_id,
            selected_frame_ids=selected_frame_ids,
            frames_hash=frames_hash,
            terms=terms,
            created_by=user_id,
        )
        _strip_callback_token(job)

        from app.infrastructure.queue.tasks.search import dispatch_search  # noqa: PLC0415

        dispatch_search.delay(job_id=str(job["id"]))

        return success(job, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_search_job_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --------------------------------------------------------------------------
# GET /api/v1/training/search/jobs/<id>
# --------------------------------------------------------------------------

def get_search_job_handler(job_id: str):
    """Status de um job de busca por conteúdo (cross-tenant → 404, C-01)."""
    try:
        tenant_id = get_tenant_id()
        repo = _get_search_repo()
        job = repo.get_by_id_and_tenant(job_id, tenant_id)
        if job is None:
            return error("Job de busca não encontrado", 404)
        _strip_callback_token(job)
        return success(job)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_search_job_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --------------------------------------------------------------------------
# GET /api/v1/training/search/jobs
# --------------------------------------------------------------------------

def list_search_jobs_handler():
    """Lista jobs de busca por conteúdo do tenant do contexto."""
    try:
        tenant_id = get_tenant_id()
        repo = _get_search_repo()
        jobs = repo.list_for_tenant(tenant_id)
        for job in jobs:
            _strip_callback_token(job)
        return success(jobs)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_search_jobs_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --------------------------------------------------------------------------
# POST /api/v1/training/search/jobs/<id>/callback (interno GPU→API)
# --------------------------------------------------------------------------

_ALLOWED_CALLBACK_STATUS = frozenset({"running", "completed", "failed"})


def _terms_lookup(terms: Any) -> dict[str, str]:
    """label -> query a partir de `search_jobs.terms` (JSONB lido de
    volta) — usado pra validar cada achado do callback."""
    if not isinstance(terms, list):
        return {}
    lookup: dict[str, str] = {}
    for item in terms:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            query = str(item.get("query") or "").strip()
            if label and query:
                lookup[label] = query
    return lookup


def _validate_completed_findings(
    findings: Any, selected_frame_ids: list[str], terms_lookup: dict[str, str],
) -> "tuple[list[dict] | None, str | None]":
    """Valida o payload final ANTES de gravar qualquer coisa — "nunca
    sucesso silencioso": qualquer achado malformado (frame fora da seleção,
    label/term que não bate com `terms_lookup`, bbox fora de [0,1],
    confidence fora de [0,1]) rejeita o payload INTEIRO (400); o job
    permanece 'running', NUNCA marcado 'completed' com dado
    parcial/adulterado. `findings=[]` (lista vazia, mas presente) é válido
    — "achou nada" é um resultado honesto. Retorna (lista normalizada,
    None) ou (None, mensagem_de_erro)."""
    if not isinstance(findings, list):
        return None, "findings deve ser uma lista"

    selected_set = set(selected_frame_ids)
    validated: list[dict] = []

    for item in findings:
        if not isinstance(item, dict):
            return None, f"achado inválido: não é objeto ({item!r})"

        frame_id = str(item.get("frame_id") or "")
        if frame_id not in selected_set:
            return None, f"frame_id fora da seleção do job: {frame_id!r}"

        label = str(item.get("label") or "").strip()
        if not label or label not in terms_lookup:
            return None, f"label inválido/desconhecido no job: {label!r}"

        term = str(item.get("term") or "").strip()
        if term != terms_lookup[label]:
            return None, (
                f"term não corresponde ao query registrado para label {label!r}: "
                f"{term!r}"
            )

        bbox = item.get("bbox")
        if (
            not isinstance(bbox, list)
            or len(bbox) != 4
            or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in bbox
            )
            or not all(0.0 <= float(v) <= 1.0 for v in bbox)
        ):
            return None, f"bbox inválido em frame {frame_id!r}: {bbox!r}"

        confidence = item.get("confidence")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not (0.0 <= float(confidence) <= 1.0)
        ):
            return None, f"confidence inválida em frame {frame_id!r}: {confidence!r}"

        validated.append({
            "frame_id": frame_id,
            "term": term,
            "label": label,
            "bbox": [float(v) for v in bbox],
            "confidence": float(confidence),
        })

    return validated, None


def search_callback_handler(job_id: str):
    """Progresso/resultado da busca remota (RunPod) — SEM JWT.

    Auth: header X-Callback-Token comparado em tempo constante
    (hmac.compare_digest) com search_jobs.callback_token (mesmo padrão de
    `propagation_handlers.py::propagation_callback_handler`). Rate limit na
    rota (routes.py).
    """
    try:
        token = request.headers.get("X-Callback-Token", "")
        if not token:
            return error("Token de callback ausente", 401)

        repo = _get_search_repo()
        job = repo.get_by_id(job_id)
        stored = str((job or {}).get("callback_token") or "")
        if not job or not stored or not hmac.compare_digest(stored, token):
            logger.warning("search_callback_token_invalido: job=%s", job_id)
            return error("Token de callback inválido", 403)

        data = request.get_json(silent=True) or {}
        status = data.get("status")
        if status not in _ALLOWED_CALLBACK_STATUS:
            return error(
                f"status inválido: {status!r} "
                f"(permitidos: {sorted(_ALLOWED_CALLBACK_STATUS)})", 400,
            )

        if status == "failed":
            error_message = str(
                data.get("error_message") or "busca falhou (sem detalhe)"
            )[:_ERROR_MAX_LEN]
            repo.apply_callback_failed(job_id, error_message)
            return success({"job_id": job_id, "status": "failed"})

        if status == "running":
            metrics = data.get("metrics")
            if metrics is not None and not isinstance(metrics, dict):
                return error("metrics deve ser um objeto", 400)
            repo.merge_metrics(job_id, metrics or {})
            return success({"job_id": job_id, "status": "running"})

        # status == "completed" — "findings" precisa estar PRESENTE (mesmo
        # que vazia): sua ausência é sinal de payload incompleto, nunca
        # tratado como "sem achados".
        if "findings" not in data:
            return error(
                "findings ausente no payload completed — envie ao menos "
                "uma lista vazia pra um resultado honesto de 'nada encontrado'",
                400,
            )

        selected_frame_ids = [str(v) for v in (job.get("selected_frame_ids") or [])]
        terms_lookup = _terms_lookup(job.get("terms"))
        validated, validation_error = _validate_completed_findings(
            data.get("findings"), selected_frame_ids, terms_lookup,
        )
        if validated is None:
            return error(validation_error or "payload de achados inválido", 400)

        metrics = data.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {}

        repo.apply_callback_completed(job_id, len(validated), validated, metrics)

        return success({
            "job_id": job_id, "status": "completed", "findings_count": len(validated),
        })
    except Exception as exc:
        logger.error("search_callback_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --------------------------------------------------------------------------
# POST /api/v1/training/search/jobs/<id>/promote
# --------------------------------------------------------------------------

def _parse_promote_items(
    raw: Any, results_len: int,
) -> "tuple[list[dict] | None, str | None]":
    """Valida `items: [{index: int, class_name?: str}]` — `index` referencia
    a posição em `search_jobs.results` (o próprio job, nunca dados
    repetidos pelo cliente — mais robusto que reenviar frame/bbox). Índice
    fora de alcance, tipo errado, ou lista vazia → rejeita o payload
    INTEIRO (fail-closed, mesmo espírito da validação do callback)."""
    if not isinstance(raw, list) or not raw:
        return None, "items é obrigatório e não pode ser vazio"

    validated: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            return None, f"item inválido (não é objeto): {item!r}"

        index = item.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            return None, f"index inválido: {index!r}"
        if not (0 <= index < results_len):
            return None, f"index fora de alcance (0..{results_len - 1}): {index}"

        class_name_raw = item.get("class_name")
        class_name: "str | None" = None
        if class_name_raw is not None:
            class_name = str(class_name_raw).strip()
            if not class_name:
                return None, f"class_name inválido (vazio) no item index={index}"

        validated.append({"index": index, "class_name": class_name})
    return validated, None


def promote_search_findings_handler(job_id: str):
    """Promove achado(s) de um job de busca por conteúdo a proposta(s)
    pendente(s) em `training_frames.pre_annotations` (MERGE — nunca
    sobrescreve propostas pendentes de outro job/promoção anterior, ver
    `FrameRepository.append_pre_annotations`). Cross-tenant → 404 (C-01).
    ---
    tags:
      - training
    summary: Promove achados de busca por conteúdo a propostas pendentes
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          properties:
            items:
              type: array
              items:
                type: object
                properties:
                  index: {type: integer}
                  class_name: {type: string}
    responses:
      200:
        description: '{"promoted": N}'
    """
    try:
        tenant_id = get_tenant_id()
        repo = _get_search_repo()
        job = repo.get_by_id_and_tenant(job_id, tenant_id)
        if job is None:
            return error("Job de busca não encontrado", 404)

        results = job.get("results") or []
        if not isinstance(results, list):
            results = []

        data = request.get_json() or {}
        items, items_error = _parse_promote_items(data.get("items"), len(results))
        if items_error:
            return error(items_error, 400)

        proposals_by_frame: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            finding = results[item["index"]]
            class_name = item["class_name"] or str(finding.get("label") or "").strip()
            if not class_name:
                return error(
                    f"achado no index={item['index']} sem label e sem "
                    "class_name informado", 400,
                )
            frame_id = str(finding.get("frame_id") or "")
            proposals_by_frame.setdefault(frame_id, []).append({
                "bbox": finding.get("bbox"),
                "class": class_name,
                "confidence": finding.get("confidence"),
            })

        frame_repo = _get_frame_repo()
        promoted = 0
        for frame_id, proposals in proposals_by_frame.items():
            frame_repo.append_pre_annotations(frame_id, tenant_id, proposals)
            promoted += len(proposals)

        return success({"promoted": promoted})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("promote_search_findings_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
