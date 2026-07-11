# Tenants (lista) — spec visual

**Rota:** `/admin/tenants`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminTenantsPage.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` · `WorkerStatusBadge.tsx` · service `adminService.getTenants()` (GET `/api/v1/admin/tenants` → `{tenants: Tenant[]}`), `adminService.createTenant()`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-tenants/dark-default.png` | `../screenshots/admin-tenants/light-default.png` |
| empty | `../screenshots/admin-tenants/dark-empty.png` | `../screenshots/admin-tenants/light-empty.png` |
| loading | `../screenshots/admin-tenants/dark-loading.png` | `../screenshots/admin-tenants/light-loading.png` |
| error | `../screenshots/admin-tenants/dark-error.png` | `../screenshots/admin-tenants/light-error.png` |
| modal Novo Tenant | `../screenshots/admin-tenants/dark-modal-novo-tenant.png` | `../screenshots/admin-tenants/light-modal-novo-tenant.png` |
| hover linha | `../screenshots/admin-tenants/dark-hover-row.png` | — (só dark) |

## Layout — regiões

- Shell + sidebar admin idênticos ao admin-dashboard.
- `pageRoot` (padding 32, maxWidth 1200):
  - `pageHeader`: título "Tenants" + subtítulo "{n} clientes cadastrados"; à direita `btnPrimary` "+ Novo Tenant" (bg `primary` ciano, texto `#fff`).
  - Card de busca (`card` + `marginBottom: 16` inline): flex com ícone `Search` 15px + `input` (flex 1) — input: padding 7px 10px, radius 4, borda `borderDefault`, bg `bgElevated`, focus borda `primary`.
  - Card da tabela: `table` 13px, `th` 8px 12px `textMuted`/600, `td` 10px 12px `textPrimary`, borda inferior `borderSubtle`.
- **Modal Novo Tenant (ad-hoc, NÃO é o Modal do kit):** overlay `position:fixed; inset:0; background: vars.color.overlay (rgba(0,0,0,.7)); zIndex:1000`, comentado `TODO-WS1: converter para Modal do kit`. Card central `s.card` width 480, maxHeight 90vh, overflowY auto. Sem X de fechar, sem Escape, sem focus-trap, sem shadow.

## Árvore de componentes

```
AdminTenantsPage (pageRoot)
├── pageHeader → pageTitle "Tenants" + pageSubtitle | btnPrimary "+ Novo Tenant"
├── [error] alertBanner.danger
├── card busca → Search(15) + input placeholder "Buscar por nome ou slug..."
├── card tabela
│   └── table: th Nome|Slug|Plano|Módulos|Worker|Usuários|Status
│       tr.trHover (cursor pointer, hover bgHover) onClick → /admin/tenants/{id}
│       td: <strong>nome</strong> | mono slug | planBadge[plan] | muted módulos.join(', ')
│           | WorkerStatusBadge ou muted '—' | user_count ?? '—' | dot healthy/critical + 'Ativo'/'Suspenso'
└── [showModal] overlay inline → card 480px
    ├── pageTitle "Novo Tenant"
    ├── label muted "Nome da empresa" + input full-width
    ├── label muted "Slug (ex: empresa-abc)" + input (normaliza p/ [a-z0-9-])
    ├── label muted "Plano" + select (basic|standard|premium|enterprise)
    ├── label muted "Módulos habilitados" + 5 checkboxes nativos (epi, counting, quality, basic, analytics)
    ├── [error] alertBanner.danger
    └── flex justify-end: btnGhost "Cancelar" | btnPrimary "Criar Tenant" (disabled sem name/slug; saving → "Criando...")
```

## Copy exata

- `Tenants` · `{n} clientes cadastrados` · `+ Novo Tenant`
- Placeholder busca: `Buscar por nome ou slug...`
- Colunas: `Nome`, `Slug`, `Plano`, `Módulos`, `Worker`, `Usuários`, `Status`
- Status: `Ativo` / `Suspenso` · vazio: `Nenhum tenant encontrado` · loading: `Carregando...`
- Modal: `Novo Tenant`, `Nome da empresa`, `Slug (ex: empresa-abc)`, `Plano`, `Módulos habilitados`, `Cancelar`, `Criar Tenant`, `Criando...`
- Sucesso (alert nativo!): `Tenant criado!\nAdmin: {email}\nSenha temporária: {senha}`
- Erro fallback: `Erro ao criar tenant`

## Dados de exemplo (fixtures)

| Nome | Slug | Plano | Módulos | Worker | Usuários | Status |
|---|---|---|---|---|---|---|
| Tenant RVB Industrial | rvb-industrial | enterprise | epi, quality, analytics | On-premise | 32 | Ativo |
| Construtora Horizonte Sul | horizonte-sul | premium | epi, basic | Railway | 18 | Ativo |
| Metalúrgica São Carlos | metalurgica-sao-carlos | standard | epi | Offline | 9 | Ativo |
| Agroindústria Vale Verde | vale-verde | basic | basic | — | 4 | Suspenso |
| Transportadora Andrade & Filhos | transportadora-andrade | standard | epi, counting | Railway | 12 | Ativo |

Modal preenchido no screenshot: Nome `Frigorífico Boa Vista`, slug `frigorifico-boa-vista`, plano `standard`, módulos `epi`+`basic` marcados.

## Estados

- **default:** 5 linhas; badges de plano (`planBadge`), worker badges, dot verde/vermelho + texto.
- **empty:** cabeçalho de tabela permanece; única linha central `Nenhum tenant encontrado` (muted 12px). Subtítulo mostra `0 clientes cadastrados`. Sem CTA.
- **loading:** texto `Carregando...` (muted) dentro do card — sem skeleton (dashboard usa Skeleton: padrão divergente).
- **error:** banner danger no topo do conteúdo + toast global colidindo com a topbar; tabela vazia embaixo (parece "empty + erro" ao mesmo tempo).
- **hover linha:** `trHover` → bg `bgHover` (visível, sutil), cursor pointer.
- **modal:** overlay 70% preto; conteúdo atrás ainda parcialmente visível; foco inicial não é gerenciado.

## Navegação e fluxos

- Clique na linha → `/admin/tenants/{id}` (detalhe).
- `+ Novo Tenant` → abre modal; `Criar Tenant` → POST, sucesso mostra `alert()` nativo com senha temporária, fecha modal e recarrega lista; `Cancelar` fecha.
- Busca filtra client-side por nome/slug.

## Problemas identificados

1. **Modal ad-hoc com overlay inline** (marcado `TODO-WS1`) em vez do Modal do kit (ADR-0023) — sem X/Escape/focus-trap/shadow (candidato task-066).
2. **planBadge hardcoded**: `enterprise` #b45309 sobre rgba(234,179,8,.15) = **2.80** no dark; `standard` #2563eb = 3.01 dark / 4.35 light — reprova AA (11px).
3. **WorkerStatusBadge** no light: On-premise #10b981 = **2.23**, Railway #ca8a04 = 2.67 — ilegível.
4. **btnPrimary** "+ Novo Tenant"/"Criar Tenant": #fff sobre #06b6d4 = **2.43** (both).
5. Empty sem convite à ação (não referencia o botão "Novo Tenant").
6. Loading "Carregando..." texto simples — inconsistente com skeletons do dashboard.
7. Senha temporária exposta via `alert()` nativo — fora do design system e sem como copiar com segurança.
8. Coluna Módulos exibe chaves (`epi, counting`) e o select de plano valores crus (`basic`...), sem rótulos humanos.
9. Célula "Suspenso" quebra linha (dot e texto em linhas separadas) na densidade default.
10. Checkboxes/select nativos sem estilização do kit dentro do modal.

## Findings (develop — 2026-07-07)

**Screenshots analisados:** dark-default, light-default, dark-empty, light-empty, dark-error, dark-loading, dark-modal-novo-tenant, light-modal-novo-tenant, dark-hover-row
**Commits relevantes:** d7a3ad3 (WS1), task-065 (guard-rail CI hardcodes)

### Findings resolvidos

*(nenhum — modal `TODO-WS1` ainda marcado como pendente; badges hardcoded não corrigidos)*

### Findings que persistem

| ID | Sev | Descrição | Evidência |
|---|---|---|---|
| F1 | P2 | Modal ad-hoc com overlay inline (marcado `TODO-WS1`) — sem X/Escape/focus-trap/shadow | dark-modal-novo-tenant.png |
| F2 | P1 | `planBadge` hardcoded: enterprise 2.80:1 dark; standard 3.01:1 dark — reprovam WCAG AA (11px) | dark-default — badges âmbar/roxo/azul/cinza |
| F3 | P1 | `WorkerStatusBadge` no light: On-premise #10b981 = 2.23:1; Railway #ca8a04 = 2.67:1 | light-default — badges verde e âmbar claramente de baixo contraste |
| F4 | P1 | `btnPrimary` "+ Novo Tenant"/"Criar Tenant": #fff sobre #06b6d4 = 2.43:1 | dark-default, dark-modal |
| F5 | P2 | Empty state sem convite à ação — não referencia o botão "+ Novo Tenant" | dark-empty, light-empty |
| F6 | P2 | Loading "Carregando..." texto simples — inconsistente com skeletons do dashboard | dark-loading |
| F7 | P2 | Senha temporária exposta via `alert()` nativo — fora do design system | — (fluxo de criação) |
| F8 | P2 | Coluna Módulos exibe chaves cruas (`epi, counting`); select de plano usa valores raw (`basic`…) | dark-default — "epi, quality, analytics" visíveis |
| F9 | P2 | Célula "Suspenso" quebra linha (dot na linha acima, texto "Suspenso" na linha abaixo) | dark-default — row Agroindústria Vale Verde |
| F10 | P2 | Checkboxes e select nativos sem estilização do kit no modal | dark-modal-novo-tenant.png |

### Findings novos

*(nenhum)*
