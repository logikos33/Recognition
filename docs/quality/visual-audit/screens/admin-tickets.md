# Tickets de Suporte — spec visual

**Rota:** `/admin/tickets`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminTicketsPage.tsx` · `components/TicketRow.tsx` · `components/SlaIndicator.tsx` · `admin.css.ts`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-tickets/dark-default.png` | `../screenshots/admin-tickets/light-default.png` |
| empty | `../screenshots/admin-tickets/dark-empty.png` | `../screenshots/admin-tickets/light-empty.png` |

Página de detalhe `/admin/tickets/:id` (destino do clique na linha) NÃO coberta neste grupo.

## Layout — regiões

- Shell AdminLayout. `pageRoot` → `pageHeader` (sem botão de ação) → linha de filtros (`s.flex`, mb 16) → card com tabela → paginação condicional (`total > 20`).

## Árvore de componentes

- `pageTitle` "Tickets de Suporte" + `pageSubtitle` "{total} tickets"
- 2 × `s.select` (bgElevated, borda borderDefault): filtro de status e de prioridade
- `card` → `table`
  - th: `#` · `Assunto` · `Categoria` · `Prioridade` · `Status` · `SLA` · `Criado`
  - `TicketRow` (`trHover`, linha inteira clicável → navega ao detalhe):
    - `#` id truncado em `mono` (`#tk-00019a`)
    - Assunto + tenant em `muted`
    - Categoria com label humano (`categoryLabel`): Bug / Dúvida / Retreino / Novo módulo / Financeiro / Outro
    - `s.priorityBadge[priority]`: low cinza #6b7280 · normal azul #2563eb · high laranja #ea580c · critical vermelho `vars.color.danger` — todos sobre rgba 15% da cor
    - `s.statusBadge[status]`: open azul · in_progress laranja · waiting_client âmbar #ca8a04 · resolved verde #16a34a · closed cinza
    - `SlaIndicator`: trilha 80×4px `rgba(0,0,0,0.08)` (allow) + fill colorido (danger se estourado; #ca8a04 se >75%; success senão) + texto `SLA vencido` (10px, danger) quando estourado sem primeira resposta
    - Criado: data pt-BR em `muted`

## Copy exata

- Título: `Tickets de Suporte` · Subtítulo: `{total} tickets`
- Filtros: `Todos os status` + opções cruas `open` / `in progress` / `waiting client` / `resolved` / `closed` (underscore → espaço); `Todas as prioridades` + `low` / `normal` / `high` / `critical`
- Cabeçalhos: `#` · `Assunto` · `Categoria` · `Prioridade` · `Status` · `SLA` · `Criado`
- Vazio: `Nenhum ticket encontrado`
- SLA estourado: `SLA vencido`
- Paginação: `Anterior` · `Pág {n}` · `Próxima`
- SLA por prioridade (horas p/ 1ª resposta): critical 1h · high 4h · normal 24h · low 72h

## Dados de exemplo (fixtures)

| # | Assunto (tenant) | Categoria | Prioridade | Status | SLA | Criado |
|---|---|---|---|---|---|---|
| #tk-00019 | Câmera Pátio Norte sem stream desde ontem (Tenant RVB Industrial) | Bug | critical | open | aberto há 50min → barra ~83%, sem resposta | 06/07/2026 |
| #tk-00028 | Falsos positivos de capacete na Doca 3 (Construtora Horizonte Sul) | Retreino | high | in progress | respondido em 2h (dentro de 4h) | 06/07/2026 |
| #tk-00037 | Dúvida sobre exportação de relatório mensal (Metalúrgica São Carlos) | Dúvida | normal | waiting client | respondido em 1 dia | 04/07/2026 |
| #tk-00046 | Solicitação de módulo de contagem de pallets (Transportadora Andrade & Filhos) | Novo módulo | low | open | aberto há 3 dias / 72h → **SLA vencido** | 03/07/2026 |
| #tk-00055 | Cobrança duplicada na fatura de junho (Tenant RVB Industrial) | Financeiro | high | resolved | respondido | 01/07/2026 |
| #tk-00064 | Acesso de novo operador ao dashboard (Agroindústria Vale Verde) | Dúvida | normal | closed | respondido | 27/06/2026 |
| #tk-00073 | Latência alta no live view do canteiro (Construtora Horizonte Sul) | Bug | normal | open | aberto há 1 dia / 24h → **SLA vencido** | 05/07/2026 |

## Estados

- **default**: 7 linhas; hover `bgHover`; barras de SLA com fills verde/âmbar/vermelho.
- **empty**: linha `Nenhum ticket encontrado`.
- **carregando**: `Carregando...` · **erro**: `alertBanner.danger`.
- Mudar filtro reseta página para 1.

## Navegação e fluxos

- Clique em qualquer linha → `navigate('/admin/tickets/{id}')` (página de detalhe, fora do escopo do grupo).
- Selects recarregam `GET /api/v1/admin/tickets?...` (20/página).

## Problemas identificados

1. **P2 contraste (dark)** — badges de status/prioridade do `admin.css.ts` usam hex fixos calibrados para fundo claro: `open`/`normal` #2563eb sobre rgba(59,130,246,0.15) no dark = **3.01:1**; `closed`/`low` #6b7280 = **3.33:1** (texto 11px/600 exige 4.5). `waiting_client` #ca8a04 (4.79) e `resolved` #16a34a (4.41) ficam no limite. No light todos ≥4.3.
2. **P2 copy** — status e prioridades exibidos como chaves cruas em inglês (`open`, `waiting client`, `critical`) nos filtros e badges, enquanto Categoria já tem dicionário pt-BR (`categoryLabel`). Inconsistência dentro da própria tela.
3. **P2 inconsistency** — paleta dos badges (blue-600/amber-600/green-600 Tailwind) é alheia à identidade ciano/laranja Recognition; é compartilhada por todo o admin via `admin.css.ts` (styleVariants sem tokens).
4. **P3 contraste (dark)** — trilha do `SlaIndicator` `rgba(0,0,0,0.08)` sobre superfície escura = **1.01:1**: a barra perde a referência visual de 100% (só o fill é visível). Tem comentário `allow`, mas o componente deveria usar um token de trilha (ex.: `borderDefault`).
5. **P3 copy** — coluna `#` mostra `#tk-00019` (8 chars do id) — útil, mas não é um número sequencial como o cabeçalho sugere.

## Findings (develop — 2026-07-07)

Revalidação rápida: comparação visual de screenshots develop vs baseline staging. Merges relevantes: task-063, task-065, WS1 (d7a3ad3) — nenhum cobriu AdminTicketsPage ou admin.css.ts.

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| 1 | P2 dark | Badges status/prioridade hex fixos: `open`/`normal` #2563eb = 3.01:1 dark; `closed`/`low` #6b7280 = 3.33:1 dark — **confirmado** em `dark-default.png` (badges coloridos visíveis mas potencialmente abaixo de AA em dark) | PERSISTE |
| 2 | P2 copy | Status/prioridades em inglês cru nos filtros e badges (`open`, `waiting client`, `critical`) — **confirmado** em ambos os screenshots | PERSISTE |
| 3 | P2 | Paleta Tailwind alheia à identidade ciano/laranja Recognition — `admin.css.ts` não foi migrado em WS1 | PERSISTE |
| 4 | P3 dark | Trilha `SlaIndicator` `rgba(0,0,0,0.08)` sobre dark = 1.01:1 — barra de referência invisível no dark | PERSISTE |
| 5 | P3 copy | Coluna `#` não é número sequencial | PERSISTE |

**Resumo develop:** 0 resolvidos · 5 persistem · 0 novos. `admin.css.ts` usa `styleVariants` com hex Tailwind fixos — fora do escopo WS1 que cobriu módulos quality/operation.
