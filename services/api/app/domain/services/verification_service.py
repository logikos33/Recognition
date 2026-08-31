"""
DOMAIN verification_service.py — Fila de verificação humana de alertas.

Fluxo desenhado (triagem por IA — atualmente NÃO conclui no worker, ver
get_human_queue):
  1. Claude pré-analisa alertas de baixa confiança
  2. "approve" e "reject" resolvem automaticamente (verdict terminal)
  3. "needs_human" é ESTADO DE TRIAGEM, não veredito — fica visível ao operador
  4. Operador confirma ou rejeita o que a IA deixou pendente

Fluxo real hoje: a triagem por IA quase nunca conclui, então a fila mostra
todo alerta ainda sem veredito TERMINAL (`verification_verdict IS NULL`) —
humano ou IA. O operador NUNCA vê os aprovados/rejeitados automaticamente.

A fila também exclui CONFORMIDADE (reuso de `AlertRepository._IS_COMPLIANCE_SQL`,
ADR-0065) e colapsa rajadas repetidas da mesma câmera+classe numa janela curta
num único representante — ver `_candidatos_sql`.
"""
import logging

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)


def _get_pool():
    return DatabasePool.get_instance()


class VerificationService:

    #: Alertas da MESMA câmera+classe que se repetem dentro desta janela são
    #: uma rajada — o modelo redetecta a mesma pessoa/situação frame a frame,
    #: não N eventos distintos. Medido no DEV (tenant RVB): 114 alertas
    #: violação/verdict-NULL colapsam para 15 eventos distintos com 60s — é a
    #: janela usada nessa medição e a que fica valendo aqui. Documentar o
    #: número é o ponto: se precisar mudar, é decisão consciente, não default
    #: escondido.
    _DEDUP_WINDOW_SECONDS = 60

    def submit_for_verification(
        self,
        alert_id: str,
        camera_id: str,
        class_name: str,
        confidence: float,
        tenant_id: str,
        module_code: str = "epi",
    ) -> None:
        """Dispara Celery task de verificação. Fire-and-forget.

        `tenant_id` é obrigatório (C-01): `verify_alert` grava o veredito da
        IA de volta no alerta, e o UPDATE lá precisa do tenant no WHERE para
        não escrever cross-tenant por um `alert_id` adivinhado.
        """
        try:
            from app.infrastructure.queue.tasks.verification import verify_alert  # noqa: PLC0415
            verify_alert.delay(
                alert_id=alert_id,
                camera_id=camera_id,
                class_name=class_name,
                confidence=confidence,
                tenant_id=tenant_id,
                module_code=module_code,
            )
            logger.info("verification_submitted: alert=%s", alert_id)
        except Exception as exc:
            logger.error("verification_submit_error: alert=%s err=%s", alert_id, exc)

    def _candidatos_sql(self, camera_filtro: bool) -> str:
        """CTE compartilhada entre `get_human_queue` e `get_queue_count`.

        As DUAS têm de usar o MESMO texto de WHERE — o cético mediu contagem
        e lista divergindo porque só a lista tinha o filtro de conformidade e
        o dedup. Devolve `(id, gap)` por alerta candidato:

          · `verification_verdict IS NULL` — critério honesto (não
            `needs_human`, ver docstring do módulo).
          · `NOT _IS_COMPLIANCE_SQL` (reuso de AlertRepository, ADR-0065) —
            exclui CONFORMIDADE. Medido no DEV: 302/416 (72,6%) dos alertas
            `verdict IS NULL` do tenant RVB são conformidade (ex.: "Protetor
            auditivo", 270 sozinho) — a fila de revisão HUMANA não é lugar
            pra confirmar o que o sistema já considera OK.
          · `gap` = tempo desde o alerta anterior da MESMA câmera+classe
            (LAG). `gap IS NULL OR gap > _DEDUP_WINDOW_SECONDS` no chamador
            mantém só o PRIMEIRO de cada rajada — ver `_DEDUP_WINDOW_SECONDS`.
            A classe usada é a do primeiro item de `violations` (imensa
            maioria dos alertas tem só 1); `alerts.class_name` (coluna
            separada) é NULL em ~20% das linhas do DEV — não serve pra dedup.

        `presence_names` (achado por `AlertRepository.presence_class_names`)
        é o `%s` embutido no texto do `_IS_COMPLIANCE_SQL` — quem monta os
        params tem de passá-lo na MESMA posição textual (depois do
        `camera_id`, se houver).
        """
        camera_clause = "AND a.camera_id = %s " if camera_filtro else ""
        return f"""
            SELECT a.id,
                   (a.created_at - LAG(a.created_at) OVER (
                       PARTITION BY a.camera_id, COALESCE(a.violations->0->>'class', '')
                       ORDER BY a.created_at
                   )) AS gap
            FROM alerts a
            WHERE a.verification_verdict IS NULL
              AND a.tenant_id = %s
              {camera_clause}
              AND NOT {AlertRepository._IS_COMPLIANCE_SQL}
        """  # noqa: SLF001 — reuso deliberado do predicado (pedido: "reuse, não reescreva")

    def get_human_queue(
        self,
        tenant_id: str,
        limit: int = 50,
        camera_id: str | None = None,
    ) -> list[dict]:
        """Lista alertas aguardando revisão do tenant, mais incertos primeiro (C-01).

        tenant_id é obrigatório — sem ele a fila vazaria alertas de todos os
        tenants (achado #14 do API_CONTRACT_MAP.md).

        Ordena por incerteza (`ABS(confidence - 0.5)` — o modelo mais em
        dúvida primeiro), não por `created_at`: com `LIMIT 50` e centenas de
        candidatos, a ordem decide QUAIS 50 aparecem, não só a sequência. Os
        50 mais recentes medidos no DEV tinham confiança 0,90-1,00 (o modelo
        já tem certeza) e bbox não-projetável — o operador nunca alcançava os
        casos realmente ambíguos (confiança 0,2-0,8) sem primeiro julgar
        dezenas de itens óbvios.

        Ver `_candidatos_sql` para o critério completo (verdict NULL +
        exclusão de conformidade + dedup de rajada).
        """
        pool = _get_pool()
        if pool is None:
            return []

        presence_names = AlertRepository(pool).presence_class_names(tenant_id)
        candidatos_sql = self._candidatos_sql(camera_filtro=bool(camera_id))

        query = f"""
            WITH candidatos AS ({candidatos_sql})
            SELECT a.*, cam.name AS camera_name
            FROM alerts a
            JOIN candidatos k ON k.id = a.id
            LEFT JOIN public.cameras cam ON cam.id = a.camera_id
            WHERE k.gap IS NULL OR EXTRACT(EPOCH FROM k.gap) > %s
            ORDER BY ABS(COALESCE(a.confidence, 1.0) - 0.5) ASC
            LIMIT %s
        """
        # `public.cameras`, não `cameras`: o pool é compartilhado entre
        # schemas (rvb/dev/admin.cameras também existe) e um search_path de
        # outra query na mesma conexão bastaria pra casar com a tabela
        # errada — ver ADR-0004 (schema-per-tenant).
        params: list = [tenant_id]
        if camera_id:
            params.append(camera_id)
        params.append(presence_names)
        params.append(self._DEDUP_WINDOW_SECONDS)
        params.append(limit)

        # ⚠️ NÃO engolir: `[]` significa "fila vazia", e a tela escreve
        # exatamente isso ("Nenhum alerta aguardando revisão humana"). Com o
        # erro capturado aqui, a rota respondia 200 e o `catch` da página nunca
        # disparava — o operador lia "vazia", ia embora, e os alertas de baixa
        # confiança ficavam invisíveis, com o badge repetindo 0 a cada 15s.
        #
        # O caminho honesto já existe nas DUAS pontas: a rota tem
        # `except Exception -> error(..., 500)` e a página tem `catch`. Só o
        # `return []` daqui impedia que fossem alcançados.
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]

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

    def get_queue_count(self, tenant_id: str, camera_id: str | None = None) -> int:
        """Conta alertas pendentes de revisão humana do tenant (C-01).

        `camera_id` opcional para casar exatamente com o filtro de
        `get_human_queue` quando o chamador escopa por câmera — contagem e
        lista com WHERE divergente é a MESMA classe de bug que o filtro
        fantasma `needs_human`: um número que não bate com o que a tela
        mostra. Ver `_candidatos_sql` para o critério completo.
        """
        pool = _get_pool()
        if pool is None:
            return 0

        presence_names = AlertRepository(pool).presence_class_names(tenant_id)
        candidatos_sql = self._candidatos_sql(camera_filtro=bool(camera_id))

        query = f"""
            WITH candidatos AS ({candidatos_sql})
            SELECT COUNT(*) AS total FROM candidatos k
            WHERE k.gap IS NULL OR EXTRACT(EPOCH FROM k.gap) > %s
        """
        params: list = [tenant_id]
        if camera_id:
            params.append(camera_id)
        params.append(presence_names)
        params.append(self._DEDUP_WINDOW_SECONDS)

        # Mesma razão de get_human_queue: 0 é uma contagem legítima, não "não
        # sei" — exceção SOBE, não vira 0 em silêncio (`AS total` + acesso por
        # NOME porque o pool usa RealDictCursor).
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            row = cur.fetchone()
            return int(row["total"]) if row else 0
