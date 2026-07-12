<!-- HERDADO DA STAGING — revalidar no próximo run do develop -->

# Sites & Saúde — spec visual

**Rota:** `/epi/sites-health` (role guard: `isAdmin` — admin|superadmin; operator vê acesso negado)
**Fontes:**
- `src/pages/epi/EpiSitesHealthPage.tsx` (página + `OverviewCards` + `SiteDetailPanel`)
- `src/pages/epi/EpiSitesHealthPage.css.ts` (todos os estilos, vanilla-extract)
- `src/components/ui/Badge/Badge.{tsx,css.ts}` (badges de status)
- `src/services/edgeService.ts` (adapta shape cru do backend), `src/hooks/usePolling.ts` (refresh 30s)
- recharts: `LineChart/Line/XAxis/YAxis/Tooltip/CartesianGrid/ResponsiveContainer`

**Screenshots:**

| Estado | Dark | Light (white-label claro) |
|---|---|---|
| default | `../screenshots/sites-health/dark-default.png` | `../screenshots/sites-health/light-default.png` |
| empty | `../screenshots/sites-health/dark-empty.png` | `../screenshots/sites-health/light-empty.png` |
| loading | `../screenshots/sites-health/dark-loading.png` | `../screenshots/sites-health/light-loading.png` |
| error | `../screenshots/sites-health/dark-error.png` | `../screenshots/sites-health/light-error.png` |
| operator-denied | `../screenshots/sites-health/dark-operator-denied.png` | `../screenshots/sites-health/light-operator-denied.png` |
| modal-site-detail | `../screenshots/sites-health/dark-modal-site-detail.png` | `../screenshots/sites-health/light-modal-site-detail.png` |
| modal-site-detail-sem-dados | `../screenshots/sites-health/dark-modal-site-detail-sem-dados.png` | `../screenshots/sites-health/light-modal-site-detail-sem-dados.png` |
| modal-site-detail-loading | `../screenshots/sites-health/dark-modal-site-detail-loading.png` | `../screenshots/sites-health/light-modal-site-detail-loading.png` |
| hover-row | `../screenshots/sites-health/dark-hover-row.png` | — (só dark) |
| hover-retry | `../screenshots/sites-health/dark-hover-retry.png` | — (só dark) |

Endpoints mockados: `GET /api/v1/edge/overview`, `GET /api/v1/edge/sites/health`,
`GET /api/v1/edge/sites/:id/heartbeats`, `GET /api/v1/edge/sites/:id/heartbeat-summary`.
Deferred: banner parcial de erro (`errorBanner` — falha de polling após primeiro load OK) não capturado.

## Layout — regiões

- **TopBar global** (52px sticky, z-index 40) + **HealthFooter global**.
- **`container`**: flex column, `padding: 24px` (space.lg), `gap: 24px`, `flex:1`, scroll vertical.
  1. **`pageHeader`**: h1 18px/700 `textPrimary` + subtítulo 13px `textMuted` (marginTop 2px).
  2. **`errorBanner`** (condicional, polling falhou com dados na tela): 13px `danger` sobre
     `dangerMuted`, borda 1px `danger`, radius 6 (md), padding 8×16.
  3. **`overviewRow`**: grid `repeat(auto-fill, minmax(152px, 1fr))`, gap 8 (sm) — 6 cards.
     Card: padding 16 (md), bg `bgCard`, borda `borderSubtle`, radius 10 (lg), gap interno 4 (xs).
     Label 10px/700 uppercase `textMuted`; valor 28px/700 mono (success/warning/danger/textPrimary);
     sub 11px `textDim`.
  4. **`mainContent`**: flex row, gap 16 (md), `flex:1`, minHeight 320px.
     - **`tableSection`** (flex 1): bg `bgCard`, borda `borderSubtle`, radius 10; header
       "SITES (n)" 12px/700 uppercase `textSecondary`, padding 8×16, borda inferior `borderSubtle`;
       tabela 13px, `th` sticky 10px/700 uppercase `textDim` sobre `bgSurface`, `td` padding 8×16
       `textSecondary` com borda inferior `borderSubtle`.
     - **`detailPanel`** (condicional, `aside` inline — NÃO é modal/overlay, não requer backdrop):
       width fixa 360px, bg `bgCard`, borda `borderSubtle`, radius 10. Header padding 16 com
       título 15px/700 ellipsis + botão X. Body padding 16, gap 16:
       `summaryGrid` 2×2 (gap 8; métrica: padding 8, bg `bgSurface`, radius 6, label 10px/700
       uppercase `textMuted`, valor 20px/700 mono `textPrimary`) + seção do gráfico
       (título 11px/700 uppercase `textMuted`; `ResponsiveContainer` 100%×160px).

## Árvore de componentes

```
EpiSitesHealthPage
├── [guard] centeredState role=alert → "Acesso restrito a administradores"   (errorText danger)
├── [loading] centeredState role=status → ícone RefreshCw 18 + "Carregando dados da frota..."
├── [erro total] centeredState role=alert → errorText + botão retryBtn "Tentar novamente"
└── [default]
    ├── pageHeader (h1 + p)
    ├── errorBanner (condicional, role=alert)
    ├── OverviewCards (region "Resumo da frota") — 6× overviewCard
    ├── tableSection (section "Lista de sites")
    │   ├── header "Sites (7)"
    │   └── table (5 colunas) — tr clicável/tabIndex=0, hover bgHover,
    │       selecionado primaryAlpha; célula Site = nome (600, textPrimary)
    │       + id técnico (11px mono textDim); Badge status; timeAgo; FPS mono; câmeras mono
    └── SiteDetailPanel (aside, data-testid="site-detail-panel")
        ├── header: h3 nome + detailCloseBtn (X 16, hover: textPrimary + bgHover)
        └── body:
            ├── [loading] centeredState → RefreshCw 16 + "Carregando detalhes..."
            ├── summaryGrid 2×2: Uptime / FPS Médio / HB (24h) / Último HB
            └── chart: título + LineChart (CartesianGrid 3 3, XAxis/YAxis ticks 10px,
                Tooltip customizado, Line monotone #06b6d4 strokeWidth 2, activeDot r=4)
                ou empty "Sem dados de heartbeat"
```

Badge (UI kit): pill radius full, 11px/700 uppercase, padding 3×10 — variantes
`success` (verde s/ successMuted), `warning`, `danger`, `neutral` (textMuted s/ bgElevated).

## Copy exata

- H1: `Sites & Saúde` — subtítulo: `Monitoramento em tempo real da frota de dispositivos edge`
- Cards (labels renderizam uppercase): `Sites Saudáveis` (sub `de {N} sites`), `Sites Degradados`,
  `Sites Críticos`, `Sites Offline`, `Devices Online` (sub `de {N} total`), `Devices Revogados`
- Seção: `Sites ({n})` — colunas: `Site` · `Status` · `Último HB` · `FPS` · `Câmeras`
- Badges: `Saudável` / `Degradado` / `Crítico` / `Offline` (renderizam uppercase)
- timeAgo: `agora` · `há {m}min` · `há {h}h` · `há {d}d` · `—` (null); FPS null → `—`
- Estados: `Carregando dados da frota...` · `Nenhum site encontrado` · `Carregando detalhes...` ·
  `Sem dados de heartbeat` · `Tentar novamente` · `Acesso restrito a administradores`
- Erro (fixture 500, mensagem do backend): `Falha ao consultar frota edge`;
  fallback do catch: `Erro ao carregar dados da frota`
- Painel: métricas `Uptime` / `FPS Médio` / `HB (24h)` / `Último HB`;
  gráfico `FPS — últimas 24 entradas`; tooltip `{v.toFixed(1)} fps` rotulado `FPS`
- aria: `Resumo da frota`, `Lista de sites`, `Sites e status de saúde da frota`,
  `Site {nome}, status {label}`, `Detalhes do site {nome}`, `Fechar detalhes do site`,
  `Métricas do site`, `Gráfico de FPS ao longo do tempo`, `Notificações` (toast viewport)
- Toast global de erro 500 (via `api.ts` → `errorTranslator.ts`): `Erro interno do servidor`

## Dados de exemplo (fixtures do spec)

Overview: `sites_total: 7`, `devices_total: 12`, `devices_online: 9`, `devices_revoked: 1`.
Cards derivados da lista: Saudáveis 3 · Degradados 1 · Críticos 1 · Offline 2 · Devices 9 "de 12 total" · Revogados 1.

| Site (nome / id) | Status | Último HB | FPS | Câmeras |
|---|---|---|---|---|
| RVB Industrial — Matriz Betim / `site-rvb-matriz` | SAUDÁVEL | agora | 24.6 | 6/6 |
| RVB Industrial — Filial Contagem / `site-rvb-contagem` | SAUDÁVEL | há 2min | 22.1 | 4/4 |
| Centro de Distribuição Cajamar / `site-cd-cajamar` | SAUDÁVEL | há 1min | 25.3 | 8/8 |
| Unidade Portuária Santos / `site-porto-santos` | DEGRADADO | há 9min | 11.4 | 3/5 |
| Planta Química Paulínia / `site-quimica-paulinia` | CRÍTICO | há 28min | 3.2 | 1/6 |
| Mineração Serra Azul / `site-mineracao-serra` | OFFLINE | há 1d | — | 0/4 |
| Terminal Logístico Sul / `site-terminal-sul` | OFFLINE | — | — | 0/2 |

Painel (RVB Matriz): Uptime `99%` · FPS Médio `23.4` · HB (24h) `288` · Último HB `agora`;
24 heartbeats de 5 em 5 min, FPS senoidal ~19.7–25.3 (linha ciana).
Painel sem dados (Terminal Logístico Sul): Uptime `0%` · FPS Médio `—` · HB (24h) `0` ·
Último HB `—` · "Sem dados de heartbeat".

## Estados

- **default**: header + 6 cards + tabela 7 linhas; sem painel.
- **empty**: cards zerados ("de 0 sites"/"de 0 total") + "Nenhum site encontrado" centrado no card
  da tabela (texto `textDim` — quase invisível no dark, ver Problemas).
- **loading**: página inteira substituída por centeredState (sem header da página).
- **error total**: página substituída por texto danger + botão "Tentar novamente" (hover:
  bgHover + borderStrong — capturado em `dark-hover-retry.png`); toast global "Erro interno do
  servidor" sobrepõe a TopBar (ver Problemas).
- **operator-denied**: página substituída por "Acesso restrito a administradores" (danger).
- **hover-row**: linha recebe `bgHover` (delta sutil sobre `bgCard`); foco visível:
  outline 2px `primary` + `primaryAlpha`.
- **selecionado**: linha com `primaryAlpha` persistente enquanto painel aberto.
- **painel loading / sem-dados / rico**: ver árvore acima.
- **errorBanner parcial**: não capturado (deferred).

## Navegação e fluxos

- Clique/Enter/Espaço em linha → abre `SiteDetailPanel` (busca heartbeats + summary; erros do
  detalhe são silenciosos — gráfico cai no empty).
- X do painel → fecha e limpa seleção.
- "Tentar novamente" → refaz `loadData()`.
- Polling de 30s re-busca overview+health; falha após primeiro load vira `errorBanner`.

## Problemas identificados

1. **P1 (light) — task-063**: ticks dos eixos do recharts `fill: rgba(255,255,255,0.4)` (1.07:1
   sobre card claro) e `CartesianGrid stroke rgba(255,255,255,0.06)` (1.01:1) — eixos ilegíveis
   no tema claro (`EpiSitesHealthPage.tsx:257-268`; `light-modal-site-detail.png`).
   No dark os ticks dão 3.82:1 (< 4.5 para texto 10px).
2. **P2 (both) — hardcode**: Tooltip `background '#1a1a2e'` (cor fora da paleta; bgElevated é
   `#1e2330`) + borda `rgba(255,255,255,0.12)`; `Line stroke '#06b6d4'` literal em vez de
   `vars.color.primary` — white-label não retematiza a série (no claro a linha dá 2.09:1 < 3:1).
3. **P1 (dark) — token**: `textDim #2a3a4a` não tem ponte white-label e dá 1.50:1 sobre `bgCard`
   / 1.59:1 sobre `bgSurface` — afeta `th`, `siteIdText`, `overviewCardSub` e todos os
   `centeredState` ("Nenhum site encontrado", "Carregando...", "Sem dados de heartbeat").
4. **P1 (light)**: `success/warning/danger` fixos do tema dark sob superfícies claras:
   badge DEGRADADO 1.73:1, SAUDÁVEL 2.01:1, CRÍTICO 2.86:1 (11px precisa 4.5:1); valores 28px
   warning 1.85:1 e success 2.18:1 (< 3:1 para texto grande).
5. **P1 (dark, ambos prováveis) — transparency**: toast global "Erro interno do servidor"
   renderiza sobre a TopBar (viewport `top:16/right:16` × TopBar sticky 52px) com fundo
   efetivamente transparente — texto do toast e controles do header mesclados/ilegíveis
   (`dark-error.png`, `dark-hover-retry.png`).
6. **P2 (dark)**: badge neutral OFFLINE — `textMuted` sobre `bgElevated` = 3.81:1 (< 4.5 p/ 11px).
7. **P2 (light)**: `errorText`/guard usam `danger #ef4444` sobre base clara = 3.45:1 (< 4.5 p/ 14px).
8. **P3**: estados loading/erro/denied descartam o `pageHeader` (página "pelada", sem contexto);
   empty "Nenhum site encontrado" e "Sem dados de heartbeat" são becos sem saída (sem CTA);
   id técnico (`site-rvb-matriz`) exposto como subtítulo da linha.
