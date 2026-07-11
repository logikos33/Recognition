# Tablet Kiosk (Quality Gate) — spec visual

**Rota:** `/tablet/:station` (capturado em `/tablet/estacao-1` = "default" e `/tablet/bench-a` = "empty"). Documentada como rota pública sem JWT (`AppRoutes.tsx:106-114`), mas o auth gate em `App.tsx:29-31` renderiza `<Login/>` para qualquer rota sem token — capturas feitas autenticadas (comportamento real do deploy).
**Fontes:** `apps/frontend/src/modules/quality/tablet/TabletKiosk.tsx` · `TabletIdle.tsx` (+ views `TabletIdentified/Validating/ResultOK/ResultNOK/Transition/Approved`, não capturadas) · WS: `useTabletWebSocket.ts` (socket.io namespace `/quality`)
**Screenshots:**

| Estado | Dark | Light |
|--------|------|-------|
| default (idle em /tablet/estacao-1) | `../screenshots/tablet-kiosk/dark-default.png` | `../screenshots/tablet-kiosk/light-default.png` |
| empty (idle em /tablet/bench-a)     | `../screenshots/tablet-kiosk/dark-empty.png`   | `../screenshots/tablet-kiosk/light-empty.png`   |

Nota: o painel navy é hardcoded — light == dark no conteúdo; muda só o chrome do AppShell ao redor (top bar "EPI", footer de status, ChatFAB).

## Layout — regiões

- `TabletKiosk` root: `width:100vw; height:100vh; overflow:hidden`, flex column centralizado — projetado para fullscreen, mas renderiza DENTRO do AppShell/AppLayout (top bar + footer visíveis; 100vh extrapola o espaço útil).
- `TabletIdle`: fundo `#1B2A4A` (navy, `// allow` no source), pilha central: emoji ⏳ 80px → título 32px/700 `#C5D8F0` → subtítulo 18px `#8BA7CC` opacity 0.7 → rodapé de branding 14px opacity 0.4 letterSpacing 2.

## Árvore de componentes

- `TabletKiosk` — máquina de views: `idle | identified | validating | ok | nok | transition | approved`, dirigida por eventos WebSocket (`stationState`, `lastResult`, `lastIdentified`).
  - `TabletIdle` (única capturada — WS não conecta sem backend, kiosk fica em idle permanente)
  - `TabletIdentified` (peça identificada) · `TabletValidating` (YOLO rodando) · `TabletResultOK` (auto-avança 3s) · `TabletResultNOK` (corrigir ou FP) · `TabletTransition` (mover p/ Bancada B) · `TabletApproved` (3/3) — não capturadas (sem injeção WS no harness).
- Normalização de station: `rawStation.replace('-', '_')` — substitui só o PRIMEIRO hífen.

## Copy exata (TabletIdle)

- `Aguardando Peça`
- Subtítulo: `Bancada A — V1 e V2` (station === 'bench_a') / `Bancada B — V3` (**qualquer outro valor**, inclusive station desconhecida)
- Rodapé: `RECOGNITION · QUALITY GATE`

## Dados de exemplo

- `/tablet/estacao-1` → normaliza para `estacao_1` → não é `bench_a` → exibe o rótulo enganoso "Bancada B — V3" (visível em dark-default.png).
- `/tablet/bench-a` → `bench_a` → "Bancada A — V1 e V2" (dark-empty.png).

## Estados

- **idle**: única view capturada; WebSocket desconectado → idle permanente.
- Views identified/validating/ok/nok/transition/approved: exclusivamente por eventos socket.io `/quality` — deferred (sem mecanismo de injeção WS no harness).
- Sem estados hover/focus (tela touch sem elementos interativos no idle).

## Navegação e fluxos

- Nenhuma navegação manual no idle; transições vêm do backend via WS.
- Fluxo projetado: peça identificada → operador inicia → validações V1/V2 (Bancada A) → transition → Bancada B (V3) → approved/nok.

## Problemas identificados (resumo)

1. **P0 funcional**: rota "pública" bloqueada pelo auth gate (`App.tsx:29-31` renderiza `<Login/>` antes do `AppRoutes`) — o tablet de bancada nunca abre sem login; contradiz o comentário em `AppRoutes.tsx:106` e inviabiliza o kiosk em produção.
2. **Layout**: autenticado, o kiosk (100vw/100vh) renderiza dentro do AppShell — top bar "EPI", ChatFAB e footer aparecem no kiosk; conteúdo 100vh extrapola o viewport (não é fullscreen como projetado).
3. **Copy enganosa**: fallback do ternário em `TabletIdle.tsx:35` rotula QUALQUER station desconhecida como "Bancada B — V3" (confirmado no screenshot de `/tablet/estacao-1`); deveria validar e exibir erro/rótulo neutro.
4. **Bug de normalização**: `replace('-','_')` só troca o primeiro hífen (`TabletKiosk.tsx:42`) — usar `replaceAll` ou regex.
5. **Contraste**: subtítulo `#8BA7CC` com opacity 0.7 sobre `#1B2A4A` = 3.61:1 (18px normal exige 4.5:1); rodapé com opacity 0.4 = 2.10:1 (branding, tolerável, mas abaixo de qualquer mínimo).
6. Paleta navy hardcoded com `// allow` — intencional (kiosk imune a white-label), consistente com o Andon.

## Findings (develop — 2026-07-07)

> Comparado com _baseline-staging/screens/tablet-kiosk.md · screenshots analisados: dark-default, light-default (ambos `/tablet/estacao-1`)

| # | Severidade | Descrição | Status |
|---|-----------|-----------|--------|
| 1 | P0 | Auth gate (`App.tsx:29-31`) bloqueia a rota `/tablet/:station` sem JWT — kiosk de bancada nunca abre sem login, inviabilizando uso em produção sem sessão ativa. Confirmado: screenshots mostram chrome do AppShell intacto (topbar "EPI", footer de status) envolvendo o conteúdo kiosk. | PERSISTE |
| 2 | P2 | Kiosk renderiza **dentro** do AppShell (topbar + footer visíveis); `width:100vw; height:100vh` extrapola o espaço útil — não é fullscreen como projetado. Confirmado em `dark-default.png` e `light-default.png`. | PERSISTE |
| 3 | P2 | Copy enganosa: `/tablet/estacao-1` normaliza para `estacao_1` (não é `bench_a`) → exibe "Bancada B — V3" incorretamente para qualquer station desconhecida. Confirmado em `dark-default.png`: subtítulo mostra "Bancada B — V3". | PERSISTE |
| 4 | P3 | `replace('-','_')` substitui apenas o primeiro hífen (`TabletKiosk.tsx:42`) — `bench-a-norte` normalizaria para `bench_a-norte` (errado). Usar `replaceAll` ou `/g`. | PERSISTE |
| 5 | P2 | Subtítulo `#8BA7CC` opacity 0.7 sobre `#1B2A4A` = 3.61:1 — 18px texto normal exige 4.5:1 WCAG AA; rodapé "RECOGNITION · QUALITY GATE" opacity 0.4 = 2.10:1 (praticamente invisível — confirmado nos screenshots). | PERSISTE |
| 6 | P3 | Paleta navy hardcoded (`#1B2A4A`, `#C5D8F0`, `#8BA7CC`) — intencional (kiosk imune a white-label, com `// allow`). Aceito por design, mas não documentado no VMS. | PERSISTE |

**Resumo:** 0 resolvidos · 6 persistem · 0 novos. Nenhum dos bugs funcionais (auth gate, copy enganosa) foi endereçado nos merges WS1/task-063/task-065.
