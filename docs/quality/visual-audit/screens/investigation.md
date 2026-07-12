# Investigação de Eventos — spec visual

**Rota:** `/epi/investigation` (AppRoutes.tsx:60 → `InvestigationPage`)
**Fontes:** `apps/frontend/src/pages/epi/InvestigationPage.tsx` (100% estilos inline; não usa `EpiInvestigation.css.ts`), `src/services/api.ts`, `src/styles/theme.css.ts` (contrato `vars`), recharts (`BarChart`)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | ../screenshots/investigation/dark-default.png | ../screenshots/investigation/light-default.png |
| filters-active | ../screenshots/investigation/dark-filters-active.png | ../screenshots/investigation/light-filters-active.png |
| empty | ../screenshots/investigation/dark-empty.png | ../screenshots/investigation/light-empty.png |
| empty-ws4-envelope (bug) | ../screenshots/investigation/dark-empty-ws4-envelope.png | ../screenshots/investigation/light-empty-ws4-envelope.png |
| loading | ../screenshots/investigation/dark-loading.png | ../screenshots/investigation/light-loading.png |
| error (500) | ../screenshots/investigation/dark-error.png | ../screenshots/investigation/light-error.png |
| modal-frame | ../screenshots/investigation/dark-modal-frame.png | ../screenshots/investigation/light-modal-frame.png |
| hover class chip (sem mudança visual) | ../screenshots/investigation/hover-class-chip.png | — |
| hover linha de evento (sem mudança visual) | ../screenshots/investigation/hover-event-row.png | — |

## Layout — regiões

- Shell do app: topbar (hambúrguer, logo "EPI", sino, toggle Pro/tema, "Auditor Visual" + badge `SUPERADMIN`, botão "Sair"); rodapé de status ("Banco de dados", "Redis", "câmeras ativas"). Shell tem `overflow:hidden` — página não rola em fullPage (viewport 1440×1900 usado na captura).
- Container da página: `padding: 24px; maxWidth: 1200px; margin: 0 auto`.
- Empilhamento vertical (sem grid de página):
  1. **Cabeçalho** — `h1` 1.5rem/700 + subtítulo 0.875rem `textSecondary`, `marginBottom: 24px`.
  2. **Card Filtros** — `bgCard`, borda 1px `borderDefault`, radius 8, padding 16, `marginBottom: 20px`. Dentro: linha de chips de classe (flex wrap, gap 6) e grid de campos `repeat(auto-fit, minmax(160px, 1fr))`, gap 12.
  3. **Card Volume de eventos (timeline)** — mesmo estilo de card; header flex space-between; `ResponsiveContainer` height 160.
  4. **Card Eventos (lista)** — mesmo estilo de card, `overflow: hidden`; header `padding: 12px 16px` com borda inferior; linhas de evento `padding: 12px 16px` com borda inferior `borderDefault`; paginação `padding: 12px 16px` com borda superior, centrada.
- **Modal de frame** — overlay `position: fixed; inset: 0; background: vars.color.overlay` (rgba(0,0,0,0.7)), `zIndex: 1000`, conteúdo centrado; painel `bgCard`, radius 8, padding 16, `maxWidth: 90vw; maxHeight: 90vh` (é um div ad-hoc com `TODO-WS1: converter para Modal do kit`).

## Árvore de componentes

- `InvestigationPage`
  - `h1` "Investigação de Eventos" + `p` subtítulo
  - Card **Filtros**
    - `h2` "Filtros" (0.875rem/600)
    - Grupo "Classe de detecção": 11 `button` chips-toggle (radius 12px, `padding: 3px 10px`, 0.75rem). Não selecionado: bg `bgSurface`, texto `textPrimary`, borda `borderDefault`. Selecionado: bg `primaryDark`, texto `textOnPrimary`, borda `primaryDark`.
    - 5 campos com `label` (span 0.75rem `textSecondary` + controle): `select` Módulo, `input datetime-local` De, `input datetime-local` Até, `input number` Confiança mín. (min 0, max 1, step 0.05), `select` Agrupamento. Controles NATIVOS sem tokenização de bg/cor (só borda `borderDefault`, radius 6, `padding: 6px 8px`) — renderizam brancos no tema dark.
    - `button` link "Limpar filtros de classe" (só quando há classe selecionada; texto sublinhado 0.75rem `textSecondary`, sem bg/borda)
  - Banner de erro (condicional): bg `dangerMuted`, borda 1px `#fca5a5` (hardcoded), radius 6, padding 12, texto `danger` 0.875rem
  - Card **Volume de eventos**
    - `h2` "Volume de eventos" + span direita `textMuted` ("Carregando…" | "{n} períodos")
    - `BarChart` recharts: `CartesianGrid` strokeDasharray "3 3" `borderDefault`; eixos tick 11px `textSecondary`; `Tooltip`; `Bar` fill `primaryDark`, radius topo [3,3,0,0]
    - Vazio do chart: div 160px centrada `textMuted`
  - Card **Eventos**
    - Header: `h2` "Eventos" + "({total} total)" em `textSecondary`/400; direita "Buscando…" `textMuted` quando carregando
    - Linha de evento (por item): thumbnail 72×48 (bg `bgSurface`, radius 4; `img object-fit: cover` ou span "sem frame" 0.625rem `textMuted`) + coluna de detalhes:
      - chips de violação (`padding: 1px 8px`, radius 10, 0.7rem/600): bg `dangerMuted`/texto `#991b1b` p/ classes `no_*`; bg `successMuted`/texto `#166534` p/ demais (hex hardcoded)
      - código do módulo à direita (`ev.module_code` cru: "epi"/"fueling", 0.7rem `textSecondary`, `marginLeft: auto`)
      - linha meta 0.75rem `textSecondary`: data/hora pt-BR + "{n}% confiança"
      - linha selecionada: bg `primaryAlpha`; cursor pointer só se `frame_url`
    - Paginação: botões "Anterior"/"Próxima" (radius 4, borda `borderDefault`, 0.75rem; desabilitado: bg `bgSurface`, texto `textMuted`) + span "{page} / {pages}"
  - **Modal frame ampliado** (condicional `selectedFrame?.frame_url`): header (data/hora 0.875rem/600 + botão "✕" 1.25rem `textSecondary` sem borda), `img` `maxWidth: 80vw; maxHeight: 70vh; objectFit: contain`, rodapé com os mesmos chips de violação

## Copy exata

- Título: `Investigação de Eventos`
- Subtítulo: `Busque e analise eventos de todos os módulos ativos`
- Card filtros: `Filtros`, `Classe de detecção`, `Módulo`, `De`, `Até`, `Confiança mín.`, `Agrupamento`, `Limpar filtros de classe`
- Chips de classe (chaves cruas do backend): `no_helmet`, `helmet`, `no_vest`, `vest`, `no_gloves`, `gloves`, `no_glasses`, `glasses`, `plate`, `truck`, `fuel_nozzle`
- Select Módulo: `Todos`, `EPI`, `Fueling`, `Quality`
- Select Agrupamento: `Por hora`, `Por dia`, `Por semana`
- Placeholder confiança: `0.0 – 1.0`
- Timeline: `Volume de eventos`, `Carregando…`, `{n} períodos`, vazio: `Nenhum dado para o período selecionado`
- Lista: `Eventos`, `({n} total)`, `Buscando…`, vazio: `Nenhum evento encontrado para os filtros aplicados`
- Erros: `Erro ao buscar eventos` (fallback quando `res.error` ausente — inclusive no bug WS4), `Não foi possível conectar à API` (exceção de rede/HTTP)
- Paginação: `Anterior`, `{page} / {pages}`, `Próxima`
- Thumbnail sem imagem: `sem frame`; modal: botão `✕`, alt `frame ampliado`

## Dados de exemplo (fixtures do harness)

- Busca: `total: 47`, `pages: 3`, página `1 / 3`. Timeline: 12 buckets por hora (05/07 22:00 → 06/07 08:00 na exibição), counts `[2,1,0,3,5,4,9,12,7,3,1,0]` → "12 períodos".
- Eventos (6 linhas):
  | id | violações (chips) | módulo | data/hora exibida | confiança | frame |
  |---|---|---|---|---|---|
  | ev-001 | `no_helmet` `vest` | epi | 06/07/2026, 05:14:23 | 92% | sim |
  | ev-002 | `no_vest` | epi | 06/07/2026, 04:52:10 | 87% | sim |
  | ev-003 | `no_gloves` `no_glasses` | epi | 06/07/2026, 04:31:44 | 78% | sim |
  | ev-004 | `helmet` `vest` | epi | 06/07/2026, 03:58:02 | 95% | não ("sem frame") |
  | ev-005 | `no_helmet` | epi | 05/07/2026, 14:20:38 | 64% | sim |
  | ev-006 | `truck` `plate` | fueling | 05/07/2026, 13:05:11 | 71% | sim |
- Frame mockado (SVG 640×360): fundo `#1e2330`, bounding box vermelha `#ef4444` com rótulo `no_helmet 0.92`, legenda `Câmera Pátio Norte — frame de evidência`.
- filters-active: chips `no_helmet` e `no_vest` selecionados (bg `primaryDark`) + confiança `0.7` + link "Limpar filtros de classe" visível.

## Estados

- **default:** filtros + timeline com barras + lista de 6 eventos + paginação 1/3.
- **filters-active:** 2 chips selecionados em `primaryDark`, campo confiança preenchido, link de limpar visível.
- **empty:** timeline mostra "Nenhum dado para o período selecionado"; lista mostra "Nenhum evento encontrado para os filtros aplicados" (padding 40, centrado, `textMuted`). Sem CTA.
- **empty-ws4-envelope (BUG):** com o envelope PADRÃO da API (`{status:'success', data}`), a página exibe o banner vermelho "Erro ao buscar eventos" mesmo com HTTP 200 — a página checa `res.success` (InvestigationPage.tsx:159).
- **loading:** "Carregando…" no header da timeline e "Buscando…" no header da lista; nenhum skeleton.
- **error:** banner "Não foi possível conectar à API" + toast do shell; timeline vazia.
- **hover:** NENHUM feedback visual em chips de classe nem linhas de evento (estilos inline sem `:hover`); única affordance é `cursor: pointer`.
- **selecionado:** linha de evento clicada ganha bg `primaryAlpha` e abre o modal.

## Navegação e fluxos

- Chip de classe → toggle do filtro → refetch busca+timeline (page volta a 1).
- Campos Módulo/De/Até/Confiança/Agrupamento → refetch automático ao mudar.
- "Limpar filtros de classe" → zera `selectedClasses`.
- Clique em linha COM frame → seleciona e abre modal de frame ampliado; clique de novo/no overlay/no "✕" → fecha. Linha sem frame não faz nada.
- "Anterior"/"Próxima" → `fetchEvents(page±1)`.
- Nenhum link de navegação externa (não abre câmera/alerta relacionados).

## Problemas identificados (resumo — detalhe no findings JSON)

1. **BUG WS4 (P1):** contrato de envelope divergente — página exige `{success,data}`, API padrão devolve `{status:'success',data}` → estado vazio real vira banner de erro.
2. **Contraste dark (P1):** chips de violação `#991b1b`/`#166534` hardcoded sobre `dangerMuted`/`successMuted` escuros ≈ 1.9:1 / 2.1:1.
3. **task-065 (P1):** hex hardcoded `#991b1b`, `#166534`, `#fca5a5` fora de token.
4. **WS1 (P2):** selects/inputs nativos sem tokenização — brancos no tema dark.
5. **Modal ad-hoc (P2):** overlay manual com TODO-WS1 em vez do Modal do kit (ADR-0023) — tem backdrop e fundo opaco (sem defeito 066), mas foge do padrão; sem focus-trap/ESC.
6. **Hover ausente (P2)** em chips e linhas clicáveis.
7. **Copy técnica (P2):** chaves cruas do backend (`no_helmet`, `fuel_nozzle`, `epi`) como labels — CountingPage já tem mapa pt-BR (`CLASS_LABELS`), inconsistente entre telas.
8. **Contraste light (P2):** texto do banner de erro `#ef4444` sobre `dangerMuted` claro = 3.04:1.
9. **Empty/erro sem ação (P3):** vazio não convida a agir; erros não dizem como resolver (sem botão "Tentar novamente").
10. **Escala (P3):** radius 12px (chips) e 8px (cards) fora da escala 4/6/10/16; paddings 3/6px fora da escala 4/8.

---

## Findings (develop — 2026-07-07)

### Alterações visíveis no develop (WS4 investigation rewrite)

`dark-empty-ws4-envelope.png` e `dark-default.png` revelam refatoração significativa dos filtros:

- **Novo filtro "Câmeras"**: select `Todas as câmeras` adicionado ao card Filtros (entre Módulo e De)
- **Info icons (ⓘ)**: adicionados a todos os labels de filtro (Classe de detecção, Módulo, Câmeras, De, Até, Confiança mín., Agrupamento)
- **Confiança mín.**: unidade mudou de `0.0–1.0` para `%` com placeholder `ex.: 70` (escala 0–100)
- **Banner de erro**: agora tem botão `✕` para fechar (era sem opção de dismiss no baseline)
- **Selects/inputs**: aparecem com background escuro no dark theme (`dark-default.png`) — sugere tokenização parcial pelo WS4/WS1

### Tabela de findings

| # | Sev | Tema | Status develop | Descrição |
|---|-----|------|---------------|-----------|
| 1 | P1 | both | **PERSISTS** | BUG WS4: envelope divergente — `{status:'success',data}` vs `{success,data}` → "Erro ao buscar eventos" com HTTP 200. Confirmado em `dark-empty-ws4-envelope.png` |
| 2 | P1 | dark | **PERSISTS** | Chips de violação `#991b1b`/`#166534` hardcoded ≈ 1.9:1/2.1:1 — confirmado em `dark-default.png` (chips vermelhos/verdes quase ilegíveis no dark) |
| 3 | P1 | both | **PERSISTS** | task-065: hex hardcoded `#991b1b`, `#166534`, `#fca5a5` não removidos |
| 4 | P2 | dark | ~~Selects/inputs nativos sem tokenização — brancos no dark~~ **(PARCIALMENTE RESOLVIDO — WS4/WS1)** | Screenshots mostram selects com bg escuro no dark; inputs datetime pré-populados com data visível — tokenização aparente, mas deve ser verificada em build local |
| 5 | P2 | both | **PERSISTS** | Modal de frame ad-hoc (TODO-WS1); sem focus-trap/ESC |
| 6 | P2 | both | **PERSISTS** | Hover ausente em chips de classe e linhas de evento |
| 7 | P2 | both | **PERSISTS** | Copy técnica: chips exibem chaves cruas do backend (`no_helmet`, `fuel_nozzle`, `epi`, `fueling`) |
| 8 | P2 | light | **PERSISTS** | Banner de erro: `#ef4444` sobre `dangerMuted` claro = 3.04:1 |
| 9 | P3 | both | **PERSISTS** | Empty/erro sem botão de ação; erros não sugerem resolução |
| 10 | P3 | both | **PERSISTS** | Radius 12px (chips) e 8px (cards) fora da escala 4/6/10/16 |
| 11 | P2 | both | **NEW** | Novo filtro "Câmeras" usa select nativo sem `aria-label` explícito; info icons (ⓘ) sem texto alternativo acessível (WCAG 1.3.1) |
| 12 | P3 | both | **NEW** | Confiança mín. mudou de escala (0–1 → 0–100%) sem atualização do placeholder `0.0 – 1.0` na spec; validação de range no frontend precisa de verificação |
| 13 | P2 | both | **NEW (positivo)** | Banner de erro agora tem `✕` para fechar — melhora UX mas o BUG WS4 subjacente persiste; fechar o banner faz UI parecer saudável sem ser |
