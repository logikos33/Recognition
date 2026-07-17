"""
Service: sessões de inspeção da integração monofatura (task-108, ADR-0053).

Inbound:  peça bipada (ID) → open_session idempotente por (piece_id, stage).
Outbound: complete_stage fecha a sessão e dispara o adapter plugável com
          evidência + resultado por atributo + tempo de etapa.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.domain.services.monofatura_adapter import (
    MonofaturaAdapter,
    get_monofatura_adapter,
)
from app.infrastructure.database.repositories.inspection_session_repository import (
    InspectionSessionRepository,
)

logger = logging.getLogger(__name__)


class InspectionService:
    """Orquestra sessões de inspeção + outbound monofatura por tenant schema."""

    def __init__(
        self,
        repo: InspectionSessionRepository,
        adapter: MonofaturaAdapter | None = None,
    ) -> None:
        self._repo = repo
        self._adapter = adapter or get_monofatura_adapter()

    def open_session(
        self,
        schema: str,
        piece_id: str,
        stage: str,
        camera_id: str | None = None,
    ) -> dict[str, Any]:
        """Bipagem: abre (ou retorna) a sessão da peça×etapa — idempotente."""
        session = self._repo.open_session(schema, piece_id, stage, camera_id)
        logger.info(
            "inspection_session_open: piece=%s stage=%s id=%s status=%s",
            piece_id, stage, session["id"], session["status"],
        )
        return session

    def complete_stage(
        self,
        schema: str,
        piece_id: str,
        stage: str,
        result: dict[str, Any],
        evidence_r2_key: str | None = None,
        elapsed_s: float | None = None,
    ) -> dict[str, Any] | None:
        """Fecha a etapa, persiste resultado e dispara o outbound.

        result esperado: {"ok": bool, "attributes": [{"name", "ok", ...}, ...]}
        (lista de pontos de atenção = input do cliente, plugável — task-109).
        Retorna a sessão fechada ou None se a sessão não existir (rota → 404).
        """
        finished_at = datetime.now(timezone.utc).isoformat()
        enriched = dict(result)
        if elapsed_s is not None:
            enriched["elapsed_s"] = elapsed_s
        session = self._repo.complete_session(
            schema, piece_id, stage, json.dumps(enriched), evidence_r2_key
        )
        if session is None:
            return None
        delivered = self._adapter.send_stage_result({
            "piece_id": piece_id,
            "stage": stage,
            "result": result,
            "evidence_r2_key": evidence_r2_key or session.get("evidence_r2_key"),
            "elapsed_s": elapsed_s,
            "finished_at": finished_at,
        })
        if not delivered:
            logger.warning(
                "monofatura_outbound_failed: piece=%s stage=%s (resultado "
                "persistido; reenvio é responsabilidade do adapter real)",
                piece_id, stage,
            )
        return session

    def list_sessions(
        self, schema: str, piece_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        return self._repo.list_sessions(schema, piece_id, limit)
