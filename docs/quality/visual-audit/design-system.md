# Auditoria de Design System — Recognition Frontend

> **Data:** 2026-07-07 · **Branch:** `feat/redesign-ocean-light` (merge target: `develop`) · **Escopo:** `apps/frontend/src/`
> **Stack:** React 18 + TypeScript + Vite + vanilla-extract (`createThemeContract` / `createTheme` / `recipe`)
> **Atualização vs staging:** task-065 subiu `textMuted` em `professional.css.ts` de `#71717a` para `#8a8a93`. Fase 1+2 redesign adicionou `recognition-light` (Ocean Blue) como tema padrão e corrigiu NS-01/S-04.

---

## 1. Arquitetura de temas

| Camada | Arquivo | Papel |
|---|---|---|
| **Contrato** | `src/styles/theme.css.ts` | `createThemeContract` — define TODOS os tokens (`vars.color.*`, `space`, `radius`, `font`, `shadow`, `animation`). Componentes nunca devem usar valor cru. |
| **Tema padrão** | `src/theme/tokens/recognition-dark.css.ts` | Recognition Dark ("Shop Floor": preto profundo, ciano elétrico, laranja-segurança). Cada token tenant-configurável referencia CSS var plana com fallback: `var(--color-bg-base, #0a0c10)`. |
| **Temas legacy** | `src/styles/themes/professional.css.ts`, `cyberpunk.css.ts` | Mantidos por compatibilidade. **Não têm bridge white-label** (valores fixos). `professional.css.ts` teve `textMuted` atualizado para `#8a8a93` em task-065. |
| **Seleção de tema** | `src/stores/themeStore.ts` + `src/theme/useTheme.ts` | `ThemeMode = 'recognition-dark' \| 'cyberpunk' \| 'professional'`; default `recognition-dark`; `toggleMode()` alterna apenas professional ↔ recognition-dark. |
| **White-label** | `src/theme/ThemeProvider.tsx` + `src/theme/tenant-theme/` | Busca `GET /api/v1/tenant/branding?tenant_id=`, resolve overrides e injeta `<style id="recognition-tenant-theme">:root { --color-*: ... }</style>` no `<head>`. Fallback silencioso pro default em erro (timeout 5s). |
| **Gráficos** | `src/theme/chartColors.ts` | Paleta Recharts/SVG tokenizada (`chartColors.primary/accent/...`, `chartSeries[6]`). |
| **Global** | `src/styles/global.css.ts` | Reset + tipografia base (`Inter Variable`), focus ring e scrollbar com ciano hardcoded anotado `// allow:`. |

---

## 2. Tokens

### 2.1 Paleta de cores por tema (hex)

| Token | **recognition-light** (novo default) | recognition-dark | professional (legacy) | cyberpunk (legacy) |
|---|---|---|---|---|
| `bgBase` | `#F8FAFC` (Slate-50) | `#0a0c10` | `#0a0a0f` | `#030305` |
| `bgSurface` | `#FFFFFF` | `#111318` | `#13131a` | `#0c0c12` |
| `bgElevated` | `#FFFFFF` | `#1e2330` | `#1a1a22` | `#121218` |
| `bgCard` | `#FFFFFF` | `#161a20` | `#20202a` | `#18181f` |
| `bgHover` | `#F1F5F9` | `#1a1f27` | `#282832` | `#1e1e28` |
| `textPrimary` | `#0F172A` | `#f0f4f8` | `#f1f5f9` | `#f1f5f9` |
| `textSecondary` | `#334155` | `#8ba3bc` | `#a1a1aa` | `#94a3b8` |
| `textMuted` | `#64748B` (4.76:1/bgSurface AA; 4.34:1/bgHover ⚠️) | `#668096` | **`#8a8a93`** (3.30:1/branco ⚠️) | `#64748b` |
| `textDim` | `#94A3B8` (2.56:1 — DECORATIVO) | `#2a3a4a` | `#52525b` | `#475569` |
| `primary` | `#0369A1` (Ocean Blue; **5.93:1**/white AA) | `#06b6d4` (ciano) | `#8b5cf6` (violeta) | `#8b5cf6` |
| `primaryLight` | `#0284C7` (**4.10:1**/white ⚠️ não usar como bg de botão) | `#22d3ee` | `#a78bfa` | `#a78bfa` |
| `primaryDark` | `#075985` (7.56:1/white AAA) | `#0891b2` | `#7c3aed` | `#7c3aed` |
| `primaryAlpha` | `rgba(3,105,161,0.10)` | `rgba(6,182,212,0.1)` | `rgba(139,92,246,0.1)` | `rgba(139,92,246,0.12)` |
| `accent` | `#B45309` (Amber; 5.02:1/white AA) | `#ea580c` | `#22d3ee` | `#22d3ee` |
| `accentLight` | `#0EA5E9` (Sky-500; 2.77:1 ⚠️ decorativo) | `#f97316` | `#67e8f9` | `#67e8f9` |
| `accentDark` | `#92400E` (7.09:1/white AAA) | `#c2410c` | `#06b6d4` | `#06b6d4` |
| `accentAlpha` | `rgba(180,83,9,0.10)` | `rgba(234,88,12,0.12)` | `rgba(34,211,238,0.08)` | `rgba(34,211,238,0.1)` |
| `success` | `#15803D` (5.02:1/white AA) | `#10b981` | `#10b981` | `#10b981` |
| `successMuted` | `#F0FDF4` | `rgba(16,185,129,0.1)` | `…0.12` | `…0.15` |
| `warning` | `#A16207` (4.92:1/white AA) | `#f59e0b` | `#f59e0b` | `#f59e0b` |
| `warningMuted` | `#FFFBEB` | `rgba(245,158,11,0.1)` | `…0.1` | `…0.12` |
| `danger` | `#B91C1C` (6.47:1/white AA) | `#ef4444` | `#ef4444` | `#ef4444` |
| `dangerMuted` | `#FEF2F2` | `rgba(239,68,68,0.1)` | `…0.12` | `…0.15` |
| `borderSubtle` | `#F1F5F9` (1.10:1 — divisória, não texto) | `#161c24` | `rgba(255,255,255,0.05)` | `rgba(139,92,246,0.20)` |
| `borderDefault` | `#E2E8F0` (1.23:1 — divisória) | `#1e2730` | `rgba(255,255,255,0.08)` | `rgba(139,92,246,0.32)` |
| `borderStrong` | `#CBD5E1` (1.48:1 — divisória) | `#2a3545` | `rgba(255,255,255,0.14)` | `rgba(139,92,246,0.52)` |
| `overlay` | `rgba(15,23,42,0.48)` | `rgba(0,0,0,0.7)` | `rgba(0,0,0,0.7)` | `rgba(0,0,0,0.75)` |
| `textOnPrimary` | `#FFFFFF` (5.93:1/primary AA; 7.56:1/primaryDark AAA) | `#ffffff` (2.43:1/ciano — S-01) | `#ffffff` | `#ffffff` |

> **recognition-light — Contraste WCAG (script verificado 2026-07-07):**
> - `primary #0369A1` / branco = **5.93:1 AA** ✓ (correção: claim anterior de "7.6:1" estava errado)
> - `textMuted #64748B` / `bgHover #F1F5F9` = **4.34:1** ⚠️ — falha AA (4.5) para texto normal; passa large-text (3.0). Aceito para textos secundários em hover.
> - `primaryLight #0284C7` / branco = **4.10:1** ⚠️ — não usar como fundo de botão com texto branco
> - `textDim #94A3B8` = 2.56:1 — DECORATIVO ONLY (espaçador/placeholder, sem texto funcional)
> - Borders (`borderSubtle/Default/Strong`) abaixo de 3.0 — aceitável (não-texto, apenas separadores visuais)

> **Finding S-01 (recognition-dark/cyberpunk):** `textOnPrimary '#ffffff'` sobre `primary '#06b6d4'` = 2.43:1 — falha WCAG AA. Não afeta recognition-light.

> **Finding task-065 / admin-audit-log:** `textMuted #8a8a93` no professional = 3.30:1 sobre `#ffffff` — regressão de `#71717a` (4.93:1). Afeta admin em white-label claro.

Defaults white-label atualizados em `src/theme/tenant-theme/defaults.ts` (`RECOGNITION_DEFAULT_PRIMARY = #0369A1`, `RECOGNITION_DEFAULT_ACCENT = #B45309`, `RECOGNITION_DEFAULT_SURFACES` = 7 chaves para light).

### 2.2 Espaçamento (idêntico nos 3 temas)

`xs: 4px · sm: 8px · md: 16px · lg: 24px · xl: 32px · xxl: 48px`

### 2.3 Radius

| Token | recognition-dark | professional/cyberpunk |
|---|---|---|
| `sm` | 4px | 6px |
| `md` | 6px | 10px |
| `lg` | 10px | 16px |
| `xl` | 16px | 20px |
| `full` | 9999px | 9999px |

### 2.4 Tipografia

**Famílias (tokens):**
- `font.sans`: `'Inter Variable', Inter, -apple-system, BlinkMacSystemFont, sans-serif`
- `font.mono`: `'JetBrains Mono', 'Fira Code', monospace`

**Sem tokens de fontSize/fontWeight/lineHeight no contrato.** Escala hardcoded por componente:

| fontSize | usos | fontSize | usos |
|---|---|---|---|
| **13px** | 82 | 22px | 9 |
| **12px** | 65 | 28px | 8 |
| **11px** | 56 | 20px | 6 |
| 14px | 20 | 16px | 6 |
| 10px | 17 | 24px | 3 |
| 15px | 16 | 32px | 2 |
| 9px | 4 | 18px | 2 |

Corpo de fato = 12–13px (denso, dashboard); títulos de página 22–28px. Valores off-scale: 9px, 26px, 36px.

**Pesos:** `600` (79×), `700` (73×), `500` (7×), `800` (3×).

### 2.5 Sombras

| Token | recognition-dark | professional | cyberpunk |
|---|---|---|---|
| `sm` | `0 2px 8px rgba(0,0,0,0.5)` | `…0.3` | `…0.4` |
| `md` | `0 4px 16px rgba(0,0,0,0.6)` | `…0.4` | `…0.5` |
| `lg` | `0 8px 40px rgba(0,0,0,0.7)` | `0 8px 32px …0.5` | `0 8px 32px …0.6` |
| `glow` | `var(--shadow-glow, 0 0 0 3px rgba(6,182,212,0.12))` (focus ring, bridged) | `none` | glow duplo violeta |
| `glowCyan` | `0 0 12px rgba(6,182,212,0.3)` | `none` | glow duplo ciano |
| `glowDanger` | `0 0 12px rgba(239,68,68,0.3)` | `none` | `0 0 20px rgba(239,68,68,0.4)` |

### 2.6 Animação

| Token | recognition-dark | professional | cyberpunk |
|---|---|---|---|
| `enabled` | `'1'` | `'0'` | `'1'` |
| `duration` | 0.2s | 0s | 0.25s |
| `durationSlow` | 0.4s | 0s | 0.5s |
| `easing` | `cubic-bezier(0.4,0,0.2,1)` | `linear` | `cubic-bezier(0.4,0,0.2,1)` |

### 2.7 Breakpoints / media queries

Não há sistema de breakpoints. **9 usos de `@media`, todos `(max-width: 768px)`**, concentrados em 3 arquivos:
- `src/components/dashboard/KPIRow.css.ts` (1×)
- `src/modules/admin/AdminLayout.css.ts` (7×)
- `src/pages/ModuleSelectionPage.css.ts` (1×)

O resto do app não é responsivo por CSS.

---

## 3. Bridge white-label (WS1 — estado develop)

### 3.1 Mecanismo

`resolver.ts → resolveTheme(overrides)` gera mapa `--color-*` e o `ThemeProvider` injeta em `:root` via tag `<style>`. O tema `recognition-dark.css.ts` consome cada var com fallback. Sem rebuild para customizações.

### 3.2 Tokens configuráveis por tenant

| Grupo | Campo | CSS vars geradas | Derivação automática |
|---|---|---|---|
| `colors` | `primary` | `--color-primary`, `--color-primary-light`, `--color-primary-dark`, `--color-primary-alpha`, `--shadow-glow` | light = `primaryHover ?? lightenHex(+30)`; dark = `darkenHex(−30)`; alpha = rgba 0.1; glow = `0 0 0 3px rgba(p,0.12)` |
| `colors` | `accent` | `--color-accent`, `-light`, `-dark`, `-alpha` | lighten/darken ±30; alpha 0.12 |
| `surfaces` | `bgBase` | `--color-bg-base` | — |
| `surfaces` | `bgSurface` | `--color-bg-surface`, **`--color-bg-hover`** | hover = `lightenHex(bgSurface, +10)` ← ERRADO para tema claro (S-06) |
| `surfaces` | `bgElevated` | `--color-bg-elevated` | — |
| `surfaces` | `bgCard` | `--color-bg-card` | — |
| `surfaces` | `textPrimary` | `--color-text-primary` | — |
| `surfaces` | `textSecondary` | `--color-text-secondary`, **`--color-text-muted`** | muted = `darkenHex(textSecondary, −24)` |
| `surfaces` | `border` | `--color-border`, `--color-border-subtle`, `--color-border-strong` | subtle = darken −10; strong = lighten +18 |
| `brand` | `productName`, `logoUrl`, `logoMonoUrl`, `faviconUrl` | (não-CSS: title, logos, favicon) | — |

### 3.3 Tokens que NÃO são configuráveis (gaps do bridge)

| Token | Situação | Risco | Status develop |
|---|---|---|---|
| **`bgHover`** | Só derivado por `lightenHex(bgSurface,10)` — ERRADO para temas claros | Alto — hover imperceptível no white-label claro | PERSISTS (S-06) |
| **`textMuted`** | Derivado de `textSecondary` (`darkenHex−24`); não configurável direto. `professional` subiu para `#8a8a93` em task-065 criando regressão no claro (3.30:1) | Médio + nova regressão | REGRESSÃO (task-065) |
| **`textDim`** | Sem CSS var — fixo `#2a3a4a`. Cor de placeholder do `Input` | Médio | PERSISTS |
| `textOnPrimary` | Fixo `#ffffff` — 2.43:1 sobre primary ciano | Médio | PERSISTS (S-01) |
| `success/warning/danger` + `*Muted` | Fixos (sem var). `*Muted` são rgba para fundo escuro | Baixo | PERSISTS |
| `overlay` | Fixo `rgba(0,0,0,0.7)` (token canônico, `allow:`) | Baixo | OK |
| `shadow.sm/md/lg`, `glowCyan`, `glowDanger` | Fixos. Só `glow` é bridged | Baixo | PERSISTS |
| `space/radius/font/animation` | Não configuráveis (esperado) | — | OK |
| Temas legacy (`professional`, `cyberpunk`) | Nenhuma var — white-label só funciona em `recognition-dark` | Info | PERSISTS |

---

## 4. Catálogo de componentes

### 4.1 UI kit — `src/components/ui/` (19 componentes)

| Componente | Variantes / API | Estados | Tokens | Adoção (arquivos que importam) |
|---|---|---|---|---|
| **Button** | `variant: primary\|secondary\|danger\|ghost\|success` · `size: sm(28px)\|md(36px)\|lg(42px)` · `loading` | `:hover` por variante, `:disabled` opacity 0.45 | 100% tokenizado (fontSize 12/14/15px hardcoded) | **17** |
| **Modal** | Radix Dialog · `title`, `footer?`, `maxWidth?` (default 520px) | backdrop `vars.color.overlay` + blur(4px), animações | `bgElevated`, `borderDefault`, `radius.xl`, `shadow.lg` | **5** — subutilizado (NS-01: portal fora do tema) |
| **ConfirmDialog** | wrapper de Modal + Button · `variant: danger\|primary`, `loading` | herda Modal | herdado | 1 |
| **AppDrawer** | painel lateral · `size: sm\|md\|lg\|xl` | overlay = `vars.color.overlay` | tokenizado (NS-01: portal fora do tema) | 2 |
| **Card** | `hoverable?` | hover style | `bgCard`, borders | **0 — órfão** |
| **Panel** | WS1 · `variant: surface\|card\|elevated` · `title/subtitle/actions` · `padding: none\|md\|lg` | — | `bgSurface/bgCard/bgElevated`, `borderDefault`, `radius.lg` | 2 (adoção inicial) |
| **Badge** | `variant: success\|warning\|danger\|primary\|neutral\|accent` | — | pares `*Muted`+cor semântica; 11px/700 uppercase | 8 |
| **DataTable** | genérico `<T>`, sort asc/desc | — | tokenizado | **0 — órfão** |
| **Input** + `Field` | forwardRef, `error?` | `:focus` borda primary | `bgSurface`, `borderDefault`, `danger` | 2 |
| **Toast** + `useToast** | `variant`, provider global | animações | tokenizado | 15 |
| **Banner** | `variant: info\|success\|warning\|danger`, `onDismiss` | — | tokenizado | **0 — órfão** |
| **Tooltip** | Radix, `side`, `delayDuration=300` | — | tokenizado (NS-01: portal fora do tema) | **0 — órfão** |
| **Popover** | Radix, `side/align`, controlado | — | tokenizado (NS-01: portal fora do tema) | **0 — órfão** |
| **Skeleton** + SkeletonGroup | `variant: text\|title\|circle\|rect` | shimmer | tokenizado | 12 |
| **Stepper** | `steps/current`, `orientation` | — | tokenizado | 3 |
| **EmptyState** | `icon/title/description/action` | — | tokenizado | só interno |
| **PageHeader** | `title/subtitle/actions` | — | tokenizado | 1 |
| **NotificationBell** | sino + dropdown + deep-links (WS6) | — | tokenizado | uso no layout |
| **ThemeToggle** | alterna professional↔recognition-dark | — | — | 2 |

### 4.2 `shared/` e `layout/` — mudanças no develop

- `layout/TopBar` + `CollapsibleSidebar` + `HealthFooter` + `StatusBadge` (labels pt-BR) alterados em WS1/WS6.
- `StatusBadge` agora traduzido para pt-BR — verificado visualmente.
- `NotificationBell` com deep-links adicionado em WS6.
- `ImpersonationBanner` novo em `App.tsx` (WS6) — não corrigiu S-04 (ThemeProvider fora do gate pré-auth).
- `AdminLayout.tsx` recebeu item 'Configurações' na sidebar + tentativa de fix rules-of-hooks (S-05) — fix NÃO confirmado no código develop.
- `layout/Header/` sem mudanças — legacy/órfão com hardcode `#fff` anotado `allow:`.

### 4.3 Padrões concorrentes (duplicação — sem mudança no develop)

**Cards:** `ui/Card` com 0 consumidores; 7 implementações de card por domínio.

**Modais:** `ui/Modal` em 5 arquivos vs **21 arquivos** com `position: 'fixed'` hand-rolled. 16 com marcador `TODO-WS1`. task-066 corrigiu ConfirmDialog e ToastProvider mas não os 16 restantes.

**Tabelas:** `ui/DataTable` órfão; listagens usam `<table>` próprias.

---

## 5. Gaps e hardcodes

### 5.1 Guard-rail — estado após extensão (feat/redesign-ocean-light, 2026-07-07)

Guard-rail: `src/theme/__tests__/no-offbrand-colors.test.ts` — **4 describe blocks**:

| Bloco | Escopo | Regras |
|---|---|---|
| `guard-rail: cores fora da marca (WS1)` | `src/**/*.tsx` | bg claros hardcoded, azuis fora da marca, violet legacy, backdrop rgba hand-rolled |
| **`guard-rail: violet legacy em .css.ts`** (novo) | `src/**/*.css.ts` (excl. 6 arquivos allowlisted com pré-existentes) | `#8b5cf6`/`rgba(139,92,246` — previne regressão tipo CameraPlayer.css.ts (corrigido) |
| **`guard-rail: NS-02 baseline`** (novo) | `src/**/*.tsx` | `color:'#f1f5f9'/'#f0f4f8'` hardcoded — baseline 34, falha se count aumentar |
| **`wcag contrasts — recognition-light`** (novo) | puro math | Verifica pares críticos; documenta 4.34 (textMuted/bgHover) e 4.10 (primaryLight) |

**Violações NS-02 conhecidas (baseline=34, medido 2026-07-07):**

| Arquivo | Count | Tela |
|---|---|---|
| `pages/CountingPage.tsx` | 7 | counting |
| `components/scenario/ModelScenarioWizard.tsx` | 4 | epi-operations, epi-scenario |
| `modules/admin/pages/DemoVideosPage.tsx` | 4 | admin-demo-videos |
| `pages/fueling/FuelingPage.tsx` | 4 | fueling |
| `pages/fueling/FuelingValidationPage.tsx` | 4 | fueling-validation |
| `pages/StreamHealthPage.tsx` | 3 | stream-health |
| `modules/admin/pages/AdminBrandingTenantsPage.tsx` | 2 | admin-branding |
| `pages/TrainingPage.tsx` | 2 | epi-training |
| `pages/epi/VerificationQueuePage.tsx` | 2 | verification-queue |
| `modules/admin/pages/AdminBrandingDefaultPage.tsx` | 1 | admin-branding |
| `components/cameras/CameraModelAssignment.tsx` | 1 | epi-cameras |
| **Total** | **34** | — |

Telas LIMPAS (sem NS-02): `EpiOperationsPage` (Operações) e `TrainingModeLayout` — confirmado por grep.

### 5.2 Estatística de hardcodes de cor (estado develop — valores approximados)

Padrões: `rgba(255…`, `rgba(0…`, hex `#xxx…` em `.ts/.tsx/.jsx` (excluindo arquivos de token).

**Total estimado: ~680 ocorrências** (−26 vs staging: task-063/065/066 removeram hardcodes em CameraFpsConfig, CameraPlayer, alguns componentes admin).

Top ofensores (sem alteração significativa no develop):

| Arquivo | Hardcodes estimados |
|---|---|
| `components/AnnotationInterface.jsx` | ~68 (inalterado) |
| `pages/TrainingPage.tsx` | ~30 |
| `components/VideoTimelineSelector.jsx` | ~32 (inalterado) |
| `modules/admin/pages/AdminBrandingDefaultPage.tsx` | ~30 (inalterado) |
| `pages/fueling/FuelingPage.tsx` | ~20 (parcialmente corrigido — S-03 PARTIAL) |
| `modules/admin/pages/AdminBrandingTenantsPage.tsx` | ~20 |
| `modules/admin/pages/AdminBrandingSandboxPage.tsx` | ~23 (allowlisted) |
| `pages/CountingPage.tsx` | ~15 (NS-02) |
| `components/scenario/ModelScenarioWizard.tsx` | ~13 (NS-02 parcial) |

### 5.3 Hardcodes NS-02 — `color: '#f1f5f9'` endêmico

Classe de defeito nova detectada no develop além do módulo Fueling (S-03):

| Arquivo | Ocorrências | Tela afetada |
|---|---|---|
| `pages/CountingPage.tsx` | 7 | counting |
| `components/scenario/ModelScenarioWizard.tsx` | 4 | epi-operations, epi-scenario-editor |
| `pages/TrainingPage.tsx` | 2 | epi-training |
| `pages/epi/VerificationQueuePage.tsx` | 2 | verification-queue |
| `modules/admin/pages/DemoVideosPage.tsx` | 4 | admin-demo-videos |
| `components/cameras/CameraModelAssignment.tsx` | 1 | epi-cameras |
| `pages/StreamHealthPage.tsx` | 3 | stream-health |
| **Total extras** | **23** | — |

Somados aos 10 do S-03 em Fueling: **33+ ocorrências** de `color: '#f1f5f9'` no codebase ativo.

### 5.4 Resumo dos gaps estruturais (develop)

1. **Tipografia sem tokens** — 16 tamanhos distintos (9–36px) e 4 pesos hardcoded em ~300 pontos; contrato só tem `font.sans/mono`. Sem alteração no develop.
2. **Sem sistema de breakpoints** — único breakpoint de fato (768px) em 3 arquivos. Sem alteração.
3. **Bridge white-label incompleto** — `bgHover` derivado por `lightenHex` (errado para claro), `textDim` sem var, `textOnPrimary` fixo `#fff`, `*Muted` rgba pensados pro dark. `textMuted` de `professional` subiu para `#8a8a93` criando nova regressão no claro. Temas legacy sem bridge.
4. **Kit subadotado** — Card/DataTable/Banner/Tooltip/Popover órfãos; Modal em só 5 arquivos vs 21 overlays `position:fixed` hand-rolled (16 com `TODO-WS1`). Sem redução significativa no develop.
5. **NS-01 novo:** Quatro componentes Radix (Modal, Popover, Tooltip, AppDrawer) montam portais em `document.body` fora da classe `recognitionDarkTheme`. Fix único: `document.body.className = recognitionDarkTheme` em `AppShell`.
6. **NS-02 novo:** `color: '#f1f5f9'` endêmico em 7+ arquivos além do Fueling (33+ ocorrências). Guard-rail não detecta esse padrão.
7. **S-07 StreamHealthPage persiste:** 348 linhas de inline styles; rota `/epi/health` mantida sem redirect para a nova `admin-observability`.
