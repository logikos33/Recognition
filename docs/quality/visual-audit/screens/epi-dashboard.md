# EPI Dashboard — spec visual

**Rota:** `/epi/dashboard`
**Fontes:**
- `apps/frontend/src/pages/epi/EpiDashboard.tsx` + `EpiDashboard.css.ts`
- `apps/frontend/src/components/dashboard/KPIRow.tsx` + `KPIRow.css.ts`
- `apps/frontend/src/components/dashboard/KPICard.tsx` + `KPICard.css.ts`
- `apps/frontend/src/components/camera-grid/CameraGrid.tsx` + `CameraGrid.css.ts`
- `apps/frontend/src/components/camera-grid/CameraCell.tsx`, `CameraPlaceholder.tsx`, `GridToolbar.tsx`, `GridPanel.tsx`
- `apps/frontend/src/components/cameras/CameraWizard.tsx`, `WizardSteps.tsx`, `CameraWizard.css.ts`

**Screenshots:**

| Estado | Dark | Light (white-label) |
|---|---|---|
| default | `../screenshots/epi-dashboard/dark-default.png` | `../screenshots/epi-dashboard/light-default.png` |
| default-quadrantes (1440×1700) | `../screenshots/epi-dashboard/dark-default-quadrantes.png` | `../screenshots/epi-dashboard/light-default-quadrantes.png` |
| empty | `../screenshots/epi-dashboard/dark-empty.png` | `../screenshots/epi-dashboard/light-empty.png` |
| loading | `../screenshots/epi-dashboard/dark-loading.png` | `../screenshots/epi-dashboard/light-loading.png` |
| error | `../screenshots/epi-dashboard/dark-error.png` | `../screenshots/epi-dashboard/light-error.png` |
| modal-kpi-alertas (drawer) | `../screenshots/epi-dashboard/dark-modal-kpi-alertas.png` | `../screenshots/epi-dashboard/light-modal-kpi-alertas.png` |
| modal-kpi-conformidade (drawer) | `../screenshots/epi-dashboard/dark-modal-kpi-conformidade.png` | `../screenshots/epi-dashboard/light-modal-kpi-conformidade.png` |
| modal-painel-cameras (GridPanel) | `../screenshots/epi-dashboard/dark-modal-painel-cameras.png` | `../screenshots/epi-dashboard/light-modal-painel-cameras.png` |
| modal-seletor-camera | `../screenshots/epi-dashboard/dark-modal-seletor-camera.png` | `../screenshots/epi-dashboard/light-modal-seletor-camera.png` |
| modal-menu-contexto | `../screenshots/epi-dashboard/dark-modal-menu-contexto.png` | `../screenshots/epi-dashboard/light-modal-menu-contexto.png` |
| wizard-step1..4 | `../screenshots/epi-dashboard/dark-wizard-step{1..4}.png` | `../screenshots/epi-dashboard/light-wizard-step{1..4}.png` |
| hover KPI Conformidade | `../screenshots/epi-dashboard/hover-kpi-conformidade.png` | — |
| hover linha de alerta | `../screenshots/epi-dashboard/hover-alert-row.png` | — |

---

## Layout — regiões

Shell da aplicação (fora do escopo desta tela): header superior (logo EPI / breadcrumb "Dashboard", sino de notificação com badge 8, toggle "Pro", nome do usuário, badge SUPERADMIN, botão "Sair") e status bar inferior (`Banco de dados · Redis · câmeras ativas`).

Conteúdo (`container` — EpiDashboard.css.ts:4): coluna flex, `flex:1`, **`overflow:hidden`** (sem scroll — origem do clipping de Q3/Q4 em viewport 900px).

1. **KPIRow** (`row` — KPIRow.css.ts:4): flex horizontal, `gap 16px`, `padding 16px 24px`, `overflow-x:auto`, 5 cards `flex 1 1 0`, `minWidth 200px`.
2. **Drawer expansível** (condicional, abaixo da KPIRow): `margin 0 24px 8px`, `padding 16px`, bg `bgCard`, borda `borderDefault`, radius `md(6px)`.
3. **quadrantGrid** (EpiDashboard.css.ts:83): `grid-template-columns: 3fr 2fr`, `gap 16px`, `margin-top 16px`, `padding 0 16px 16px`. Quatro células:
   - **Q1 (col 1, linha 1):** `cameraSection` — grid DVR de câmeras, bg `#000000`, sem padding.
   - **Q2 (col 2, linha 1):** quadrant "Últimos Alertas".
   - **Q3 (col 1, linha 2):** quadrant "Registro de Eventos" (tabela).
   - **Q4 (col 2, linha 2):** quadrant "Distribuição de Violações" (donut recharts).
   - `quadrant`: bg `bgCard`, borda `borderSubtle`, radius `lg(10px)`, padding 16px, `min-height 240px`, `overflow:hidden`.

### Grid DVR (Q1)
- `container` (CameraGrid.css.ts:4): bg `#000000`, `overflow:hidden`, relativo.
- Botão hambúrguer (`hamburgerBtn`): absoluto `top 6px / left 6px`, 32×32, bg `rgba(0,0,0,0.6)`, borda `rgba(255,255,255,0.1)`, blur 4px, z-index 20 — **sobrepõe o nome da primeira câmera** ("ra Pátio Norte").
- `grid`: CSS grid, `gap 2px`, `padding 2px`, colunas/linhas conforme preset (2×2 default). Célula `cellBase`: bg `#0a0a0a`, borda `rgba(255,255,255,0.05)`, radius 2px, `aspect-ratio 16/9`.
- Overlay header da célula (`cellHeader`): gradiente `rgba(0,0,0,0.7)→transparent`, nome da câmera 11px mono `rgba(255,255,255,0.9)` + badge `● LIVE` (#22c55e) ou `● ALERT` (#ef4444).
- Overlay footer (`cellFooter`): gradiente invertido; localização e relógio HH:MM 10px `rgba(255,255,255,0.5)`.
- Toolbar (`toolbar`): bg `bgSurface`, borda superior `borderSubtle`; presets `1×1 2×2 3×3 4×4 1+5 1+7`, olho (toggle labels), `Salvar`, fullscreen.

---

## Árvore de componentes

```
EpiDashboard
├─ KPIRow
│  ├─ KPICard ×5 (Cameras Ativas / Taxa de Conformidade* / Alertas Hoje* / Deteccoes/Hora / Modelo Ativo)
│  │   * clicáveis — expandem drawer; borda ciano quando active
│  └─ drawer (condicional): "Ultimos Alertas" (lista 10 itens) | "Conformidade por EPI" (lista classes + %)
├─ quadrantGrid
│  ├─ Q1 CameraGrid (module="epi")
│  │  ├─ hamburgerBtn → GridPanel (painel lateral 280px, overlay rgba(0,0,0,0.4))
│  │  │  ├─ busca ("Buscar camera...") + lista de câmeras (dot verde/cinza, nome, local, +)
│  │  │  ├─ botão "+ Nova Camera" → CameraWizard
│  │  │  ├─ Presets built-in (grid 3 col) + "Meus Presets" + "Salvar Layout Atual" → modal Salvar Preset
│  │  ├─ DndContext > SortableContext > CameraCell ×N | CameraPlaceholder (célula vazia "+ Adicionar câmera")
│  │  │  └─ CameraCell: CameraPlayer (HLS) + DetectionOverlay + overlays nome/LIVE/local/hora
│  │  ├─ GridToolbar (presets, eye, Salvar, fullscreen) + modal Salvar Preset
│  │  ├─ contextMenu (right-click na célula): Expandir/Restaurar · Trocar câmera · Remover do grid
│  │  └─ cameraSelector (célula vazia): dropdown central "SELECIONAR CÂMERA" + lista
│  ├─ Q2 Últimos Alertas: 5 × alertRow (câmera bold 13px / violações 12px / tempo 11px) + link "Ver todos →"
│  ├─ Q3 Registro de Eventos: tabela (Câmera | Violação | Confiança | Horário) 8 linhas + "Ver histórico completo →"
│  └─ Q4 Distribuição de Violações: PieChart donut (inner 50/outer 80, height 180) + legenda (dot 10px, nome, valor)
└─ CameraWizard (modal 520px, 4 passos, progressBar 4 segmentos)
   ├─ Passo 1 Fabricante: grid 2 col de 6 botões
   ├─ Passo 2 Conexão: hint azul + campos IP/Porta/Usuário/Senha/Caminho
   ├─ Passo 3 Identificação: Nome/Localização + preview "URL RTSP QUE SERÁ USADA" (mono laranja)
   └─ Passo 4 Teste: botão "Testar Conexão" → banner resultado + box DIAGNÓSTICO (5 checks)
```

---

## Copy exata

### KPIRow / KPICard (KPIRow.tsx)
- Títulos: `Cameras Ativas` · `Taxa de Conformidade` · `Alertas Hoje` · `Deteccoes/Hora` · `Modelo Ativo` (sem acentos no source)
- Subtextos: `de {N} total` · `ultimas 24h` · `mAP50: {X}%` | fallback `base model`
- Trend: `↑ vs {N}` / `↓ vs {N}`
- Drawer alertas: título `Ultimos Alertas`; vazio `Nenhum alerta recente`; fallback violação `violacao`; botão `Ver todos →`
- Drawer conformidade: título `Conformidade por EPI`; fallback sem dados: linhas `Capacete / Colete / Oculos / Luvas` com `—`

### Quadrantes (EpiDashboard.tsx)
- Títulos: `Últimos Alertas` · `Registro de Eventos` · `Distribuição de Violações`
- Vazios: `Nenhum alerta recente` · `Nenhum evento registrado` · `Sem dados no período`
- Links: `Ver todos →` · `Ver histórico completo →`
- Cabeçalhos tabela Q3: `Câmera` · `Violação` · `Confiança` · `Horário`
- Labels de violação (VIOLATION_LABELS): `Sem capacete` · `Sem colete` · `Sem luvas` · `Sem óculos`
- Tempo relativo: `agora` · `há {N}min` · `há {N}h` · `há {N}d`
- Tooltip donut: `{valor} ocorrências`

### CameraGrid / GridPanel / GridToolbar
- aria hambúrguer: `Abrir painel de controle`; painel: `Painel de Controle`; aria fechar: `Fechar painel`
- Busca placeholder: `Buscar camera...`; seções `CAMERAS` / `PRESETS` / `MEUS PRESETS`
- Vazio busca: `Nenhuma camera encontrada`; tooltips: `Ja no grid` / `Adicionar ao grid`
- Botões: `+ Nova Camera` · `Salvar Layout Atual` · `Salvar`
- Modal preset: título `Salvar Preset`; placeholder `Nome do preset (ex: Portaria + Estoque)`; `Cancelar` / `Salvar`
- Menu de contexto: `Expandir` / `Restaurar` · `Trocar câmera` · `Remover do grid`
- Seletor: título `Selecionar câmera`; vazio `Nenhuma câmera cadastrada`
- Placeholder de célula: `Adicionar câmera` (aria: `Adicionar câmera na posição {N}`)
- Célula: badges `LIVE` / `ALERT`; fallback local `Sem local`; player `Conectando...`

### CameraWizard / WizardSteps
- Título: `Nova Câmera` / `Editar Câmera`; subtítulo `Passo {N} de 4 — {Fabricante|Conexão|Identificação|Teste}`
- Passo 1: hint `Selecione o fabricante para configuração automática do caminho RTSP.`; fabricantes `Hikvision · Dahua · Intelbras · Axis · Samsung · Outra marca`; erro `Selecione o fabricante`
- Passo 2: hint `💡 O IP está nas configurações de rede da câmera. Usuário/senha são os mesmos usados para acessá-la pelo navegador.`; campos `Endereço IP *` (placeholder `192.168.1.100`), `Porta`, `Usuário` (placeholder `admin`), `Senha` (placeholder `Senha de acesso` | edição `(deixe vazio para manter)`), `Caminho do stream (opcional)` (placeholder `Padrão: {path}`); help `Deixe em branco para usar o padrão do fabricante`; erros `Informe o IP da câmera` / `IP inválido (ex: 192.168.1.100)` / `Porta inválida (1–65535)`
- Passo 3: `Nome da câmera *` (placeholder `Ex: Entrada Principal, Baia 1...`), `Localização (opcional)` (placeholder `Ex: Bloco A, Térreo...`), label `URL RTSP QUE SERÁ USADA`; erro `Dê um nome para a câmera`
- Passo 4: `Clique abaixo para verificar se a câmera está acessível na rede.` · `Testar Conexão` · `Testando conexão...` (⏳) · `✓ Conexão estabelecida!` / `✗ Falha na conexão` · `DIAGNÓSTICO` com checks: `Formato da URL RTSP` / `Câmera acessível na rede` / `Porta RTSP aberta` / `Resposta ao protocolo RTSP` / `Stream de vídeo disponível` · falha: `← Corrigir dados` + `Testar novamente` · sugestão prefixada `💡 `
- Rodapé: `Cancelar` (passo 1) / `← Voltar` · `Próximo →` · `Concluir`
- Toasts: `Câmera adicionada` / `Câmera atualizada`

---

## Dados de exemplo (fixtures do harness)

**KPIs:** Cameras Ativas `3` (`de 4 total`) · Taxa de Conformidade `87%` (`ultimas 24h`, ícone âmbar 70–89) · Alertas Hoje `12` (pulsando) · Deteccoes/Hora `342` (`↑ vs 310`) · Modelo Ativo `LGKV26s-epi-rvb-v3` (`mAP50: 91.2%`)

**Câmeras (grid 2×2, localStorage `epi-camera-grid`):**
| Célula | Nome | Local |
|---|---|---|
| 0 | Câmera Pátio Norte | Pátio Norte — Portão 2 |
| 1 | Câmera Doca 3 | Doca de Carregamento |
| 2 | Câmera Linha de Produção A | Galpão 1 — Linha A |
| 3 | (vazia — "Adicionar câmera") | — |
| painel | Câmera Almoxarifado | Bloco B — Térreo |

**Alertas (8, pt-BR) — Q3 Registro de Eventos:**
| Câmera | Violação | Confiança | Horário | ack (opacity .5) |
|---|---|---|---|---|
| Câmera Pátio Norte | Sem capacete | 94% | há 4min | não |
| Câmera Doca 3 | Sem colete | 88% | há 13min | não |
| Câmera Linha de Produção A | Sem luvas | 81% | há 28min | sim |
| Câmera Pátio Norte | Sem óculos | 73% | há 47min | não |
| Câmera Almoxarifado | Sem colete | 90% | há 1h | não |
| Câmera Doca 3 | Sem capacete | 86% | há 1h | sim |
| Câmera Linha de Produção A | Sem luvas | 79% | há 2h | não |
| Câmera Pátio Norte | Sem colete | 92% | há 4h | sim |

**Q2** usa os 5 primeiros; alerta 3 mostra violação dupla `Sem luvas, Sem capacete`.
**Q4 donut:** Sem capacete `3` (#06b6d4) · Sem colete `3` (#f97316) · Sem luvas `2` (#a855f7) · Sem óculos `1` (#10b981). Paleta `CHART_COLORS = ['#06b6d4','#f97316','#a855f7','#10b981','#f59e0b']`.
**Drawer KPI Alertas:** horários `23:12 · 23:03 · 22:48 · 22:29 · 22:08 · 21:41 · 20:44 · 19:16`.
**Drawer Conformidade (compliance_by_class, chaves cruas do backend):** `Helmet 94.2%` (verde) · `Vest 88.7%` (âmbar) · `Gloves 71.3%` (âmbar) · `Glasses 65.8%` (vermelho).

---

## Estados

- **default:** tudo populado como acima. Em 1280×720 apenas KPIRow + Q1/Q2 visíveis; Q3/Q4 **clipados** (sem scroll). `default-quadrantes` (1440×1700) revela Q3/Q4.
- **empty:** KPIs `0 / — / 0 / 0 / LGKV8n (base model)`; grid 2×2 só placeholders; Q2 `Nenhum alerta recente` (quase invisível no dark — textDim); Q3/Q4 clipados mostrariam `Nenhum evento registrado` / `Sem dados no período`.
- **loading:** **visualmente idêntico ao empty** — não há skeleton/spinner; useQuery sem indicador.
- **error:** **visualmente idêntico ao empty** — erro da API não é tratado na página (alerts → `[]`, KPIs zerados); único vestígio é um toast clipado/sobreposto ao header (ver dark-error.png, canto superior direito).
- **hover KPI card:** borda `borderStrong` + glow violeta `rgba(139,92,246,0.1)`; mesmo efeito em cards clicáveis e não-clicáveis.
- **hover linha de alerta (Q2):** **nenhuma mudança visual** (linhas não são interativas).
- **KPI active (drawer aberto):** borda `vars.color.primary` (ciano).
- **célula com violação:** borda 2px pulsando `rgba(239,68,68,0.6)↔0.15` + badge ALERT.
- **célula em drag:** opacity 0.4; alvo de drop: borda `borderStrong` + inset glow violeta.

## Navegação e fluxos

- KPI `Taxa de Conformidade` (click) → drawer Conformidade por EPI (toggle).
- KPI `Alertas Hoje` (click) → drawer Ultimos Alertas → `Ver todos →` navega `/epi/alerts`.
- Q2 `Ver todos →` e Q3 `Ver histórico completo →` → `/epi/alerts` (NavLink).
- Hambúrguer (Q1) → GridPanel; `+ Nova Camera` → CameraWizard (passos 1→4; `Testar Conexão` cria/atualiza a câmera e roda diagnóstico; `Concluir` habilita só com sucesso).
- Célula vazia (click) → seletor "Selecionar câmera"; right-click em célula → menu de contexto; double-click → expandir célula; Esc fecha painel/célula expandida.
- Toolbar: presets de layout, olho (esconde labels), `Salvar` → modal Salvar Preset, fullscreen.

## Problemas identificados (resumo — detalhes no findings JSON)

1. **P0 task-063:** KPI cards com bg hardcoded `rgba(12,12,18,0.8)` — sob white-label claro os 5 KPIs ficam ilegíveis (valor 1.5:1, subtexto 1.04:1).
2. **P1:** `textDim #2a3a4a` (1.5:1 no dark) usado em conteúdo real: subtextos de KPI, headers da tabela Q3, horários, empty states.
3. **P1:** Q3/Q4 100% clipados em viewport ≤900px (`overflow:hidden` sem scroll).
4. **P1:** hambúrguer sobrepõe o nome da câmera da célula 0 ("ra Pátio Norte").
5. **P1:** empty state do drawer com `rgba(255,255,255,0.4)` hardcoded (invisível no claro).
6. **P1:** hint e banners de resultado do wizard com hex pastel hardcoded (#93c5fd/#fca5a5/#86efac) — ilegíveis no claro.
7. **P1:** erro da API silencioso — dashboard de segurança mostra zeros como se estivesse saudável.
8. **P2:** ícone de busca e vazio do GridPanel com `rgba(255,255,255,0.3)` (invisível no claro); loading = empty; acento violeta legado `rgba(139,92,246,*)` fora da identidade ciano; copy sem acentos; chaves do backend em inglês no drawer (Helmet/Vest/...); "Ver todos" ciano 2.09:1 no claro; URL RTSP laranja 3.56:1 no claro; placeholder "Adicionar câmera" 1.77:1.
9. **P3:** overlays inconsistentes (0.65 vs token 0.7); pulse sem prefers-reduced-motion; linhas de alerta parecem clicáveis mas não têm ação nem hover; empty states sem CTA.

---

## Findings (develop — 2026-07-07)

### Alterações visíveis no develop

**WS3 — INDICADORES substitui Q2/Q3/Q4**

A seção de quadrantes foi substituída por um bloco **INDICADORES** abaixo da grade de câmeras (visível em `light-default-quadrantes.png`):
- Seletor de período: `Hoje (24h)` · `7 dias` *(active — bg ciano)* · `30 dias` · `Personalizar`
- Widget **"Alertas ao longo do tempo"**: BarChart recharts com time-range; empty state: `Sem dados no período / Nenhum evento registrado no intervalo selecionado.`
- Widget **"Distribuição de Violações"**: donut recharts (ex-Q4) com empty state `Sem dados no período`
- Widget **"Câmeras com mais alertas"**: NOVO; empty state `Sem dados no período`
- Cada widget tem handle de drag (⣿) e toggle de visibilidade (👁) no canto superior direito
- Q2 "Últimos Alertas" (lista rápida de 5 alertas) não aparece mais neste estado

**task-068 — Stall / Reconexão de câmera (NOVO positivo)**

Células de câmera offline exibem `Câmera offline — reconectando...` + botão `Reconectar` (ciano tokenizado). Stall detection de task-068 operacional — melhoria de feedback ao usuário.

### Tabela de findings

| # | Sev | Tema | Status develop | Descrição |
|---|-----|------|---------------|-----------|
| 1 | P0 | light | **PERSISTS** | KPI cards bg `rgba(12,12,18,0.8)` hardcoded — WS1 não corrigiu; valores ~1.5:1, subtextos ~1.04:1 no light (confirmado em `light-default-quadrantes.png`) |
| 2 | P1 | dark | **PERSISTS** | `textDim #2a3a4a` (1.5:1) em subtextos de KPI, horários, empty states |
| 3 | P1 | both | ~~Q3/Q4 clipados em ≤900px~~ **(PARCIALMENTE RESOLVIDO — WS3)** | INDICADORES agora está abaixo da grade e aparece com scroll; risco residual em viewports muito curtos |
| 4 | P1 | both | **PERSISTS** | Hambúrguer sobrepõe o nome da câmera 0 ("ra Pátio Norte") |
| 5 | P1 | light | **PERSISTS** | Empty state do drawer com `rgba(255,255,255,0.4)` hardcoded — invisível no claro |
| 6 | P1 | both | **PERSISTS** | Wizard: hints e banners com hex pastel hardcoded (#93c5fd/#fca5a5/#86efac) — ilegíveis no claro |
| 7 | P1 | both | **PERSISTS** | Erro de API silencioso — dashboard mostra zeros como se estivesse saudável |
| 8 | P2 | both | **PERSISTS** | GridPanel: busca/vazio `rgba(255,255,255,0.3)` invisível no claro; glow violeta legado; copy sem acentos; chaves em inglês no drawer; links ciano 2.09:1 no claro; URL RTSP laranja 3.56:1 |
| 9 | P3 | both | **PERSISTS** | Overlays inconsistentes; pulse sem `prefers-reduced-motion`; linhas de alerta sem hover; empty states sem CTA |
| 10 | P2 | both | **NEW** | WS3: botão `Personalizar` do seletor de período não tem borda/affordance clara no dark — difícil distinguir de inactive; hover state não definido |
| 11 | P3 | both | **NEW** | Spec layout Q2/Q3/Q4 desatualizada — estrutura INDICADORES não está documentada; copy dos novos widgets ausente da spec (`Alertas ao longo do tempo`, `Câmeras com mais alertas`, `Sem dados no período`, `Nenhum evento registrado no intervalo selecionado.`) |
