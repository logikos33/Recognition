# Dashboard de Qualidade — spec visual

**Rota:** `/quality/dashboard` (modo Pro; toggle Pro/Demo persistido em `localStorage.quality_dashboard_mode`, default `pro`)
**Fontes:** `apps/frontend/src/modules/quality/pages/QualityDashboard.tsx`, `components/dashboard/DashboardHero.tsx`, `components/dashboard/KpiCard.tsx`, `components/dashboard/StationGrid.tsx`, `components/dashboard/StationCard.tsx`, `components/dashboard/StepTimer.tsx`, `hooks/useQualityDashboard.ts`, layout raiz `QualityLayout.tsx` + `QualityLayout.css.ts`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | ../screenshots/quality-dashboard/dark-default.png | ../screenshots/quality-dashboard/light-default.png |
| empty | ../screenshots/quality-dashboard/dark-empty.png | ../screenshots/quality-dashboard/light-empty.png |

## Layout — regiões

- **Top bar do módulo** (QualityLayout): sticky, `bgSurface`, borda inferior `1px borderSubtle`, padding `8px 32px`, submenu horizontal com 8 links: Câmeras · Dashboard · Inspeções · Treinamento · Peças · Retrabalho · Relatórios · Config. Link ativo: `bgElevated` + `textPrimary` + weight 600; inativo: `textSecondary`; hover: `bgHover` + `textPrimary`. Radius `4px`, fonte 13px/500, gap `4px`.
- **Conteúdo**: `padding: 24px`, `maxWidth: 1600px`, centralizado (`margin: 0 auto`), fundo `bgBase`.
- **Header da página**: flex space-between, `marginBottom: 20`. Título h1 22px/700 `textPrimary` à esquerda; à direita dois botões (Demo, ↺ Atualizar).
- **Hero de KPIs**: flex row com `gap: 14`, `marginBottom: 28`, `flexWrap: wrap` — 5 KpiCards com `flex: 1`.
- **Label da seção**: "Estações (N)" 14px/600 `textSecondary`, `marginBottom: 16`; sufixo "atualizando…" 12px `textMuted` quando polling com dados.
- **Grid de estações**: `grid-template-columns: repeat(auto-fill, minmax(340px, 1fr))`, `gap: 20`.

## Árvore de componentes

- `QualityDashboard` (roteia pro/demo)
  - `QualityDashboardPro`
    - Botão "Demo" — 5×12px padding, radius 8, borda `borderDefault`, bg `bgCard`, texto 12px/600 `textSecondary`, sem hover definido
    - Botão "↺ Atualizar" — 6×14px padding, radius 8, borda `borderDefault`, bg `bgCard`, 13px `textSecondary`, sem hover definido
    - `DashboardHero` → 5× `KpiCard` (bg `bgCard`, borda `borderSubtle`, radius 12, padding 18×20; label 11px/600 uppercase `textSecondary`; valor 28px/700, cor default `textPrimary` ou accentColor)
      - variante loading: bloco 36px `bgHover` no lugar do valor
      - variante erro: banner `dangerMuted` + borda `danger` radius 12 com mensagem 14px `danger` + botão "Tentar novamente" (borda danger, bg transparent)
    - `StationGrid`
      - `StationCard` (borda `1px {statusColor}40` ou `borderSubtle` se offline; radius 14; bg `bgCard`; `opacity 0.6` se offline)
        - Placeholder de vídeo 16:9, bg `bgBase`, texto central 13px `textDim`, badge canto sup. dir. `rgba(0,0,0,0.55)` texto 11px `textSecondary` radius 20 ("Nx cam")
        - Bloco de dados: nome 15px/700 `textPrimary` + pill de status 11px/600 (`color` = statusColor, bg = `statusColor + '18'`, radius 20, prefixo "●")
        - Divisor 1px `borderSubtle`
        - Tabela label/valor 13px (labels 45% `textSecondary`): Operador, OP, Peça, Etapa (bold `textPrimary`), Tempo na etapa (`StepTimer`, tabular-nums, `warning` quando warn), Turno OK / NOK
      - skeleton (3 cards com blocos `bgHover`) quando loading sem dados
      - empty: box tracejado `1px dashed borderDefault`, radius 14, padding 60×20, texto 14px `textMuted` + link `accent`

## Copy exata

- Título: `Dashboard de Qualidade`
- Botões: `Demo` · `↺ Atualizar` · `Tentar novamente`
- Labels KPI (uppercase): `Peças no turno` · `OK %` · `NOK` · `Retrabalho ativo` · `Estações ativas`
- Seção: `Estações ({N})` · sufixo polling: `atualizando…`
- Status das estações: `OK` · `Atenção` · `Crítico` · `Offline` (prefixo `●`)
- Labels da tabela do card: `Operador` · `OP` · `Peça` · `Etapa` · `Tempo na etapa` · `Turno OK / NOK`
- Placeholder vídeo: `{N} câmera(s) — stream v2` · `Sem câmera atribuída` · badge `{N}x cam`
- Card sem peça: `Aguardando peça` · offline: `Estação offline`
- Empty: `Nenhuma estação configurada. Configurar estações →` (link para `/quality/config`)

## Dados de exemplo (fixtures do harness)

KPIs: Peças no turno **342** · OK % **94.7%** (verde) · NOK **18** (vermelho) · Retrabalho ativo **3** (âmbar) · Estações ativas **3 / 4**.

| Estação | Status | Operador | OP | Peça | Etapa | Câmeras |
|---|---|---|---|---|---|---|
| Bancada A — Montagem | OK | José Carlos Menezes | OP-2026-0142 | PC-88412 | V1 Analisando | 2 |
| Bancada B — Acabamento | Atenção | Marina Duarte | OP-2026-0139 | PC-88377 | V3 Analisando | 1 |
| Bancada C — Retrabalho | Crítico | Antônio Ferreira Lima | OP-2026-0142 | PC-88401 | Retrabalho V2 | 1 |
| (4ª estação offline) | Offline | — | — | — | — | 0 |

Empty: todos KPIs zerados (`0`, `0.0%`, `0 / 0`) e box "Nenhuma estação configurada.".

## Estados

- **default**: KPIs + grid de cards; polling 5s (summary) / 15s (stations) com backoff.
- **empty**: KPIs zerados + box tracejado com link para Config.
- **loading (primeira carga)**: KPI com bloco `bgHover`; grid com 3 cards skeleton.
- **loading (re-poll)**: dados mantidos + sufixo "atualizando…".
- **erro**: banner `dangerMuted` com mensagem e "Tentar novamente" (Hero e Grid têm banners independentes).
- **hover**: NENHUM elemento da página define hover (botões Demo/Atualizar e link do empty não têm feedback).
- **offline (card)**: opacity 0.6, borda `borderSubtle`, texto "Estação offline".

## Navegação e fluxos

- `Demo` → troca para `QualityDashboardDemo` (grava `quality_dashboard_mode=demo`).
- `↺ Atualizar` → `refresh()` (re-fetch summary + stations).
- `Tentar novamente` → `refresh()`.
- Link `Configurar estações →` → `/quality/config` (via `<a href>`, não React Router — força full reload).
- Cards de estação não são clicáveis.

## Problemas identificados

1. **P2 dark**: placeholder de vídeo `textDim #2a3a4a` sobre `bgBase #0a0c10` = **1.68:1** — quase invisível no tema padrão (StationCard.tsx:48).
2. **P2 light (task-063)**: badge "Nx cam" mistura bg fixo `rgba(0,0,0,0.55)` com `textSecondary` do tema → no claro fica `#3f4650` sobre `#6e6f6f` = **1.89:1** (StationCard.tsx:56).
3. **P1 light**: pill "Atenção" usa `#FFB74D` hardcoded (StationCard.tsx:8) sobre `#FFB74D18` → **1.42:1** no tema claro; deveria usar `vars.color.warning` + par AA.
4. **P2 light**: valores de KPI com accent `success` (2.18:1) e `warning` (1.85:1) sobre card claro falham até o limite de texto grande (3:1) (DashboardHero.tsx:43-45).
5. **P2**: link do empty state usa `<a href>` em vez de `Link` do router; contraste `accent` no claro = 3.26:1 (< 4.5) (StationGrid.tsx:65).
6. **P2**: nenhum hover em botões/link da página (Demo, Atualizar, Tentar novamente).
7. **P3**: página inteira estilizada inline (sem `.css.ts`), divergindo do padrão do módulo.

## Findings (develop — 2026-07-07)

> Comparado com _baseline-staging/screens/quality-dashboard.md · screenshots analisados: dark-default, light-default, dark-empty, light-empty

| # | Severidade | Descrição | Status |
|---|-----------|-----------|--------|
| 1 | P2 | Placeholder de vídeo das estações usa `textDim` (#2a3a4a) sobre `bgBase` (#0a0c10) = 1.68:1 em dark — texto "2 câmera(s) — stream v2" quase invisível. Confirmado em `dark-default.png`: placeholder visualmente vazio/escuro sem texto legível. | PERSISTE |
| 2 | P2 | Badge "Nx cam" (top-right do vídeo) usa `rgba(0,0,0,0.55)` como bg fixo + `textSecondary` do tema como texto → no claro resulta em contraste insuficiente (~1.89:1). Confirmado em `light-default.png`: badges "2x cam"/"1x cam" visíveis mas com texto de baixo contraste. | PERSISTE |
| 3 | P1 | Pill de status "● Atenção" usa `#FFB74D` hardcoded sobre `#FFB74D18` → 1.42:1 no claro (WCAG AA falha). Confirmado em `light-default.png`: badge "Atenção" na Bancada B. Deveria usar `vars.color.warning` + pair AA-compliant. | PERSISTE |
| 4 | P2 | Valores de KPI com `accentColor = vars.color.success` (2.18:1) e `vars.color.warning` (1.85:1) sobre card claro — ambos abaixo de 3:1 (mínimo para texto large/bold). Confirmado em `light-default.png`: "94.7%" e "3" em teal/amber sobre branco. | PERSISTE |
| 5 | P2 | Link "Configurar estações →" no empty state usa `<a href>` (força full reload) em vez de `<Link>` React Router. Contraste `accent` (#06b6d4?) sobre branco no claro ≈ 3.26:1 — abaixo de 4.5:1. Confirmado em `light-empty.png` e `dark-empty.png`. | PERSISTE |
| 6 | P2 | Botões "Demo" e "↺ Atualizar" não têm hover definido. Confirmado: sem feedback visual ao interagir. | PERSISTE |
| 7 | P3 | `QualityDashboard.tsx` e subcomponentes (`DashboardHero`, `StationCard`, `StationGrid`) estilizados com objetos inline em vez de `.css.ts`, divergindo do padrão vanilla-extract do módulo. | PERSISTE |

**Observação positiva:** O título "Dashboard de Qualidade" e os nomes de estação ("Bancada A — Montagem" etc.) estão tokenizados via `textPrimary` — renderizam corretamente em ambos os temas (WS1 d7a3ad3 ou anterior).

**Resumo:** 0 resolvidos · 7 persistem · 0 novos. O componente `StationCard.tsx` concentra os P1/P2 mais críticos de contraste.
