# Changelog — spec visual

**Rota:** `/admin/changelog` (dentro do `AdminLayout`, role `superadmin`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminChangelogPage.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` · `adminService.getChangelog({category, importance, affected_area, page, per_page})` → GET `/api/v1/admin/changelog?…` (Paginated: `items/total/page/per_page`) · `createChangelogEntry` → POST `/api/v1/admin/changelog`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (8 entradas) | `../screenshots/admin-changelog/dark-default.png` | `../screenshots/admin-changelog/light-default.png` |
| expanded (descrição aberta) | `../screenshots/admin-changelog/dark-expanded-descricao.png` | `../screenshots/admin-changelog/light-expanded-descricao.png` |
| empty | `../screenshots/admin-changelog/dark-empty.png` | `../screenshots/admin-changelog/light-empty.png` |
| loading | `../screenshots/admin-changelog/dark-loading.png` | `../screenshots/admin-changelog/light-loading.png` |
| error (500) | `../screenshots/admin-changelog/dark-error.png` | `../screenshots/admin-changelog/light-error.png` |
| modal Nova Entrada (preenchido) | `../screenshots/admin-changelog/dark-modal-nova-entrada.png` | `../screenshots/admin-changelog/light-modal-nova-entrada.png` |
| hover linha | `../screenshots/admin-changelog/dark-hover-row.png` | — (só dark) |

## Layout — regiões

- **Shell do app:** topbar global + sidebar admin 220px (item ativo "Changelog", grupo Modelos & Treino) + rodapé de status.
- **Conteúdo** (`pageRoot`): padding 32px, maxWidth 1200px.
  - `pageHeader`: `pageTitle` "Changelog" + `pageSubtitle` "Histórico de mudanças"; à direita `btnPrimary` "[Plus 14] Adicionar entrada".
  - **Barra de filtros** (flex wrap, gap 8, marginBottom 16): select categorias + select importâncias + input "Área afetada..." (Enter aplica) + `btnGhost` "Filtrar". Filtros só aplicam ao clicar Filtrar (inputs pendentes vs aplicados).
  - Card da tabela: `s.card` com `padding: 0; overflow: hidden` (inline).
  - **Paginação** (flex space-between, marginTop 12): `muted` "Mostrando X–Y de Z" + btnGhost "Anterior"/"Próxima" (disabled nos limites).
- **Modal "Nova Entrada":** mesmo padrão ad-hoc do admin-versions — overlay inline `vars.color.overlay` (TODO-WS1), `s.card` width 480, grid 2 colunas para Categoria/Importância.

## Árvore de componentes

```
AdminLayout
└── AdminChangelogPage (pageRoot)
    ├── pageHeader → título/subtítulo + btnPrimary "Adicionar entrada"
    ├── alertBanner.danger (só em erro)
    ├── filtros: select (7 opções) · select (5 opções) · input · btnGhost "Filtrar"
    ├── card (padding 0)
    │   ├── muted "Carregando..." (padding 24)
    │   └── table — 7 colunas: Importância | Categoria | Título | Área | Versão | Data | Por
    │       ├── tr.trHover clicável (toggle descrição) por entrada:
    │       │   ├── td badge importância com IMPORTANCE_STYLE inline:
    │       │   │     critical: rgba(239,68,68,.1)+danger · high: rgba(249,115,22,.1)+#ea580c ·
    │       │   │     normal: rgba(107,114,128,.1)+textSecondary · low: rgba(107,114,128,.05)+textMuted
    │       │   ├── td badge categoria (sem bg — texto puro)
    │       │   ├── td título (textPrimary)
    │       │   ├── td muted área · td mono versão · td muted data dd/mm/aaaa · td muted e-mail
    │       │   └── (expandida) tr extra: td colSpan 7, bg rgba(107,114,128,0.04), muted descrição
    │       └── (vazio) tr única: td colSpan 7 centralizado, muted "Nenhuma entrada encontrada."
    ├── paginação (se total > 0)
    └── modal (showModal): overlay → s.card 480
        ├── pageTitle "Nova Entrada de Changelog"
        ├── "Título *" + input
        ├── grid 1fr 1fr: "Categoria" select + "Importância" select (ambos com "— selecione —")
        ├── "Descrição" + textarea (minHeight 72)
        ├── "Área afetada" + input
        ├── alertBanner.danger (erro de submit)
        └── flex flex-end: btnGhost "Cancelar" + btnPrimary "Salvar" ("Salvando..."; disabled sem título)
```

## Copy exata

- Título: `Changelog` · Subtítulo: `Histórico de mudanças`
- Botões: `Adicionar entrada`, `Filtrar`, `Anterior`, `Próxima`, `Cancelar`, `Salvar` / `Salvando...`
- Filtros: `Todas categorias` + opções `feature|fix|config|security|breaking|infra`; `Todas importâncias` + `critical|high|normal|low`; placeholder `Área afetada...`
- Colunas: `Importância`, `Categoria`, `Título`, `Área`, `Versão`, `Data`, `Por`
- Paginação: `Mostrando {start}–{showing} de {total}` (ex.: `Mostrando 1–8 de 8`)
- Vazio: `Nenhuma entrada encontrada.` · Loading: `Carregando...` · Erro: `Erro interno do servidor` / `Erro ao salvar`
- Modal: `Nova Entrada de Changelog`, `Título *`, `Categoria`, `Importância` (opção vazia `— selecione —`), `Descrição`, `Área afetada`

## Dados de exemplo (fixtures do spec 21-admin-health)

| Importância | Categoria | Título | Área | Versão | Data | Por |
|---|---|---|---|---|---|---|
| critical | fix | Modal de operação com fundo opaco | operations | 2.3.0 | 04/07/2026 | vitor@logikos.com.br |
| high | feature | Substream padrão no live view | live-view | 2.3.0 | 04/07/2026 | vitor@logikos.com.br |
| critical | security | Isolamento de tenant nas queries de validação | backend | 2.3.0 | 03/07/2026 | suporte@logikos.com.br |
| normal | infra | Guard-rail CI contra cores hardcoded | ci | 2.3.0 | 03/07/2026 | vitor@logikos.com.br |
| high | fix | Contraste do painel de vídeo em superfície clara | operations | 2.2.1 | 27/06/2026 | suporte@logikos.com.br |
| low | config | Tuning de latência HLS (playlist 3, segmento 1s) | streaming | 2.2.1 | 26/06/2026 | vitor@logikos.com.br |
| high | breaking | CSS vars planas para white-label de superfícies | frontend | 2.2.0 | 15/06/2026 | vitor@logikos.com.br |
| normal | feature | Módulo Fueling em beta para tenants selecionados | modules | 2.1.0 | 27/05/2026 | vitor@logikos.com.br |

Descrição expandida (linha 1): `Corrige vídeo vazando atrás do modal de operação em tenants white-label com superfícies claras.`
Modal preenchido: título `Reconexão automática do WS Gateway`, categoria `fix`, importância `high`, descrição `Backoff exponencial na reconexão do gateway de WebSocket após perda de heartbeat.`, área `ws-gateway`.

## Estados

- **default:** 8 linhas, filtros visíveis, paginação "Mostrando 1–8 de 8" com ambos os botões disabled.
- **expanded-descricao:** linha clicada ganha uma tr extra com a descrição; bg quase invisível (`rgba(107,114,128,0.04)`), texto `muted`.
- **empty:** header da tabela + "Nenhuma entrada encontrada." — sem CTA nem sugestão de limpar filtros; paginação some.
- **loading:** `Carregando...` com padding 24 dentro do card.
- **error:** banner danger + toast global transparente (ver admin-health); tabela não renderiza.
- **hover linha:** bg `bgHover` — funciona (linha É clicável: expande descrição).
- **modal:** overlay 70% preto (verificado nos dois temas), card opaco.

## Navegação e fluxos

- Linha da tabela → clique alterna a descrição expandida (uma por vez).
- `Adicionar entrada` → modal; `Salvar` faz POST e recarrega; `Cancelar` fecha.
- `Filtrar` (ou Enter no input de área) copia inputs pendentes para os filtros aplicados e volta à página 1.
- `Anterior`/`Próxima` mudam `page` (recarrega via useEffect).
- Modal sem Esc/backdrop-close/focus-trap/`role="dialog"`.

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P1 · contrast (light):** badge `high` `#ea580c` sobre tint laranja = 3.21:1; `critical` `#ef4444` sobre tint = 3.29:1. `btnPrimary` "Adicionar entrada"/"Salvar" branco sobre ciano = 2.43:1 (ambos os temas).
2. **P2 · contrast (dark):** badge `low` `#668096` sobre tint = 4.31:1 (abaixo de 4.5).
3. **P2 · hardcode (task-063/065):** `IMPORTANCE_STYLE` com rgba fixos e literal `'#ea580c'` (deveria ser `vars.color.accent`); bg da linha expandida `rgba(107,114,128,0.04)`.
4. **P2 · inconsistency:** modal ad-hoc (TODO-WS1) fora do kit; badge de categoria sem cor (pill invisível) ao lado de badge de importância colorida; categorias/importâncias como chaves cruas em inglês.
5. **P2 · layout:** linha expandida quase indistinguível da normal (bg alpha 0.04) — hierarquia fraca.
6. **P3 · inconsistency:** lista renderiza fragmento `<>` sem `key` (warning React no console; key está na `<tr>` interna).
7. **P3 · copy:** vazio sem convite à ação (ex.: "Limpar filtros" ou "Adicionar a primeira entrada").

## Findings (develop — 2026-07-07)

| # | Sev | Tema | Componente | Descrição | Status |
|---|-----|------|-----------|-----------|--------|
| F-1 | P1 | light | Badges importância / btnPrimary | "high" #ea580c = 3.21:1; "critical" #ef4444 = 3.29:1 (ambos 11px/600); btnPrimary branco sobre ciano = 2.43:1 | **persists** |
| F-2 | P2 | dark | Badge "low" | textMuted sobre tint escuro = 4.31:1 (abaixo de 4.5:1) | **persists** |
| F-3 | P2 | ambos | IMPORTANCE_STYLE hardcodes | rgba fixos e '#ea580c' literal; bg linha expandida rgba fixo | **persists** |
| F-4 | P2 | ambos | Modal / badges | Modal ad-hoc TODO-WS1; categoria sem cor; chaves cruas inglês | **persists** |
| F-5 | P2 | ambos | Linha expandida | bg rgba(107,114,128,0.04) quase invisível — hierarquia fraca | **persists** |
| F-6 | P3 | ambos | React key | Fragmento `<>` sem key (warning React) | **persists** |
| F-7 | P3 | ambos | Estado vazio | Sem CTA (limpar filtros / primeira entrada) | **persists** |
| N-1 | P1 | light | Subtítulo / células muted | **task-065 regression:** `vars.color.textMuted` = #8a8a93 → ~3.30:1 sobre bgSurface branca. Afeta "Histórico de mudanças" 13px, texto de células (Área, Data, Por) 13px, badge "low" 11px em light (onde antes passava ~4.17:1) — falha WCAG AA 4.5:1. | **new** |

**Resolved:** nenhum nesta passagem.
