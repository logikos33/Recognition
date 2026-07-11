# Seleção de Módulo — spec visual

**Rota:** `/modules`
**Fontes:** `apps/frontend/src/pages/ModuleSelectionPage.tsx` · `apps/frontend/src/pages/ModuleSelectionPage.css.ts` · monta dentro de `AppLayout` (header/topbar + `ChatFAB`; `HealthFooter` visível para superadmin) · `useAuth` (`hasModule`, `isSuperAdmin`) · `appStore.setSelectedModule`
**Screenshots:**

| Estado | Dark | Light (white-label) |
|---|---|---|
| default (operator, 3 módulos) | `../screenshots/module-selection/dark-default.png` | `../screenshots/module-selection/light-default.png` |
| modules-limited (operator, só `epi`) | `../screenshots/module-selection/dark-modules-limited.png` | `../screenshots/module-selection/light-modules-limited.png` |
| role-superadmin (só `epi` + override) | `../screenshots/module-selection/dark-role-superadmin.png` | `../screenshots/module-selection/light-role-superadmin.png` |
| hover-card-epi | `../screenshots/module-selection/hover-card-epi.png` | — |
| hover-card-quality | `../screenshots/module-selection/hover-card-quality.png` | — |

## Layout — regiões

- **Topbar (AppLayout)**: hambúrguer, logo, breadcrumb `EPI / Módulos`, sino de notificações, toggle `Pro`, usuário `Auditor Visual` + badge de role (`OPERATOR` verde / `SUPERADMIN` laranja) + botão `Sair`.
- **Conteúdo (page)**: `flex: 1`, coluna centrada (horizontal+vertical), `padding: vars.space.xl` (32px). Fundo com **mesh animado** via `::before`: 3 radial-gradients `rgba(139,92,246,0.08/0.04)` (violeta) + `rgba(6,182,212,0.06)` (ciano), `backgroundSize 200%`, animação `meshMove` 20s infinita, `pointerEvents: none`.
- **header**: centrado, `marginBottom: vars.space.xxl` (48px), zIndex 1.
- **cardsRow**: `display: flex; gap: vars.space.xl` (32px); `@media (max-width: 768px)` vira coluna centrada.
- **ChatFAB**: botão flutuante circular ciano no canto inferior direito.
- **HealthFooter** (só superadmin): barra 32px no rodapé, `bgSurface`, borda superior `borderSubtle`, itens 11px mono `textDim` com dots de status (`Banco de dados`, `Redis`, `câmeras ativas`).

## Árvore de componentes

- `page` (mesh ::before)
  - `header`
    - `title` — h1 32px/800, letterSpacing -0.02em, **gradient text** 135° `textPrimary → primaryLight` (WebkitBackgroundClip: text)
    - `subtitle` — 15px `textSecondary`, maxWidth 480px
  - `cardsRow`
    - **Card EPI** (sempre ativo) — `card`: 340px, `bgCard`, borda 1px `borderDefault`, radius `vars.radius.xl` (16px), padding 32px, coluna gap 16px, `cursor: pointer`, `role="button"`, `tabIndex=0`
      - `cardIconWrap` — 56×56, radius 10, gradient `rgba(139,92,246,0.15) → rgba(6,182,212,0.1)`, borda `borderSubtle`; ícone lucide `Shield` 28px cor `vars.color.primaryLight`
      - `badgeActive` — pill (radius full), 12px/700 uppercase, letterSpacing 0.04em, fundo `rgba(16,185,129,0.15)`, texto `vars.color.success`, borda `rgba(16,185,129,0.3)`; `badgeDot` 6px `success` com animação `pulseGreen` 2s
      - `cardTitle` — h2 20px/700, gradient text `textPrimary → primaryLight`
      - `cardDesc` — 14px/1.6 `textSecondary`
      - `cardCta` — `marginTop: auto`, 13px/600 `vars.color.primaryLight`, flex gap 4px, ícone `ArrowRight` 14px
    - **Card Qualidade Industrial** — ativo se `hasModule('quality')`; ícone `Microscope` 28px cor **`#34d399` hardcoded** (ativo) ou `textMuted` (desabilitado)
    - **Card Controle de Carregamento** — ativo se `isSuperAdmin || hasModule('fueling')`; ícone `Truck` 28px cor **`#f59e0b` hardcoded** (ativo) ou `textMuted` (desabilitado)
    - **Variante desabilitada** (`cardDisabled = [card, ...]`): `opacity: 0.55`, `cursor: not-allowed`, hover neutralizado, sem `cardCta` e sem `tabIndex`; `badgeComingSoon` — pill fundo `rgba(249,115,22,0.15)`, texto `vars.color.warning`, borda `rgba(249,115,22,0.3)`, sem dot

## Copy exata

| Elemento | Texto |
|---|---|
| Título | `Selecione o Módulo` |
| Subtítulo | `Escolha o módulo de monitoramento para acessar o dashboard e as câmeras.` |
| Badge ativo | `Ativo` (renderiza `ATIVO` por `textTransform: uppercase`) |
| Badge desabilitado | `Em breve` (renderiza `EM BREVE`) |
| Card 1 título | `EPI` |
| Card 1 desc | `Monitoramento inteligente de Equipamentos de Proteção Individual. Detecção em tempo real via câmeras CCTV com visão computacional YOLOv8.` |
| Card 2 título | `Qualidade Industrial` |
| Card 2 desc | `Inspeção visual automatizada com YOLO, controle estatístico de processo (CEP) e relatórios de turno em tempo real.` |
| Card 3 título | `Controle de Carregamento` |
| Card 3 desc | `Acompanhamento de operações de carga e descarga. Contabilização automática de materiais e verificação de qualidade em tempo real.` |
| CTA | `Acessar módulo` + ícone → |
| aria-labels (ativos) | `Acessar módulo EPI` · `Acessar módulo Qualidade Industrial` · `Acessar módulo Controle de Carregamento` |
| aria-labels (desabilitados) | `Módulo Qualidade Industrial em breve` · `Módulo Controle de Carregamento em breve` |

## Dados de exemplo (fixtures)

Página 100% client-side — sem endpoint próprio (role + modules vêm do user no `localStorage`).

- **default**: user `Auditor Visual`, role `operator`, `modules: ['epi','fueling','quality']` → 3 cards ativos.
- **modules-limited**: role `operator`, `modules: ['epi']` → EPI ativo; Qualidade e Carregamento `EM BREVE` (opacity 0.55).
- **role-superadmin**: role `superadmin`, `modules: ['epi']` → Carregamento **ativo por override de role**; Qualidade `EM BREVE`; `HealthFooter` visível no rodapé.

## Estados

- **default** — 3 cards ativos com badge `ATIVO` pulsante e CTA.
- **modules-limited** — cards sem módulo: `cardDisabled` (opacity 0.55, badge `EM BREVE` laranja, sem CTA, hover morto).
- **role-superadmin** — igual ao limited, mas Carregamento ativo (evidência do override por role); barra HealthFooter aparece.
- **hover (card ativo)** — `translateY(-4px)`, `boxShadow: vars.shadow.glow`, borda `borderStrong` (transition 0.2s). Confirmado em `hover-card-quality.png`.
- **focus** — anel global `:focus-visible` `2px solid rgba(6,182,212,0.6)` + offset 2px (global.css.ts).
- **loading/empty/error** — N/A: página não faz request.

## Navegação e fluxos

- **Card EPI** → `setSelectedModule('epi')` + `navigate('/epi/dashboard')`.
- **Card Qualidade** → `setSelectedModule('quality')` + `navigate('/quality/dashboard')`.
- **Card Carregamento** → `setSelectedModule('fueling')` + `navigate('/fueling/dashboard')`.
- Teclado: `Enter`/`Espaço` disparam a mesma ação (onKeyDown nos cards ativos).
- Cards desabilitados: nenhuma ação (aria-disabled, sem handler).

## Problemas identificados

1. **[P1 — light]** `cardCta` "Acessar módulo" `#22d3ee` sobre `#eceef1` = **1.55:1**; badges `ATIVO` **1.93:1** e `EM BREVE` **1.61:1**; porção ciano dos títulos gradient **1.55–1.66:1**. Tokens de acento/status otimizados para dark não têm contraparte clara no bridge white-label (classe task-063).
2. **[P2 — both]** `cardDisabled` com `opacity: 0.55` no container derruba TODO o conteúdo abaixo do AA: dark desc **2.83:1** / badge **2.94:1**; light desc **2.67:1** / badge **1.31:1**.
3. **[P2 — hardcode]** Hex/rgba literais fora de token: `#34d399` e `#f59e0b` nos ícones (TSX), violeta `rgba(139,92,246,…)` (mesh + iconWrap) fora da paleta da marca, `rgba(16,185,129,…)`/`rgba(249,115,22,…)` nos badges apesar de existirem `successMuted`/`warningMuted`/`primaryAlpha`.
4. **[P1 — dark]** `HealthFooter` (superadmin): texto 11px `textDim #2a3a4a` sobre `bgSurface #111318` = **1.59:1** — ilegível (visível em `dark-role-superadmin.png`).
5. **[P3]** `badgeComingSoon` mistura famílias de laranja: fundo/borda orange-500 `#f97316`, texto warning âmbar `#f59e0b`.
6. **[P3]** Card desabilitado tem `role="button"` sem ser focável — semântica de botão sem comportamento; preferir remover role ou manter foco com aria-disabled.

---

## Findings (develop — 2026-07-07)

| # | Severidade | Tema | Status | Descrição |
|---|---|---|---|---|
| 1 | P1 | light | **PERSISTS** | `cardCta` "Acessar módulo →" usa `#22d3ee` (primaryLight) sobre fundo claro `#eceef1` ≈ 1.55:1; badges "ATIVO" ≈1.93:1; porção ciano dos títulos gradient ≈1.55–1.66:1. Confirmado em `light-default` e `light-modules-limited`: visualmente acessível por contraste de forma, mas falha WCAG AA de texto. |
| 2 | P1 | dark | **PERSISTS** | `HealthFooter` (superadmin): texto 11px `textDim #2a3a4a` sobre `bgSurface #111318` = 1.59:1 — ilegível. Visível em `dark-role-superadmin`. |
| 3 | P2 | both | **PERSISTS** | `cardDisabled` com `opacity: 0.55` derruba contraste de TODO o conteúdo interno abaixo do AA: dark desc 2.83:1 / badge 2.94:1; light desc 2.67:1 / badge 1.31:1. |
| 4 | P2 | both | **PERSISTS** | Hardcodes fora de token: `#34d399`/`#f59e0b` nos ícones, violeta `rgba(139,92,246,…)` (mesh + iconWrap) fora da paleta da marca, `rgba(16,185,129,…)`/`rgba(249,115,22,…)` nos badges apesar de existirem `successMuted`/`warningMuted`. |
| 5 | P3 | both | **PERSISTS** | `badgeComingSoon` mistura famílias de laranja: fundo/borda orange-500 `#f97316`, texto warning âmbar `#f59e0b`. |
| 6 | P3 | both | **PERSISTS** | Card desabilitado com `role="button"` sem `tabIndex` — semântica incorreta; usar `aria-disabled` e manter focabilidade. |
