# Controle de Carregamento (Fueling) — spec visual

**Rota:** `/fueling` (abas deep-linkáveis via `?tab=dashboard|baias|eventos`)
**Fontes:** `apps/frontend/src/pages/fueling/FuelingPage.tsx` (página inteira, estilos inline), `src/components/shared/LoadingSpinner`, `src/components/monitoring/CameraPlayer` (não exercitado nesta captura), `src/styles/theme.css.ts` (contrato `vars`), recharts (LineChart/BarChart/PieChart)
**Nota de escopo:** o briefing dizia que `/fueling` era o placeholder "Em breve" (`FuelingPlaceholder.tsx`) — está DESATUALIZADO. `AppRoutes` roteia `FuelingPage` (dashboard completo, 3 abas). `FuelingPlaceholder.tsx` é código morto.

**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (aba Dashboard rica) | ../screenshots/fueling/dark-default.png | ../screenshots/fueling/light-default.png |
| empty (dashboard `no_data`) | ../screenshots/fueling/dark-empty.png | ../screenshots/fueling/light-empty.png |
| tab-baias (6 baias, sem câmeras) | ../screenshots/fueling/dark-tab-baias.png | ../screenshots/fueling/light-tab-baias.png |
| tab-eventos (7 detecções) | ../screenshots/fueling/dark-tab-eventos.png | ../screenshots/fueling/light-tab-eventos.png |

## Layout — regiões

- Shell padrão da app: topbar global (logo EPI, toggle Pro/tema, "Auditor Visual", badge SUPERADMIN, "Sair"), sem sidebar expandida nesta captura; footer de status ("Banco de dados / Redis / câmeras ativas").
- Conteúdo: container `padding: 24px`, `maxWidth: 1100px`, `margin: 0 auto`.
- Header da página: flex space-between, `marginBottom: 20` — esquerda: ícone `Package` 22px (`#f59e0b`) + h2 20px/700 + badge "DEMO" (superadmin); direita: botão "Atualizar".
- Barra de abas: flex `gap: 4`, `marginBottom: 24`.
- Aba Dashboard: seletor de período (pill container `bgBase` + borda `bgSurface`, radius 8, padding 4, width fit-content, `marginBottom: 24`) → grid KPIs `repeat(4, 1fr)` gap 14 → grid KPIs 2 `repeat(3, 1fr)` gap 14 `marginBottom: 28` → 2 grids de gráficos `1fr 1fr` gap 20.
- Aba Baias: grid `repeat(3, 1fr)` gap 16 (6 cards → 2 linhas).
- Aba Eventos: card único com header + tabela full-width.
- Cards: `background: vars.color.bgBase`, `border: 1px solid vars.color.bgSurface`, `borderRadius: 10`, padding `18px 22px` (KPI) ou `18px 20px` (gráficos). Observação: usa `bgBase` como fundo de card e `bgSurface` como cor de borda — semântica invertida em relação aos tokens (`bgCard`/`borderDefault` existem e não são usados).

## Árvore de componentes

- `FuelingPage`
  - Header: `Package` (lucide) + `h2` "Controle de Carregamento" + badge DEMO (condicional `isSuperAdmin`) + botão "Atualizar" (`RefreshCw` 13px, ghost com borda `borderStrong`)
  - Tabs (3 `<button>` genéricos, sem role=tab): Dashboard | Monitoramento de Baias | Eventos — ativo: bg `rgba(99,102,241,0.18)`, cor `#a5b4fc`; inativo: transparent, `textMuted`
  - **Aba Dashboard**
    - Period selector (3 botões): Hoje | Semana | Mês — mesmo padrão índigo do tab ativo
    - `LoadingSpinner` (loading) | empty state | conteúdo:
    - 4× `KpiCard` (label uppercase 11px `textMuted`, valor 28px/700 monospace com `accent` prop, sub 12px `textMuted`)
    - 3× linha 2: 2 `KpiCard` + card "Status do Módulo" (ícone `Activity` 20px `#6366f1`, texto "● Ativo" em `success`)
    - Card "Operações Diárias": recharts `LineChart` 200px, linha `#6366f1` strokeWidth 2, grid `bgSurface`, ticks `textMuted` 10px, Tooltip com `contentStyle` bg `bgBase`
    - Card "Tempo Médio por Baia (min)": recharts `BarChart`, barras `#6366f1` radius `[4,4,0,0]`
    - Card "Causas de Não Conformidade": recharts `PieChart` donut 160×160 (inner 45/outer 70), cores `PIE_COLORS = ['#6366f1', '#f59e0b', vars.color.success, '#f87171']` + legenda à direita (swatch 10×10 radius 2, nome 12px `textSecondary`, valor 12px 600 monospace `#f1f5f9`)
    - Card "Top Baias": seção "Mais produtivas" (valor monospace `success`) + divisor + "Maior perda" (valor monospace `#f87171`)
  - **Aba Baias**
    - `LoadingSpinner` | empty state | grid de 6× `BayCameraCard`:
      - header (padding `10px 14px`, borda inferior `bgSurface`): `Video` 13px `textMuted` + nome da baia 13px/600 `#f1f5f9` + nome da câmera 11px `textMuted` (se houver) + badge de status (10px/700, padding `2px 8px`, radius 4, bg `${statusColor}22`, cor `statusColor`)
      - área de vídeo `aspectRatio 16/9`, bg `#020617`: `CameraPlayer` (com câmera) | `<video>` demo (superadmin) | placeholder `Video` 28px opacity .3 + "Câmera não configurada" 11px/600 cor `vars.color.borderStrong`
      - rodapé de dados (padding `12px 14px`): ativo → grid 2 col Operador/Placa (labels 10px uppercase `textMuted`, valores 12px `textSecondary`, placa monospace) + linha "Itens carregados" (valor `success` monospace) + barra de progresso 5px (track `bgSurface`, fill `linear-gradient(90deg, #6366f1, vars.color.success)`) + percentual 10px `textMuted` à direita; idle/manutenção → texto centralizado 12px `textMuted`
      - borda do card: `rgba(34,197,94,0.25)` quando `active`, senão `bgSurface`
  - **Aba Eventos**
    - Card com header "Eventos Recentes" (13px/600 `textSecondary`)
    - Empty state | `<table>` borderCollapse collapse:
      - `<th>`: 11px/600 uppercase `textMuted`, padding `10px 20px`
      - `<td>`: Classe 13px/500 `#f1f5f9` | Confiança 13px monospace com cor semafórica (`confidenceColor`: <0.5 `#ef4444`, <0.7 `#f59e0b`, senão `success`; null `textMuted`) | Câmera 12px monospace `textMuted` (uuid truncado em 12 chars) | Horário 12px `textMuted`
      - zebra: linhas ímpares `background: rgba(255,255,255,0.015)`; borda inferior `bgBase`

## Copy exata

- Título: `Controle de Carregamento` · Badge: `DEMO` · Botão: `Atualizar`
- Abas: `Dashboard` · `Monitoramento de Baias` · `Eventos`
- Período: `Hoje` · `Semana` · `Mês`
- KPIs (labels/subs): `Total Carregado`/`caminhões no período` · `Tempo Médio` (valor `{n} min`)/`por carregamento` · `Itens Não Conformes`/`{taxa}% do total` · `Itens Movimentados`/`unidades no período` · `Não Conformidades`/`eventos registrados` · `Taxa de Ocupação` (valor `{n}%`)/`das baias no período` · `Status do Módulo`/`● Ativo`
- Gráficos: `Operações Diárias` · `Tempo Médio por Baia (min)` · `Causas de Não Conformidade` · `Top Baias` (`Mais produtivas` / `Maior perda`)
- Tooltips recharts: `{v} un` + `Operações` · `{v} min` + `Tempo médio` · `{v}%`
- Formato de itens: `fmtItens` → `1.8k un` (≥1000) ou `960 un`; `fmtNum` → `12.5k`
- Empty dashboard: `Nenhum dado de carregamento disponível` / `Configure câmeras de carregamento para visualizar métricas aqui.`
- Status de baia: `Em operação` · `Aguardando` · `Manutenção` (renderizados em UPPERCASE no badge)
- Labels de baia: `Operador` · `Placa` · `Itens carregados` · placeholder `Câmera não configurada` · idle `Aguardando próxima operação` · manutenção `Baia em manutenção`
- Empty baias: `Nenhuma baia configurada` / `Configure câmeras de carregamento para monitorar as baias aqui.`
- Eventos: header `Eventos Recentes`; colunas `Classe` · `Confiança` · `Câmera` · `Horário`; classes traduzidas: truck→`Caminhão`, plate→`Placa`, forklift→`Empilhadeira`, product_box→`Caixa`, pallet→`Pallet`; sem valor → `—`
- Empty eventos: `Sem eventos registrados ainda` / `Os eventos aparecerão aqui quando câmeras de carregamento forem configuradas.`

## Dados de exemplo (fixtures do spec 26-fueling)

- KPIs: total_carregado 42 · tempo_medio 38 min · itens_movimentados 12480 (`12.5k`) · não conformes 187 (1.5%) · eventos NC 23 · ocupação 78%
- Operações diárias: 30/06→34, 01/07→41, 02/07→38, 03/07→46, 04/07→29, 05/07→22, 06/07→42
- Tempo por baia: B01 34 · B02 41 · B03 29 · B04 52 · B05 37 · B06 44
- Pizza causas: Caixa avariada 42% · Item trocado 28% · Falta de item 18% · Outros 12%
- Top produtivas: Baia 03 3.1k un · Baia 01 2.8k un · Baia 05 2.2k un; Maior perda: Baia 05 84 un · Baia 02 57 un · Baia 04 31 un
- Baias: Baia 01 active/Carlos Menezes/RVB2C34/1.8k un/72% · Baia 02 active/Marina Duarte/FKT7A81/960 un/38% · Baia 03 idle · Baia 04 maintenance · Baia 05 active/Antônio Ferreira Lima/QXP4D18/2.1k un/91% · Baia 06 idle
- Eventos: Caminhão 94% · Placa 88% · Caixa 67% · Pallet 91% · Empilhadeira 46% · Caixa — · Caminhão 82% (camera_id truncado tipo `a1b2c3d4-e5f`)

## Estados

- **loading:** `LoadingSpinner` no corpo da aba ativa.
- **default:** dashboard rico (KPIs + 4 gráficos).
- **empty (no_data):** ícone `Package` 36px opacity .25 + título 15px/600 + orientação; seletor de período e abas continuam visíveis.
- **tab-baias:** mosaico 3×2; cards ativos com borda verde translúcida e barra de progresso; idle/manutenção com mensagem central.
- **tab-eventos:** tabela zebra com cor semafórica na confiança.
- **hover:** NENHUM elemento define hover (tudo inline style) — abas, período, Atualizar, linhas de tabela e cards não reagem.
- **selecionado:** aba/período ativo = fundo índigo translúcido `rgba(99,102,241,0.18/0.2)` + texto `#a5b4fc`.
- **polling:** dashboard+baias recarregam a cada 30s.

## Navegação e fluxos

- Abas gravam `?tab=` via `setSearchParams` (deep-link da sidebar suportado; sincroniza se URL muda externamente).
- "Atualizar" recarrega dashboard e, se já carregadas, baias/eventos.
- Período (Hoje/Semana/Mês) refaz `GET /api/fueling/dashboard?period=`.
- Baias/câmeras/eventos são lazy-load na primeira visita à aba (`GET /api/fueling/bays`, `GET /api/cameras`, `GET /api/fueling/events?limit=30`).
- Card de baia com câmera ativa montaria `CameraPlayer` (HLS) — não capturado (deferred p/ grupo monitoring).
- Nenhum modal/drawer nesta tela.

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P0 task-063:** título, nomes de baia, coluna Classe, valores de KPI default e legenda da pizza usam `#f1f5f9` hardcoded → invisíveis no tema claro (ratio 1.0–1.1).
2. **P1:** paleta índigo `#6366f1/#a5b4fc` (tabs, período, DEMO, charts) ilegível no claro (1.58–1.83) e fora da identidade Recognition (primary ciano `#06b6d4`).
3. **P1 dark:** placeholder "Câmera não configurada" em `borderStrong` sobre `#020617` = 1.63 no dark (ilegível no tema PADRÃO; no claro fica ok porque a var é sobrescrita).
4. **P2:** cores semafóricas (`#f59e0b`, `#10b981`, `#f87171`, badges de status) 1.97–2.54 sobre superfícies claras.
5. **P2:** hover ausente em todos os interativos; página 100% inline styles fora do design system; radius 3/5 e spacings 14/18/22 fora da escala; `bgBase`/`bgSurface` usados com semântica invertida (deveria ser `bgCard`/`borderDefault`).
6. **P3:** zebra `rgba(255,255,255,0.015)` hardcoded (invisível no claro); borda verde `rgba(34,197,94,…)` difere do token success `#10b981`; `FuelingPlaceholder.tsx` é código morto; abas sem semântica de tabs (role/aria-selected).

## Findings (develop — 2026-07-07)

> Comparado com _baseline-staging/screens/fueling.md · screenshots analisados: dark-default, light-default, dark-tab-baias, light-tab-baias, dark-tab-eventos, light-tab-eventos, dark-empty, light-empty

| # | Severidade | Descrição | Status |
|---|-----------|-----------|--------|
| 1 | P0 | Título "Controle de Carregamento", nomes de baia ("Baia 01" etc.) e coluna Classe da tabela Eventos usam `#f1f5f9` hardcoded → invisíveis no tema claro. Confirmado: `light-tab-eventos.png` mostra coluna CLASSE vazia; `light-tab-baias.png` não mostra nomes das baias nos cabeçalhos dos cards. `FuelingPage.tsx` NÃO foi migrado pelo WS1 (d7a3ad3). | PERSISTE |
| 2 | P1 | Paleta índigo `#6366f1/#a5b4fc` nas abas, seletor de período, badge DEMO e gráficos — ilegível no claro (1.58–1.83:1 vs WCAG AA 4.5:1); diverge da identidade Recognition (`primary` #06b6d4). | PERSISTE |
| 3 | P1 | Placeholder "Câmera não configurada" usa `vars.color.borderStrong` (#2a3545) sobre fundo de vídeo `#020617` = 1.63:1 no tema dark (abaixo de 4.5:1). | PERSISTE |
| 4 | P2 | Cores semafóricas hardcoded (`#f59e0b`, `#10b981`, `#f87171`) e badges de status (EM OPERAÇÃO, MANUTENÇÃO) falham contraste sobre superfícies claras (1.97–2.54:1). | PERSISTE |
| 5 | P2 | Hover ausente em todos os elementos interativos (abas, período, Atualizar, linhas de tabela, cards); `bgBase`/`bgSurface` com semântica invertida vs tokens `bgCard`/`borderDefault`; espaçamentos 14/18/22 fora da escala do DS. | PERSISTE |
| 6 | P3 | Zebra `rgba(255,255,255,0.015)` invisível no claro; borda verde ativa `rgba(34,197,94,0.25)` diverge do token `success #10b981`; `FuelingPlaceholder.tsx` é código morto; abas `<button>` sem `role="tab"/aria-selected`. | PERSISTE |

**Resumo:** 0 resolvidos · 6 persistem · 0 novos. `FuelingPage.tsx` não foi incluído na migração WS1 — página inteira em inline styles.
