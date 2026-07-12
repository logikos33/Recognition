"""
Recognition — DINO+SAM backend (pre-annotation-service, HTTP).

Proxy pro microserviço `pre-annotation-service/` (DINO+SAM). O microserviço
tem conexão própria ao Postgres e persiste `training_frames.pre_annotations`
diretamente — este backend só confirma o resultado, não escreve no banco.

Removido do caminho de produção em maio/2026 (commit e5582c9, "DINO+SAM
nunca usado em prod" — custo de GPU por chamada desproporcional à qualidade
observada). Disponível de novo só atrás da feature flag (ADR-0031, adendo) —
não é o backend default quando a flag liga.
"""
import logging
import os

import requests

from app.domain.services.pre_annotation.base import PreAnnotationBackend

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://pre-annotation-service:8080"
_DEFAULT_TIMEOUT_SECONDS = 30


class DinoSamHttpBackend(PreAnnotationBackend):
    """Chama POST /api/v1/pre-annotate/<frame_id> no pre-annotation-service."""

    def __init__(self, base_url: str | None = None, timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> None:
        self._base_url = (
            base_url or os.environ.get("PRE_ANNOTATION_URL", _DEFAULT_BASE_URL)
        ).rstrip("/")
        self._timeout = timeout

    def predict_and_store(self, frame_id: str, module_code: str) -> int:
        resp = requests.post(
            f"{self._base_url}/api/v1/pre-annotate/{frame_id}",
            timeout=self._timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success"):
            raise RuntimeError(body.get("error") or "pre-annotation falhou")
        data = body.get("data") or {}
        return int(data.get("annotations_count", 0))
