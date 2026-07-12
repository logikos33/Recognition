# Relatórios — Quality Gate — spec visual

**Rota:** `/quality/reports` (sub-rota lazy do `QualityLayout`, dentro do AppShell/AppLayout)
**Fontes:** `apps/frontend/src/modules/quality/pages/QualityReportsPage.tsx` · layout: `apps/frontend/src/modules/quality/QualityLayout.tsx` + `QualityLayout.css.ts` · tokens: `src/styles/theme.css.ts` / `src/theme/tokens/recognition-dark.css.ts`
**Screenshots:**

| Estado  | Dark | Light |
|---------|------|-------|
| default | `../screenshots/quality-reports/dark-default.png` | `../screenshots/quality-reports/light-default.png` |
| empty   | `../screenshots/quality-reports/dark-empty.png`   | `../screenshots/quality-reports/light-empty.png`   |

## Layout — regiões

- **AppShell global**: top bar (hambúrguer, logo do módulo "Qualidade" + breadcrumb "/ Qualidade", sino, toggle Pro, "Auditor Visual" + badge SUPERADMIN, botão "Sair"), footer de status (Banco de dados / Redis / câmeras ativas), ChatFAB ciano no canto inferior direito.
- **Submenu Qualidade** (`QualityLayout` topBar): links horizontais — Câmeras · Dashboard · Inspeções · Treinamento · Peças · Retrabalho · **Relatórios** (ativo, pill escura) · Config.
- **Conteúdo**: container `padding: 24px; maxWidth: 1400px; margin: 0 auto` (inline styles — página inteira usa inline styles, não `.css.ts`).
  - Linha 1: `h1` (24px/700, `textPrimary`) à esquerda; ações globais à direita (`display:flex; gap:12`).
  - Faixa de feedback de lote (condicional), `padding 12px 16px`, radius 8, `marginBottom 16`.
  - Linha de filtros: `display:flex; gap:12; marginBottom:24; flexWrap:wrap; alignItems:flex-end`.
  - Grupos por OP: blocos com `marginBottom 24` — cabeçalho (radius `12px 12px 0 0`, bg `bgSurface`, border `borderDefault`) + tabela (bg `bgCard`, radius `0 0 12px 12px`, border sem topo).
  - Linhas da tabela: `display:grid; gridTemplateColumns: 1.5fr 1fr 1fr 1fr 0.5fr; padding: 12px 16px`, separador `1px solid vars.color.bgSurface` (token de fundo usado como borda).

## Árvore de componentes

- `QualityReportsPage`
  - `h1` "Relatórios — Quality Gate"
  - Botão **Exportar Wiser (N)** — condicional `pendingWiserCount > 0`; bg `primaryDark` (#0891b2), texto `textPrimary` (muda com o tema!), radius 8, `10px 20px`; disabled → bg `textSecondary` + cursor not-allowed
  - Botão **↓ Baixar CSV** — bg `primary` (#06b6d4), texto `textOnPrimary` (#fff), radius 8
  - Banner de resultado de lote — bg `#F0FDF4` hardcoded (sucesso) ou `dangerMuted` (erro)
  - Filtros: 2× `input[type=date]`, 1× `input[type=text]` (OP), 1× `select` (Wiser), todos bg `bgCard`, border `borderDefault`, radius 8, `8px 12px`; botão "Limpar filtros" (condicional se algum filtro ativo)
  - Por grupo OP:
    - Cabeçalho: nome da OP (16px/700), contagem "N aprovadas" (13px, `success`), "N pendente Wiser" (13px, `warning`, condicional), spacer flex, botão **Exportar OP para Wiser** (bg `#7C3AED20`, border `#7C3AED40`, texto `primaryDark`, radius 6, 12px/600 — condicional pendências)
    - Linha de peça: `piece_number` (600, `textPrimary`) · data `completed_at` (13px `textSecondary`) · retrabalho ("N retrabalho(s)" em `warning` ou "Sem retrabalho" em `textMuted`) · ícone status Wiser (⏳ `warning` / ✓ `success` com tooltip da data / ✗ `danger` / ○ `warning`) + rótulo ("Exportando..." | "Wiser OK" | "Pendente Wiser", 12px `textSecondary`) · botão **Exportar** (outline `primaryDark`, bg transparent, radius 6, 12px — só se pendente)

## Copy exata

- Título: `Relatórios — Quality Gate`
- Botões: `Exportar Wiser (3)` / `Exportando...` · `↓ Baixar CSV` · `Exportar OP para Wiser` · `Exportar` · `Limpar filtros`
- Labels de filtro: `De` · `Até` · `Ordem de Produção` (placeholder `Ex: OP-2024-001`) · `Wiser` (options `Todos` / `Pendente` / `Exportado`)
- Status por peça: `Wiser OK` · `Pendente Wiser` · `Exportando...` · `Sem retrabalho` · `{n} retrabalho(s)`
- Grupo: `{n} aprovadas` · `{n} pendente Wiser`
- Feedback de lote: `{n} peças exportadas com sucesso.` · `Erro de conexão ao exportar em lote.`
- Loading: `Carregando relatório...` · Erro: `Erro ao carregar relatório.`
- Vazio: `Nenhuma peça aprovada encontrada com os filtros selecionados.`
- Placeholder nativo dos date inputs: `mm/dd/yyyy` (locale do browser, não pt-BR)

## Dados de exemplo (fixtures do harness)

- **OP-2026-0107**: RVB-8841 (Wiser OK, sem retrabalho) · RVB-8842 (Wiser OK, 1 retrabalho) · RVB-8843 (Pendente, sem retrabalho, botão Exportar) · RVB-8844 (Wiser OK, 2 retrabalhos). Cabeçalho: "4 aprovadas · 1 pendente Wiser".
- **OP-2026-0112**: RVB-8850 (Pendente) · RVB-8851 (Pendente, 1 retrabalho). "2 aprovadas · 2 pendente Wiser".
- **(sem OP)**: RVB-8860 (Wiser OK) — grupo do fallback `work_order = null`.
- Botão global: `Exportar Wiser (3)`.

## Estados

- **default**: grupos + botões conforme acima.
- **empty**: some o `Exportar Wiser (N)` (0 pendências); apenas "Baixar CSV" + filtros + mensagem central `textMuted`, padding 60.
- **loading**: texto "Carregando relatório..." em `textSecondary`; grupos ocultos.
- **erro**: faixa `danger` sobre `dangerMuted`, radius 8.
- **hover**: NENHUM estado hover definido (inline styles sem `:hover`) em botões, linhas ou filtros.
- **exportação individual**: ícone ⏳ + "Exportando..." → ✓ + "Wiser OK" (atualização otimista sem re-fetch).

## Navegação e fluxos

- `Exportar Wiser (N)` → `POST /v1/quality/gate/export-wiser/batch` → banner de resultado + reload.
- `Exportar OP para Wiser` → dispara `handleExportOne` para cada peça pendente do grupo (N requisições paralelas).
- `Exportar` (linha) → `POST /v1/quality/gate/pieces/{id}/export-wiser`.
- `↓ Baixar CSV` → cria `<a download>` para `{API_BASE}/api/v1/quality/gate/pieces/export?...&token={jwt}` (token JWT exposto na URL/histórico do browser).
- Filtros disparam re-fetch imediato (`useEffect` em cada mudança).
- Nenhum modal nesta tela.

## Problemas identificados (resumo)

1. **Contraste**: `↓ Baixar CSV` branco sobre `primary` #06b6d4 = 2.43:1 (ambos os temas).
2. **Contraste/inconsistência**: `Exportar Wiser (N)` usa `textPrimary` (tema-dependente) sobre bg fixo `primaryDark` → 3.33:1 no dark; deveria ser `textOnPrimary`.
3. **Hardcode**: `#F0FDF4` no banner de lote (fora de token; texto `success` sobre ele = 2.42:1) e `#7C3AED20/#7C3AED40` no botão de OP (roxo fora da paleta; texto teal 3.05:1 no light).
4. **Contraste light**: `success`/`warning` (13px) sobre branco = 2.54/2.15:1 nos cabeçalhos de grupo; "N retrabalho(s)" warning sobre `bgCard` claro = 1.85:1.
5. **Hover ausente** em todos os interativos; separador de linha usa token de fundo `bgSurface` como borda.
6. **Copy/l10n**: placeholder nativo `mm/dd/yyyy` (en) e exemplo `OP-2024-001` desatualizado vs dados OP-2026.
7. **Segurança/UX**: token JWT na querystring do CSV (fora de escopo visual, registrado como observação).

## Findings (develop — 2026-07-07)

Revalidação rápida: comparação visual de screenshots develop vs baseline staging. Merges relevantes: task-063, task-065, WS1 (d7a3ad3).

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| 1 | P1 | `↓ Baixar CSV` branco sobre `primary` = 2.43:1 — confirmado visualmente em ambos os temas (screenshots develop idênticos ao baseline) | PERSISTE |
| 2 | P1 | `Exportar Wiser (N)` — em develop ambos os botões aparecem com mesma estética teal; se `textPrimary` foi substituído por `textOnPrimary`, contraste still 2.43:1 (white/teal). Verificar se bg foi unificado para `primary`. | PERSISTE |
| 3 | P2 hardcode | `#F0FDF4` no banner; `#7C3AED20/#7C3AED40` no botão "Exportar OP" — botão roxo-outline visível em ambos os temas nos screenshots de develop | PERSISTE |
| 4 | P1 light | `success`/`warning` 13px nos cabeçalhos de grupo = 2.54/2.15:1 no claro — "N aprovadas"/"N pendente Wiser" visíveis em light-default.png mas potencialmente abaixo de AA | PERSISTE |
| 5 | P2 | Hover ausente em todos interativos; `bgSurface` como separador de linha | PERSISTE |
| 6 | P3 copy | Placeholder `mm/dd/yyyy` en-US; exemplo `OP-2024-001` desatualizado | PERSISTE |
| 7 | P3 | Token JWT na querystring do CSV | PERSISTE |

**Resumo develop:** 0 resolvidos · 7 persistem · 0 novos. Nenhum dos problemas desta tela estava no escopo dos merges recentes.
