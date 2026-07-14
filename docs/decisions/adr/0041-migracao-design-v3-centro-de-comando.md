# ADR-0041 — Migração do design v3 "Centro de Comando" para o frontend React

**Status:** Proposta · **Data:** 2026-07-12 · **Relaciona:** ADR-0035 (feature flags + white-label
por tenant), ADR-0022 (VMS/live), ADR-0031 (Training Studio — canvas de pipeline), design v3
"Centro de Comando" (Claude Design), `apps/frontend/`.

## Contexto

O redesign v3 "Centro de Comando" (paradigma novo: 4 workspaces Operar/Investigar/Treinar/Administrar
+ paleta de comando ⌘K + situation room + canvas de 6 nós do pipeline + identidade charcoal/signal
amber) foi feito como HTML standalone no Claude Design. Precisamos trazê-lo pro app real
(`apps/frontend/`, React 18 + TS + Vite + vanilla-extract) **em ambiente de desenvolvimento**.

Recon do front atual (grounding, não memória): já existem as primitivas que o v3 precisa —
vanilla-extract com contrato de tema (`styles/theme.css.ts` + `themes/professional|cyberpunk`),
Radix UI (dialog/dropdown/popover/tabs/tooltip), framer-motion, **@dnd-kit** (canvas do pipeline),
zustand, tanstack-query, hls.js (live), recharts, e biblioteca `components/ui/*`. A maior parte da
fundação existe; a migração é de *paradigma/identidade*, não de stack.

## Dependência bloqueante — RESOLVIDA (2026-07-12)

**Export final chegou.** Fonte de verdade ÚNICA: `docs/design/recognition-v3/Recognition-visao-final.dc.html`
(4681 linhas — design primário) + `support.js` (runtime) + `screenshots/`. Exports antigos/duplicados
foram movidos pra `docs/design/_ARQUIVO-NAO-USAR/` (quarentena). As Fases 1+ estão **destravadas**.

## Identidade e telas REAIS (fonte da verdade — substitui a suposição provisória amber/Bricolage)

- **Tema:** **dark E light**. Dark (padrão): `bgBase #0a0c10`, `bgSurface #111318`, `textPrimary
  #f0f4f8`, `textSecondary #8ba3bc`, `textMuted #5b6b7d`, `primary #06b6d4` (cyan),
  `primaryAlpha rgba(6,182,212,0.12)`, `success #10b981`, `warning #f59e0b`, `danger #ef4444`,
  `borderDefault #1e2730`, `shadowLg 0 8px 40px rgba(0,0,0,0.7)`. Light definido em paralelo.
- **Accents (white-label nativo):** cyan `#06b6d4` / amber `#f59e0b` / purple `#8b5cf6` — o design
  já prevê troca de cor de marca, o que **confirma** manter o bridge de white-label.
- **Fontes:** Inter (400–800) + JetBrains Mono (mono/telemetria).
- **Telas (seções do dc.html):** Boot · Login · Module Select · App Shell · workspaces
  **Monitorar / Câmeras / Alertas / Modelos / Treinar** · modais Camera Wizard, Operation Wizard,
  Scenario/ROI Editor, Alert Detail Drawer, Tenant Detail (super admin) · Toasts.

## Decisão

### 1. Estratégia: shell v3 paralelo atrás de feature flag (em dev)
Construir o shell v3 **ao lado** do atual, ligado por **feature flag** (`ui_v3`, mecanismo ADR-0035,
global + override por tenant/usuário), default **ON só em dev**. Motivos: reversível, permite A/B
(v3 × atual) durante a construção, e não quebra o app em produção enquanto migra. O estado-alvo é
"v3 puro", mas a *transição* passa pela flag. (Confirmar — Q1 ficou em aberto na conversa.)

### 2. Identidade: consolidar no v3, preservando white-label
"Substitui os temas atuais" (escolha do Vitor): remover **professional/cyberpunk como alternativas
selecionáveis** e adotar o v3 (charcoal + signal amber) como identidade única. **MAS manter o
`createThemeContract` + bridge de white-label** — o v3 vira a *baseline* de tokens; cada tenant ainda
pode sobrescrever marca (logo, cor primária) via override. Consolidar em uma identidade ≠ matar
white-label (que é requisito). Se o Vitor quiser remover white-label também, revisar aqui.

### 3. Faseamento
- **Fase 0 — Andaime (task-070):** ligar a flag `ui_v3`; criar o shell/rota v3 (`AppShellV3`) sob a
  flag; `styles/themes/recognition-v3.css.ts` com o contrato preenchido com os **tokens REAIS** (dark
  + light + accents) extraídos de `docs/design/recognition-v3/Recognition-visao-final.dc.html`; ⌘K como casca.
- **Fase 1..N — Telas (destravadas):** recriar **pixel-perfect** em React, uma fatia por PR, reusando
  `components/ui/*`. Ordem sugerida: (1) Auth — Boot/Login/Module Select; (2) App Shell + Monitorar
  (situation room); (3) Câmeras + Camera Wizard + Scenario/ROI Editor; (4) Alertas + Alert Detail
  Drawer; (5) Modelos + Treinar (canvas via @dnd-kit) + Operation Wizard; (6) Admin/Super — Tenant
  Detail. Match visual do `.dc.html`, **sem copiar** a estrutura do protótipo.
- **Fase final — Cutover:** com todas as telas no v3 e validadas, v3 vira default e remove-se o shell
  antigo + temas professional/cyberpunk (forward-only). White-label (accents) preservado.

### 4. Restrições
- Trabalho de frontend **no worktree a partir de origin/develop**, nunca no checkout `wip/*` (que tem
  mudança não commitada — Achado 2 do plano da pipeline). Um workspace = um branch = um PR.
- `npx tsc --noEmit` limpo, `usePolling`/`cacheDir` do Vite (path com espaço) preservados.
- Tokens hardcoded barrados pelo guard-rail de cores (task-065) — tudo via contrato de tema.

## Consequências / trade-offs
- **A favor:** flag torna a migração reversível e A/B-able; reuso da fundação existente reduz risco;
  faseamento por workspace mantém PRs pequenos.
- **Contra:** shell paralelo = código dobrado temporário (mitigado pelo cutover que remove o antigo);
  tokens provisórios geram uma rodada de reconciliação quando o final chegar.
- **Bloqueio:** sem o export final do v3, Fases 1+ não avançam — só a Fase 0.

## Referências
Design v3 "Centro de Comando" (Claude Design, a exportar), ADR-0035, ADR-0031, ADR-0022,
`apps/frontend/src/styles/theme.css.ts`.
