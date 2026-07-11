# Design System (vitrine de tokens) — spec visual

**Rota:** `/design-system` (fora do `AdminLayout`; topbar global "EPI" apenas)
**Fontes:** `apps/frontend/src/pages/DesignSystemPage.tsx` (316 linhas); UI kit: `components/ui/{Button,Badge,Input,Skeleton,Toast,Panel,PageHeader,Modal,AppDrawer}`; tema: `styles/theme.css.ts` (contrato), `theme/tokens/recognition-dark.css.ts`, `components/layout/AppShell/AppShell.tsx`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (fullpage ≈ viewport) | `../screenshots/design-system/dark-default.png` | `../screenshots/design-system/light-default.png` |
| modal-canonico | `../screenshots/design-system/dark-modal-canonico.png` | `../screenshots/design-system/light-modal-canonico.png` |
| modal-appdrawer | `../screenshots/design-system/dark-modal-appdrawer.png` | `../screenshots/design-system/light-modal-appdrawer.png` |

## Layout — regiões

- Conteúdo: `padding: 32px 40px`, `maxWidth: 900px`, `margin: 0 auto`.
- Header: H1 `Design System` (28px/800 `vars.color.textPrimary`) + parágrafo 14px `vars.color.textMuted`.
- Seções (`Section`, `marginBottom: 48`): título 13px/700 uppercase `vars.color.textMuted` com borda inferior `borderSubtle`.

## Árvore de componentes

- `DesignSystemPage` (100% tokenizada via `vars`)
  - **Color Tokens**: 20 `TokenRow` (swatch 24×24 borda `borderDefault` + nome `vars.color.*` em `primary` + valor mono em `textSecondary`)
  - **Typography**: Display 32/700 · H1 24/700 · H2 20/700 · H3 16/600 · Body 14/400 · Small 12/400 · Caption 11/400 · Label 10/600 uppercase — amostra "X — Recognition platform typography"
  - **Spacing**: barras `xs 4px · sm 8px · md 16px · lg 24px · xl 32px · xxl 48px`
  - **Containers — Panel / PageHeader / Modal / AppDrawer**:
    - `PageHeader` demo: "Título da página" / "Subtítulo em textSecondary — substitui H1 hardcoded" / `Button primary sm` "Ação"
    - 3 `Panel` (surface/card/elevated) com subtítulos `vars.color.bg*`
    - `Button secondary` "Abrir Modal" / "Abrir AppDrawer"
    - `Modal` "Modal canônico" (Radix Dialog em Portal; overlay `vars.color.overlay` + blur 4px; content `bgElevated` border radius xl shadow lg; footer `Button ghost` "Cancelar" + `Button primary` "Confirmar")
    - `AppDrawer` "AppDrawer canônico" size sm (Radix Dialog Portal; painel lateral `bgElevated`)
  - **Button**: primary/secondary/ghost/danger/disabled + sm/md/lg
  - **Badge**: success/warning/danger/primary/neutral/accent
  - **Input**: sem label · `Field` "Com label" · "Com erro" ("Este campo é obrigatório") · "Desabilitado" ("valor fixo")
  - **Skeleton**: title/text/rect + composição
  - **Toast**: 4 botões disparam success/error/warning/info
  - **Shadow**: sm/md/lg/glow/glowCyan
  - **Border Radius**: sm/md/lg/xl/full

## Copy exata

- H1: `Design System` · subtítulo: `Recognition · Logikos — Tokens, primitivos e padrões de composição.`
- Títulos de seção: `Color Tokens` · `Typography` · `Spacing` · `Containers — Panel / PageHeader / Modal / AppDrawer` · `Button` · `Badge` · `Input` · `Skeleton` · `Toast` · `Shadow` · `Border Radius`
- Modal: título `Modal canônico`; corpo: `Único contêiner sobreposto permitido (com AppDrawer). Abre sobre o contexto com animação (vars.animation) e overlay tokenizado (vars.color.overlay) — VMS §7.`; footer `Cancelar`/`Confirmar`
- AppDrawer: título `AppDrawer canônico`; corpo: `Gaveta lateral padrão — abre sobre o contexto sem desmontar o que roda atrás; fecha com Esc, overlay ou X.`
- Toasts: `Operação concluída com sucesso` · `Erro ao processar solicitação` · `Atenção: limite próximo do limite` · `Informação importante disponível`

## Dados de exemplo

Catálogo estático (`COLOR_TOKENS`, `SPACING` no componente) — valores hex dark listados: bgBase #0a0c10 … borderStrong #2a3545 (20 entradas; ver source).

## Estados

- **default**: página completa; fullPage limitado ao viewport (scroll interno do shell).
- **modal-canonico / modal-appdrawer**: overlay com blur sobre a página + contêiner sobreposto (ver problemas — contêiner ausente nos screenshots).
- Hover: definidos nos recipes do UI kit (Button/Badge/closeButton) — não capturados (tier 2).

## Navegação e fluxos

- `Abrir Modal` → `Modal` Radix (fecha por X, overlay, Esc, Cancelar/Confirmar).
- `Abrir AppDrawer` → `AppDrawer` (fecha por Esc, overlay, X).
- Botões de Toast disparam `useToast`.

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P0 (both)** `Modal` renderiza SEM contêiner: sem fundo `bgElevated`, sem borda, sem sombra, sem scrim do overlay — título, corpo e botões "Cancelar/Confirmar" flutuam soltos sobre a página borrada; botões do footer perdem todo o chrome. **Causa-raiz identificada:** o tema vanilla-extract é aplicado num `<div>` interno (`AppShell.tsx:33`), mas `Dialog.Portal` do Radix monta em `document.body` — fora do escopo — então TODO `vars.*` resolve vazio (`background: unset`). O overlay só mostra o blur porque `backdrop-filter` não depende de token. Classe task-066.
2. **P0 (both)** `AppDrawer` idem: painel lateral invisível, texto sobreposto ao conteúdo (mesma causa-raiz).
3. **P1** `ToastProvider` montado como irmão de `<App/>` em `main.tsx:17` — também fora do escopo do tema → toasts transparentes (evidência real em `admin-branding-editor/dark-preview-tenant.png`).
4. **P3 (light)** Catálogo lista os HEX do tema dark enquanto a página renderiza com vars claras — valores exibidos divergem do que está na tela (confusão esperada da classe task-063, aqui é vitrine estática; anotar "valores do tema dark" resolveria).
5. **P3** `COLOR_TOKENS` incompleto vs contrato (`accentDark`, `accentAlpha`, `textDim`, `overlay`, `textOnPrimary`, `successMuted`/`warningMuted`/`dangerMuted` ausentes) e duplicado à mão (3ª cópia junto com AdminBrandingDefaultPage).
6. **P3** Copy do toast de warning: `Atenção: limite próximo do limite` — redundante (texto demo).

## Findings (develop — 2026-07-07)

> Comparado com _baseline-staging/screens/design-system.md · screenshots analisados: dark-default, light-default, dark-modal-canonico, light-modal-canonico, dark-modal-appdrawer, light-modal-appdrawer

| # | Severidade | Descrição | Status |
|---|-----------|-----------|--------|
| 1 | P0 | `Modal` renderiza sem contêiner em **dark**: título "Modal canônico", corpo e botões "Cancelar/Confirmar" flutuam sobre a página borrada sem fundo `bgElevated`, sem borda e sem sombra (`dark-modal-canonico.png`). Em light, `background: unset` herda o branco do `<body>` → aparentemente visível, mas é falso-positivo: qualquer cor escura de bgElevated no light não seria renderizada. Causa-raiz: `Dialog.Portal` do Radix monta em `document.body`, fora do escopo vanilla-extract. | PERSISTE |
| 2 | P0 | `AppDrawer` idem: painel lateral abre no canto superior direito sem fundo/borda em dark (`dark-modal-appdrawer.png`); em light aparenta ter fundo branco pelo mesmo false-positive do `<body>`. Texto/corpo flutuam sobre o conteúdo borrado. | PERSISTE |
| ~~3~~ | ~~P1~~ | ~~`ToastProvider` fora do escopo do tema → toasts transparentes~~. | **RESOLVIDO** (task-066) — evidência em `fueling-validation/dark-error.png` e `light-error.png`: toasts agora exibem fundo opaco legível em ambos os temas. |
| 4 | P3 | Catálogo `COLOR_TOKENS` lista os HEX do tema dark (`bgBase #0a0c10`, etc.) enquanto a página renderiza com vars claras no light-default — os swatches mostrando quadrados pretos sobre fundo branco confundem o leitor. Confirmado: `light-default.png` mostra swatches near-black em página light. | PERSISTE |
| 5 | P3 | `COLOR_TOKENS` incompleto vs contrato do tema (`accentDark`, `accentAlpha`, `textDim`, `overlay`, `textOnPrimary`, `successMuted`/`warningMuted`/`dangerMuted` ausentes); lista está duplicada à mão em `DesignSystemPage` e `AdminBrandingDefaultPage`. | PERSISTE |
| 6 | P3 | Copy do toast de warning: `"Atenção: limite próximo do limite"` — "limite" duplicado (texto demo). | PERSISTE |

**Resumo:** 1 resolvido (finding 3, P1 toast transparency — task-066) · 5 persistem · 0 novos. Os dois P0 de Modal/AppDrawer requerem solução de escopo de tema para portais Radix (ex: `ThemeProvider` em `document.body`, ou `container` prop do Dialog apontando para o div temático).
