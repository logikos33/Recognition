# Retrabalhos — Quality Gate — spec visual

**Rota:** `/quality/rework` (sub-rota lazy do `QualityLayout`)
**Fontes:** `apps/frontend/src/modules/quality/pages/QualityReworkPage.tsx` · tipos: `src/modules/quality/types/gate.ts` · tokens: `src/styles/theme.css.ts`
**Screenshots:**

| Estado       | Dark | Light |
|--------------|------|-------|
| default      | `../screenshots/quality-rework/dark-default.png` | `../screenshots/quality-rework/light-default.png` |
| empty        | `../screenshots/quality-rework/dark-empty.png`   | `../screenshots/quality-rework/light-empty.png`   |
| modal-fotos  | `../screenshots/quality-rework/dark-modal-fotos.png` | `../screenshots/quality-rework/light-modal-fotos.png` |

## Layout — regiões

- AppShell + submenu Qualidade (item ativo: **Retrabalho**), como em quality-reports.
- Conteúdo `padding 24px; maxWidth 1400; margin 0 auto` (tudo inline styles).
  - `h1` 24px/700, `marginBottom 24`.
  - Grid de KPIs: `grid; gridTemplateColumns: repeat(4, 1fr); gap 16; marginBottom 28` — 4 cards (`bgSurface`, border `borderDefault`, radius 12, padding `18px 20px`).
  - Card "Distribuição por Validação": `bgSurface`, radius 12, padding `20px 24px`, `marginBottom 24`; barras empilhadas com `gap 14`, trilho 8px (`borderDefault`, radius 4), fill com `transition width 0.6s ease`.
  - Filtros: flex `gap 12; marginBottom 20`, mesmos inputs de reports.
  - Tabela: container `bgCard`, border `borderDefault`, radius 12; header e linhas em `grid; gridTemplateColumns: 1fr 1fr 1.5fr 1fr 1fr 1fr 0.6fr`; header `bgSurface`, 12px/600 uppercase `textSecondary`, letterSpacing 0.5.
  - Paginação: flex à direita, `marginTop 16`.
  - Modal: overlay `position:fixed; inset:0; background: vars.color.overlay` (rgba(0,0,0,0.7)) — **inline, com `TODO-WS1: converter para Modal do kit`**; caixa `bgCard`, radius 16, padding 32, maxWidth 800, width 90%, `boxShadow: 0 20px 60px rgba(0,0,0,0.3)` (hardcoded).

## Árvore de componentes

- `QualityReworkPage`
  - KPI cards: "Total de Retrabalhos" (valor 32px/700 `danger`) · "Tempo Médio" (`warning`) · "Retrabalhos V1" (cor `METRIC_COLORS.v1 = warning`) · "Retrabalhos V2" (`primaryDark`) — cada card por validação tem sublinha "Avg {t}" em `textMuted` 12px. Só os 2 primeiros `by_validation` viram card (`slice(0, 2)` — V3 fica de fora).
  - Gráfico de barras: por validação — rótulo (`VALIDATION_LABEL`), contagem "count · avg t" à direita (`textSecondary`), barra fill `METRIC_COLORS[tipo]` com % relativa ao máximo.
  - Filtros: select `Validação` (Todas/V1/V2/V3), date `Data`, text `Operador (ID)` (placeholder "ID do operador"), botão condicional "Limpar filtros".
  - Tabela: colunas PEÇA (últimos 8 chars do `piece_id`, 600) · VALIDAÇÃO (badge pill radius 20, bg `METRIC_COLORS[tipo]+'20'`, texto `METRIC_COLORS[tipo]`, 12px/600) · DEFEITO (`defect_type ?? defect_description ?? '—'`) · TENTATIVA (`#N`) · DURAÇÃO (`fmtDuration`) · INICIADO (data/hora pt-BR) · FOTOS (botão "Ver fotos" 12px `primary` sobre `bgCard`, ou "—" na cor `borderDefault`).
  - Paginação: "{total} retrabalhos · página {p} de {n}" + botões "← Anterior"/"Próxima →" (disabled: texto na cor `borderDefault`).
  - Modal de fotos: título "Fotos do Retrabalho — {V*}" (18px/700) + botão × (24px, `textSecondary`); grid 2 colunas `gap 20`; rótulos uppercase 12px/600 "ANTES DO RETRABALHO"/"APÓS O RETRABALHO"; imagem antes com `border 2px solid #EF4444` (hardcoded), depois com `2px solid vars.color.success`; fallback "Sem foto" (caixa 200px `bgSurface` texto `textMuted`); bloco "Observações:" (`bgSurface`, radius 8).

## Copy exata

- Título: `Retrabalhos — Quality Gate`
- KPIs: `Total de Retrabalhos` · `Tempo Médio` · `Retrabalhos V1` · `Retrabalhos V2` · `Avg {t}`
- Gráfico: `Distribuição por Validação` · `V1 — Fio Alinhado no Anel` · `V2 — Saída Isolada` · `V3 — Anel Encapado` · `{n} · avg {t}`
- Filtros: `Validação` (Todas) · `Data` · `Operador (ID)` (placeholder `ID do operador`) · `Limpar filtros`
- Header tabela: `PEÇA · VALIDAÇÃO · DEFEITO · TENTATIVA · DURAÇÃO · INICIADO · FOTOS`
- Célula fotos: `Ver fotos` · vazio `—`
- Vazio: `Nenhum retrabalho encontrado.` · Loading: `Carregando retrabalhos...` · Erro: `Erro ao carregar retrabalhos.`
- Paginação: `{total} retrabalhos · página {p} de {n}` · `← Anterior` · `Próxima →`
- Modal: `Fotos do Retrabalho — V1` · `ANTES DO RETRABALHO` · `APÓS O RETRABALHO` · `Sem foto` · `Observações: `
- Duração: `—` (null/0) · `{s}s` (<60) · `{m}m {s}s`

## Dados de exemplo (fixtures)

- Métricas: total 27, avg 128s ("2m 8s"); by_validation: v1=14/95s, v2=8/142s, v3=5/210s.
- Tabela (6 linhas, total 27, 2 páginas): ex. `9f3e21aa · V1 · Fio desalinhado no anel · #1 · 1m 24s · 06/07/2026, 23:09 · Ver fotos`; outros defeitos: "Saída sem isolamento" (V2, 2m 36s), "Anel sem capa isolante" (V3, #2, 3m 53s), "Isolamento parcial na saída 2" (V2, 2m 22s).
- Modal: observação `Fio 3 reposicionado no anel guia; verificado torque do terminal.` — fotos SVG "gate/close-up · anel 12 vias".
- Empty: métricas `total_reworks: 0`, avg 0 → card Tempo Médio mostra apenas o traço `—` laranja; tabela com "Nenhum retrabalho encontrado."

## Estados

- **default**: 4 cards + gráfico + tabela 6 linhas + paginação (27 itens).
- **empty**: só 2 cards (Total=0 vermelho, Tempo Médio "—"), sem gráfico (`by_validation.length === 0`), tabela com mensagem central; sem paginação.
- **loading**: "Carregando retrabalhos..." (tabela oculta).
- **erro**: faixa `danger`/`dangerMuted`.
- **modal-fotos**: overlay 70% preto + card opaco `bgCard` — backdrop presente e fundo opaco (sem defeito task-066); click fora ou × fecha.
- **hover**: nenhum definido (nem nas linhas da tabela, que nem são clicáveis — só o botão "Ver fotos").
- **disabled** (paginação): texto na cor `borderDefault` = 1.15:1 sobre `bgCard` dark (praticamente invisível; WCAG isenta disabled, mas o affordance some).

## Navegação e fluxos

- "Ver fotos" → abre modal inline (estado `modalRework`).
- Filtros/paginação → re-fetch `GET /v1/quality/gate/reworks` + `GET /v1/quality/gate/stats/rework`.
- Modal fecha por click no backdrop ou ×; sem tecla Esc, sem focus-trap, sem `role="dialog"`/`aria-modal`.

## Problemas identificados (resumo)

1. **Inconsistência (ADR-0023)**: modal inline com TODO-WS1 no source em vez do `Modal` do kit; sem Esc/focus-trap/aria.
2. **Contraste light**: KPI "Tempo Médio" `warning` 32px sobre branco = 2.15:1 (falha até para texto grande, 3:1); badge V1 `warning` sobre `#f59e0b20`+branco = 1.95:1; "Ver fotos" `primary` sobre `bgCard` claro = 2.09:1.
3. **Hardcode**: `#EF4444` (borda da foto antes — existe token `danger` com o mesmo valor) e boxShadow `0 20px 60px rgba(0,0,0,0.3)` (existe `vars.shadow.lg`).
4. **Dados**: cards de métricas mostram só V1/V2 (`slice(0,2)`) — V3 aparece no gráfico mas nunca ganha card; grid fixa `repeat(4,1fr)` deixa 2 buracos no empty.
5. **Hover ausente** em botões/linhas; disabled da paginação invisível no dark.
6. **A11y**: ícones ✓/✗/—; título do modal não é `aria-labelledby`.

## Findings (develop — 2026-07-07)

Revalidação rápida: comparação visual de screenshots develop vs baseline staging. Merges relevantes: task-063 (painel vídeo), task-065 (guard-rail CI), WS1 (d7a3ad3).

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| 1 | P2 | Modal ad-hoc com TODO-WS1 — sem Esc/focus-trap/aria — confirmado em `light-modal-fotos.png` develop (modal branco sobre backdrop dimmed, sem kit Dialog) | PERSISTE |
| 2 | P2 light | KPI "Tempo Médio" warning 32px = 2.15:1; badge V1 warning 1.95:1; "Ver fotos" primary 2.09:1 — confirmado em `light-default.png` (valores laranja sobre branco) | PERSISTE |
| 3 | P2 hardcode | Borda `#EF4444` na foto "ANTES" — **confirmada visualmente** em `light-modal-fotos.png` (borda vermelha evidente); `boxShadow` hardcoded no modal | PERSISTE |
| 4 | P2 dados | Cards mostram só V1/V2 — V3 ausente dos KPI cards — confirmado em `dark-default.png` e `light-default.png` (4 cards mas só V1/V2 nomeados) | PERSISTE |
| 5 | P2 | Hover ausente; disabled paginação invisível no dark | PERSISTE |
| 6 | P3 a11y | Ícones sem aria-label; modal sem aria-labelledby | PERSISTE |

**Resumo develop:** 0 resolvidos · 6 persistem · 0 novos. task-063 tokenizou TrainingModeLayout mas não QualityReworkPage; modal permanece TODO-WS1 inline.
