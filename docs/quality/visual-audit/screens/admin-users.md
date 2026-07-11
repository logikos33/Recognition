# Usuários (plataforma) — spec visual

**Rota:** `/admin/users`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminUsersPage.tsx` · `admin.css.ts` · `UserRoleBadge.tsx` · endpoints: GET `/api/v1/admin/users?search=&role=&page=` → `{items: AdminUser[], total}`, POST createUser, deactivate/reactivateUser
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-users/dark-default.png` | `../screenshots/admin-users/light-default.png` |
| empty | `../screenshots/admin-users/dark-empty.png` | `../screenshots/admin-users/light-empty.png` |
| loading | `../screenshots/admin-users/dark-loading.png` | `../screenshots/admin-users/light-loading.png` |
| error | `../screenshots/admin-users/dark-error.png` | `../screenshots/admin-users/light-error.png` |
| modal Novo Usuário | `../screenshots/admin-users/dark-modal-novo-usuario.png` | `../screenshots/admin-users/light-modal-novo-usuario.png` |
| hover linha | `../screenshots/admin-users/dark-hover-row.png` | — (só dark) |

## Layout — regiões

- Shell + sidebar admin idênticos ao grupo (item ativo: "Usuários").
- `pageRoot` (padding 32, maxWidth 1200):
  - `pageHeader`: "Usuários" + "{total} usuários cadastrados"; `btnPrimary` "+ Novo Usuário".
  - Barra de filtros (flex, marginBottom 16, **fora de card** — diferente de Tenants que envolve a busca num card): Search 15 + input flex 1 placeholder "Buscar por email..." + select "Todas as roles"/roles cruas.
  - Card da tabela (7 colunas; última sem header, com botão de ação).
  - Paginação (só se `total > 20`): btnGhost "Anterior" | muted "Pág {n}" | btnGhost "Próxima".
- **Modal Novo Usuário (ad-hoc):** mesmo overlay inline `vars.color.overlay` com `TODO-WS1`; card width 420. Sem X/Escape/focus-trap.

## Árvore de componentes

```
AdminUsersPage (pageRoot)
├── pageHeader → pageTitle "Usuários" + pageSubtitle | btnPrimary "+ Novo Usuário"
├── [error] alertBanner.danger
├── flex filtros: (Search + input) | select roleFilter
├── card tabela
│   └── table: th Email|Role|Tenant|Último login|Logins|Status|(vazio)
│       tr.trHover (cursor pointer — SEM onClick!)
│       td: email | UserRoleBadge | muted tenant_name ?? tenant_id.slice(0,8) | muted data pt-BR
│           | login_count | dot healthy/critical (só o dot) | btnGhost 11px "Desativar"/"Reativar"
├── [total>20] paginação
└── [showModal] overlay inline → card 420px
    ├── pageTitle "Novo Usuário"
    ├── muted "Email" + input
    ├── muted "Role" + select (admin|operator|analyst|trainer|viewer — valores crus)
    ├── muted "Tenant ID" + input placeholder "UUID do tenant"
    ├── [error] alertBanner.danger
    └── btnGhost "Cancelar" | btnPrimary "Criar Usuário"/"Criando..." (disabled sem email/tenant_id)
```

## Copy exata

- `Usuários` · `{total} usuários cadastrados` · `+ Novo Usuário`
- Placeholder: `Buscar por email...` · Filtro: `Todas as roles` + `admin/operator/analyst/trainer/viewer` (crus, minúsculos)
- Colunas: `Email`, `Role`, `Tenant`, `Último login`, `Logins`, `Status`, (coluna de ação sem título)
- Badges de role (traduzidas): `Superadmin`, `Admin`, `Operador`, `Analista`, `Treinador`, `Viewer`
- Ações: `Desativar` / `Reativar` · vazio: `Nenhum usuário encontrado` · loading: `Carregando...`
- Paginação: `Anterior`, `Pág {n}`, `Próxima`
- Modal: `Novo Usuário`, `Email`, `Role`, `Tenant ID`, placeholder `UUID do tenant`, `Cancelar`, `Criar Usuário`, `Criando...`
- Confirm nativo: `Desativar {email}?` · alert: `Usuário criado!\nSenha temporária: {senha}` · erros: `Erro ao criar usuário`, `Erro`

## Dados de exemplo (fixtures)

| Email | Role | Tenant | Último login | Logins | Status |
|---|---|---|---|---|---|
| joana.melo@rvb.ind.br | Admin | Tenant RVB Industrial | 06/07/2026 | 318 | ativo |
| pedro.assis@horizontesul.com.br | Admin | Construtora Horizonte Sul | 06/07/2026 | 205 | ativo |
| carlos.tavares@rvb.ind.br | Operador | Tenant RVB Industrial | 06/07/2026 | 512 | ativo |
| seguranca@msc.ind.br | Operador | Metalúrgica São Carlos | 04/07/2026 | 154 | ativo |
| ana.beatriz@rvb.ind.br | Analista | Tenant RVB Industrial | 05/07/2026 | 96 | ativo |
| frota@andradefilhos.com.br | Treinador | Transportadora Andrade & Filhos | 29/06/2026 | 33 | ativo |
| gestor@valeverde.agr.br | Viewer | Agroindústria Vale Verde | 06/06/2026 | 8 | inativo (dot vermelho, botão "Reativar") |

Modal preenchido: email `novo.usuario@horizontesul.com.br`, role `operator`, Tenant ID `t-0002`.

## Estados

- **default:** 7 linhas, roles com badges coloridas, status apenas dot.
- **empty:** header da tabela + `Nenhum usuário encontrado` central; sem CTA. Catch-all `{}` quebra (`r.items` undefined) — fixture explícito `{items:[], total:0}`.
- **loading:** `Carregando...` (muted) no card — sem skeleton.
- **error:** banner danger + toast global sobrepondo a topbar.
- **hover linha:** bgHover; cursor pointer, mas a linha NÃO tem ação (só o botão Desativar/Reativar tem).
- **modal:** overlay 70% preto, card opaco.

## Navegação e fluxos

- `+ Novo Usuário` → modal; `Criar Usuário` → POST → `alert()` com senha temporária → reload.
- `Desativar`/`Reativar` → `confirm()` nativo → POST → reload.
- Busca/filtro role → refetch com `page=1`. Paginação client-side de 20/pg via API.

## Problemas identificados

1. **Linha com `trHover` + cursor pointer sem onClick** — affordance enganosa (em Tenants a linha navega; aqui não).
2. **Status = dot apenas** (sem rótulo) — informação somente por cor; verde #10b981 = 2.54:1 sobre branco (< 3:1 non-text). Inconsistente com Tenants (dot + "Ativo"/"Suspenso").
3. **Modal ad-hoc TODO-WS1** (mesma classe do de Tenants) — fora do padrão do kit.
4. **Campo "Tenant ID" pede UUID cru** com placeholder `UUID do tenant` — deveria ser um seletor de tenant por nome.
5. **Filtro/select de roles com valores crus minúsculos** (`operator`) enquanto as badges traduzem (`Operador`) — vocabulário inconsistente na mesma tela.
6. **btnPrimary/btnSuccess** contraste 2.43/2.54 (ver admin.css.ts).
7. Role badges hardcoded: `Admin` #2563eb 3.01:1 no dark; `Operador` #16a34a 2.89:1 no light.
8. Senha temporária via `alert()`; exclusão lógica via `confirm()` nativo.
9. Empty sem convite à ação; loading sem skeleton (inconsistente com dashboard).

## Findings (develop — 2026-07-07)

**Screenshots analisados:** dark-default, light-default, dark-empty, light-empty, dark-error, dark-loading, dark-modal-novo-usuario, light-modal-novo-usuario, dark-hover-row
**Commits relevantes:** d7a3ad3 (WS1), task-065

### Findings resolvidos

*(nenhum)*

### Findings que persistem

| ID | Sev | Descrição | Evidência |
|---|---|---|---|
| F1 | P2 | Linha com `trHover` + cursor pointer mas sem `onClick` — affordance enganosa (em Tenants a linha navega; aqui não) | dark-default, dark-hover-row |
| F2 | P1 | Status = dot apenas (sem rótulo) — informação somente por cor; verde #10b981 = 2.54:1 sobre branco | dark-default, light-default — coluna Status sem texto |
| F3 | P2 | Modal ad-hoc `TODO-WS1` — sem X/Escape/focus-trap | dark-modal-novo-usuario |
| F4 | P2 | Campo "Tenant ID" pede UUID cru (placeholder `UUID do tenant`) — deveria ser seletor por nome | dark-modal-novo-usuario, light-modal-novo-usuario |
| F5 | P2 | Select de roles com valores crus minúsculos (`operator`) enquanto badges traduzem (`Operador`) — vocabulário inconsistente | dark-modal-novo-usuario — "operator" no select |
| F6 | P1 | `btnPrimary`/`btnSuccess` contraste 2.43/2.54:1 — reprova WCAG AA | dark-default (botão "+ Novo Usuário") |
| F7 | P1 | Role badges hardcoded: `Admin` #2563eb = 3.01:1 dark; `Operador` #16a34a = 2.89:1 light | light-default |
| F8 | P2 | Senha temporária via `alert()` nativo; `confirm()` nativo para desativação | — (fluxo) |
| F9 | P2 | Empty sem convite à ação; loading sem skeleton (inconsistente com dashboard) | dark-empty, dark-loading |

### Findings novos

*(nenhum)*
