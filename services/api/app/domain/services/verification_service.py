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
        tenant_id: str,
        limit: int = 50,
        camera_id: str | None = None,
    ) -> list[dict]:
        """Lista alertas needs_human do tenant, mais recentes primeiro (C-01).

        tenant_id é obrigatório — sem ele a fila vazaria alertas needs_human
        de todos os tenants (achado #14 do API_CONTRACT_MAP.md).
        """
        pool = _get_pool()
        if pool is None:
            return []

        base_query = (
            "SELECT a.*, c.name AS camera_name "
            "FROM alerts a "
            "LEFT JOIN cameras c ON c.id = a.camera_id "
            "WHERE a.verification_status = 'needs_human' AND a.tenant_id = %s "
        )
        params: list = [tenant_id]
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
        tenant_id: str,
        reason: str | None = None,
    ) -> bool:
        """Operador confirma (approve) ou rejeita (reject) um alerta do tenant.

        O veredito humano vale para QUALQUER alerta do tenant, não só os que a
        IA marcou como `needs_human`: nada chama `submit_for_verification`, a
        fila da IA nunca é alimentada, e a cláusula antiga
        (`AND verification_status = 'needs_human'`) fazia esta rota devolver
        404 para 100% dos alertas reais — por isso `verification_verdict` está
        NULL nos 334 alertas do shadow. Revisão é a tela de detalhe, não só a
        fila. Re-revisão é permitida de propósito (operador muda de ideia);
        `verified_at` carimba a ÚLTIMA decisão.

        tenant_id é obrigatório e faz parte do WHERE — um alerta de outro
        tenant não bate a condição, rowcount fica 0 e a rota trata isso como
        404 (achado #14 do API_CONTRACT_MAP.md: sem isso, um operador de um
        tenant podia revisar/editar alertas de outro tenant via IDOR).
        """
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
                "verified_at = NOW(), verified_by = %s, "
                # A justificativa é o que alimenta a recalibração de limiar
                # depois ("errou porque a caixa pegou a luva do outro"). A rota
                # já aceitava `reason` no corpo e o descartava em silêncio.
                "verification_reason = %s "
                "WHERE id = %s AND tenant_id = %s",
                (status, verdict, f"user:{user_id}", reason or None,
                 alert_id, tenant_id),
            )
            affected = cur.rowcount

        logger.info("human_review: alert=%s verdict=%s user=%s", alert_id, verdict, user_id)
        return affected > 0

    def get_queue_count(self, tenant_id: str) -> int:
        """Conta alertas pendentes de revisão humana do tenant (badge na nav, C-01)."""
        pool = _get_pool()
        if pool is None:
            return 0
        try:
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM alerts "
                    "WHERE verification_status = 'needs_human' AND tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0
