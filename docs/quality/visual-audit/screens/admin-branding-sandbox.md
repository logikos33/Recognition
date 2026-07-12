# Sandbox de Branding — spec visual

**Rota:** `/admin/branding/sandbox` (dentro do `AdminLayout`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminBrandingSandboxPage.tsx` (153 linhas); componentes: `modules/admin/components/ColorPicker.tsx`, `BrandingPreview.tsx`; tema: `theme/tenant-theme/resolver.ts`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-branding-sandbox/dark-default.png` | `../screenshots/admin-branding-sandbox/light-default.png` |
| preset-aplicado | `../screenshots/admin-branding-sandbox/dark-preset-aplicado.png` | — (página já recolorida pelos vars do preset) |

## Layout — regiões

- Conteúdo: `padding: 32px`, `maxWidth: 1100px`.
- Header breadcrumb: `← Tenants` (13px `#668096`) + `/` (`#334155`) + H2 `Sandbox` (20px/700 `#f0f4f8`) com ícone `FlaskConical` 18px `#a78bfa` + badge condicional `Aplicado na página` (bg `rgba(167,139,250,0.12)`, texto `#a78bfa`, 11px/600).
- Descrição 13px `#668096`, `margin: 0 0 24px`.
- Barra de presets: flex wrap, `gap: 8`, `marginBottom: 28`.
- Grid `1fr 320px`, `gap: 32`: painel "Cores" (esq.) + painel de preview sticky (`top: 20`, dir.).

## Árvore de componentes

- `AdminBrandingSandboxPage`
  - Chip de preset (×6): bg `#111318`, border `1px solid` (`#2a3545` se `primary === p.primary`, senão `#1e2730`), radius 6, padding `5px 12px`, texto 12px `#8ba3bc`; 2 bolinhas 10×10 (primária/acento). Sem hover.
  - Painel "Cores" (div hardcoded bg `#111318` border `#1e2730` radius 10 padding 24 — NÃO usa `Panel`):
    - H3 `Cores` 15px/600 `#f0f4f8`
    - Campo "Nome do produto": label 12px `#8ba3bc` (hardcoded); input bg `#0a0c10` border `#1e2730` texto `#f0f4f8`
    - `ColorPicker` "Cor primária" / "Cor de acento" (labels TOKENIZADOS `vars.color.textSecondary`; input hex `vars.color.bgSurface` — mistura token+hardcode no mesmo painel)
    - Ações: botão `Aplicar na página` (bg `#7c3aed`, texto `#fff`, 13px/600) ⟷ `Remover da página` (bg `rgba(167,139,250,0.1)`, border `rgba(167,139,250,0.3)`, texto `#a78bfa`) + botão `Resetar` (transparent, border `#1e2730`, texto `#668096`, ícone RotateCcw)
  - Painel de preview (div hardcoded `#111318` radius 10 padding 20, sticky):
    - `BrandingPreview` sem prop `surfaces` → mini-telas sempre nas superfícies dark padrão (LOGIN / PAINEL + MODAL / DASHBOARD, ver admin-branding-editor.md)

## Copy exata

- Título: `Sandbox` · badge `Aplicado na página`
- Descrição: `Experimente combinações de cores livremente. Nada é salvo — use para testar paletas antes de aplicar a um tenant.`
- Presets: `Recognition` (#06b6d4/#ea580c) · `Verde Industrial` (#16a34a/#f59e0b) · `Azul Corporativo` (#2563eb/#f59e0b) · `Roxo Tech` (#7c3aed/#f97316) · `Vermelho Crítico` (#dc2626/#06b6d4) · `Teal Segurança` (#0d9488/#fb923c)
- Painel: `Cores` · `Nome do produto` · `Cor primária` · `Cor de acento`
- Botões: `Aplicar na página` · `Remover da página` · `Resetar`
- Defaults: `Recognition` / `#06b6d4` (8.06:1 AA ✓) / `#ea580c` (5.50:1 AA ✓)

## Dados de exemplo

- Estado local puro (useState) — não há endpoints além dos do `AdminLayout`. Fixture preset-aplicado: `Verde Industrial` aplicado (`#16a34a` 5.94:1 ✓ / `#f59e0b` 9.11:1 ✓), badge visível, botão `Remover da página`, página recolorida via `style#recognition-tenant-theme`.

## Estados

- **default**: valores Recognition; botão roxo `Aplicar na página`.
- **preset selecionado**: só a borda do chip muda `#1e2730 → #2a3545` (quase invisível).
- **preset-aplicado**: badge no header + botão vira `Remover da página` + CSS vars aplicados em `:root` (preview do editor recolore o app inteiro — capturado só em dark).
- **hover**: inexistente em chips e botões.
- **empty/loading/error**: não existem (estado local, nada é salvo).

## Navegação e fluxos

- `← Tenants` → `/admin/branding/tenants`.
- Chip → seta primária/acento locais.
- `Aplicar na página` → `resolveTheme({brand, colors})` → injeta em `style#recognition-tenant-theme`; `Remover da página`/`Resetar` limpam (Resetar também restaura defaults).

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P0 (light)** Título `Sandbox` `#f0f4f8` hardcoded → invisível sobre bgBase claro (`1.01:1`).
2. **P1 (light)** Labels do `ColorPicker` ("Cor primária"/"Cor de acento") tokenizados (`textSecondary` → `#3f4650` no claro) sobre painel HARDCODED `#111318` → `1.95:1`, ilegível — colisão token×hardcode.
3. **P1** Painéis, chips e inputs hardcoded dark (`#111318`/`#0a0c10`/`#1e2730`) — ilhas escuras sob white-label claro; inputs hex do ColorPicker (tokenizados) viram caixas brancas dentro do painel escuro.
4. **P2** Botão `Aplicar na página` roxo `#7c3aed` + família `#a78bfa` fora da paleta Recognition (herança pré-rebrand) — deveria usar `vars.color.primary`/badge tokenizado.
5. **P2 (light)** Descrição/breadcrumb `#668096` → `3.78:1`.
6. **P3 (dark)** Separador `/` `#334155` sobre bgBase = `1.89:1` (decorativo, mas abaixo de 3:1 e fora dos tokens de borda).
7. **P3** Estado selecionado do preset imperceptível (só borda) e compara apenas `primary`; sem hover em nenhum interativo.
8. **P3** Sandbox só edita marca (nome+2 cores) — sem as superfícies WS1 que o editor tem; usuário não consegue testar paletas claras completas aqui.

## Findings (develop — 2026-07-07)

| # | Sev | Tema | Componente | Descrição | Status |
|---|-----|------|-----------|-----------|--------|
| F-1 | P0 | light | Breadcrumb/título | Título "Sandbox" #f0f4f8 hardcoded invisível em bgBase claro (1.01:1) — confirmado em light-default.png | **persists** |
| F-2 | P1 | light | ColorPicker labels | Labels "Cor primária"/"Cor de acento" tokenizadas (textSecondary #3f4650) sobre painel hardcoded #111318 → 1.95:1 | **persists** |
| F-3 | P1 | light | Painel/chips/inputs | Ilhas dark hardcoded (#111318/#0a0c10/#1e2730) sob bgBase claro — confirmadas em light-default.png | **persists** |
| F-4 | P2 | ambos | Botão "Aplicar" | Roxo #7c3aed + família #a78bfa fora da paleta ciano Recognition — visível em dark-default.png | **persists** |
| F-5 | P2 | light | Descrição/breadcrumb | #668096 → ~3.78:1 sobre bgBase claro — abaixo de WCAG AA 4.5:1 para 13px | **persists** |
| F-6 | P3 | dark | Separador breadcrumb | "/" #334155 sobre bgBase dark = 1.89:1 (decorativo, fora dos tokens) | **persists** |
| F-7 | P3 | ambos | Chips de preset | Estado selecionado imperceptível (só borda); sem hover em interativos | **persists** |
| F-8 | P3 | ambos | Layout | Sandbox não expõe superfícies WS1; paletas claras não podem ser testadas completamente | **persists** |
| N-1 | P1 | light | Descrição/breadcrumb | **task-065 regression (condicional):** se WS1 (d7a3ad3) tokenizou a descrição/breadcrumb para `vars.color.textMuted`, o valor #8a8a93 cai para ~3.30:1 — pior que F-5 (3.78:1). Verificar `AdminBrandingSandboxPage.tsx`. | **new** |

**Resolved:** nenhum nesta passagem.
