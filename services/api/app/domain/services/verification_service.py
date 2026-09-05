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

Contrato A1: o CONJUNTO aqui não muda — classe de polaridade INDECIDIDA
(`is_violation IS NULL`, ou fora do catálogo) CONTINUA na fila, é justamente
o que precisa de um humano decidindo. Só a leitura de `AlertRepository.
list_with_filters` deixou de chamá-la de 'violation' (virou 'observacao',
ver `_IS_VIOLATION_SQL`); esta fila não devolve `event_kind` nenhum, então
não havia rótulo pra corrigir aqui — o item chega com a classe crua
(`violations[0].class`) e cabe à tela não afirmar polaridade que não veio.

⚠️ Decisão de produto PENDENTE (não implementada aqui — perguntar ao Vitor):
julgar o representante de uma rajada deveria decidir a rajada inteira
(propagar o veredito pros irmãos)? Isso tornaria "quantos EVENTOS distintos"
a contagem certa de novo — mas grava veredito em alertas que ninguém olhou.
Até essa decisão, cada alerta é julgado individualmente e o contador mostra
o trabalho real (114 no tenant RVB), não os 15 eventos.
"""
import hashlib
import logging
from datetime import datetime, timezone

from app.core.exceptions import ConflictError
from app.core.rajada import DEDUP_WINDOW_SECONDS
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)


#: Prefixo que `human_review` grava em `verified_by` — a ÚNICA prova de que
#: quem julgou foi GENTE (`tasks/verification.py` grava 'claude-haiku' na mesma
#: coluna). O front lê a mesma regra em `VereditoHumano.tsx`.
_PREFIXO_HUMANO = "user:"


def _ha_quanto_tempo(quando: datetime | None) -> str:
    """Texto relativo ("há 2 minutos") pro aviso de conflito.

    Relativo, não data absoluta: o operador precisa saber se foi AGORA (o
    colega ao lado, na mesma fila) ou semana passada. `verified_at` é
    `timestamptz`; datetime naive (mock/teste antigo) é lido como UTC.
    """
    if quando is None:
        return "antes de você"
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    segundos = int((datetime.now(timezone.utc) - quando).total_seconds())
    if segundos < 60:
        return "agora há pouco"
    if segundos < 3600:
        m = segundos // 60
        return f"há {m} minuto{'s' if m > 1 else ''}"
    if segundos < 86400:
        h = segundos // 3600
        return f"há {h} hora{'s' if h > 1 else ''}"
    return f"em {quando.astimezone().strftime('%d/%m/%Y %H:%M')}"


def _quem_julgou(verified_by: str | None, autor_nome: str | None) -> str:
    """Nome de quem já julgou. NUNCA o UUID cru (`user:<uuid>` é id interno —
    mesma regra de `EventoDetalhe`/`correcao_ultima`: mostra-se NOME).

    Só pessoa chega aqui: veredito sem o prefixo `user:` (a IA) NÃO bloqueia o
    UPDATE, logo nunca vira conflito. Os dois ramos abaixo são a rede: nome
    apagado do banco → "Outro operador", nunca o UUID na tela.
    """
    if autor_nome:
        return autor_nome
    if verified_by and not verified_by.startswith(_PREFIXO_HUMANO):
        # Inalcançável pela guarda atual (veredito de máquina é sobrescrevível)
        return "A verificação automática"
    return "Outro operador"


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
    #: escondido. Valor vem de `app.core.rajada` (ux2/dedup) — fonte única
    #: compartilhada com `AlertRepository.list_with_filters` (`total_situacoes`).
    _DEDUP_WINDOW_SECONDS = DEDUP_WINDOW_SECONDS

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

    #: RODÍZIO DE FILA (bloco 4). A fila é determinística: mesma ordem, mesmo
    #: `LIMIT` → dois operadores abriam o MESMO alerta e duplicavam 100% do
    #: trabalho. Aqui a lista continua a MESMA (ninguém some, `get_queue_count`
    #: não muda) — só o ponto de partida gira por usuário: as posições são
    #: distribuídas em `_TRILHAS` faixas e cada operador começa pela sua.
    #: Com 3 operadores (RVB, segunda) em trilhas DIFERENTES eles abrem 1º, 3º
    #: e 2º item da fila em vez dos três o mesmo. Medido (segundo cético): a
    #: trilha é hash do id, então 3 operadores caem em 3 trilhas distintas em
    #: ~22% dos sorteios e dois deles dividem trilha em ~1/3 das duplas — isto
    #: REDUZ a colisão, não a elimina. A garantia dura é o 409 do
    #: `human_review`; o rodízio é só o que evita chegar nele o tempo todo.
    #: ponytail: constante, não contagem de sessões ativas — 3 é o time real
    #: da RVB. Se um dia importar de verdade quantos estão logados, é aqui que
    #: o número deixa de ser fixo (nada mais muda).
    _TRILHAS = 3

    @classmethod
    def _trilha(cls, user_id: str | None) -> int:
        """Faixa (0.._TRILHAS-1) do operador — estável entre polls.

        Estável é requisito, não detalhe: a tela reabastece por dedup de id
        (`anexarSemRepetir`) e NUNCA reordena o que já está na tela; um offset
        que mudasse a cada request faria a ordem dançar entre os polls de 15s.
        Hash do id, não `random`.
        """
        if not user_id:
            return 0
        digest = hashlib.blake2b(user_id.encode(), digest_size=4).hexdigest()
        return int(digest, 16) % cls._TRILHAS

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
        user_id: str | None = None,
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

          3. `trilha` — rodízio por operador (`_trilha`), aplicado DENTRO da
             camada 1, nunca por cima dela: as posições são repartidas em
             `_TRILHAS` faixas e cada operador começa pela SUA. Com 3
             operadores na mesma fila eles abrem representantes DIFERENTES
             (1º, 3º e 2º da lista) em vez dos três o mesmo — e todo
             representante continua vindo antes de qualquer irmão de rajada.
             Ninguém é filtrado: cada um vê a fila inteira, só a partir de um
             ponto diferente.

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
            ),
            ordenados AS (
                SELECT id, rank_na_rajada,
                       ROW_NUMBER() OVER (
                           ORDER BY rank_na_rajada ASC, ABS(COALESCE(confidence, 1.0) - 0.5) ASC, id ASC
                       ) AS pos
                FROM ranked
            )
            SELECT a.*, cam.name AS camera_name
            FROM alerts a
            JOIN ordenados o ON o.id = a.id
            LEFT JOIN public.cameras cam ON cam.id = a.camera_id
            ORDER BY o.rank_na_rajada ASC, (o.pos - 1 + %s) %% %s, o.pos
            LIMIT %s
        """
        # `pos` materializa a ordem canônica (rajada → incerteza → id) numa
        # coluna, e o `ORDER BY` de fora a GIRA por trilha DENTRO do tier.
        # Três decisões deliberadas:
        #   · `o.rank_na_rajada` continua sendo a PRIMEIRA chave — o rodízio
        #     não pode desfazer a camada 1 (todo representante de rajada antes
        #     de qualquer irmão). Girar a lista inteira intercalaria irmão
        #     entre representantes, que é a ordem que a rodada 1 já reprovou.
        #   · `id ASC` fecha o desempate — sem ele, empate de incerteza saía
        #     em ordem livre do Postgres e `pos` (logo, a trilha) mudava
        #     entre polls do MESMO usuário.
        #   · `%%` é `%` literal pro psycopg2 (o operador módulo), não um
        #     placeholder.
        # `public.cameras`, não `cameras`: o pool é compartilhado entre
        # schemas (rvb/dev/admin.cameras também existe) e um search_path de
        # outra query na mesma conexão bastaria pra casar com a tabela
        # errada — ver ADR-0004 (schema-per-tenant).
        params: list = [tenant_id]
        if camera_id:
            params.append(camera_id)
        params.append(presence_names)
        params.append(self._DEDUP_WINDOW_SECONDS)
        params.append(self._trilha(user_id))
        params.append(self._TRILHAS)
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
            itens = [dict(row) for row in cur.fetchall()]

        # `a.*` já traz `violations_historico` (migration 126) — projeta a
        # MESMA autoria que GET/PATCH de alerts expõem (ADR-0066). Sem isto o
        # badge "corrigido por X" só sobrevivia na sessão do PATCH e sumia da
        # tela ao recarregar a fila (achado do cético, rodada 2).
        for item in itens:
            item["correcao_ultima"] = AlertRepository.ultima_correcao(
                item.get("violations_historico")
            )
        return itens

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
        fila. Re-revisão PELO PRÓPRIO AUTOR é permitida de propósito (operador
        muda de ideia); `verified_at` carimba a ÚLTIMA decisão.

        Retorno / erros:
          · `True`  — gravou.
          · `False` — alerta não existe neste tenant (a rota traduz em 404).
          · `ConflictError` (409) — OUTRA PESSOA já julgou; a mensagem diz
            quem e quando. Nada é sobrescrito: o veredito que fica é o do
            primeiro. Ver o bloco de comentário no WHERE do UPDATE.

        Veredito da IA (`verified_by='claude-haiku'`) NÃO é conflito: o humano
        sobrescreve, que é o produto. Só veredito com o prefixo `user:` de
        OUTRA pessoa bloqueia.

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

        autor = f"{_PREFIXO_HUMANO}{user_id}"
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
                # ── A GUARDA DA CORRIDA (bloco 4) ────────────────────────
                # Sem `verification_verdict IS NULL` no WHERE, dois operadores
                # na MESMA fila (segunda, 3 usuários reais) julgavam o mesmo
                # alerta e o SEGUNDO sobrescrevia o veredito do primeiro —
                # `verified_by` incluído, 200 nos dois, aviso nenhum. Agora o
                # UPDATE só pega linha ainda não julgada.
                #
                # `OR verified_by = %s` (o PRÓPRIO autor) preserva o que a
                # docstring já prometia: "re-revisão é permitida de propósito
                # (operador muda de ideia)". Mudar de ideia sobre o SEU
                # veredito continua valendo; sobrescrever o de OUTRA pessoa
                # em silêncio é que não.
                #
                # `OR verified_by NOT LIKE 'user:%'` (segundo cético): só o
                # veredito de OUTRA PESSOA bloqueia. `tasks/verification.py`
                # grava o MESMO 'approve'/'reject' com
                # `verified_by='claude-haiku'`, e corrigir a IA é o produto
                # inteiro — as telas de evento mostram "Não revisado" para
                # esses alertas (VereditoHumano.tsx: só o prefixo 'user:'
                # prova humanidade) e oferecem os botões. Sem esta cláusula, o
                # primeiro clique nesses botões viraria 409 "A verificação
                # automática já avaliou este alerta", e a revisão humana da
                # decisão da máquina ficaria impossível pela rota. O prefixo
                # vai como PARÂMETRO, não literal: `%` literal no texto da
                # query é armadilha do psycopg2.
                "WHERE id = %s AND tenant_id = %s "
                "  AND (verification_verdict IS NULL OR verified_by = %s "
                "       OR verified_by NOT LIKE %s)",
                (status, verdict, autor, reason or None,
                 alert_id, tenant_id, autor, f"{_PREFIXO_HUMANO}%"),
            )
            if cur.rowcount:
                logger.info(
                    "human_review: alert=%s verdict=%s user=%s", alert_id, verdict, user_id
                )
                return True

            # 0 linhas tem DUAS causas e elas não podem virar a mesma resposta:
            #   · alerta inexistente / de outro tenant  → 404 (C-01: não vaze
            #     existência — a rota já traduz `False` em 404)
            #   · alerta ALHEIO JÁ JULGADO              → 409 com quem e quando
            # A leitura roda na MESMA conexão do UPDATE que falhou.
            cur.execute(
                "SELECT a.verification_verdict, a.verified_at, a.verified_by, "
                "       u.name AS autor_nome "
                "FROM alerts a "
                "LEFT JOIN public.users u ON a.verified_by = 'user:' || u.id::text "
                "WHERE a.id = %s AND a.tenant_id = %s",
                (alert_id, tenant_id),
            )
            row = cur.fetchone()

        if row is None or not row["verification_verdict"]:
            # Não existe no tenant (404). O `not verdict` cobre o impossível
            # teórico (linha existe, verdict nulo, UPDATE não pegou) sem
            # inventar um 409 que não dá pra explicar ao operador.
            return False

        quem = _quem_julgou(row["verified_by"], row["autor_nome"])
        quando = _ha_quanto_tempo(row["verified_at"])
        logger.info(
            "human_review_conflito: alert=%s user=%s ja_julgado_por=%s",
            alert_id, user_id, row["verified_by"],
        )
        raise ConflictError(f"{quem} já avaliou este alerta {quando}.")

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
