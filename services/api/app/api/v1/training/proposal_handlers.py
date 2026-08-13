"""
Recognition — Propagation Proposal handlers (migration 118, grade de triagem).

Rotas (routes.py):
  GET  /api/v1/training/proposals                                grade paginada + facetas
  POST /api/v1/training/proposals/reject-batch                   rejeição por classe/confiança/seleção
  POST /api/v1/training/propagation/jobs/<job_id>/reject-proposals  wrapper fino → reject-batch com job_id
  POST /api/v1/training/proposals/<id>/reject                    rejeita uma (grade: X)
  POST /api/v1/training/proposals/<id>/accept                    aceita uma, com correção opcional (grade: A)

Segurança: escopo por get_tenant_id() (ADR-0017, sem fallback). Lote: ids de
outro tenant são silenciosamente ignorados no WHERE (C-01, sem 404/403 —
nunca vaza existência). Item único inexistente/cross-tenant → 404.
"""
import logging
from uuid import UUID

from flask import request

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.infrastructure.storage.local_storage import get_storage

from .helpers import get_annotation_service

logger = logging.getLogger(__name__)

_VALID_PROPOSAL_STATUS = frozenset({"pending", "accepted", "rejected", "corrected"})
_MAX_PAGE_SIZE = 200
_MAX_BATCH_IDS = 5000


def _get_pool():
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415

    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _get_proposal_repo():
    from app.infrastructure.database.repositories.propagation_proposal_repository import (  # noqa: PLC0415,E501
        PropagationProposalRepository,
    )

    return PropagationProposalRepository(_get_pool())


def _parse_csv_or_repeated(param: str) -> "list[str] | None":
    """Aceita `?<param>=a&<param>=b` (repetido) e/ou `?<param>=a,b` (CSV) —
    mesmo espírito de image_handlers._parse_camera_ids."""
    raw = request.args.getlist(param)
    if not raw:
        return None
    items = [part.strip() for item in raw for part in item.split(",") if part.strip()]
    return items or None


def _validate_uuid_list(
    raw, field_name: str,
) -> "tuple[list[str] | None, str | None]":
    """(ids normalizados, None) ou (None, mensagem de erro) — usado nos
    filtros de lote do body do reject-batch."""
    if raw is None:
        return None, None
    if not isinstance(raw, list) or not raw:
        return None, f"{field_name}, se informado, deve ser uma lista não vazia"
    if len(raw) > _MAX_BATCH_IDS:
        return None, f"{field_name}: máximo de {_MAX_BATCH_IDS} itens por lote"
    ids: "list[str]" = []
    for item in raw:
        try:
            ids.append(str(UUID(str(item))))
        except (ValueError, AttributeError, TypeError):
            return None, f"{field_name} inválido (esperado UUID): {item!r}"
    return ids, None


def _derive_reject_reason(
    job_id: "str | None", class_names: "list | None", confidence_lt: "float | None",
) -> str:
    """reason default quando o body não informa um explícito — ordem
    espelha o vocabulário do contrato (job > class > confidence > seleção
    manual, do critério mais amplo pro mais específico)."""
    if job_id:
        return "job"
    if class_names:
        return "class"
    if confidence_lt is not None:
        return "confidence"
    return "selection"


def list_proposals_handler():
    """Grade de triagem paginada de propostas de propagação/busca.

    Query params: status(=pending), job_id?, class_name?(CSV/repetível),
    confidence_min?, confidence_max?, camera_id?(CSV/repetível),
    sort?∈{confidence,class_name,created_at}(=confidence),
    order?∈{asc,desc}(=asc), page?(=1), page_size?(=60, máx 200).
    """
    try:
        tenant_id = get_tenant_id()

        status = request.args.get("status", "pending")
        if status not in _VALID_PROPOSAL_STATUS:
            return error(
                f"status inválido: {status!r} "
                f"(esperado: {sorted(_VALID_PROPOSAL_STATUS)})",
                400,
            )

        job_id = request.args.get("job_id")
        if job_id is not None:
            try:
                UUID(job_id)
            except ValueError:
                return error("job_id inválido (esperado UUID)", 400)

        class_names = _parse_csv_or_repeated("class_name")

        camera_ids = _parse_csv_or_repeated("camera_id")
        if camera_ids is not None:
            for cid in camera_ids:
                try:
                    UUID(cid)
                except ValueError:
                    return error(f"camera_id inválido (esperado UUID): {cid!r}", 400)

        confidence_min_raw = request.args.get("confidence_min")
        confidence_max_raw = request.args.get("confidence_max")
        try:
            confidence_min = (
                float(confidence_min_raw) if confidence_min_raw not in (None, "") else None
            )
            confidence_max = (
                float(confidence_max_raw) if confidence_max_raw not in (None, "") else None
            )
        except (TypeError, ValueError):
            return error("confidence_min/confidence_max devem ser numéricos", 400)

        sort = request.args.get("sort", "confidence")
        order = request.args.get("order", "asc")
        page = max(1, request.args.get("page", 1, type=int))
        page_size = min(
            _MAX_PAGE_SIZE, max(1, request.args.get("page_size", 60, type=int))
        )

        repo = _get_proposal_repo()
        result = repo.list_proposals(
            tenant_id,
            status=status,
            job_id=job_id,
            class_names=class_names,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            camera_ids=camera_ids,
            sort=sort,
            order=order,
            page=page,
            page_size=page_size,
        )

        storage = get_storage()
        for item in result.get("proposals", []):
            frame = item.get("frame") or {}
            r2_key = frame.get("r2_key")
            frame["url"] = None
            if r2_key:
                try:
                    frame["url"] = storage.generate_presigned_download_url(
                        r2_key, ttl=3600, response_content_type="image/jpeg",
                    )
                except Exception as url_exc:  # noqa: BLE001
                    logger.warning(
                        "proposal_presigned_url_failed: id=%s err=%s",
                        item.get("id"), url_exc,
                    )

        return success(result)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_proposals_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def reject_batch_handler():
    """Rejeição em lote por classe/confiança/seleção — POST /proposals/reject-batch.

    Body: {proposal_ids?, frame_ids?, job_id?, class_names?, confidence_lt?, reason?}
    Exige ao menos um filtro de escopo (senão 400 — nunca rejeitar tudo por
    acidente). proposal_ids/frame_ids ≤ 5000 itens.
    """
    try:
        tenant_id = get_tenant_id()
        user_id = get_current_user_id()
        data = request.get_json() or {}

        proposal_ids, err_msg = _validate_uuid_list(data.get("proposal_ids"), "proposal_ids")
        if err_msg:
            return error(err_msg, 400)
        frame_ids, err_msg = _validate_uuid_list(data.get("frame_ids"), "frame_ids")
        if err_msg:
            return error(err_msg, 400)

        job_id = data.get("job_id")
        if job_id is not None:
            try:
                job_id = str(UUID(str(job_id)))
            except (ValueError, AttributeError, TypeError):
                return error("job_id inválido (esperado UUID)", 400)

        class_names = data.get("class_names")
        if class_names is not None and (
            not isinstance(class_names, list) or not class_names
        ):
            return error("class_names, se informado, deve ser uma lista não vazia", 400)

        confidence_lt = data.get("confidence_lt")
        if confidence_lt is not None:
            try:
                confidence_lt = float(confidence_lt)
            except (TypeError, ValueError):
                return error("confidence_lt deve ser numérico", 400)

        if not any(
            [proposal_ids, frame_ids, job_id, class_names, confidence_lt is not None]
        ):
            return error(
                "Informe ao menos um filtro de escopo (proposal_ids, "
                "frame_ids, job_id, class_names ou confidence_lt) — "
                "rejeição sem filtro não é permitida", 400,
            )

        reason = str(
            data.get("reason") or _derive_reject_reason(job_id, class_names, confidence_lt)
        )[:40]

        repo = _get_proposal_repo()
        result = repo.reject_batch(
            tenant_id,
            user_id,
            reason=reason,
            proposal_ids=proposal_ids,
            frame_ids=frame_ids,
            job_id=job_id,
            class_names=class_names,
            confidence_lt=confidence_lt,
        )
        logger.info(
            "proposals_rejected_batch: tenant=%s reason=%s rejected=%d frames=%d",
            tenant_id, reason, result["rejected_count"], result["affected_frame_count"],
        )
        return success(result)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("reject_batch_proposals_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def reject_job_proposals_handler(job_id: str):
    """Wrapper fino → reject-batch com job_id fixo — POST
    /propagation/jobs/<job_id>/reject-proposals. Body opcional
    {class_names?, confidence_lt?}. reason='job' sempre."""
    try:
        tenant_id = get_tenant_id()
        user_id = get_current_user_id()

        try:
            job_uuid = str(UUID(job_id))
        except ValueError:
            return error("job_id inválido (esperado UUID)", 400)

        data = request.get_json(silent=True) or {}

        class_names = data.get("class_names")
        if class_names is not None and (
            not isinstance(class_names, list) or not class_names
        ):
            return error("class_names, se informado, deve ser uma lista não vazia", 400)

        confidence_lt = data.get("confidence_lt")
        if confidence_lt is not None:
            try:
                confidence_lt = float(confidence_lt)
            except (TypeError, ValueError):
                return error("confidence_lt deve ser numérico", 400)

        repo = _get_proposal_repo()
        result = repo.reject_batch(
            tenant_id,
            user_id,
            reason="job",
            job_id=job_uuid,
            class_names=class_names,
            confidence_lt=confidence_lt,
        )
        logger.info(
            "proposals_rejected_job: tenant=%s job=%s rejected=%d frames=%d",
            tenant_id, job_uuid, result["rejected_count"], result["affected_frame_count"],
        )
        return success(result)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("reject_job_proposals_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def reject_one_handler(proposal_id: str):
    """Rejeita uma única proposta — POST /proposals/<id>/reject (grade: X).
    reason='selection'. Cross-tenant/inexistente → 404 (C-01)."""
    try:
        tenant_id = get_tenant_id()
        user_id = get_current_user_id()

        try:
            UUID(proposal_id)
        except ValueError:
            return error("proposal_id inválido (esperado UUID)", 400)

        repo = _get_proposal_repo()
        row = repo.reject_one(tenant_id, user_id, proposal_id, reason="selection")
        if row is None:
            return error("Proposta não encontrada", 404)

        logger.info("proposal_rejected: tenant=%s id=%s", tenant_id, proposal_id)
        return success({"id": str(row["id"]), "status": row["status"]})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("reject_proposal_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def accept_one_handler(proposal_id: str):
    """Aceita (com correção opcional) uma única proposta — POST
    /proposals/<id>/accept (grade: A / corrigir-e-aprovar).

    Body opcional: {bbox: [cx, cy, w, h]} — caixa corrigida (0..1). Sem
    bbox: aceita a proposta tal como veio (status vira 'accepted'); com
    bbox diferente do original: 'corrected'.
    """
    try:
        tenant_id = get_tenant_id()
        user_id = get_current_user_id()

        try:
            UUID(proposal_id)
        except ValueError:
            return error("proposal_id inválido (esperado UUID)", 400)

        data = request.get_json(silent=True) or {}
        corrected_bbox = data.get("bbox")
        if corrected_bbox is not None:
            if not isinstance(corrected_bbox, list) or len(corrected_bbox) != 4:
                return error("bbox deve ser uma lista [cx, cy, w, h]", 400)
            try:
                corrected_bbox = [float(v) for v in corrected_bbox]
            except (TypeError, ValueError):
                return error("bbox deve conter valores numéricos", 400)
            if not all(0.0 <= v <= 1.0 for v in corrected_bbox):
                return error("bbox deve estar normalizado entre 0 e 1", 400)

        service = get_annotation_service()
        result = service.accept_proposal(tenant_id, user_id, proposal_id, corrected_bbox)

        logger.info(
            "proposal_accepted: tenant=%s id=%s status=%s",
            tenant_id, proposal_id, result["status"],
        )
        return success(result)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("accept_proposal_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
