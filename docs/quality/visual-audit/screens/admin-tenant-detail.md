# Detalhe do Tenant — spec visual

**Rota:** `/admin/tenants/:id` (ex.: `/admin/tenants/t-0001`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminTenantDetailPage.tsx` (inclui subcomponentes `Row`, `UsersTab`, `ModulesTab`, `TenantFlagsTab`, `PlanHistoryTab`) · `admin.css.ts` · `WorkerStatusBadge.tsx` · `UserRoleBadge.tsx` · endpoints: GET `/api/v1/admin/tenants/:id`, GET `/api/v1/admin/feature-flags/tenant/:id`, GET `/api/v1/admin/tenants/:id/plan-history`, POST suspend/reactivate, `createUser`, `updateTenant`
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default (Visão Geral) | `../screenshots/admin-tenant-detail/dark-default.png` | `../screenshots/admin-tenant-detail/light-default.png` |
| empty (tenant novo) | `../screenshots/admin-tenant-detail/dark-empty.png` | `../screenshots/admin-tenant-detail/light-empty.png` |
| loading | `../screenshots/admin-tenant-detail/dark-loading.png` | `../screenshots/admin-tenant-detail/light-loading.png` |
| error | `../screenshots/admin-tenant-detail/dark-error.png` | `../screenshots/admin-tenant-detail/light-error.png` |
| tab Usuários | `../screenshots/admin-tenant-detail/dark-tab-users.png` | `../screenshots/admin-tenant-detail/light-tab-users.png` |
| form Adicionar usuário | `../screenshots/admin-tenant-detail/dark-modal-add-user.png` | `../screenshots/admin-tenant-detail/light-modal-add-user.png` |
| tab Worker | `../screenshots/admin-tenant-detail/dark-tab-worker.png` | `../screenshots/admin-tenant-detail/light-tab-worker.png` |
| tab Módulos | `../screenshots/admin-tenant-detail/dark-tab-modules.png` | `../screenshots/admin-tenant-detail/light-tab-modules.png` |
| tab Feature Flags | `../screenshots/admin-tenant-detail/dark-tab-flags.png` | `../screenshots/admin-tenant-detail/light-tab-flags.png` |
| tab Histórico de Plano | `../screenshots/admin-tenant-detail/dark-tab-history.png` | `../screenshots/admin-tenant-detail/light-tab-history.png` |
| hover Suspender | `../screenshots/admin-tenant-detail/dark-hover-suspender.png` | — (só dark) |

## Layout — regiões

- Shell + sidebar admin idênticos ao grupo.
- `pageRoot` (padding 32, maxWidth 1200):
  - Header: `btnGhost` "← Tenants" (marginBottom 8) acima do `pageTitle` (nome do tenant); `pageSubtitle` = `mono` slug + ` · ` + `planBadge[plan]` + ` · ` + `WorkerStatusBadge` (condicional — separador `·` SEMPRE renderiza, fica pendurado quando não há worker). À direita: `btnDanger` "Suspender" (Ban 14) ou `btnSuccess` "Reativar" (RefreshCw 14).
  - Banner `alertBanner.danger` "Tenant suspenso" quando `!is_active`.
  - **Barra de tabs**: flex gap 0, `borderBottom: 1px solid var(--border-subtle)` — **var inexistente** (o token real é `--color-border-subtle`), a linha nunca renderiza. Tab: botão 8px 16px, 13px, sem bg/borda; ativa = 600 + `borderBottom 2px solid vars.color.primary` + cor `primary`; inativa = 400, cor `inherit`.
  - Conteúdo por tab; Visão Geral usa `twoColumn` (1fr 1fr, gap 24).
- `Row` (linhas label/valor): flex, padding `6px 0`, `borderBottom: 1px solid rgba(0,0,0,.05)` — **invisível no dark** (razão 1.01 sobre #111318); label `muted` width 140.

## Árvore de componentes

```
AdminTenantDetailPage (pageRoot)
├── pageHeader: btnGhost "← Tenants" | pageTitle | pageSubtitle (mono slug · planBadge · WorkerStatusBadge)
│   └── btnDanger "Suspender" | btnSuccess "Reativar" (disabled busy)
├── [suspenso] alertBanner.danger "Tenant suspenso"
├── tabs: Visão Geral | Usuários | Worker | Módulos | Feature Flags | Histórico de Plano
├── tab Visão Geral → twoColumn
│   ├── card "INFORMAÇÕES": Row Schema (mono) | Câmeras | Criado em | [Suspenso em] | [Notas internas]
│   └── card "MÓDULOS HABILITADOS": badges `s.badge` com bg rgba(59,130,246,0.1) + color vars.color.primary
├── tab Usuários → UsersTab (card)
│   ├── header flex: cardTitle "Usuários do tenant" + btnPrimary "+ Adicionar usuário"
│   ├── [showAdd] painel bg rgba(0,0,0,.03) radius 8 padding 16
│   │   └── input placeholder "email@empresa.com" | select roles | btnPrimary "Criar"/"Criando..." | btnGhost "Cancelar"
│   └── table: Email | Role (UserRoleBadge) | Último login (muted) | Status (dot only) | Ações (btnDanger "Desativar" / btnSuccess "Reativar" 12px)
├── tab Worker → card "WORKER ON-PREMISE"
│   └── Row Status (WorkerStatusBadge) | GPU "62.4%" | VRAM "9.8 GB" | FPS médio "24.6" | Câmeras ativas 11
│       ou muted "Nenhum worker registrado para este tenant."
├── tab Módulos → ModulesTab (card "MÓDULOS DISPONÍVEIS")
│   ├── muted "Ative ou desative módulos para este tenant. Mudanças entram em vigor imediatamente."
│   └── 6 linhas (epi, counting, quality, basic, analytics, fueling): nome (600 se ativo) | muted "Ativo"/"Inativo" | ToggleRight/ToggleLeft 24 (cor primary/textMuted)
│       borderBottom rgba(0,0,0,.05) por linha
├── tab Feature Flags → card "FEATURE FLAGS DO TENANT" → TenantFlagsTab
│   └── linhas: mono chave | checkbox nativo (update otimista, erro silencioso .catch(() => {}))
└── tab Histórico de Plano → card "HISTÓRICO DE PLANO" → PlanHistoryTab
    └── table: Data (mono) | De | Para | Por (muted email)
```

## Copy exata

- Voltar: `Tenants` · Ações: `Suspender`, `Reativar` · Banner: `Tenant suspenso`
- Tabs: `Visão Geral`, `Usuários`, `Worker`, `Módulos`, `Feature Flags`, `Histórico de Plano`
- Card titles: `Informações`, `Módulos habilitados`, `Usuários do tenant`, `Worker On-Premise`, `Módulos disponíveis`, `Feature Flags do Tenant`, `Histórico de Plano`
- Rows: `Schema`, `Câmeras`, `Criado em`, `Suspenso em`, `Notas internas`, `Status`, `GPU`, `VRAM`, `FPS médio`, `Câmeras ativas`
- Módulos: `Ative ou desative módulos para este tenant. Mudanças entram em vigor imediatamente.` · `Ativo` / `Inativo`
- Vazios: `Nenhum worker registrado para este tenant.` · `Nenhum usuário cadastrado neste tenant.` · `Nenhuma flag configurada para este tenant.` · `Nenhuma mudança de plano registrada.` · Carregando: `Carregando...`
- UsersTab: `+ Adicionar usuário`, placeholder `email@empresa.com`, `Criar`, `Criando...`, `Cancelar`, colunas `Email|Role|Último login|Status|Ações`, `Desativar`/`Reativar`
- Histórico: colunas `Data|De|Para|Por`
- Prompt nativo de suspensão: `Motivo da suspensão:` · alert de usuário criado: `Usuário criado!\nSenha temporária: {senha}` · erro: `Tenant não encontrado`, `Erro ao criar usuário`, `Erro ao carregar flags`, `Erro ao atualizar módulos`, `Erro`

## Dados de exemplo (fixtures)

- Tenant RVB Industrial · `rvb-industrial` · enterprise · On-premise · schema `tenant_rvb` · 12 câmeras · criado 12/11/2025 · notas `Contrato renovado em maio/2026 — POC de contagem agendada para agosto.` · módulos epi/quality/analytics.
- Worker: GPU 62.4% · VRAM 9.8 GB · FPS 24.6 · 11 câmeras ativas (hostname rvb-edge-01).
- Usuários: joana.melo@rvb.ind.br (Admin, 318 logins), carlos.tavares@rvb.ind.br (Operador), ana.beatriz@rvb.ind.br (Analista), ricardo.nunes@rvb.ind.br (Treinador), estagiario.seg@rvb.ind.br (Viewer, inativo).
- Flags: `epi.live_view_substream` ✓, `epi.alert_webhooks` ✓, `reports.auto_export_pdf` ✗, `training.auto_approve` ✗, `quality.pre_annotation_dino` ✓.
- Histórico: 24/06/2026 premium→enterprise (vitor@) · 08/03/2026 standard→premium (vitor@) · 12/11/2025 —→standard (suporte@).
- Empty: `Tenant Novo Cadastro` · `novo-cadastro` · basic · 0 câmeras · sem módulos/worker/usuários (subtítulo exibe `novo-cadastro · basic ·` com `·` final pendurado).

## Estados

- **default:** Visão Geral com 2 cards; separadores de Row **invisíveis no dark**, visíveis no light (rgba preto).
- **empty:** card "Módulos habilitados" completamente vazio (sem mensagem); Informações com 3 rows.
- **loading:** Skeletons (title 260 + 5 rect 90×32 + 6 linhas de texto) — único lugar do grupo além do dashboard com skeleton.
- **error:** banner danger (`Tenant não encontrado` ou msg da API) + toast global sobre a topbar.
- **tab-users + form:** painel de realce rgba(0,0,0,.03) é invisível nos dois temas — inputs parecem soltos no card.
- **hover Suspender:** `opacity .85` no botão vermelho — feedback quase imperceptível.

## Navegação e fluxos

- `← Tenants` → `/admin/tenants`.
- `Suspender` → `prompt()` nativo pedindo motivo → POST suspend → estado local `is_active:false`. `Reativar` → POST reactivate.
- Tabs trocam conteúdo local (sem rota). Flags: cada checkbox dispara PATCH imediato (erro engolido). Módulos: toggle dispara `updateTenant` imediato.
- `+ Adicionar usuário` abre form inline; `Criar` → POST createUser → `alert()` com senha temporária → reload.

## Problemas identificados

1. **`var(--border-subtle)` inexistente** (linha 111) — a borda da barra de tabs nunca renderiza; token correto é `vars.color.borderSubtle`.
2. **Separadores `rgba(0,0,0,.05)`** em Row/ModulesTab/FlagsTab (linhas 191/325/361) — invisíveis no dark (1.01:1), classe task-063.
3. **Badge de módulo** (linha 140): bg hardcoded rgba(59,130,246,.1) azul + texto `primary` ciano — 2.16:1 no light; mistura de matiz azul/ciano.
4. **Realce do form add-user rgba(0,0,0,.03)** (linha 241) — invisível nos dois temas.
5. **Tab ativa ciano** sobre fundo claro = 2.23:1 no white-label claro.
6. Badges de role/plan/worker hardcoded (ver findings de admin.css.ts) — `enterprise` 2.80 dark; `On-premise` 2.23 light.
7. Status de usuário = dot colorido apenas (sem texto) — informação só por cor; dot verde 2.54:1 no light.
8. `prompt()`/`alert()` nativos para suspensão e senha temporária.
9. Separador `·` pendurado no subtítulo quando tenant não tem worker.
10. Card "Módulos habilitados" vazio sem mensagem no estado empty.
11. Flags exibem chaves cruas (`epi.live_view_substream`) com checkbox nativo; falha de update é silenciosa.

## Findings (develop — 2026-07-07)

**Screenshots analisados:** dark-default, light-default, dark-empty, light-empty, dark-error, dark-loading, dark-tab-users, light-tab-users, dark-tab-flags, light-tab-flags, dark-tab-modules, dark-tab-worker, dark-tab-history, dark-modal-add-user, light-modal-add-user, dark-hover-suspender
**Commits relevantes:** d7a3ad3 (WS1), task-063 (tokenização — sem impacto aqui), task-065

### Findings resolvidos

*(nenhum — nenhuma das issues documentadas foi corrigida no develop)*

### Findings que persistem

| ID | Sev | Descrição | Evidência |
|---|---|---|---|
| F1 | P1 | `var(--border-subtle)` inexistente na barra de tabs — borda inferior da barra nunca renderiza | dark-default: linha entre tabs e conteúdo ausente |
| F2 | P1 | Separadores `rgba(0,0,0,.05)` em Row/ModulesTab/FlagsTab — invisíveis no dark (1.01:1) | dark-default — rows de Informações sem separador visível |
| F3 | P1 | Badge de módulo bg hardcoded `rgba(59,130,246,.1)` azul + texto `primary` ciano — 2.16:1 no light | light-default — badges "epi", "quality", "analytics" de baixo contraste |
| F4 | P2 | Realce do form add-user `rgba(0,0,0,.03)` — invisível nos dois temas; inputs parecem soltos | dark-modal-add-user |
| F5 | P1 | Tab ativa (ciano) sobre fundo claro white-label = 2.23:1 | light-default — underline e texto "Visão Geral" em ciano |
| F6 | P1 | Badges de role/plan/worker hardcoded — `enterprise` 2.80:1 dark; `On-premise` 2.23:1 light | dark-default (subtítulo) |
| F7 | P1 | Status de usuário = dot colorido apenas (sem rótulo) — informação só por cor; verde 2.54:1 light | dark-tab-users — coluna Status com dots sem label |
| F8 | P2 | `prompt()`/`alert()` nativos para suspensão e senha temporária | — (fluxo) |
| F9 | P2 | Separador `·` pendurado no subtítulo quando tenant não tem worker (subtítulo termina em `· `) | dark-empty |
| F10 | P2 | Card "Módulos habilitados" completamente vazio no estado empty — sem mensagem | dark-empty |
| F11 | P2 | Feature flags exibem chaves cruas (`epi.live_view_substream`) com checkbox nativo; erros de update silenciosos | dark-tab-flags |

### Findings novos

*(nenhum)*
