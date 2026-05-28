"""
DOMAIN verification_service.py — Fila de verificação humana de alertas.

Fluxo automatizado:
  1. Claude pré-analisa alertas de baixa confiança
  2. "approve" e "reject" resolvem automaticamente
  3. "needs_human" vai para a fila visível ao operador
  4. Operador confirma ou rejeita o que a IA deixou pendente

O operador NUNCA vê os aprovados/rejeitados automaticamente.
"""
import logging
from datetime import datetime
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)


def _get_pool():
    return DatabasePool.get_instance()


class VerificationService:

    def submit_for_verification(
        self,
        alert_id: str,
        camera_id: str,
        class_name: str,
        confidence: float,
        module_code: str = "epi",
    ) -> None:
        """Dispara Celery task de verificação. Fire-and-forget."""
        try:
            from app.infrastructure.queue.tasks.verification import verify_alert  # noqa: PLC0415
            verify_alert.delay(
                alert_id=alert_id,
                camera_id=camera_id,
                class_name=class_name,
                confidence=confidence,
                module_code=module_code,
            )
            logger.info("verification_submitted: alert=%s", alert_id)
        except Exception as exc:
            logger.error("verification_submit_error: alert=%s err=%s", alert_id, exc)

    def get_human_queue(
        self,
        limit: int = 50,
        camera_id: str | None = None,
    ) -> list[dict]:
        """Lista alertas needs_human, mais recentes primeiro."""
        pool = _get_pool()
        if pool is None:
            return []

        base_query = (
            "SELECT a.*, c.name AS camera_name "
            "FROM alerts a "
            "LEFT JOIN ip_cameras c ON c.id = a.camera_id "
            "WHERE a.verification_status = 'needs_human' "
        )
        params: list = []
        if camera_id:
            base_query += "AND a.camera_id = %s "
            params.append(camera_id)
        base_query += "ORDER BY a.created_at DESC LIMIT %s"
        params.append(limit)

        try:
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(base_query, tuple(params))
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("human_queue_error: %s", exc)
            return []

    def human_review(
        self,
        alert_id: str,
        verdict: str,
        user_id: str,
    ) -> bool:
        """Operador confirma (approve) ou rejeita (reject) alerta needs_human."""
        if verdict not in ("approve", "reject"):
            raise ValueError("verdict deve ser 'approve' ou 'reject'")

        status = "human_approved" if verdict == "approve" else "human_rejected"
        pool = _get_pool()
        if pool is None:
            raise RuntimeError("Database não disponível")

        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE alerts SET "
                "verification_status = %s, verification_verdict = %s, "
                "verified_at = NOW(), verified_by = %s "
                "WHERE id = %s AND verification_status = 'needs_human'",
                (status, verdict, f"user:{user_id}", alert_id),
            )
            affected = cur.rowcount

        logger.info("human_review: alert=%s verdict=%s user=%s", alert_id, verdict, user_id)
        return affected > 0

    def get_queue_count(self) -> int:
        """Conta alertas pendentes de revisão humana (para badge na nav)."""
        pool = _get_pool()
        if pool is None:
            return 0
        try:
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM alerts WHERE verification_status = 'needs_human'")
                row = cur.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0
