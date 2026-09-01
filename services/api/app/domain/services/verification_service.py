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
ADR-0065). Rajadas de câmera+classe (o modelo redetectando a mesma
pessoa/situação frame a frame) NÃO são removidas — só reordenadas: o
representante mais incerto de cada rajada aparece primeiro, os irmãos vêm
depois. `total`/`get_queue_count` conta TODO o trabalho real (candidatos
únicos, sem dedup) — ver `_candidatos_sql` e `get_human_queue`.

⚠️ Decisão de produto PENDENTE (não implementada aqui — perguntar ao Vitor):
julgar o representante de uma rajada deveria decidir a rajada inteira
(propagar o veredito pros irmãos)? Isso tornaria "quantos EVENTOS distintos"
a contagem certa de novo — mas grava veredito em alertas que ninguém olhou.
Até essa decisão, cada alerta é julgado individualmente e o contador mostra
o trabalho real (114 no tenant RVB), não os 15 eventos.
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
    #: não N eventos distintos. Usada SÓ para decidir quem aparece primeiro
    #: (`get_human_queue`) — nunca para excluir (`get_queue_count` conta
    #: todo mundo). Medido no DEV (tenant RVB): 114 alertas violação/
    #: verdict-NULL formam 15 rajadas (a maior com 32 itens, média 7,6) — é a
    #: janela usada nessa medição e a que fica valendo aqui. Documentar o
    #: número é o ponto: se precisar mudar, é decisão consciente, não default
    #: escondido.
    _DEDUP_WINDOW_SECONDS = 60

    #: `presence_class_names` ESCOPADO por módulo (ver docstring do método na
    #: própria AlertRepository — omitir `module_code` já foi bug real:
    #: catálogo global sem filtro vaza classes de OUTRO módulo, ex. `truck`/
    #: `pallet`/`forklift` de fueling lidas como conformidade de EPI).
    #: ponytail: hardcoded "epi" — é o único módulo com alertas reais hoje
    #: (RVB). Quando um tenant de fueling/quality tiver fila de verificação
    #: de verdade, isto precisa virar filtro por `a.module_code` na própria
    #: query (não só no catálogo), porque HOJE a query mistura alertas de
    #: todos os módulos do tenant sem filtrar por linha.
    _MODULE_CODE = "epi"

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
        """CTE base compartilhada entre `get_human_queue` e `get_queue_count`
        — o TRABALHO REAL: um alerta por linha, sem dedup nenhum.

        As DUAS têm de contar/listar exatamente o mesmo conjunto — o cético
        mediu contagem e lista divergindo porque só a lista tinha o filtro de
        conformidade. Critério:

          · `verification_verdict IS NULL` — critério honesto (não
            `needs_human`, ver docstring do módulo).
          · `NOT _IS_COMPLIANCE_SQL` (reuso de AlertRepository, ADR-0065) —
            exclui CONFORMIDADE. Medido no DEV: 302/416 (72,6%) dos alertas
            `verdict IS NULL` do tenant RVB são conformidade (ex.: "Protetor
            auditivo", 270 sozinho) — a fila de revisão HUMANA não é lugar
            pra confirmar o que o sistema já considera OK.

        `presence_names` (achado por `AlertRepository.presence_class_names`,
        JÁ escopado por `_MODULE_CODE`) é o `%s` embutido no texto do
        `_IS_COMPLIANCE_SQL` — quem monta os params tem de passá-lo na MESMA
        posição textual (depois do `camera_id`, se houver).

        `classe` (a do primeiro item de `violations` — imensa maioria dos
        alertas tem só 1) é exposta aqui porque `get_human_queue` precisa
        dela para agrupar rajada; `alerts.class_name` (coluna separada) é
        NULL em ~20% das linhas do DEV — não serve pro agrupamento.
        """
        camera_clause = "AND a.camera_id = %s " if camera_filtro else ""
        return f"""
            SELECT a.id, a.camera_id, a.created_at, a.confidence,
                   COALESCE(a.violations->0->>'class', '') AS classe
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
        """Lista TODO o trabalho real do tenant, ordenado pra maximizar
        eventos distintos vistos cedo (C-01) — nunca some ninguém.

        tenant_id é obrigatório — sem ele a fila vazaria alertas de todos os
        tenants (achado #14 do API_CONTRACT_MAP.md).

        Ordenação em DUAS camadas (achado do cético, rodada 3 — "o contador
        não pode mentir de novo"):

          1. `rank_na_rajada` — dentro de cada rajada (câmera+classe, gap
             ≤ `_DEDUP_WINDOW_SECONDS`), o alerta MAIS INCERTO vira rank 1.
             Um representante (rank 1) de CADA rajada aparece antes de
             qualquer rank 2 — maximiza quantos EVENTOS DISTINTOS o operador
             vê nos primeiros N cliques, sem esconder ninguém.
          2. Incerteza (`ABS(confidence - 0.5)`) desempata dentro da mesma
             camada — mesmo raciocínio de antes: os mais recentes medidos no
             DEV tinham confiança 0,90-1,00 (o modelo já tinha certeza) e
             bbox não-projetável.

        Nenhum alerta é FILTRADO por rajada — só reordenado. Julgar o
        representante NÃO decide os irmãos (nenhuma propagação de veredito
        aqui): eles continuam na fila, aparecem depois, e `get_queue_count`
        já os conta desde o início. Isso é deliberado — ver docstring do
        módulo sobre a decisão de produto pendente.
        """
        pool = _get_pool()
        if pool is None:
            return []

        presence_names = AlertRepository(pool).presence_class_names(tenant_id, self._MODULE_CODE)
        candidatos_sql = self._candidatos_sql(camera_filtro=bool(camera_id))

        query = f"""
            WITH candidatos AS ({candidatos_sql}),
            com_gap AS (
                SELECT *,
                       LAG(created_at) OVER (
                           PARTITION BY camera_id, classe ORDER BY created_at
                       ) AS anterior
                FROM candidatos
            ),
            sessoes AS (
                SELECT *,
                       SUM(CASE
                             WHEN anterior IS NULL
                                  OR EXTRACT(EPOCH FROM (created_at - anterior)) > %s
                             THEN 1 ELSE 0
                           END) OVER (
                           PARTITION BY camera_id, classe ORDER BY created_at
                       ) AS sessao_id
                FROM com_gap
            ),
            ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY camera_id, classe, sessao_id
                           ORDER BY ABS(COALESCE(confidence, 1.0) - 0.5) ASC, created_at ASC
                       ) AS rank_na_rajada
                FROM sessoes
            )
            SELECT a.*, cam.name AS camera_name
            FROM alerts a
            JOIN ranked r ON r.id = a.id
            LEFT JOIN public.cameras cam ON cam.id = a.camera_id
            ORDER BY r.rank_na_rajada ASC, ABS(COALESCE(a.confidence, 1.0) - 0.5) ASC
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

        Escopo: SOMENTE o alerta `alert_id`. Sem propagação para irmãos de
        rajada (`get_human_queue`) — decisão de produto pendente, ver
        docstring do módulo.
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
                # COALESCE, não sobrescrita direta: re-julgar (mudança de
                # ideia é permitida de propósito, ver docstring) sem motivo é
                # o atalho de lista (Eventos.tsx, Acoes.tsx,
                # AlertsHistoryPage.tsx) — NUNCA manda `reason`. Sobrescrever
                # com `%s` puro apagava (NULL) um motivo estruturado já
                # gravado pela tela de Verificação a cada re-julgamento pelo
                # atalho — dado de calibração perdido em silêncio (achado do
                # cético). `reason` só troca o valor quando de fato vem um.
                "verification_reason = COALESCE(%s, verification_reason) "
                "WHERE id = %s AND tenant_id = %s",
                (status, verdict, f"user:{user_id}", reason or None,
                 alert_id, tenant_id),
            )
            affected = cur.rowcount

        logger.info("human_review: alert=%s verdict=%s user=%s", alert_id, verdict, user_id)
        return affected > 0

    def get_queue_count(self, tenant_id: str, camera_id: str | None = None) -> int:
        """Conta o TRABALHO REAL do tenant — todo alerta candidato, sem
        dedup de rajada (C-01).

        Achado do cético (rodada 3): contar só os representantes (15 no
        tenant RVB) fazia "N RESTANTES" cair pra 0 assim que os 15 fossem
        julgados, enquanto 99 alertas (os irmãos de rajada, nunca julgados)
        continuavam no banco — "Fila zerada" mentindo de novo, a MESMA classe
        de bug que abriu esta rodada. Contagem honesta = 114 (todo alerta
        candidato); `get_human_queue` só REORDENA pra mostrar 1 representante
        de cada rajada primeiro — nunca filtra.

        `camera_id` opcional para casar exatamente com o filtro de
        `get_human_queue` quando o chamador escopa por câmera — contagem e
        lista com WHERE divergente é a MESMA classe de bug do parágrafo
        acima. Ver `_candidatos_sql` para o critério completo.
        """
        pool = _get_pool()
        if pool is None:
            return 0

        presence_names = AlertRepository(pool).presence_class_names(tenant_id, self._MODULE_CODE)
        candidatos_sql = self._candidatos_sql(camera_filtro=bool(camera_id))

        query = f"""
            WITH candidatos AS ({candidatos_sql})
            SELECT COUNT(*) AS total FROM candidatos
        """
        params: list = [tenant_id]
        if camera_id:
            params.append(camera_id)
        params.append(presence_names)

        # Mesma razão de get_human_queue: 0 é uma contagem legítima, não "não
        # sei" — exceção SOBE, não vira 0 em silêncio (`AS total` + acesso por
        # NOME porque o pool usa RealDictCursor).
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            row = cur.fetchone()
            return int(row["total"]) if row else 0
