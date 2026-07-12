# Versões do Sistema — spec visual

**Rota:** `/admin/versions` (dentro do `AdminLayout`, role `superadmin`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminVersionsPage.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` · `adminService.getVersions()` → GET `/api/v1/admin/versions` · `createVersion` → POST `/api/v1/admin/versions` · `rollbackVersion(id)` → POST rollback
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (6 versões) | `../screenshots/admin-versions/dark-default.png` | `../screenshots/admin-versions/light-default.png` |
| expanded (detalhes v2.3.0) | `../screenshots/admin-versions/dark-expanded-detalhes.png` | `../screenshots/admin-versions/light-expanded-detalhes.png` |
| empty | `../screenshots/admin-versions/dark-empty.png` | `../screenshots/admin-versions/light-empty.png` |
| loading | `../screenshots/admin-versions/dark-loading.png` | `../screenshots/admin-versions/light-loading.png` |
| error (500) | `../screenshots/admin-versions/dark-error.png` | `../screenshots/admin-versions/light-error.png` |
| modal Nova Versão (preenchido) | `../screenshots/admin-versions/dark-modal-nova-versao.png` | `../screenshots/admin-versions/light-modal-nova-versao.png` |
| hover Rollback | `../screenshots/admin-versions/dark-hover-rollback.png` | — (só dark) |

## Layout — regiões

- **Shell do app:** topbar global + sidebar admin 220px (item ativo "Registry", grupo Modelos & Treino) + rodapé de status.
- **Conteúdo** (`pageRoot`): padding 32px, maxWidth 1200px.
  - `pageHeader`: `pageTitle` "Versões do Sistema" + `pageSubtitle` "Checkpoints de configuração"; à direita `btnPrimary` "[Tag 14] Nova Versão" (bg `primary` ciano, texto `#fff`).
  - Lista vertical de cards (flex column, `gap: 12` inline).
- **Card de versão** (`card`): `bgSurface`, borda `borderSubtle`, radius 6, padding 24.
  - Linha 1 (flex space-between, wrap, gap 8): esquerda = badge de versão + (se atual) dot verde + "Atual" + título 700; direita = badge "N entradas" + `btnGhost` "Detalhes" + `btnDanger` "Rollback" (condicional).
  - Linha 2 (flex, gap 16, marginTop 8): data/hora `muted` · e-mail do autor `muted` · (se revertida) texto em `danger` 12px.
  - Painel expandido: `marginTop 16`, `borderTop: 1px solid rgba(107,114,128,0.2)` (hardcoded), `paddingTop 16` — descrição `muted` + tabela do changelog embutido.
- **Modal "Nova Versão":** overlay inline `position: fixed; inset: 0; background: vars.color.overlay` (rgba(0,0,0,.7), com comentário `TODO-WS1: converter para Modal do kit`), flex center, zIndex 1000. Card interno = `s.card` width 480 (opaco nos dois temas — verificado). Campos com label `muted` (marginBottom 4) e `input`/`select` full-width (bg `bgElevated`, borda `borderDefault`, radius 4, focus borda `primary`).

## Árvore de componentes

```
AdminLayout
└── AdminVersionsPage (pageRoot)
    ├── pageHeader → título/subtítulo + btnPrimary "Nova Versão"
    ├── alertBanner.danger (só em erro)
    ├── muted "Carregando..." (loading)
    ├── coluna gap 12 — card por versão:
    │   ├── badge versão "v{X.Y.Z}" com VERSION_TYPE_STYLE inline:
    │   │     major: bg rgba(239,68,68,.1) + danger · minor: bg rgba(59,130,246,.1) + primary · patch: bg rgba(107,114,128,.1) + textSecondary
    │   ├── (is_current) dot.healthy 8px + muted "Atual"
    │   ├── título (700)
    │   ├── badge "N entradas" (sem bg — texto puro 11px/600)
    │   ├── btnGhost "[Chevron] Detalhes" (toggle expandir)
    │   ├── btnDanger "[RotateCcw] Rollback" (se !is_current && !rolled_back_at; "Restaurando..." durante ação)
    │   ├── muted data "dd/mm/aaaa, hh:mm" · muted e-mail · danger 12px "Revertida em {data} por {email}"
    │   └── painel expandido: descrição muted + table (th Importância|Categoria|Título|Área)
    │         td: badge sem cor {importance} | badge sem cor {category} | título | muted área
    │         (sem changelog) muted "Nenhuma entrada de changelog vinculada."
    └── modal (showModal): overlay → s.card 480
        ├── pageTitle "Nova Versão"
        ├── label muted "Versão" + input placeholder "1.2.0"
        ├── label "Tipo" + select [major|minor|patch]
        ├── label "Título" + input
        ├── label "Descrição (opcional)" + textarea (minHeight 72, resize vertical)
        ├── alertBanner.danger (erro de submit)
        └── flex flex-end: btnGhost "Cancelar" + btnPrimary "Criar Versão" ("Criando..." ao salvar; disabled sem versão/título)
```

## Copy exata

- Título: `Versões do Sistema` · Subtítulo: `Checkpoints de configuração`
- Botões: `Nova Versão`, `Detalhes`, `Rollback` / `Restaurando...`, `Cancelar`, `Criar Versão` / `Criando...`
- Badge atual: `Atual` · Badge contagem: `{N} entradas`
- Meta de reversão: `Revertida em {dd/mm/aaaa} por {email}`
- Confirm nativo do rollback: `Restaurar configuração para versão {X.Y.Z}? Esta ação modifica módulos e planos de todos os tenants.`
- Tabela expandida: `Importância`, `Categoria`, `Título`, `Área` · vazio: `Nenhuma entrada de changelog vinculada.`
- Modal: `Nova Versão`, `Versão` (placeholder `1.2.0`), `Tipo` (opções `major`/`minor`/`patch` cruas), `Título`, `Descrição (opcional)`
- Loading: `Carregando...` · Erro: `Erro interno do servidor` / `Erro ao fazer rollback` / `Erro ao criar versão`
- **Não há copy de vazio** — lista vazia renderiza página em branco.

## Dados de exemplo (fixtures do spec 21-admin-health)

- `v2.3.0` minor · **Atual** · "Live view com substream padrão" · 4 entradas · 04/07/2026, vitor@logikos.com.br · descrição "Substream ativado por padrão em todas as câmeras, redução de 40% no consumo de banda do live view." · changelog embutido: high/feature "Substream padrão no live view" (live-view) · critical/fix "Modal de operação com fundo opaco" (operations) · normal/infra "Guard-rail CI contra cores hardcoded" (ci) · low/config "Tuning de latência HLS (playlist 3)" (streaming)
- `v2.2.1` patch · "Correções no painel de operação" · 2 entradas · suporte@logikos.com.br · Rollback visível
- `v2.2.0` minor · "White-label de superfícies (WS1)" · 3 entradas · **Revertida em 18/06/2026 por vitor@logikos.com.br** (sem botão Rollback)
- `v2.1.0` minor · "Módulo Fueling em beta" · 5 entradas · Rollback visível
- `v2.0.0` major · "Recognition V2 — arquitetura multi-tenant" · 12 entradas · Rollback visível
- `v1.9.4` patch · "Hotfix reconexão HLS" · 1 entrada
- Modal preenchido: versão `2.4.0`, tipo `minor`, título `Estabilidade do streaming em escala`, descrição `Consolida lifecycle do live view, substream padrão e redução de footprint de recursos.`

## Estados

- **default:** 6 cards colapsados; Rollback só em versões não-atuais e não revertidas.
- **expanded-detalhes:** card v2.3.0 com chevron para baixo, descrição e tabela de 4 entradas de changelog; borda separadora cinza hardcoded.
- **empty:** **nada é renderizado** além do header — sem mensagem, sem CTA (`versions.map` sobre lista vazia).
- **loading:** `Carregando...` muted.
- **error:** banner danger + toast global transparente (ver admin-health).
- **modal-nova-versao:** overlay escurece o fundo (verificado por pixel nos dois temas: fundo ~70% mais escuro), card opaco; "Criar Versão" habilita com versão+título.
- **hover Rollback:** `btnDanger` muda para `opacity: 0.85` (perceptível por ser bg sólido, mas sutil).

## Navegação e fluxos

- `Nova Versão` → abre modal (form zerado). `Cancelar` fecha sem limpar erro. `Criar Versão` → POST → fecha, recarrega lista.
- `Detalhes` → expande/colapsa inline (um por vez — `expandedId`).
- `Rollback` → `window.confirm` NATIVO → POST rollback → recarrega. Sem modal do kit.
- Modal não fecha por Esc nem clique no backdrop; sem focus-trap; sem `role="dialog"`.

## Problemas identificados (resumo — detalhe no findings JSON)

1. **P1 · contrast (both):** `btnPrimary` branco sobre `#06b6d4` = 2.43:1 ("Nova Versão", "Criar Versão"). `btnDanger` branco sobre `#ef4444` = 3.76:1 ("Rollback").
2. **P1 · contrast (light):** badge de versão minor `#06b6d4` sobre tint azul = **2.16:1** (v2.3.0/v2.2.0/v2.1.0 quase ilegíveis); major `#ef4444` = 3.29:1. Texto "Revertida em..." `#ef4444` 12px sobre branco = 3.76:1.
3. **P2 · hardcode (task-063/065):** `VERSION_TYPE_STYLE` com `rgba(239,68,68,0.1)`, `rgba(59,130,246,0.1)` (azul que não é o primary ciano!), `rgba(107,114,128,0.1)`; borda do painel expandido `rgba(107,114,128,0.2)`.
4. **P2 · inconsistency:** modal ad-hoc com overlay inline (TODO-WS1) em vez do Modal do kit (ADR-0023); rollback via `window.confirm` nativo; badges de importância/categoria na tabela expandida sem variante de cor (pill invisível).
5. **P2 · layout/empty:** estado vazio não renderiza nada — beco sem saída.
6. **P2 · a11y-other:** modal sem `role="dialog"`, sem focus-trap, sem fechar por Esc/backdrop.
7. **P2 · copy:** tipos `major`/`minor`/`patch` e importâncias exibidos como chaves cruas.

## Findings (develop — 2026-07-07)

| # | Sev | Tema | Componente | Descrição | Status |
|---|-----|------|-----------|-----------|--------|
| F-1 | P1 | ambos | btnPrimary / btnDanger | #fff sobre #06b6d4 = 2.43:1; #fff sobre #ef4444 = 3.76:1 — confirmados em dark/light-default.png | **persists** |
| F-2 | P1 | light | Badges de versão | minor ciano 2.16:1; major danger 3.29:1; "Revertida em..." 12px = 3.76:1 — confirmados em light-default.png | **persists** |
| F-3 | P2 | ambos | VERSION_TYPE_STYLE | rgba hardcodes (azul blue-500 em vez de primary ciano; gray); borda expandida rgba fixo | **persists** |
| F-4 | P2 | ambos | Modal / Rollback | Modal ad-hoc TODO-WS1; rollback via window.confirm nativo; badges expandidos sem cor | **persists** |
| F-5 | P2 | ambos | Estado vazio | Página em branco sem mensagem nem CTA — confirmado em dark/light-empty.png | **persists** |
| F-6 | P2 | ambos | Modal a11y | Sem role="dialog", focus-trap, Esc/backdrop close | **persists** |
| F-7 | P2 | ambos | Copy | Tipos e importâncias em chaves cruas inglês | **persists** |
| N-1 | P1 | light | Subtítulo / meta text | **task-065 regression:** `vars.color.textMuted` = #8a8a93 → ~3.30:1 sobre bgSurface branca. Afeta "Checkpoints de configuração" 13px, data/hora muted 13px, e-mail muted 13px e badge "N entradas" 11px/600 — todos falham WCAG AA 4.5:1. | **new** |

**Resolved:** nenhum nesta passagem.
