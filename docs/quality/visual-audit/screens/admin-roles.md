# Permissões (roles customizadas) — spec visual

**Rota:** `/admin/roles`
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminRolesPage.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` · `apps/frontend/src/modules/admin/types/admin.ts` (`PERMISSION_GROUPS`, `CustomRole`) · service `adminService.getRoles()/createRole()/updateRole()/deleteRole()` (GET/POST `/api/admin/roles`, PUT/DELETE `/api/admin/roles/{id}` — **SEM prefixo `/v1`**, divergente do resto do adminService)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-roles/dark-default.png` | `../screenshots/admin-roles/light-default.png` |
| empty | `../screenshots/admin-roles/dark-empty.png` | `../screenshots/admin-roles/light-empty.png` |
| loading | `../screenshots/admin-roles/dark-loading.png` | `../screenshots/admin-roles/light-loading.png` |
| error | `../screenshots/admin-roles/dark-error.png` | `../screenshots/admin-roles/light-error.png` |
| modal Nova Role | `../screenshots/admin-roles/dark-modal-nova-role.png` | `../screenshots/admin-roles/light-modal-nova-role.png` |
| modal Editar Role | `../screenshots/admin-roles/dark-modal-editar-role.png` | `../screenshots/admin-roles/light-modal-editar-role.png` |
| hover Nova Role | `../screenshots/admin-roles/dark-hover-nova-role.png` | — (só dark) |
| hover Editar | `../screenshots/admin-roles/dark-hover-editar.png` | — (só dark) |

## Layout — regiões

- Shell AdminLayout: topbar preta (logo, "Painel Admin", sino, toggle "Pro" claro/escuro, "Auditor Visual" + badge verde `SUPERADMIN`, botão "Sair") + sidebar 220px (grupos VISÃO GERAL / OPERAÇÃO / MODELOS & TREINO / RELATÓRIOS / ADMINISTRAÇÃO; "Aprovações" com badge vermelho `3`). Rodapé fixo com status `● Banco de dados · ● Redis · ● câmeras ativas`.
- `pageRoot`: padding `vars.space.xl` (32px), maxWidth 1200.
- `pageHeader` (flex space-between, marginBottom 32): título `pageTitle` 20px/700 "Permissões" + `pageSubtitle` 13px textMuted; à direita `btnPrimary` "+ Nova Role".
- Card único (`s.card`: bg `bgSurface`, borda `borderSubtle`, radius `md` 6px, padding 24) contendo a tabela.
- **Tabela SEM classes do kit**: `<table className={s.table}>` mas `<th>`/`<td>` **sem** `s.th`/`s.td` → cabeçalhos centralizados pelo user-agent, sem padding vertical nem bordas de linha (divergente de admin-feature-flags, que usa as classes).
- **Modal ad-hoc (NÃO é o Modal do kit / ADR-0023):** `overlayStyle` inline — `position:fixed; inset:0; background: vars.color.overlay (rgba(0,0,0,.7)); zIndex:9999`, comentário `TODO-WS1: converter para Modal do kit` (AdminRolesPage.tsx:302). Caixa `s.card` maxWidth 680, maxHeight 90vh, overflowY auto — **rodapé de ações rola junto e fica cortado no viewport 720p**. Sem Escape, sem focus-trap, sem `role="dialog"`.

## Árvore de componentes

```
AdminRolesPage (pageRoot)
├── pageHeader → pageTitle "Permissões" + pageSubtitle "{n} role(s) customizada(s) neste tenant"
│                | btnPrimary [Plus 14] "Nova Role"
├── [err] alertBanner.danger (mensagem da API)
├── card
│   ├── [loading] muted "Carregando..."
│   ├── [empty] bloco centralizado: Shield 36px opacity .25 + "Nenhuma role customizada" (14px/600)
│   │            + muted "Crie roles para atribuir permissões granulares a usuários deste tenant."
│   └── table (th sem classe: Nome | Permissões ativas | Usuários | Criada em | Ações[88px])
│       └── tr por role:
│           ├── td nome (fontWeight 500)
│           ├── td flex wrap gap 4: até 4× PermBadge (badge + bg rgba(59,130,246,.12) inline,
│           │     color vars.color.primary, 11px) + badge "+{n}" cinza (rgba(107,114,128,.1),
│           │     textSecondary) | ou badge "Sem permissões"
│           ├── td CountBadge (badge; >0: rgba(34,197,94,.12)+success | 0: rgba(107,114,128,.12)+textSecondary)
│           ├── td muted data pt-BR
│           └── td flex: btnGhost [Edit2 14] title "Editar" | btnDanger [Trash2 14]
│                 (disabled se user_count>0 — title "Role possui usuários vinculados")
└── [modal.open] RoleModal (overlay inline zIndex 9999)
    └── s.card 680px: pageHeader ("Nova Role"/"Editar Role" + btnGhost [X 16] aria-label "Fechar")
        ├── label "Nome da role" (12px/600 opacity .7) + s.input full-width placeholder "Ex.: Operador de câmeras"
        ├── cardTitle "PERMISSÕES"
        ├── grid 2 colunas gap 12: 7 s.card aninhados (padding 10px 12px) por grupo de PERMISSION_GROUPS
        │     título 11px/700 uppercase opacity .6 + checkboxes nativos com chave técnica 12px
        ├── [err] alertBanner.danger
        └── flex justify-end gap 8: btnGhost "Cancelar" | btnPrimary "Salvar"/"Salvando..."
```

## Copy exata

- Header: `Permissões` · `{n} role(s) customizada(s) neste tenant` · `Nova Role`
- Colunas: `Nome`, `Permissões ativas`, `Usuários`, `Criada em`, `Ações`
- Badges: chaves técnicas (`cameras:read`, `alerts:export`…), `+{n}`, `Sem permissões`
- Empty: `Nenhuma role customizada` / `Crie roles para atribuir permissões granulares a usuários deste tenant.`
- Loading: `Carregando...`
- Tooltips: `Editar` · `Deletar` · `Role possui usuários vinculados`
- Delete (nativos!): `alert()` — `A role "{nome}" possui {n} usuário(s) vinculado(s).\nRemova a role de todos os usuários antes de deletar.` · `confirm()` — `Deletar a role "{nome}"? Esta ação não pode ser desfeita.` · fallback `Erro ao deletar`
- Modal: `Nova Role` / `Editar Role` · `Nome da role` · placeholder `Ex.: Operador de câmeras` · `Permissões` · grupos: `Câmeras`, `Alertas`, `Treinamento`, `Relatórios`, `Administração`, `Contagem`, `Verificação` · `Cancelar` · `Salvar` / `Salvando...` · validação `Nome é obrigatório` · fallback `Erro ao salvar`
- Erro de load (fixture): `Falha ao carregar roles do tenant` · fallback `Erro ao carregar roles`

## Dados de exemplo (fixtures)

| Nome | Permissões ativas | Usuários | Criada em |
|---|---|---|---|
| Supervisor de Segurança | cameras:read, alerts:read, alerts:export, reports:read **+2** (reports:export, training:approve) | 4 | 14/03/2026 |
| Operador de Câmeras | cameras:read, cameras:write, alerts:read | 7 | 01/02/2026 |
| Analista de Alertas | alerts:read, alerts:export, reports:read | 3 | 22/04/2026 |
| Gestor de Treinamento | training:read, training:write, training:approve | 2 | 05/05/2026 |
| Auditor Externo | reports:read | 0 | 18/06/2026 |
| Recepção Portaria | *Sem permissões* | 0 | 30/06/2026 |

Permissões por grupo (modal): Câmeras `cameras:read|write|delete` · Alertas `alerts:read|export` · Treinamento `training:read|write|approve` · Relatórios `reports:read|export` · Administração `admin:users|roles|settings` · Contagem `counting:read|write` · Verificação `verification:read|write`.

## Estados

- **default:** 6 linhas; delete habilitado (vermelho pleno) só para Auditor Externo e Recepção Portaria (user_count 0); demais com `:disabled` opacity .5.
- **empty:** ícone Shield + título + subtexto dentro do card; botão "Nova Role" permanece no header (empty razoável, com direção).
- **loading:** apenas `Carregando...` muted no card — sem skeleton (divergente do admin-dashboard).
- **error:** banner danger **e** empty state "Nenhuma role customizada" simultâneos (confuso: parece vazio legítimo). No dark-error.png a topbar apresenta texto sobreposto (artefato de toast global colidindo com o header).
- **hover:** `btnPrimary`/`btnGhost` → opacity .85 (sutil); linhas da tabela sem hover (não têm `trHover` — mas também não são clicáveis).
- **modal:** backdrop 70% preto (verificado por pixel: `#49494a` sobre light, opaco e visível nos dois temas); caixa opaca (`bgSurface`). Editar Role abre com checkboxes pré-marcados da role.

## Navegação e fluxos

- `Nova Role` → RoleModal vazio; `Salvar` → POST `/api/admin/roles` → fecha + recarrega lista.
- Lápis (Editar) → RoleModal preenchido; `Salvar` → PUT `/api/admin/roles/{id}`.
- Lixeira → `confirm()` nativo → DELETE; bloqueada com `alert()` se houver usuários vinculados.
- `X`/`Cancelar` fecham o modal (sem Escape/click-fora).

## Problemas identificados

1. **P1 contraste (light):** PermBadge `#06b6d4` sobre `rgba(59,130,246,.12)`→`#e7f0fe` = **2.11:1**; CountBadge `#10b981` sobre `#e4f8ec` = **2.29:1** — ilegíveis sob white-label claro (classe task-063).
2. **P1 contraste (ambos):** `btnPrimary` `#fff` sobre `#06b6d4` = **2.43:1** (13px/600 não é "texto grande").
3. **P2 hardcode:** `rgba(59,130,246,.12)`, `rgba(34,197,94,.12)`, `rgba(107,114,128,.1/.12)` inline no TSX (task-063/065 — alvo do guard-rail CI).
4. **P2 inconsistência:** `<th>`/`<td>` sem `s.th`/`s.td` → cabeçalho centralizado, linhas sem borda/padding — única tabela admin fora do padrão.
5. **P2 layout:** modal 90vh com footer rolável — botões Cancelar/Salvar cortados no fold em 720p; modal ad-hoc fora do ADR-0023 (sem Escape/focus-trap/dialog role); zIndex 9999 ≠ 1000 do modal de Plans.
6. **P2 copy:** checkboxes e badges expõem chaves técnicas de backend (`cameras:read`) em vez de nomes humanos; delete usa `alert()`/`confirm()` nativos.
7. **P2 API:** endpoints de roles sem prefixo `/v1` (adminService.ts:317-328) — divergente de todo o resto do serviço.
8. **P3:** estado error mantém o empty state visível junto do banner (ambíguo).

## Findings (develop — 2026-07-07)

**Screenshots analisados:** dark-default, light-default, dark-empty, light-empty, dark-error, dark-loading, dark-modal-nova-role, light-modal-nova-role, dark-modal-editar-role, light-modal-editar-role, dark-hover-nova-role, dark-hover-editar
**Commits relevantes:** d7a3ad3 (WS1), task-065 (guard-rail CI hardcodes)

### Findings resolvidos

*(nenhum — task-065 é guard-rail CI, não corrige hardcodes existentes)*

### Findings que persistem

| ID | Sev | Descrição | Evidência |
|---|---|---|---|
| F1 | P1 | PermBadge: `#06b6d4` sobre `rgba(59,130,246,.12)` → #e7f0fe = 2.11:1 no light; CountBadge `#10b981` = 2.29:1 | light-default — badges "cameras:read", "alerts:read" etc. |
| F2 | P1 | `btnPrimary` "Nova Role"/"Salvar": #fff sobre #06b6d4 = 2.43:1 | dark-default, dark-modal-nova-role |
| F3 | P2 | Hardcodes inline: `rgba(59,130,246,.12)`, `rgba(34,197,94,.12)`, `rgba(107,114,128,.1/.12)` no TSX | confirmado por code review (task-065 alvo) |
| F4 | P2 | `<th>`/`<td>` sem `s.th`/`s.td` → cabeçalhos centralizados pelo user-agent; linhas sem borda/padding | dark-default — "Nome", "Usuários", "Criada em" centralizados; "Permissões ativas" alinhado diferente |
| F5 | P2 | Modal 90vh com rodapé rolável em 720p; modal ad-hoc fora do ADR-0023 (sem Escape/focus-trap); zIndex 9999 ≠ 1000 de Plans | dark-modal-nova-role |
| F6 | P2 | Checkboxes e badges expõem chaves técnicas (`cameras:read`) em vez de nomes humanos; delete usa `alert()`/`confirm()` nativos | dark-modal-nova-role — "cameras:read", "training:approve" etc. |
| F7 | P2 | Endpoints de roles sem prefixo `/v1` (adminService.ts:317-328) — divergente do resto do serviço | código |
| F8 | P3 | Estado error mantém o empty state visível junto do banner (ambíguo) | dark-error |

### Findings novos

*(nenhum)*
