# Relatório da rodada de correção UX (31/08/2026)

> Origem: revisão do Vitor no front novo (30–31/08), 7 achados. Formato: **achado → causa medida → conserto → prova**.
> Regra que governou a rodada: nada de conserto sem medir a causa na fonte primeiro.

---

## A TESE DA RODADA: "vazio/cego com o dado existindo"

A hipótese era **uma** raiz comum (critério fantasma). A medição achou **duas**, e uma terceira coisa que nem era bug:

| Tela | O que dizia | O que era |
|---|---|---|
| A1 Verificação | "Fila zerada" | **Critério fantasma** — filtrava `verification_status='needs_human'`, coluna **nunca escrita em todo o banco** (o writer, uma task Celery, nunca concluiu). 416 alertas esperando. |
| A2 Propostas | "Nenhuma proposta pendente" | **Filtro residual invisível** — `source=upload` de uma seleção anterior + `pending_review` = zero por construção (proposta nasce de nvr/auto). 281 imagens existiam. |
| A4 Dashboard | painéis de "hoje" vazios | **Nada de errado**: o último evento é de 25/08. Janela honesta. O defeito era outro: **nenhum widget tinha clique**. |

**O elo real não é técnico, é de postura**: a tela afirmava sobre o mundo o que era limitação da própria pergunta. "Fila zerada" e "nenhuma proposta" são conclusões; o que o sistema sabia era "minha consulta não voltou nada". Mesma família do `0,0%` (B1) — zero como afirmação — e do `needs_human`.

---

## Bloco A

### A1 · Fila de verificação — PR #620
- **Causa medida**: `verification_service.py:66` filtra `needs_human`; **0 linhas** desse estado em todos os tenants; RVB tem 423 alerts (416 `pending`).
- **Conserto**: critério honesto (`verification_verdict IS NULL`) + teste de mutação.
- **O cético foi além e achou o que estava embaixo** (por isso o PR foi reprovado na 1ª volta): dos 416, **302 são conformidade** (nem violação) e **347 são repetição da mesma câmera+classe em ≤10s** → a fila real são **15 eventos**. A ordenação prometia incerteza mas ordenava no cliente sobre `LIMIT 50` por data: os 50 mais recentes têm confiança 0,90+ e bbox sem coordenada — o operador veria 50 fichas **sem caixa e sem rótulo**. E a barra de progresso, vinda do array local, escreveria "Fila zerada" **com 366 no banco**. Achado extra: a task grava `needs_human` **dentro do campo de veredito** — quando o worker voltar, esconderia da fila exatamente o que manda ao humano (**regressão programada**).
- **Pedido a outra pista**: investigar por que `verify_alert` nunca conclui no worker (SEMANA-CLIENTE).

### A2 · Propostas pendentes — PR #625
- **Causa provada no navegador** (captura de request/response): filtro residual em `source`; o backend estava certo (281 imagens / 349 propostas).
- **Conserto**: o vazio passa a **revelar os filtros ativos** com "limpar filtros"; aviso da combinação impossível; contador no chip via `get_facets`.
- **Prova**: mutação (vazio antigo reinstalado → 3 testes falham) + evidência visual `docs/quality/evidence/ux-a2/05-*.png`.

### A3 · Beco sem saída — PR #623
- **Causa**: logo não era link; Estúdio substitui a nav principal sem volta; nenhum breadcrumb no front novo.
- **Conserto**: logo leva à home do papel (regra extraída em `rotaHomeDoUsuario()`, reusada pela raiz — que **mandava todos, inclusive superadmin, ao dashboard EPI**), "← Voltar" no Estúdio, e **régua global** que percorre as rotas e falha se a área não oferecer saída.
- **Honestidade registrada**: Quality/Carga/Admin têm a mesma lacuna; o teste documenta como dívida conhecida em vez de fingir cobertura.
- **Bônus de causa raiz**: o CI quebrou por um import estático que violava a regra `lazy()` do próprio arquivo; corrigido na raiz, **recusando** o fallback de env que mascararia o problema.

### A4 · Dashboard leva ao evento — PR #621 ✅ mergeado
- Barra/classe/câmera/KPI abrem a lista já filtrada (params que a tela de Eventos já aceitava); **vazio de janela oferece "ver últimos 30 dias"**; câmera sem id fica **sem** link (filtro vazio mostraria tudo — seria mentira).
- 28 testes novos, todos com asserção de `href`/querystring.

### A5 · Ações corretivas — PR #624 ✅ mergeado
- Miniatura + card abre o evento + verbos reais (confirmar/descartar), respeitando **polaridade ≠ veredito ≠ reconhecimento** e "abrir nunca marca visto".
- **Tratativa (título/dono/prazo) não existe no backend** → selo honesto + pedido registrado.

## Bloco B

### B1 · Catálogo com 0,0% — PR #622 ✅ mergeado
- **Causa**: métricas são **zero literal, não NULL**, e o guard `!= null` deixava passar.
- **Conserto**: "—" + "métrica não registrada" em **cinco** superfícies (vitrine, job ao vivo, tabela legada, dropdown, card admin), com helper central.
- **Bloqueio declarado**: `ap_do_log.py` **não existe no repo** — backfill (B1-ii) pendente de decisão. Pedidos registrados: backend distinguir NULL de 0; job gravar métrica real.
- **Achado da prancha C1**: `map50` **já vem servido** em `GET /v1/models` — o front é que não exibia.

### B2+B3 · Escopo e a régua furada — PR #626
- **B3 (o achado mais valioso da rodada)**: a régua de linguagem tinha **dois furos independentes** — varria só `src/app/**` (o texto ofensor estava em `src/components/training/`) e era denylist fechada de 12 termos (jamais pegaria `tasks/inference.py` ou `#519`).
- **Conserto**: escopo por **alcançabilidade de import** a partir de `src/app` (pega o que o tenant realmente vê, sem arrastar o legado) + **detecção estrutural** (`.py`, `::`, `_snake_case` líder, `#NNN` com 3+ dígitos), calibrada contra falso-positivo real (`_list_reworks` dentro de `gate_list_reworks`).
- **B2**: chips tokenizados no lugar do checkbox nativo, linha compacta, Salvar explicando o bloqueio, e a **duplicação consolidada** (era a mesma classe de bug da 3ª cópia que vazava jargão).

## Bloco C · Desenho — PR #628
- **C1 Modelos por Câmera**: chips por par presença↔ausência (medido: **8 classes**, não 13), linha colapsável, **ações em massa** com prévia por câmera. Pedido P1 (BLOQUEIA): endpoint de aplicação em lote.
- **C3 Fila de Propostas**: sugestões como caminho principal, ordenação leiga, card separando **caixas humanas × sugestões**, aceitar vira "Aprovada" (nunca "Humana"). Achado: o motor **já aceita `?ordenar=incerteza`** — a galeria nunca manda o parâmetro.
- C2/C4/C5 permanecem na fila da LISTA-PARA-O-DESIGN.

---

## Dívidas e incidentes registrados

- **Issue #618** — flaky `CropClassifierFiltro` (custou rerun em 2 PRs).
- **Issue #627** — flaky por poluição cross-file (`CameraModelAssignment` passa isolado, falha em paralelo). Duas famílias de flaky em um dia: a suíte precisa de uma rodada de isolamento.
- **Incidente de processo**: `git stash` é **global do repositório**, não do worktree — dois agentes em worktrees irmãos se atropelaram e um WIP vazou. Nada perdido (backup + exemplar íntegro). **Regra nova: nada de `git stash` com worktrees irmãos ativos.**
- **Risco de quarta**: sem evento novo desde 25/08, o dashboard abre vazio. Mitigado pelo CTA "ver últimos 30 dias" (#621), mas a decisão de roteiro/coleta é humana.
