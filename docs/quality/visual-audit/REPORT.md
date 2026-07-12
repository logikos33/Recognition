# Relatório de Auditoria Visual — Recognition (EPI Monitor V2)

> Gerado em 2026-07-07. Branch `develop`. Diff-aware contra baseline `staging`.
> Temas: `recognition-dark` (padrão) e superfícies claras white-label por tenant.
> Metodologia: Fable (planejamento de shards) + Sonnet (execução), harness Playwright (526 screenshots, 2 temas).
> Supervisor de contraste recomputou todos os ratios WCAG a partir dos hex reais dos tokens.

---

## Sumário Executivo

| Métrica | Staging (baseline) | Develop (atual) | Delta |
|---|---|---|---|
| Telas auditadas | 55 | **54** | −1 (3 removidas, 2 novas não impl.) |
| Screenshots capturados | 526 | 526 | 0 |
| Findings confirmados | 398 | **369** | **−29** |
| P0 (crítico) | 38 | **25** | −13 |
| P1 (alto) | 105 | **104** | −1 |
| P2 (médio) | 160 | **165** | +5 |
| P3 (baixo) | 95 | **75** | −20 |
| Findings novos | — | **23** | — |
| Findings resolvidos | — | **18** | — |
| Defeitos sistêmicos | 7 | **9** (7 persistem + 2 novos) | +2 |

### Distribuição por Severidade × Tema (develop, estimada)

| Severidade | dark | light | both | **Total** |
|---|---|---|---|---|
| P0 | 3 | 16 | 6 | **25** |
| P1 | 10 | 40 | 54 | **104** |
| P2 | 12 | 22 | 131 | **165** |
| P3 | 5 | 4 | 66 | **75** |
| **Total** | 30 | 82 | 257 | **369** |

### Telas Removidas do Escopo

`/epi/health` (stream-health), `/epi/sites-health` (sites-health) e `/admin/health` (admin-health) foram substituídas pela nova tela `admin-observability` (`/admin/observability` — WS9+WS11). Ambas as telas novas (`admin-observability` e `admin-demo-events`) não têm implementação no develop: 0 findings cada.

### Tasks com Impacto Visual Confirmado

| Task | Impacto visual |
|---|---|
| task-059 | Live view lazy-start sem lock órfão; Redis dedup/lock |
| task-061/062/064 | HLS substream H.264, áudio suprimido, latência reduzida |
| task-063 / PR #118 | CameraFpsConfig painel dark tokenizado; CameraPlayer clipping corrigido; painel Operação WS1 |
| task-065 / PR #119 | Guard-rail CI anti-cores-hardcoded; textMuted `professional` → `#8a8a93` |
| task-066 | ConfirmDialog opaco em ambos os temas; ToastProvider corrigido em fueling-validation |
| task-067 / PR #121 | live_view_subtype independente + fallback main stream |
| task-068 / PR #122 | Estados offline/stall no CameraPlayer; botão Reconectar ciano tokenizado |

---

## Delta vs Staging (2026-07-07)

> Comparativo entre a auditoria da staging (baseline) e o develop atual.

| Métrica | Staging | Develop | Δ |
|---|---|---|---|
| Telas auditadas | 55 | 54 | −1 |
| Screenshots | 526 | 526 | 0 |
| Findings confirmados | 398 | 369 | −29 |
| P0 (crítico) | 38 | 25 | −13 |
| P1 (alto) | 105 | 104 | −1 |
| P2 (médio) | 160 | 165 | +5 |
| P3 (baixo) | 95 | 75 | −20 |
| Telas novas | 0 | 2 | +2 |
| Defeitos S-0X resolvidos | 0 | 18 | +18 |

> Tasks mergeadas no develop que impactam findings: task-063 (Operações WS1), task-065 (guard-rail cores), task-067 (live_view_subtype), task-068 (stall detection).

---

## Defeitos Sistêmicos

> Causa-raiz única — corrigir o arquivo-fonte elimina todas as ocorrências da classe.

### S-01 — `textOnPrimary #ffffff` sobre primary ciano `#06b6d4` = 2.43:1

**Status:** PERSISTS | **Severidade:** P1 | **Temas:** both
**Evidência:** `recognition-dark.css.ts:51` e `professional.css.ts:45` — sem diff no develop.
**Telas afetadas:** epi-alerts, epi-cameras, epi-dashboard, epi-training, admin-tenants, admin-roles, admin-plans, admin-integrations, module-selection, login, training-classes, counting, fueling, fueling-validation, quality-cameras, quality-config, quality-reports e outras.
**Correção única:** `textOnPrimary: '#0a0c10'` em ambos os temas, ou escurecer `primary` para `#0891b2`.

---

### S-02 — `ToastProvider` montado em `main.tsx` fora do `AppShell`

**Status:** PERSISTS | **Severidade:** P1 | **Temas:** light
**Evidência:** `main.tsx:17` `<ToastProvider />` fora do `ThemeProvider`; `App.tsx:34` confirma.
**Telas afetadas:** epi-alerts, epi-cameras, epi-training, training-classes, admin-dashboard, admin-roles, admin-branding-editor, fueling-validation e outras.
**Correção única:** Mover `<ToastProvider>` para dentro do `AppShell` ou aplicar `recognitionDarkTheme` em `document.body`.

---

### S-03 — Hardcodes `#f1f5f9` no módulo Fueling

**Status:** PARTIAL | **Severidade:** P0 | **Temas:** light
**Evidência:** 5 ocorrências em `FuelingPage.tsx` + 5 em `FuelingValidationPage.tsx` = 10 literais + 2 defaults remanescentes. task-066 corrigiu toasts mas não os textos.
**Telas afetadas:** fueling, fueling-validation
**Correção única:** Substituir os 10 literais por `vars.color.textPrimary`.

---

### S-04 — `App.tsx` sem classe de tema no branch pré-auth + bloqueio de `/tablet/*`

**Status:** PERSISTS | **Severidade:** P0 | **Temas:** both
**Evidência:** `App.tsx:29` retorna `<Login />` antes do `ThemeProvider` (linha 34). `ImpersonationBanner` (WS6) não altera a estrutura.
**Telas afetadas:** login, tablet-kiosk
**Correção única:** (a) Aplicar `recognitionDarkTheme` no wrapper externo; (b) extrair `/tablet/*` para `Router` antes do gate de auth.

---

### S-05 — `AdminLayout.tsx` viola rules-of-hooks

**Status:** PERSISTS | **Severidade:** P1 | **Temas:** both
**Evidência:** `AdminLayout.tsx:96` `return <Navigate>` antes dos `useEffect` (linhas 99–122). Fix descrito na CLAUDE.md não confirmado no código develop.
**Telas afetadas:** todas as 21+ rotas `/admin/*`
**Correção única:** Mover `return <Navigate>` para depois do último `useEffect`.

---

### S-06 — `bgHover` invisível no tema claro (`lightenHex` em superfície já clara)

**Status:** PERSISTS | **Severidade:** P2 | **Temas:** light
**Evidência:** `resolver.ts:66` `lightenHex(s.bgSurface, 10)` sem diff. Para `bgSurface = #ffffff`, resultado = `#ffffff`.
**Correção única:** Substituir por `darkenHex(s.bgSurface, 15)`.

---

### S-07 — `StreamHealthPage` 100% inline styles

**Status:** PERSISTS | **Severidade:** P2 | **Temas:** both
**Evidência:** `StreamHealthPage.tsx` existe (348 linhas); `AppRoutes.tsx:20` mantém rota `/epi/health` sem redirect.
**Correção única:** Substituir rota por redirect para `/admin/observability` ou extrair estilos para `.css.ts`.

---

### NS-01 — Radix portals montam em `document.body` fora da classe `recognitionDarkTheme` (NOVO)

**Status:** NEW | **Severidade:** P1 | **Temas:** light (white-label)
**Diagnóstico:** `Modal.tsx`, `Popover.tsx`, `Tooltip.tsx`, `AppDrawer.tsx` usam `Dialog.Portal` sem prop `container`. Em white-label claro, CSS vars não resolvem nos portais → overlays transparentes.
**Telas afetadas:** epi-cameras, epi-training, admin-tenants, admin-users, admin-branding-editor, training-classes, counting, fueling, module-selection
**Correção única:** `document.body.className = recognitionDarkTheme` via `useEffect` no `AppShell`.

---

### NS-02 — `color: '#f1f5f9'` endêmico em 7+ arquivos além do módulo Fueling (NOVO)

**Status:** NEW | **Severidade:** P1 | **Temas:** light
**Diagnóstico:** `CountingPage.tsx` (7×), `ModelScenarioWizard.tsx` (4×), `TrainingPage.tsx` (2×), `VerificationQueuePage.tsx` (2×), `DemoVideosPage.tsx` (4×), `CameraModelAssignment.tsx` (1×), `StreamHealthPage.tsx` (3×) = 23 ocorrências extras + 10 do S-03 = **33+ total**.
**Telas afetadas:** counting, epi-training, verification-queue, admin-demo-videos, epi-cameras
**Correção única:** Substituição global + regra no guard-rail CI para detectar `'#f1f5f9'` fora de `*.css.ts`.

---

## Inventário de Problemas por Tela

> Findings confirmados no develop. Ordenados por P0+P1 decrescente.

### `verification-queue` — P0×2 P1×3 P2×2
- P0: Título e rótulos de classe `#f1f5f9` → invisíveis no light (NS-02)
- P0: Timestamps com `borderStrong` como cor de texto — 1.58:1 dark / 1.71:1 light
- P1: Erro 500 → 'Fila vazia' — falso estado saudável em tela de segurança crítica
- P1: Bordas de card com `bgSurface` — 1.05:1 dark / 1.09:1 light

### `epi-cameras` — P0×2 P1×3 P2×5 P3×1 | Resolvidos: 2 | Novos: 1
- P0 RESOLVIDO (task-066): ConfirmDialog opaco em ambos os temas
- P0 RESOLVIDO (task-063): CameraFpsConfig painel dark tokenizado
- P0 PERSISTS: CameraModelAssignment selects `color:#f1f5f9` → vazios no light (NS-02)
- P0 PERSISTS: CameraOnboardingWizard transparente no dark
- NEW P2: Seção 'Saúde do edge' adicionada — sem spec

### `epi-operations` — P0×1 P1×3 P2×3 P3×1 | Resolvidos: 2
- P0 PERSISTS: Modais wizard e excluir transparentes no dark (task-066 não aplicado)
- P1 RESOLVIDO (task-063): CameraPlayer clipping corrigido
- P2 RESOLVIDO (task-068): Botão 'Reconectar' ciano/tokenizado
- P1 PERSISTS: `STATUS_COLORS` hardcoded nas ROIs — #f59e0b = 2.15:1 sobre branco no light
- P1 PERSISTS: PositionForm descarta `onRoiChange` — impossível desenhar ROI

### `admin-tenant-detail` — P1×6 P2×5
- P1 (6 findings): `var(--border-subtle)` inexistente; separadores invisíveis; badge módulo 2.16:1; tab ativa 2.23:1; status dot sem rótulo; badges hardcoded
- P2: Feature flags com chaves cruas + checkbox nativo; erro de update silencioso

### `epi-dashboard` — P0×1 P1×5 P2×2 P3×2 | Resolvidos: 1 | Novos: 2
- P0 PERSISTS: KPI cards `rgba(12,12,18,0.8)` hardcoded no light
- NEW (WS3): Bloco INDICADORES substitui Q2/Q3/Q4 — widgets sem spec
- NEW (task-068): Células offline com 'Câmera offline — reconectando...' + botão Reconectar ciano (positivo)
- P1 PERSISTS: Hamburger sobrepõe nome da câmera 0

### `epi-training` — P0×1 P1×4 P2×3 | Resolvidos: 2 | Novos: 2
- P0 RESOLVIDO: Chips 'Classes de Detecção' legíveis
- P0 PERSISTS: Heading 'Modelo Ativo' `color:#f1f5f9` → apagado no light (NS-02)
- P1 PERSISTS: Console LOG DE EVENTOS `bg:#0a0f1a` permanece dark em light
- NEW P2: Botão 'Configurar Cenário' — rota não documentada
- NEW P2: Coluna 'COBERTURA' renomeada de 'RECALL'

### `epi-alerts` — P0×1 P1×4 P2×6 P3×3 | Resolvidos: 1 | Novos: 1
- P0 PERSISTS: Modal `bg #1a1d23` hardcoded no light
- RESOLVIDO: Valores do grid do modal legíveis no dark
- NEW: Filtro ID da câmera — 5 controles; novo campo sem `aria-label`
- P1 PERSISTS: Hover 1s dispara `POST acknowledge` sem confirmação
- P1 PERSISTS: Pendente #f59e0b = 1.85:1; Reconhecido #10b981 = 2.18:1 no light

### `admin-users` — P1×3 P2×6
- P1: Status = dot apenas sem rótulo; verde 2.54:1 sobre branco
- P1: Role badges hardcoded: Admin #2563eb = 3.01:1 dark; Operador #16a34a = 2.89:1 light
- P2: Campo 'Tenant ID' no modal pede UUID cru

### `epi-monitoring` — P1×1 P2×3 P3×1 | Resolvidos: 3 | Novos: 1
- P0 RESOLVIDO (task-066): AppDrawer opaco em ambos os temas
- P1 RESOLVIDO (task-068): Overlay 'Câmera offline' visível no drawer
- P2 RESOLVIDO: Botão 'Reconectar' ciano tokenizado
- NEW P2: Aba 'Desempenho' adicionada ao drawer — sem spec
- P1 PERSISTS: Erro `GET /cameras` engolido → 'Nenhuma câmera encontrada' indistinguível de vazio

### `epi-scenario-editor` — P0×1 P1×1 P2×6 P3×1 | Novos: 1
- P0 PERSISTS: `inputStyle color:textOnPrimary (#fff)` → 'Nome da Operação' invisível no light
- P1 PERSISTS: Chips de ferramenta inativos com `borderStrong` como texto — 1.50:1 em dark
- P2 PERSISTS: `module_code 'fueling'` exibido cru na sidebar
- NEW P2: Tipo 'Ponto de interesse' adicionado — sem spec de copy

### `training-classes` — P0×1 P1×3 P2×1 P3×1 | Resolvidos: 1
- P2 RESOLVIDO: Input do frame ID tokenizado no dark
- P0 PERSISTS: Caixa DINO `bg:#f0fdf4` hardcoded → texto invisível no dark (1.06:1)
- P1 PERSISTS: Chips ativos Colete/Sem colete = 1.99:1 / 1.79:1 no light
- P1 PERSISTS: Toast sobrepõe o header
- P1 PERSISTS: Erro 500 → 'Ativas (0)' falso-saudável

### `admin-branding-sandbox` — P0×1 P1×3 P2×2 P3×3 | Novos: 1
- P0 PERSISTS: Título 'Sandbox' `#f0f4f8` → invisível em bgBase claro (1.01:1)
- P1 PERSISTS: Painéis/chips/inputs hardcoded dark como ilhas escuras no light
- P1 NEW (task-065): `textMuted #8a8a93` → ~3.30:1 sobre bgSurface branca

### `fueling-validation` — P0×2 P1×1 P2×4 | Resolvidos: 1 | Novos: 1
- P0 PERSISTS (S-03): Título e placas `#f1f5f9` → invisíveis no light
- P0 PERSISTS: `inputStyle color:#f1f5f9` — filtros inutilizáveis no light
- RESOLVIDO (task-066): Toasts com fundo opaco
- NEW P2: Toasts opacos ainda sobrepõem a topbar em dark

### `login` — P0×1 P1×1 P2×2 P3×2
- P0 PERSISTS (S-04): Login sem classe de tema — CSS vars não resolvem
- P1 PERSISTS: Credenciais admin expostas publicamente
- P2 PERSISTS: Zero estados :hover em elementos interativos

### `investigation` — P1×3 P2×5 P3×4 | Resolvidos: 1 | Novos: 3
- P1 BUG WS4 PERSISTS: Envelope divergente — 'Erro ao buscar eventos' com HTTP 200
- RESOLVIDO: Selects/inputs tokenizados no dark (WS4 rewrite)
- NEW WS4: Filtro 'Câmeras'; ícones de info nos labels; Confiança mín. em % em vez de 0.0–1.0
- NEW: Banner de erro com botão X — fechar oculta o bug subjacente

### `admin-tenants` — P1×3 P2×7
- P1: WorkerStatusBadge light: On-premise #10b981 = 2.23:1, Railway #ca8a04 = 2.67:1
- P1: planBadge: enterprise 2.80:1 dark, standard 3.01:1 dark
- P2: Célula 'Suspenso' quebra linha

### `design-system` — P0×2 P3×3 | Resolvidos: 1
- P0 PERSISTS (NS-01): Modal sem contêiner no dark — componentes flutuam sem fundo
- P0 PERSISTS (NS-01): AppDrawer idem
- RESOLVIDO (task-066): ToastProvider produz toasts com fundo opaco
- P3: Catálogo COLOR_TOKENS lista HEX do tema dark enquanto página renderiza em light

### `admin-versions` — P1×3 P2×5 | Novos: 1
- P1 PERSISTS (S-01): btnPrimary = 2.43:1; btnDanger = 3.76:1
- P1 NEW (task-065): `textMuted #8a8a93` → ~3.30:1 no light; subtítulo, meta text, badge 'N entradas' falham AA
- P2 PERSISTS: Badge minor ciano = 2.16:1; major danger = 3.29:1 no light

### `admin-branding-editor` — P1×3 P2×1 P3×1 | Novos: 1
- P1 PERSISTS: Toast 'Visualizando como...' sobrepõe topbar
- P1 NEW (task-065): `textMuted #8a8a93` → ~3.30:1; subtítulo e breadcrumb falham AA
- P1 PERSISTS: Badge AA ✗ engana em campos de superfície/borda

### `admin-dashboard` — P0×1 P1×2 P2×5 P3×1
- P0: Toast de erro sobrepõe a topbar
- P1: Worker badges hardcoded — 2.23:1 e 2.67:1 no light
- P2: Breadcrumb duplicado 'Painel Admin / Painel Admin'

### `counting` — P0×1 P1×2 P2×2 P3×3
- P0 PERSISTS (NS-02): `#f1f5f9` em 7 pontos — título e câmeras invisíveis no light
- P1 PERSISTS: 7+ hardcodes task-065 não removidos

### `admin-retention` — P0×1 P1×2 P2×1 P3×1 | Novos: 1
- P0 PERSISTS: Labels '1/7/30/90 dias' com `bgSurface` como cor de texto → 1.00:1 invisível
- P1 PERSISTS: Badge 'Retenção atual' = 2.18:1 no light
- P1 NEW (task-065): `textMuted #8a8a93` → ~3.30:1; subtítulo 13px e 'Conformidade' falham AA

### `fueling` — P0×1 P1×2 P2×2 P3×1
- P0 PERSISTS (S-03): Título, nomes de baia, coluna Classe `#f1f5f9` → invisíveis no light
- P1 PERSISTS: Paleta índigo incompatível com identidade ciano (1.58–1.83:1 no claro)

### `epi-reports` — P0×1 P2×1 P3×2
- P0 PERSISTS: Página completa invisível no light — `rgba(255,255,255,x)` hardcoded; título 1.05:1
- Sem alterações no develop

### `admin-branding-tenants` — P0×1 P1×2 P2×3 P3×1 | Novos: 1
- P0 PERSISTS: Título `#f0f4f8` invisível no light (1.01:1)
- P1 PERSISTS: Botões rodapé `#8ba3bc` = 2.39:1 no claro
- NEW P2: 'Nenhum tenant encontrado.' em `#668096` = 3.78:1 no light

### `admin-branding-default` — P0×1 P2×3 P3×4 | Novos: 1
- P0 PERSISTS: H2 'Tema Padrão Recognition' `#f0f4f8` invisível no light (1.01:1)
- NEW P2: Catálogo desatualizado em ≥8 tokens após WS1
- P2 PERSISTS: Chrome hardcoded (`#111318/#0d1117`) — ilhas escuras sobre fundo claro

### `admin-demo-videos` — P0×1 P1×1 P2×3 P3×1 | Novos: 1
- P0 PERSISTS (NS-02): `#f1f5f9` em h2, células Label, h3 modal e input value — invisíveis no light
- P1 PERSISTS: Paleta índigo incompatível com identidade ciano
- NEW P2: Campo MÓDULO read-only com #a5b4fc ≈ 2.10:1 no light

### `tablet-kiosk` — P0×1 P2×3 P3×2
- P0 FUNCIONAL (S-04): Auth gate bloqueia `/tablet/:station` sem JWT
- P2: Copy enganosa — 'Bancada B — V3' para qualquer station desconhecida
- P2: Kiosk renderiza dentro do AppShell — não é fullscreen

### `module-selection` — P1×2 P2×2 P3×2
- P1: `cardCta` '#22d3ee' sobre fundo claro ≈ 1.55:1; badges ATIVO/EM BREVE abaixo do AA
- P1: HealthFooter `textDim #2a3a4a` sobre `bgSurface #111318` = 1.59:1 no dark

### `admin-audit-log` — P1×1 P3×3 | Novos: 1
- P1 NEW (task-065 REGRESSION): `textMuted #8a8a93` → ~3.30:1; subtítulo e cabeçalhos th falham AA — staging estava OK com `#6b7280` (4.93:1)
- P3: Título 'Audit Log' em inglês; `trHover cursor:pointer` sem `onClick`

### `admin-changelog` — P1×2 P2×4 P3×2 | Novos: 1
- P1 PERSISTS: Badge 'high' #ea580c = 3.21:1 a 11px/600 no light
- P1 NEW (task-065): `textMuted #8a8a93` → ~3.30:1; subtítulo e células falham AA

### `admin-announcements` — P1×2 P2×3 P3×2 | Novos: 1
- P1 PERSISTS: Badge de tipo = 2.16:1 a 11px/600 no light
- P1 NEW (task-065): `textMuted #8a8a93` → ~3.30:1; subtítulo '{n} comunicados ativos' falha AA

### `admin-feature-flags` — P1×2 P2×1 P3×2 | Novos: 1
- P1 PERSISTS (S-01): Toggle 'Ativo' `#fff/#06b6d4` = 2.43:1 a 11px/600
- P1 NEW (task-065): `textMuted #8a8a93` → ~3.30:1 no light
- P2 PERSISTS: Controle ambíguo — exibe estado atual, clique executa ação oposta

### `quality-cameras` — P1×3 P2×4 P3×1
- P1 light: Salvar usa `color:bgBase` sobre primary claro = 2.23:1
- P1 light: Badges Ativa (2.00:1) e Setup (~1.9:1) falham AA
- P1 light: '+ Adicionar' primary sobre primaryAlpha = 2.22:1

### `quality-config` — P1×3 P2×4 P3×1 | Resolvidos: 1
- P1 both (S-01): '+ Adicionar estação' `textOnPrimary` sobre primary = 2.43:1
- P1: Seção Parâmetros de Inspeção é código morto

### `quality-inspections` — P1×3 P2×4 P3×2
- P1: Página inteira mock MODO DEMONSTRAÇÃO — feedback descartado
- P1 light: Botões drawer `#0f2e1a/#2e0f0f` hardcoded
- P1 light: Badges PENDENTE/CONFIRMADO/OK hardcoded falham AA no claro

### `admin-roles` — P1×2 P2×5 P3×1
- P1: PermBadge `#06b6d4` sobre rgba(59,130,246,.12) = 2.11:1 no light
- P2: Endpoints sem prefixo `/v1`

### `admin-plans` — P1×2 P2×4 P3×1
- P1: planBadge reprova em 4/4 variantes no dark (2.80–3.33:1)
- P2: Cards clicáveis sem hover/focus visível

### `admin-integrations` — P1×2 P2×5 P3×1 | Resolvidos: 1
- RESOLVIDO (WS1): Inputs tokenizados no dark
- P1: '● Conectado' = 2.18:1; '● Erro' = 3.24:1 no light
- P1: Faixa `last_error` #ef4444 12px reprova em ambos

### `admin-workers` — P1×1 P2×2 P3×3
- P1: workerBadge On-premise = 2.23:1; Railway = 2.67:1; Offline = 3.10:1 no light
- P2: `confirm()`/`alert()` nativos para Restart

### `admin-settings` — P1×1 P2×1 P3×2
- P1: Erro 500 engolido silenciosamente
- P2: Cabeçalhos de roles e permissões em inglês técnico

### `admin-test-console` — P1×2 P2×3 P3×1
- P1: Log panel `rgba(0,0,0,0.3)` sobre fundo claro ≈ 2.28:1
- P1: Form integration `rgba(0,0,0,0.2)` vira slab cinza no light

### `admin-training-approvals` — P1×1 P2×3 P3×1
- P1: Badge texto fixo 'Pendente' ignora `approval.status`
- P2: Badge #ea580c 11px/600 = 3.05:1 no light

### `quality-annotation` — P1×2 P2×4 P3×1
- P1: `CLASS_COLORS` com 7/9 valores hex fixos — viola guard-rail task-065
- P1: 'Salvando…' em `#FFB74D` sobre bgCard claro = 1.59:1

### `quality-dashboard` — P1×1 P2×5 P3×1
- P1: Pill '● Atenção' `#FFB74D` = 1.42:1 no claro
- P2: Placeholder de vídeo `textDim` sobre `bgBase` = 1.68:1 em dark

### `quality-andon` — P1×2 P2×2 P3×1
- P1: Labels 12px `#555` sobre `#0a0a0a` = 2.66:1
- P1: Status '—' 96px `#555` sobre `#0a0a0a` = 2.66:1
- P2: Display não é fullscreen

### `quality-pieces` — P1×2 P2×3 P3×2 | Resolvidos: 1
- P1 dark: Pill Rejeitada `#991B1B` = 2.04:1
- P1 light: Pills status = 1.85–3.17:1

### `quality-reports` — P1×2 P2×3 P3×2
- P1 both (S-01): 'Baixar CSV' branco sobre primary = 2.43:1
- P2: `#7C3AED` no botão Exportar — roxo fora da paleta Recognition

### `admin-inventory` — P1×2 P2×4
- P1 dark: ProbeStatusBadge Erro `#991b1b` = 2.17:1; Timeout `#92400e` = 2.40:1
- P1 layout: Coluna Módulo efetivamente vazia para câmeras ativas
- P2 dark: Inputs Tenant ID com fundo BRANCO UA sobre tema escuro

### `quality-rework` — P2×5 P3×1
- P2 light: KPI Tempo Médio warning 32px = 2.15:1
- P2: Modal ad-hoc `TODO-WS1` sem Esc/focus-trap

### `admin-tickets` — P2×3 P3×2
- P2 dark: Badges status hex fixos calibrados para claro — open/normal #2563eb = 3.01:1 dark
- P2 copy: Status e prioridades como chaves inglesas cruas

### `quality-training` — P3×1
- Visualmente saudável. `QualityTrainingPage.tsx` (dead code, 215 linhas) contém hardcodes que violam guard-rail task-065.

### `admin-observability` — 0 findings
Não implementada (WS9/WS11 pendente).

### `admin-demo-events` — 0 findings
Não implementada (WS9/WS11 pendente).

---

## Backlog em Ondas

### Onda 1 — Bloqueadores White-Label (P0 / P1 sistêmico)

| Prioridade | Item | Arquivo-fonte | Raiz |
|---|---|---|---|
| P0 | ThemeProvider no branch pré-auth + rotas públicas | `App.tsx:29,34` | S-04 |
| P0 | `#f1f5f9` global (33+ ocorrências: Fueling + 7 arquivos extras) | FuelingPage, CountingPage, VerificationQueuePage, DemoVideosPage, CameraModelAssignment, StreamHealthPage, ModelScenarioWizard | S-03 + NS-02 |
| P0 | Labels de retenção com `bgSurface` como cor de texto | AdminRetentionPage | — |
| P0 | KPI cards `rgba(12,12,18,0.8)` hardcoded no epi-dashboard light | EpiDashboard | — |
| P0 | Modais transparentes em epi-operations dark | OperationsPage + ui/Modal | NS-01 |
| P1 | `recognitionDarkTheme` em `document.body` (fix NS-01 + S-02) | `AppShell.tsx` via `useEffect` | NS-01 + S-02 |
| P1 | `textOnPrimary: '#0a0c10'` em ambos os temas | `recognition-dark.css.ts`, `professional.css.ts` | S-01 |
| P1 | AdminLayout early-return depois dos hooks | `AdminLayout.tsx:96` | S-05 |

### Onda 2 — Contraste e Hardcodes Prioritários (P1 endêmico)

| Prioridade | Item | Telas |
|---|---|---|
| P1 | `textMuted #8a8a93` regressão task-065 no light (3.30:1) | admin-audit-log + 8 telas admin |
| P1 | Envelope divergente Investigation `{success,data}` vs `{status,data}` | investigation |
| P1 | workerBadge / planBadge hardcoded (#10b981/#ca8a04/#ea580c) | admin-tenants, admin-workers, admin-dashboard, admin-plans, admin-tenant-detail |
| P1 | `CLASS_COLORS` hex fixos em quality-annotation | quality-annotation |
| P1 | Overlay 'MODO DEMONSTRAÇÃO' em quality-inspections | quality-inspections |
| P1 | STATUS_COLORS hardcoded nas ROIs de epi-operations | epi-operations |
| P1 | Credenciais admin expostas no login | login |
| P1 | Auth gate em `/tablet/*` (S-04) | tablet-kiosk |
| P1 | BadgeApproval texto fixo 'Pendente' ignora status real | admin-training-approvals |

### Onda 3 — Polimento, Copy e A11y (P2 / P3)

| Prioridade | Item | Telas |
|---|---|---|
| P2 | `bgHover` via `darkenHex` no tema claro (S-06) | todas com hover |
| P2 | StreamHealthPage → redirect `/admin/observability` (S-07) | stream-health |
| P2 | Implementar admin-observability e admin-demo-events (WS9/WS11) | admin-* |
| P2 | Modais ad-hoc `TODO-WS1` → migrar para `ui/Modal` (16 arquivos) | admin-* + quality-* |
| P2 | Paleta índigo incompatível (#a5b4fc/#6366f1) | fueling, investigation, admin-demo-videos |
| P2 | Catálogo design-system desatualizado (≥8 tokens WS1) | admin-branding-default |
| P3 | Internacionalização de chaves técnicas | admin-tickets, admin-roles, admin-settings |
| P3 | Copy: 'epimonitor.com' e 'EpiMonitor' no login | login |
| P3 | 'Audit Log' em inglês; glifos sem aria-label | admin-audit-log, admin-settings |

---

## Guard-Rail task-065 — Recomendação de Extensão

### Gap 1 — `#f1f5f9` não está na lista proibida (43+ ocorrências escapam)

```ts
// no-offbrand-colors.test.ts — adicionar ao BANNED_PATTERNS:
/'#f1f5f9'/,   // textPrimary do tema escuro — usar vars.color.textPrimary
/'#f0f4f8'/,   // variante branding pages
```

### Gap 2 — Guard-rail não cobre `.css.ts` nem `.jsx`

`AnnotationInterface.jsx` (68 hardcodes) e `VideoTimelineSelector.jsx` (32) ficam invisíveis. Estender para `**/*.{tsx,ts,css.ts,jsx}` com ALLOWLIST para arquivos legados anotados.

### Gap 3 — `textMuted #8a8a93` criou regressão cross-theme (task-065 regression)

Mudança de `#71717a` (4.93:1 sobre `#ffffff`) para `#8a8a93` (3.30:1 sobre `#ffffff`) resolve AA no dark mas cria failing no white-label claro. Adicionar teste cross-theme:

```ts
// Verificar textMuted contra todos os bgSurface conhecidos:
// professional bgSurface #13131a: #8a8a93 OK (4.35:1)
// white-label bgSurface #ffffff: #8a8a93 FAIL (3.30:1 < 4.5:1)
// Solução: derivar textMuted dinamicamente em resolver.ts
```

### Hardcodes que escapam ao guard-rail atual

| Pattern | Motivo |
|---|---|
| `rgba(0,0,0,0.2/0.3)` | Abaixo do threshold `0.7` do guard |
| `#FFB74D`, `#FF8A65`, `#4FC3F7` | Famílias não proibidas |
| `#8ba3bc`, `#668096` | Cinzas fora das famílias listadas |
| `#0f2e1a`, `#2e0f0f` | Verdes/vermelhos escuros não listados |

