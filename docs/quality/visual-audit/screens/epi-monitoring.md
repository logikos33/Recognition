# Monitoramento ao vivo (VMS) — spec visual

**Rota:** `/epi/monitoring` (`/monitoring` redireciona para cá — `AppRoutes.tsx:88-89`)
**Fontes:** `src/pages/MonitoringPage.tsx`, `src/pages/MonitoringPage.css.ts`, `src/components/monitoring/CameraPlayer.tsx|.css.ts`, `src/components/monitoring/DetectionOverlay.tsx|.css.ts`, `src/components/ui/AppDrawer/AppDrawer.tsx|.css.ts`, `src/hooks/useMonitoringSocket.ts`
**Screenshots:**

| Estado | Dark | Light (white-label) |
|---|---|---|
| default | ../screenshots/epi-monitoring/dark-default.png | ../screenshots/epi-monitoring/light-default.png |
| offline-players | ../screenshots/epi-monitoring/dark-offline-players.png | ../screenshots/epi-monitoring/light-offline-players.png |
| empty | ../screenshots/epi-monitoring/dark-empty.png | ../screenshots/epi-monitoring/light-empty.png |
| loading | ../screenshots/epi-monitoring/dark-loading.png | ../screenshots/epi-monitoring/light-loading.png |
| error | ../screenshots/epi-monitoring/dark-error.png | ../screenshots/epi-monitoring/light-error.png |
| tab EPI | ../screenshots/epi-monitoring/dark-tab-epi.png | ../screenshots/epi-monitoring/light-tab-epi.png |
| drawer Feed | ../screenshots/epi-monitoring/dark-drawer-feed.png | ../screenshots/epi-monitoring/light-drawer-feed.png |
| drawer Logs | ../screenshots/epi-monitoring/dark-drawer-tab-logs.png | ../screenshots/epi-monitoring/light-drawer-tab-logs.png |
| drawer Info | ../screenshots/epi-monitoring/dark-drawer-tab-info.png | ../screenshots/epi-monitoring/light-drawer-tab-info.png |
| hover card (dark) | ../screenshots/epi-monitoring/dark-hover-camera-card.png | — |
| hover toggle Overlay (dark) | ../screenshots/epi-monitoring/dark-hover-overlay-toggle.png | — |

## Layout — regiões

- **Shell da app** (fora desta página): header global (hambúrguer, logo EPI, sino, toggle Pro, "Auditor Visual", badge SUPERADMIN, botão Sair) e footer de status (Banco de dados / Redis / câmeras ativas).
- **`page`** — coluna flex ocupando o viewport útil, `background: vars.color.bgBase` (#0a0c10 dark / #f4f5f7 light), `overflow: hidden`.
- **Toolbar** (`toolbar`) — linha flex, `gap: vars.space.sm (8px)`, `padding: 8px 16px`, `background: vars.color.bgSurface`, `borderBottom: 1px solid vars.color.borderSubtle`, `flexWrap: wrap`.
  - Esquerda: `moduleTabList` (tabs de módulo, gap 2px).
  - `spacer` (flex 1).
  - Direita: `statusBadge` (dot 6px + texto 11px/600 `textMuted`) e botão `overlayToggle` (12px/600, padding 5px 12px, radius `vars.radius.sm` 4px).
- **`gridContainer`** — `flex: 1`, `overflowY: auto`, `padding: vars.space.md (16px)`.
- **`cameraGrid`** — `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`, `gap: 16px`.
- **AppDrawer** (ao clicar num card) — gaveta lateral direita `size="lg"` = `min(660px, 100vw)`, `zIndex 201`, backdrop `vars.color.overlay` (rgba(0,0,0,0.7)) com `backdropFilter: blur(3px)`.

## Árvore de componentes

```
MonitoringPage (page)
├─ toolbar
│  ├─ moduleTabList
│  │  ├─ button "Todos"            (moduleTabActive quando activeModule==='all')
│  │  └─ button por módulo do user (EPI, Combustível, Qualidade…)
│  ├─ spacer
│  ├─ statusBadge  [dot statusDotOnline (success, pulso 2s) | statusDotOffline (textDim)] + "Ao vivo"/"Desconectado"
│  └─ button overlayToggle/overlayToggleActive  [ícone Eye/EyeOff 13px] "Overlay"  (aria-pressed)
├─ gridContainer
│  ├─ emptyState "Carregando câmeras..."      (loading)
│  ├─ emptyState "Nenhuma câmera encontrada"  (vazio E erro — mesmo estado!)
│  └─ cameraGrid → VmsCameraCard × N
│     └─ div cameraCard | cameraCardAlert (role=button, tabIndex 0, aria-label "Abrir câmera {nome}")
│        └─ cardAspect (16:9) → cardInner
│           ├─ CameraPlayer (lazy via IntersectionObserver; placeholder "carregando...")
│           │  ├─ "Conectando..." (connectingText) → estado inicial
│           │  ├─ offlineOverlay: "Camera offline" + button retryBtn "Reconectar"
│           │  └─ <video muted playsInline autoPlay>
│           ├─ DetectionOverlay (canvas, pointerEvents none) — só com detecções WS
│           ├─ cardHeader (gradiente ↓ rgba(0,0,0,.8)): cardName + cardAlertLabel "Alerta"
│           └─ cardFooter (gradiente ↑): cardLocation + cardModuleBadge (EPI/QUALIDADE/COMBUSTÍVEL)
└─ AppDrawer (Radix Dialog.Portal → document.body) title={camera.name}
   ├─ drawerHeader: Dialog.Title + closeBtn X (aria-label "Fechar gaveta")
   └─ drawerBody → CameraDrawerContent
      ├─ drawerFeed (16:9, bg #000, sempre montado; display none fora da tab Feed)
      ├─ drawerTabList: "Feed" | "Logs ao vivo" | "Info" (drawerTab/drawerTabActive — underline 2px primary)
      └─ drawerScrollBody
         ├─ tab Logs: logsList → logEntry|logEntryAlert (logTimestamp + logDetectionRow "classe — NN%")
         │  └─ emptyState "Aguardando detecções..."
         └─ tab Info: drawerInfoGrid 2 colunas (gap 16px, padding 24px) × 6 drawerInfoItem
```

## Copy exata

- Tabs de módulo: `Todos`, `EPI`, `Combustível`, `Qualidade`, `Estacionamento` (labels de `MODULE_LABELS`; fallback = module_code cru).
- Badge de conexão: `Ao vivo` | `Desconectado`.
- Toggle: `Overlay`.
- Estados do grid: `Carregando câmeras...` | `Nenhuma câmera encontrada`.
- Placeholder lazy do card: `carregando...` (minúsculo, mono).
- Player: `Conectando...` | `Camera offline` (sem acento no source) + botão `Reconectar` | `HLS nao suportado neste browser` | `Vídeo indisponível — verifique a configuração do vídeo demo` (modo demo).
- Card: label de alerta `Alerta`; fallback de local `Sem local`.
- Drawer tabs: `Feed`, `Logs ao vivo`, `Info`.
- Logs vazio: `Aguardando detecções...`; linha de log: `{classe} — {confiança}%` + hora `pt-BR`.
- Info labels (uppercase 10px): `Nome`, `Módulo`, `Localização`, `Status`, `Fabricante`, `FPS atual`; valores de status: `Ativa` (verde #22c55e inline) | `Inativa` (#ef4444); FPS: `~5 FPS` | `N/A`; fallback `—`.
- Aria: `Abrir câmera {nome}`, `Fechar gaveta`.

## Dados de exemplo (fixtures do harness)

| Câmera | Localização | Badge módulo |
|---|---|---|
| Câmera Pátio Norte | Pátio Norte — Galpão A | EPI |
| Câmera Doca de Carga 2 | Doca 2 — Expedição | EPI |
| Câmera Linha de Produção | Linha 1 — Envase | QUALIDADE |
| Câmera Portaria Principal | Portaria — Entrada de Veículos | COMBUSTÍVEL |
| Câmera Almoxarifado | Almoxarifado Central | EPI |
| Câmera Estacionamento Sul | Estacionamento — Bloco S | QUALIDADE |

Drawer (Câmera Doca de Carga 2): Nome=Câmera Doca de Carga 2 · Módulo=EPI · Localização=Doca 2 — Expedição · Status=Ativa · Fabricante=hikvision · FPS atual=N/A. Socket `/monitor` não conecta no harness → badge `Desconectado`. Tab EPI filtra para 3 câmeras.

## Estados

- **default:** 6 cards com players em `Conectando...` (wells pretos #0a0a0a), toggle Overlay ativo (ciano `primaryAlpha` + borda `primary`), badge `Desconectado` (dot `textDim`).
- **loading:** grid substituído por `Carregando câmeras...` centrado (`emptyState`, textMuted 13px).
- **empty:** `Nenhuma câmera encontrada` centrado.
- **error:** IDÊNTICO ao empty — o `catch` de `fetchCameras` engole o erro (`MonitoringPage.tsx:409-413`).
- **offline-players:** após 3 retries fatais do hls.js (~15s com manifest 404) o overlay `Camera offline`+`Reconectar` aparece — porém CLIPADO para fora do card (ver Problemas).
- **hover card:** borda `borderStrong` + `shadow.md` (delta sutil); focus-visible: outline 2px `primary`.
- **hover tabs/toggle:** tab → `textPrimary` + `bgHover`; toggle ativo → `primaryLight`.
- **alerta (WS):** card com borda 2px pulsando rgba(239,68,68,0.7→0.2) 1.5s + label `Alerta`; não capturável sem socket real.
- **drawer aberto:** backdrop blur 3px; painel deveria ser `bgElevated` opaco — hoje renderiza TRANSPARENTE (bug P0, ver Problemas).

## Navegação e fluxos

- Tab de módulo → refetch `GET /api/cameras?module={code}` + filtro client-side secundário.
- Toggle Overlay → liga/desliga o repasse de detecções para o `DetectionOverlay` (players continuam).
- Clique/Enter/Espaço num card → abre `AppDrawer` lg com `CameraDrawerContent` da câmera.
- Fechar drawer: X, Escape ou clique no backdrop → volta ao grid sem recarregar.
- `Reconectar` (overlay offline) → reinicia HLS (`startHls`, zera retries).
- HLS: `GET {API}/api/cameras/{id}/stream/stream.m3u8`; detecções/alerts: socket.io namespace `/monitor` (subscribe por câmera).

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P0 transparency (task-066, both):** AppDrawer monta via Radix `Dialog.Portal` em `document.body`, FORA da classe de tema vanilla-extract aplicada só no subtree do AppShell (`AppShell.tsx:33`). Todas as `vars.*` ficam indefinidas no portal: `background: vars.color.bgElevated` não resolve → painel 100% transparente; textos da Info flutuam sobre o grid borrado; o dim rgba(0,0,0,.7) do backdrop também não aplica (só o blur literal).
2. **P1 layout (both):** `CameraPlayer` recebe `width={640} height={360}` fixos → wrapper transborda o card (~300px, overflow hidden) e o overlay `Camera offline`/`Reconectar` fica clipado (só fragmento "Can" visível); ação de reconexão inacessível no grid.
3. **P1 copy (both):** erro de `GET /cameras` é engolido e vira `Nenhuma câmera encontrada` — usuário não distingue falha de ausência.
4. **P2 contrast:** `cardLocation` rgba(255,255,255,0.4) 10px = 3.67:1; `logTimestamp` `textDim` #2a3a4a sobre `bgCard` = 1.50:1; `cardPlaceholder` 0.12 alpha = 1.33:1.
5. **P2 inconsistency:** `retryBtn` roxo #8b5cf6 hardcoded — fora da paleta Recognition (primary ciano / accent laranja).
6. **P2 copy:** empty state sem CTA (cadastrar câmera / limpar filtro).
7. **P3:** "Camera offline" e "HLS nao suportado" sem acentuação; verde `Ativa` #22c55e inline diverge do token success #10b981; dot `Desconectado` (#2a3a4a sobre #111318 ≈1.2:1) invisível.

---

## Findings (develop — 2026-07-07)

| # | Severidade | Tema | Status | Descrição |
|---|---|---|---|---|
| 1 | ~~P0~~ | both | **RESOLVED (task-066)** | ~~`AppDrawer` via Radix `Dialog.Portal` sem tema → painel 100% transparente~~ — `dark-drawer-feed`, `dark-drawer-tab-info` e variantes light mostram painel com fundo opaco correto e backdrop blur funcionando. |
| 2 | ~~P1~~ | both | **RESOLVED (task-068)** | ~~`CameraPlayer` fixo 640×360 → overlay "Camera offline/Reconectar" clipado fora do card~~ — `dark-drawer-feed` mostra "Câmera offline — reconectando..." e botão "Reconectar" completamente visíveis dentro do player. |
| 3 | P1 | both | **PERSISTS** | Erro de `GET /cameras` engolido → `Nenhuma câmera encontrada` — usuário não distingue falha de ausência (`dark-error` idêntico a `dark-empty`). |
| 4 | P2 | dark | **PERSISTS** | `cardLocation` rgba(255,255,255,0.4) 10px = 3.67:1; `logTimestamp` `textDim` #2a3a4a sobre `bgCard` = 1.50:1. |
| 5 | P2 | both | **PERSISTS** | Empty state sem CTA (cadastrar câmera / limpar filtro de módulo). |
| 6 | P2 | — | **NEW** | Aba "Desempenho" adicionada ao drawer (4 tabs: Feed · Logs ao vivo · **Desempenho** · Info) — não estava no spec anterior; copy e layout desta aba não documentados. |
| 7 | P2 | both | **RESOLVED** | ~~`retryBtn` roxo #8b5cf6 hardcoded~~ — botão "Reconectar" no drawer usa cor tokenizada em ambos os temas. |
| 8 | P3 | both | **PERSISTS** | "Camera offline" / "HLS nao suportado" sem acentuação; verde `Ativa` #22c55e diverge de `success` #10b981; dot `Desconectado` (≈1.2:1) invisível. |
