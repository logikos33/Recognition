# Audit Log — spec visual

**Rota:** `/admin/audit-log`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminAuditLogPage.tsx` · `apps/frontend/src/modules/admin/components/AuditLogTable.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` · serviço `adminService.getAuditLog/exportAuditLog`
**Screenshots:**

| Estado  | Dark | Light |
|---------|------|-------|
| default | `../screenshots/admin-audit-log/dark-default.png` | `../screenshots/admin-audit-log/light-default.png` |
| empty   | `../screenshots/admin-audit-log/dark-empty.png` | `../screenshots/admin-audit-log/light-empty.png` |

## Layout — regiões

- **Shell AdminLayout** (comum a todo o grupo): topbar (hamburger, "Painel Admin", sino, toggle "Pro", "Auditor Visual" + badge `SUPERADMIN` verde, botão "Sair"), sidebar esquerda ~220px com seções VISÃO GERAL / OPERAÇÃO / MODELOS & TREINO / RELATÓRIOS / ADMINISTRAÇÃO (item ativo: **Compliance**), rodapé de status ("Banco de dados · Redis · câmeras ativas").
- **Conteúdo** (`s.pageRoot`): `padding: 32px` (vars.space.xl), `maxWidth: 1200px`.
- `s.pageHeader`: flex space-between, `marginBottom: 32px` — título à esquerda, botão "Exportar CSV" à direita.
- Barra de filtros: `s.flex` (gap 8px), `marginBottom: 16`, `flexWrap: wrap` — 3 inputs lado a lado.
- Card único (`s.card`: bg `bgSurface`, borda 1px `borderSubtle`, radius 6px, padding 24px) contendo a tabela com `overflowX: auto`.
- Paginação (só se `total > 50`): flex centralizado, `marginTop: 12`.

## Árvore de componentes

- `pageRoot`
  - `pageHeader`
    - `pageTitle` ("Audit Log", 20px/700, textPrimary) + `pageSubtitle` ("{total} registros", 13px, textMuted)
    - `btnGhost` com ícone `Download` 14px — "Exportar CSV" (disabled enquanto exporta)
  - `alertBanner.danger` (condicional, se erro)
  - Filtros: `input` texto (placeholder "Filtrar por ação...") + 2 × `input[type=date]`
  - `card`
    - `AuditLogTable` → `table` (13px) com `thead` (th: 8px 12px, textMuted, border-b borderSubtle) e linhas `trHover` (hover bgHover, cursor pointer)
  - Paginação: `btnGhost` "Anterior" · `muted` "Pág {n}" · `btnGhost` "Próxima"

## Copy exata

- Título: `Audit Log` · Subtítulo: `{total} registros` (fixture: "7 registros")
- Botão export: `Exportar CSV` / durante export: `Exportando...`
- Placeholder filtro: `Filtrar por ação...` (inputs de data usam placeholder nativo do browser `mm/dd/yyyy`)
- Cabeçalhos da tabela: `Quando` · `Ator` · `Tenant` · `Ação` · `Alvo` · `IP`
- Vazio: `Nenhum registro` (linha única centralizada, `muted`)
- Paginação: `Anterior` · `Pág {page}` · `Próxima`
- Fallbacks de célula: `—` (ator sem e-mail, tenant nulo, IP nulo)
- Nome do arquivo exportado: `audit-log-YYYY-MM-DD.csv`

## Dados de exemplo (fixtures do builder)

| Quando | Ator (email / role) | Tenant | Ação | Alvo | IP |
|---|---|---|---|---|---|
| há 18min | vitor@logikos.com.br / superadmin | Agroindústria Vale Verde | `tenant.suspend` | tenant #t-0004aa | 187.55.102.14 |
| há 95min | joana.melo@rvb.ind.br / admin | Tenant RVB Industrial | `camera.create` | camera #cam-7788 | 200.148.33.7 |
| há 230min | suporte@logikos.com.br / superadmin | Construtora Horizonte Sul | `training.approve` | training #job-45f2 | 187.55.102.14 |
| há 410min | vitor@logikos.com.br / superadmin | Metalúrgica São Carlos | `user.force_password_reset` | user #u-30122a | 187.55.102.14 |
| há 760min | pedro.assis@horizontesul.com.br / admin | Construtora Horizonte Sul | `alert_rule.update` | rule #r-9982fe | 177.68.90.201 |
| há 1 dia | — / system | Transportadora Andrade & Filhos | `auth.login_failed_burst` | user | — |
| há 2 dias | vitor@logikos.com.br / superadmin | Tenant RVB Industrial | `tenant.plan_change` | tenant #t-0001bb | 187.55.102.14 |

Datas renderizadas com `toLocaleString('pt-BR')` em `mono` (JetBrains Mono 12px). Ação e IP também em `mono`.

## Estados

- **default**: tabela com 7 linhas; hover de linha muda bg para `bgHover`.
- **empty**: tabela mantém thead; única linha `Nenhum registro` centralizada.
- **carregando**: card mostra apenas `Carregando...` (`muted`).
- **erro**: `alertBanner.danger` acima dos filtros com a mensagem da exceção.
- **exportando**: botão desabilitado (opacity 0.5) com texto "Exportando...".
- Alterar qualquer filtro reseta `page = 1` e refaz a busca.

## Navegação e fluxos

- "Exportar CSV" → `adminService.exportAuditLog({action})` → download de blob (não exercitado no harness).
- Filtro de ação (texto), data inicial, data final → recarregam a listagem (`GET /api/v1/admin/audit-log?...`).
- Paginação só aparece com `total > 50` (50 itens/página).
- Linhas têm `trHover` (cursor pointer) mas **não têm onClick** — o cursor promete navegação que não existe.

## Problemas identificados

1. **P3 copy** — título "Audit Log" em inglês numa UI inteiramente pt-BR (sidebar chama de "Compliance").
2. **P3 a11y-other** — `trHover` aplica `cursor: pointer` em linhas sem ação de clique (affordance falsa). Detalhe no findings JSON.
3. **P3 copy** — inputs `type=date` sem label; placeholder nativo `mm/dd/yyyy` em locale US destoa do pt-BR.
4. Contraste verificado OK nos dois temas (textMuted #668096 sobre card dark = 4.51:1; light usa #6b7280 sobre branco).

## Findings (develop — 2026-07-07)

| # | Sev | Tema | Componente | Descrição | Status |
|---|-----|------|-----------|-----------|--------|
| F-1 | P3 | ambos | Título da página | "Audit Log" em inglês numa UI pt-BR (sidebar chama de "Compliance") | **persists** |
| F-2 | P3 | ambos | Linhas da tabela | `trHover` com `cursor: pointer` sem onClick — affordance falsa de navegação | **persists** |
| F-3 | P3 | ambos | Filtros de data | inputs `type=date` sem label; placeholder nativo `mm/dd/yyyy` (locale US) | **persists** |
| N-1 | P1 | light | Subtítulo / th | **task-065 REGRESSION (contraste era OK no baseline):** `vars.color.textMuted` = #8a8a93 → ~3.30:1 sobre bgSurface branca. Baseline verificava OK com #6b7280 (~4.93:1). Afeta "7 registros" 13px e cabeçalhos th (Quando, Ator, Tenant, Ação, Alvo, IP) — falha WCAG AA 4.5:1. | **new** |

**Resolved:** nenhum nesta passagem.
