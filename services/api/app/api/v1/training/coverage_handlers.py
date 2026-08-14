"""Handler: matriz de cobertura de anotação por câmera (Volta 1).

"Quantas imagens por câmera têm anotadas, para haver equilíbrio entre todas as
câmeras." A célula zerada é a informação mais valiosa: mostra o buraco.
"""
import logging

from flask import request

from app.core.auth import get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.domain.services.coverage_service import build_coverage
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)

logger = logging.getLogger(__name__)


def _get_annotation_repo() -> AnnotationRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AnnotationRepository(pool)


def get_coverage_matrix_handler():
    """Matriz classe × câmera de anotação — equilíbrio da base (Volta 1).

    Conta IGUAL ao export de treino (só humana/auto_aprovada, sem classe
    arquivada, sem frame excluído — mesmo universo de _fetch_annotations).
    Escopo por tenant do JWT (get_tenant_id() — sem fallback silencioso,
    ADR-0017): a matriz é sempre do tenant do contexto assumido, nunca vaza
    câmera de outro tenant.

    Query: module (default 'epi').
    Resposta: success({targets, totals, classes, cameras, matrix, gaps,
                       needs_collection, imbalance, warnings}).
    """
    try:
        tenant_id = get_tenant_id()
        module_code = request.args.get("module", "epi")
        repo = _get_annotation_repo()
        raw = repo.get_coverage_matrix(
            tenant_id=str(tenant_id), module_code=module_code
        )
        return success(build_coverage(raw))
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_coverage_matrix_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
