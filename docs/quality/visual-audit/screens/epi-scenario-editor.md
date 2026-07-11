# Editor de Cenário (EPI) — spec visual

**Rota:** `/epi/cameras/:cameraId/scenario` (auditada com `cameraId=1`)
**Fontes:**
- `apps/frontend/src/pages/epi/EpiScenarioEditorPage.tsx` (página)
- `apps/frontend/src/components/scenario/ScenarioEditor.tsx` (layout, sidebar, sub-componentes SideSection/SideButton/EmptyHint, `inputStyle`)
- `apps/frontend/src/components/scenario/DrawingCanvas.tsx` (overlay SVG de desenho, toolbar, instruções)
- `apps/frontend/src/components/monitoring/CameraPlayer.tsx` (vídeo HLS)
- Hooks: `useScenario`, `useScenarioOperationTypes`, `useOperations`

**Screenshots:**

| Estado | Dark | Light (white-label) |
|---|---|---|
| default (zona 4 pts desenhada, nome + 2 classes) | `../screenshots/epi-scenario-editor/dark-default.png` | `../screenshots/epi-scenario-editor/light-default.png` |
| empty (sem módulos) | `../screenshots/epi-scenario-editor/dark-empty.png` | `../screenshots/epi-scenario-editor/light-empty.png` |
| loading | `../screenshots/epi-scenario-editor/dark-loading.png` | `../screenshots/epi-scenario-editor/light-loading.png` |
| error (500) | `../screenshots/epi-scenario-editor/dark-error.png` | `../screenshots/epi-scenario-editor/light-error.png` |
| ferramenta linha (2 pts) | `../screenshots/epi-scenario-editor/dark-tool-linha.png` | `../screenshots/epi-scenario-editor/light-tool-linha.png` |
| ferramenta ponto (1 pt) | `../screenshots/epi-scenario-editor/dark-tool-ponto.png` | `../screenshots/epi-scenario-editor/light-tool-ponto.png` |
| hover canvas (linha elástica) | `../screenshots/epi-scenario-editor/hover-canvas.png` (dark) | — |

## Layout — regiões

Coluna de altura `100vh`, fundo `bgBase`:

1. **Header** (`padding: 10px 16px`, `borderBottom: 1px solid borderDefault`): "← Voltar" (textMuted 13px) · "/" (textPrimary 12px) · `<h1>` "Editor de Cenário" (14px/600 textSecondary) · "/" · nome da câmera (13px textMuted) · spacer · feedback à direita: `saveError` (12px `#ef4444` hardcode) ou "Operação salva com sucesso!" (12px success).
2. **Corpo** (flex, `flex:1, overflow:hidden`):
   - **Sidebar** 260px, `borderRight: 1px solid borderDefault`, scroll. Empilha SideSections (marginBottom 10; título `padding: 6px 16px 4px`, 10px/600 uppercase letterSpacing .07em, cor **textPrimary**): Módulo → Tipo de Operação → Ferramenta de Desenho → Nome da Operação → Classes a Monitorar → Threshold de Alerta → botão Salvar → divisor `#181818` (hardcode) → Operações (N).
   - **Main** (`padding: 24`, conteúdo centrado no topo): container do canvas 640×360, radius 8, bg `#000`, borda `1px solid #1e3a5f` (hardcode azul).
3. **Canvas em camadas** (dentro do container 640×360):
   - Layer 1: `CameraPlayer` (HLS) ou placeholder gradiente `#0a0e1a → #0d1420` com texto `#2a4a6a` mono.
   - Layer 2: `DrawingCanvas` — SVG `viewBox 0 0 1 1` com shapes `pointerEvents:none` + camada de interação separada (`cursor: crosshair`, `tabIndex 0`) + toolbar top-right (undo ↩ / redo ↪ / limpar ✕, 28×28, bg `rgba(0,0,0,0.75)`, borda `rgba(255,255,255,0.2)`) + instrução bottom-left (11px `rgba(255,255,255,0.5)` sobre `rgba(0,0,0,0.4)`, radius 4, padding 3px 8px).

Espaçamentos observados: 4/6/8/10/16/24 (6/10 fora da escala tokenizada).

## Árvore de componentes

```
EpiScenarioEditorPage
└── ScenarioEditor
    ├── header (Voltar · título · câmera · feedback salvar)
    ├── [loading] "Carregando cenário..." (role=status, centrado)
    ├── [error]   mensagem crua (role=alert, #ef4444, centrado)
    └── corpo
        ├── aside 260px (aria-label "Painel de configuração")
        │   ├── SideSection "Módulo" (radiogroup) → SideButton por módulo (module_code cru: "epi", "fueling")
        │   │   · ativo: bg rgba(59,130,246,0.1) + borderLeft 2px primary + texto textSecondary
        │   │   · inativo: transparente + texto textMuted (módulo disabled NÃO é diferenciado)
        │   ├── SideSection "Tipo de Operação" (radiogroup) → SideButton por tipo: "▶" + type_label + description (10px, opacity .5)
        │   ├── SideSection "Ferramenta de Desenho" → 3 chips: "⬡ Zona" / "— Linha" / "• Ponto"
        │   │   · ativo: bg rgba(59,130,246,0.2) + borda primary + texto primary
        │   │   · inativo: bg bgSurface + borda bgCard + texto **borderStrong** (bug de token)
        │   │   └ hint "Definida pelo tipo selecionado" (11px **textPrimary**)
        │   ├── SideSection "Nome da Operação" → input (inputStyle: bg bgSurface, borda borderDefault, cor **textOnPrimary** — bug)
        │   ├── SideSection "Classes a Monitorar" → checkbox + display_name por classe (13px textSecondary, accentColor primary)
        │   ├── SideSection "Threshold de Alerta" → input number 80px (default 1)
        │   ├── botão "Salvar Operação" (full-width; habilitado: bg primary + textOnPrimary; desabilitado: bg bgCard + texto borderStrong)
        │   ├── divisor #181818
        │   └── SideSection "Operações (N)" → linha por operação: dot 6px (success/#ef4444/#f59e0b/textMuted) + nome (12px textMuted, ellipsis)
        └── main (aria-label "Área de desenho")
            └── container 640×360
                ├── CameraPlayer | placeholder "Stream não disponível"
                └── DrawingCanvas
                    ├── SVG: ROIs existentes (polígono/linha/círculo tracejados, cor STATUS_COLORS hardcode + label mono do nome)
                    ├── SVG: desenho atual em #3b82f6 (polígono fill 15% / polyline tracejada / linha elástica até hover / círculos de vértice, 1º maior)
                    ├── camada de interação (click adiciona ponto; zona fecha clicando no 1º ponto; Ctrl+Z / Ctrl+Shift+Z)
                    ├── toolbar ↩ ↪ ✕ (✕ só com pontos > 0)
                    └── instrução (role=status, aria-live=polite)
```

## Copy exata

**Header:** `← Voltar` (aria-label `Voltar`) · `Editor de Cenário` · nome da câmera · `Operação salva com sucesso!` · erro de save cru (ex.: mensagem da API) · fallback página `Câmera não encontrada`.

**Estados de página:** `Carregando cenário...` · erro cru (ex.: `Erro interno do servidor`).

**Sidebar (títulos de seção):** `Módulo` · `Tipo de Operação` · `Ferramenta de Desenho` · `Nome da Operação` · `Classes a Monitorar` · `Threshold de Alerta` · `Operações ({n})`.

**Hints/vazios:** `Nenhum módulo habilitado` · `Carregando...` · `Nenhum tipo disponível` · `Nenhuma operação cadastrada` · `Definida pelo tipo selecionado`.

**Chips de ferramenta:** `⬡ Zona` · `— Linha` · `• Ponto` (aria-label `Ferramenta {zone|line|point}( (ativa))`).

**Input nome:** placeholder `Ex: {type_label}` (aria-label `Nome da operação`).

**Botão salvar:** `Salvar Operação` / `Salvando...` (aria-label `Salvar operação`).

**Placeholder sem stream:** `Stream não disponível` + `desenhe no placeholder ou conecte um stream`.

**Toolbar canvas:** `↩` (title `Desfazer (Ctrl+Z)`) · `↪` (title `Refazer (Ctrl+Shift+Z)`) · `✕` (title `Limpar desenho`).

**Instruções do canvas (por ferramenta/progresso):**
- zona: `Clique para adicionar pontos da zona` → `{n} ponto(s) — adicione mais {3-n}` → `{n} pontos — clique no ● inicial para fechar`
- linha: `Clique para definir início da linha` → `Clique para definir fim da linha` → `Linha definida — clique para redesenhar`
- ponto: `Clique para definir o ponto de interesse` → `Ponto definido — clique para reposicionar`

## Dados de exemplo (fixtures do harness)

`GET /api/cameras/1/scenario` → câmera **Câmera Pátio Norte** (site-rvb-01); módulos: `epi` (habilitado) e `fueling` (desabilitado); classes EPI: Capacete (#10b981), Sem capacete (#ef4444), Colete (#06b6d4), Sem colete (#f59e0b), Pessoa (#8ba3bc).

`GET /api/scenarios/operation-types?module=epi` → 5 tipos: Contagem estática, Sobreposição dinâmica, Posição, Linha de contagem, **Ponto de interesse** ("Monitora presença de classe em um ponto fixo do cenário" — exercita a ferramenta ponto).

`GET /api/cameras/1/operations?module_id=epi` → 2 operações com ROI renderizadas sobre o vídeo: **Zona Portão Leste** (position, active → verde) e **Contagem Doca 2** (count_static, error → vermelho).

Valores digitados nas capturas: nome "Zona Estoque Químico" (default, zona 4 pts, classes Capacete+Colete), "Linha Portaria Principal" (linha), "Ponto Extintor Corredor B" (ponto — **invisível no tema claro por bug do input**).

## Estados

- **default:** módulo `epi` auto-selecionado (primeiro habilitado); tipo Posição selecionado → ferramenta Zona ativa; polígono azul #3b82f6 desenhado sobre o vídeo; 2 ROIs de fixture (verde/vermelha tracejadas) com labels mono; instrução "4 pontos — clique no ● inicial para fechar".
- **empty (sem módulos):** sidebar mostra apenas "Módulo → Nenhum módulo habilitado" e "Operações (0) → Nenhuma operação cadastrada"; canvas segue visível e desenhável, mas não há como salvar (beco sem saída — sem CTA para habilitar módulo).
- **loading:** texto centrado "Carregando cenário...".
- **error:** texto centrado cru "Erro interno do servidor" em #ef4444, sem ação de retry.
- **tool-linha / tool-ponto:** chip correspondente ativa; desenho muda (linha sólida 2 pts / círculo duplo 1 pt); trocar tipo/módulo reseta o desenho e o histórico.
- **hover-canvas:** linha elástica tracejada do último vértice até o cursor + dot de hover 35% opacidade.
- **selecionado:** SideButton ativo ganha barra lateral primary + bg azul 10%; checkbox marcado usa accent primary.
- **salvar:** habilita apenas com tipo + nome + geometria completa (zona ≥3, linha =2, ponto =1); sucesso limpa formulário e mostra "Operação salva com sucesso!" por 3s.

## Navegação e fluxos

- "← Voltar" → `/epi/cameras/{id}/operations`.
- Selecionar módulo → carrega tipos (`/api/scenarios/operation-types?module=…`) e operações do módulo; reseta tipo/desenho.
- Selecionar tipo → infere ferramenta pelo `config_schema` (`roi_points`→zona, `line_points`→linha, `point`→ponto) e revela seções Nome/Classes/Threshold/Salvar.
- Clique no canvas → adiciona ponto (normalizado 0–1); Ctrl+Z/Ctrl+Shift+Z/✕ para desfazer/refazer/limpar.
- "Salvar Operação" → `POST /cameras/{id}/operations` com `{module_id, type_id, name, config{…, roi_points|line_points|point, target_classes, threshold}}` → refetch de cenário + operações.
- Não há modais nesta tela.

## Problemas identificados (resumo)

1. **P0 · texto invisível no tema claro:** `inputStyle` usa `color: vars.color.textOnPrimary` (#ffffff) — no white-label claro o texto digitado em "Nome da Operação" fica branco sobre branco (1.0:1). Evidência: light-default / light-tool-ponto (input aparenta vazio apesar de preenchido).
2. **P1 · chips de ferramenta ilegíveis (dark):** texto dos chips inativos usa `borderStrong` (#2a3545) sobre bgSurface (#111318) = 1.50:1 — "⬡ Zona/— Linha/• Ponto" praticamente invisíveis; no claro também degradado. Token de borda usado como cor de texto.
3. **P2 · hierarquia invertida:** títulos de seção (10px), `EmptyHint` e o hint "Definida pelo tipo selecionado" usam `textPrimary` (ênfase máxima) enquanto o conteúdo real usa textMuted — microcopy grita mais que o conteúdo, nos dois temas.
4. **P2 · classe 063 no canvas:** instrução `rgba(255,255,255,0.5)` sobre `rgba(0,0,0,0.4)`, toolbar `rgba(0,0,0,0.75)`/borda `rgba(255,255,255,0.2)`, divisor `#181818`, borda do canvas `#1e3a5f`, STATUS_COLORS e `drawColor #3b82f6` hardcoded (azul divergente do primary ciano; mesma paleta legada do EditMode da tela de operações).
5. **P2 · módulo desabilitado sem estado visual:** `fueling` (disabled) renderiza e clica igual ao habilitado.
6. **P2 · copy técnica:** lista de módulos exibe `module_code` cru ("epi", "fueling") em vez de nome humano.
7. **P2 · erro/vazio sem ação:** erro 500 vira texto cru sem retry; vazio sem CTA.
8. **P3 · botão salvar desabilitado** quase ilegível no dark (borderStrong sobre bgCard = 1.41:1 — isento por WCAG para disabled, mas abaixo de qualquer affordance); **P3 ·** placeholder sem stream `#2a4a6a` sobre gradiente ≈2.1:1.

Detalhamento com ratios e refs no findings JSON da auditoria.

---

## Findings (develop — 2026-07-07)

| # | Severidade | Tema | Status | Descrição |
|---|---|---|---|---|
| 1 | P0 | light | **PERSISTS** | `inputStyle` usa `color: vars.color.textOnPrimary` (#ffffff) — texto digitado em "Nome da Operação" branco sobre fundo branco no claro (1.0:1). Confirmado em `light-default`: input "Zona Estoque Químico" aparece vazio enquanto `dark-default` mostra o texto corretamente. |
| 2 | P1 | both | **PERSISTS** | Chips inativos de ferramenta ("⬡ Zona / — Linha / • Ponto") usam `borderStrong` (#2a3545) como `color`: 1.50:1 em dark, igualmente degradado em light — praticamente invisíveis. |
| 3 | P2 | both | **PERSISTS** | Hierarquia invertida: títulos de seção (10px) e hints usam `textPrimary` (ênfase máxima) enquanto conteúdo usa `textMuted`. |
| 4 | P2 | both | **PERSISTS** | Hardcodes no canvas: `rgba(255,255,255,0.5)` na instrução, `rgba(0,0,0,0.75)`/`rgba(255,255,255,0.2)` na toolbar, divisor `#181818`, borda canvas `#1e3a5f`, STATUS_COLORS e `drawColor #3b82f6` (azul divergente do primary ciano). |
| 5 | P2 | both | **PERSISTS** | Módulo "fueling" exibe `module_code` cru na sidebar em vez de nome humano ("Abastecimento"). Confirmado em `dark-default` e `light-default`. |
| 6 | P2 | both | **PERSISTS** | Módulo desabilitado (`fueling`) sem diferenciação visual de estado: clica e rende igual ao habilitado. |
| 7 | P2 | both | **PERSISTS** | Erro 500 vira texto cru sem retry; empty sem CTA para habilitar módulo. |
| 8 | P2 | — | **NEW** | Tipo "Ponto de interesse" adicionado à lista de tipos (`dark-default` sidebar) — não estava no spec de copy anterior. Exercises a ferramenta "• Ponto". |
| 9 | P3 | dark | **PERSISTS** | Botão "Salvar Operação" desabilitado: `borderStrong` sobre `bgCard` = 1.41:1 (WCAG isenta disabled, mas sem affordance visual). |
