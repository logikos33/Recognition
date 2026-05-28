"""
DOMAIN counting_service.py — Sessões de contagem com anti-duplicata via track_id.

Fluxo:
  1. start_session(camera_id, module_code) → cria sessão, retorna session_id
  2. record_detection(session_id, track_id, class_name, confidence)
     → upsert idempotente por track_id (DeepSORT garante unicidade)
  3. stop_session(session_id) → finaliza, retorna totais agregados

O track_id vem do DeepSORT no inference-service. Cada objeto físico recebe
um track_id único por sessão — sem duplicatas mesmo com múltiplas detecções.
"""
import logging
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.infrastructure.database.repositories.counting_repository import CountingRepository

logger = logging.getLogger(__name__)


class CountingService:

    def __init__(self, repo: CountingRepository) -> None:
        self._repo = repo

    def start_session(
        self,
        tenant_id: UUID,
        camera_id: UUID,
        module_code: str,
    ) -> dict:
        """Cria nova sessão de contagem. Retorna session dict."""
        if not module_code:
            raise ValidationError("module_code é obrigatório")
        session = self._repo.create_session(tenant_id, camera_id, module_code)
        logger.info(
            "counting_session_started: id=%s camera=%s module=%s",
            session["id"], camera_id, module_code,
        )
        return session

    def stop_session(self, session_id: UUID, tenant_id: UUID) -> dict:
        """Encerra sessão e retorna totais agregados por classe."""
        session = self._repo.get_session(session_id)
        if not session:
            raise NotFoundError(f"Sessão {session_id} não encontrada")
        if str(session["tenant_id"]) != str(tenant_id):
            raise NotFoundError(f"Sessão {session_id} não encontrada")

        # Aggregate counts from events
        rows = self._repo.get_session_counts(session_id)
        total_counts = {r["class_name"]: r["count"] for r in rows}

        updated = self._repo.stop_session(session_id, total_counts)
        logger.info(
            "counting_session_stopped: id=%s counts=%s",
            session_id, total_counts,
        )
        return updated or session  # type: ignore[return-value]

    def record_detection(
        self,
        session_id: UUID,
        track_id: int,
        class_name: str,
        confidence: float,
    ) -> None:
        """Registra (ou atualiza) uma detecção rastreada. Idempotente por track_id."""
        try:
            self._repo.upsert_event(session_id, track_id, class_name, confidence)
        except Exception as exc:
            logger.warning("counting_record_error: session=%s track=%s err=%s", session_id, track_id, exc)

    def get_live_stats(self, session_id: UUID, tenant_id: UUID) -> dict:
        """Retorna contagens ao vivo por classe."""
        session = self._repo.get_session(session_id)
        if not session:
            raise NotFoundError(f"Sessão {session_id} não encontrada")
        if str(session["tenant_id"]) != str(tenant_id):
            raise NotFoundError(f"Sessão {session_id} não encontrada")

        rows = self._repo.get_session_counts(session_id)
        counts = {r["class_name"]: r["count"] for r in rows}
        return {
            "session_id": str(session_id),
            "status": session["status"],
            "started_at": session["started_at"].isoformat() if session.get("started_at") else None,
            "counts": counts,
            "total": sum(counts.values()),
        }

    def list_active(self, tenant_id: UUID) -> list[dict]:
        return self._repo.list_active_sessions(tenant_id)
