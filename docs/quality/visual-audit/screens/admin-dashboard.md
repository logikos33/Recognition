# Dashboard Admin — spec visual

**Rota:** `/admin` (index do `AdminLayout`, role `superadmin`)
**Fontes:** `apps/frontend/src/modules/admin/pages/AdminDashboard.tsx` · `apps/frontend/src/modules/admin/components/admin.css.ts` · `apps/frontend/src/modules/admin/components/MetricCard.tsx` · `apps/frontend/src/modules/admin/components/WorkerStatusBadge.tsx` · `apps/frontend/src/modules/admin/AdminLayout.tsx` + `AdminLayout.css.ts` · hook `useAdminDashboard` (GET `/api/v1/admin/dashboard`)
**Screenshots:**

| Estado | Dark | Light |
|---|---|---|
| default | `../screenshots/admin-dashboard/dark-default.png` | `../screenshots/admin-dashboard/light-default.png` |
| empty | `../screenshots/admin-dashboard/dark-empty.png` | `../screenshots/admin-dashboard/light-empty.png` |
| loading | `../screenshots/admin-dashboard/dark-loading.png` | `../screenshots/admin-dashboard/light-loading.png` |
| error | `../screenshots/admin-dashboard/dark-error.png` | `../screenshots/admin-dashboard/light-error.png` |
| hover "Ver workers" | `../screenshots/admin-dashboard/dark-hover-ver-workers.png` | — (só dark) |

## Layout — regiões

- **Shell do app (fora da página):** topbar global (hambúrguer, logo, breadcrumb "Painel Admin / Painel Admin", sino, toggle "Pro", "Auditor Visual", badge `SUPERADMIN` verde, botão "Sair") + rodapé de status ("● Banco de dados · ● Redis · ● câmeras ativas").
- **Sidebar admin** (`AdminLayout.css.ts#sidebar`): 220px fixos, sticky, `bgSurface`, borda direita `borderSubtle`. Header com "Painel Admin" (13px/700) e "Logikos · Recognition" (11px, `textMuted`). Grupos de nav com label uppercase 10px/600 `textMuted` letterSpacing .08em: **Visão Geral** (Dashboard), **Operação** (Monitoramento, Câmeras, Alertas), **Modelos & Treino** (Aprovações [badge vermelho `3`], Registry, Changelog, Console de Teste), **Relatórios** (Compliance, Comunicados, Integrações), **Administração** (Tenants, Usuários, Permissões, Roles, Planos, Retenção, White-label, Vídeos Demo), **Saúde** (Workers, Tickets [badge], Inventário, Health). Item: 13px/500 `textSecondary`, hover `textPrimary`+`bgHover`, ativo `bgElevated`+`textPrimary`/600. Footer: "← Voltar ao sistema" (12px `textMuted`). Badge de nav: `danger` bg, texto `#fff` 10px/700, pill.
- **Conteúdo** (`admin.css.ts#pageRoot`): padding 32px (`space.xl`), maxWidth 1200px.
  - `pageHeader` (marginBottom 32): título "Dashboard Admin" 20px/700 `textPrimary` + subtítulo 13px `textMuted`.
  - `metricsGrid`: `repeat(auto-fill, minmax(180px,1fr))`, gap 16 — 7 MetricCards (na viewport 1280 rendem 5 + 2 na segunda linha).
  - `twoColumn`: `1fr 1fr`, gap 24 — card "Workers" e card "Top tenants por usuários".
  - Card "Eventos críticos recentes" full-width, `marginTop: 24` (inline).
- **Card** (`admin.css.ts#card`): `bgSurface`, borda `borderSubtle`, radius 6 (`radius.md`), padding 24. `cardTitle`: 13px/600 `textSecondary`, uppercase, letterSpacing .05em, marginBottom 16.

## Árvore de componentes

```
AdminLayout (sidebar + main)
└── AdminDashboard (pageRoot)
    ├── pageHeader → pageTitle "Dashboard Admin" + pageSubtitle
    ├── metricsGrid
    │   └── MetricCard ×7 (icon lucide 20px textMuted | metricValue 28px/700 | metricLabel 12px textMuted)
    │       ícones: Building2, Users, Camera, AlertTriangle, Brain, Ticket, DollarSign
    ├── twoColumn
    │   ├── card "WORKERS"
    │   │   ├── flex gap 24: 3× (metricValue + WorkerStatusBadge onpremise|railway|offline)
    │   │   └── btnGhost full-width "Ver workers" (ícone Server 14) → nav('/admin/workers')
    │   └── card "TOP TENANTS POR USUÁRIOS"
    │       └── table (sem thead): td nome | td strong count (textAlign right)
    └── card "EVENTOS CRÍTICOS RECENTES" (só se recent_critical_events.length > 0)
        └── table: th Quando | Ator | Ação | Tenant
            td: mono(data pt-BR) | actor_email ?? actor_role | mono(action) | tenant_name ?? '—'
```

## Copy exata

- Título: `Dashboard Admin` · Subtítulo: `Visão geral da plataforma Logikos`
- Labels de métricas: `Tenants ativos`, `Usuários total`, `Câmeras online`, `Alertas 24h`, `Aprovações pendentes`, `Tickets abertos`, `MRR estimado`
- Valor MRR: `R$ 48.200` (`toLocaleString('pt-BR')`)
- Card titles: `Workers`, `Top tenants por usuários`, `Eventos críticos recentes` (renderizadas uppercase via CSS)
- Badges de worker: `On-premise`, `Railway`, `Offline` (ícones Server/Wifi/WifiOff 11px)
- Botão: `Ver workers`
- Tabela de eventos: `Quando`, `Ator`, `Ação`, `Tenant`
- Erro (banner): texto vindo da API, ex.: `Erro interno do servidor`

## Dados de exemplo (fixtures do spec 19-admin-core)

- KPIs: 8 tenants ativos, 164 usuários, 42 câmeras, 37 alertas 24h, 3 aprovações pendentes (deltaType negative), 5 tickets, MRR R$ 48.200 (deltaType positive).
- Workers: 6 online (On-premise), 2 fallback (Railway), 1 offline.
- Top tenants: Tenant RVB Industrial 32 · Construtora Horizonte Sul 18 · Transportadora Andrade & Filhos 12 · Metalúrgica São Carlos 9 · Agroindústria Vale Verde 4.
- Eventos críticos: `tenant.suspend` (vitor@logikos.com.br, Agroindústria Vale Verde, −35min) · `user.force_password_reset` (RVB, −140min) · `version.rollback` (suporte@logikos.com.br, Construtora Horizonte Sul) · `auth.login_failed_burst` (actor_role `system`, Metalúrgica São Carlos) · `tenant.plan_change` (Transportadora Andrade & Filhos).

## Estados

- **default:** tudo acima. Card de eventos críticos visível.
- **empty (fixture zerado):** todos os KPIs `0`, MRR `R$ 0`, workers `0/0/0`; card "Top tenants por usuários" fica **totalmente vazio** (só o título); card de eventos críticos some. ATENÇÃO: payload catch-all `{}` **quebra a página** (`data.mrr_estimated.toLocaleString` e `data.workers.online` undefined) — empty exige fixture explícito.
- **loading:** Skeletons — 1 title (200px) + grid `minmax(200px,1fr)` com 8 pares (text 55% + title 35%). Obs.: grid do skeleton (200px, 8 itens) difere do grid real (180px, 7 cards) → layout shift.
- **error:** banner `alertBanner.danger` (bg rgba(239,68,68,.1), borda esquerda 3px #dc2626) com a mensagem; adicionalmente um toast global de erro renderiza SOBRE a topbar (colide com "Auditor Visual"/toggle Pro/Sair) nos dois temas.
- **hover "Ver workers":** `btn:hover` = `opacity 0.85` — mudança quase imperceptível no ghost.

## Navegação e fluxos

- `Ver workers` → `/admin/workers`.
- MetricCards não são clicáveis (sem affordance de navegação).
- Sidebar: cada NavItem navega; "Aprovações" e "Tickets" mostram badges alimentados pelo mesmo GET `/api/v1/admin/dashboard` (chamado pelo AdminLayout em toda mudança de rota).

## Problemas identificados

1. **Toast de erro sobrepõe a topbar** no estado error (both themes) — ilegível, cobre controles.
2. **btnPrimary/btnSuccess/btnDanger** com `#fff` hardcoded sobre `primary`/`success`/`danger`: 2.43/2.54/3.76 — reprova WCAG AA (13px).
3. Badges de worker com palete hardcoded (`#ca8a04` etc. em `admin.css.ts`) — contraste reprova no light (On-premise 2.23, Railway 2.67) e não retematiza no white-label (classe task-063).
4. Card "Top tenants" vazio no estado empty sem mensagem/CTA (beco).
5. Coluna "Ação" exibe chaves técnicas do backend (`tenant.suspend`) em vez de rótulos humanos.
6. `R$ 48.200` quebra em duas linhas no MetricCard (28px numa coluna de 180px).
7. Skeleton de loading usa grid diferente do real (200px vs 180px; 8 vs 7 cards).
8. Breadcrumb da topbar duplicado nesta rota: "Painel Admin / Painel Admin".
9. `AdminLayout.tsx:96` faz early-return **antes** dos hooks (`if (!isSuperAdmin) return <Navigate/>`) — risco de violação da ordem de hooks se `isSuperAdmin` mudar em sessão viva.

## Findings (develop — 2026-07-07)

**Screenshots analisados:** dark-default, light-default, dark-error, dark-empty, light-empty, dark-hover-ver-workers, dark-loading, light-loading
**Commits relevantes:** d7a3ad3 (WS1 design system ~70 telas), task-063 (painel vídeo), task-065 (guard-rail CI hardcodes)

### Findings resolvidos

*(nenhum — WS1 não abrangeu admin-dashboard)*

### Findings que persistem

| ID | Sev | Descrição | Evidência |
|---|---|---|---|
| F1 | P0 | Toast de erro sobrepõe a topbar (cobre "Auditor Visual"/toggle Pro/Sair) | dark-error.png — texto da topbar mesclado com toast |
| F2 | P1 | `btnPrimary/btnSuccess/btnDanger` com `#fff` sobre `primary`/`success`/`danger`: 2.43–3.76 — reprova WCAG AA (13px) | dark-default, light-default |
| F3 | P1 | Worker badges hardcoded (`#ca8a04`, `#10b981`, `#ef4444`) — não retematiza no white-label; On-premise 2.23, Railway 2.67 no light | light-default — badges verdes/âmbar/vermelho inalterados |
| F4 | P2 | Card "Top tenants por usuários" totalmente vazio no estado empty — sem mensagem ou CTA | dark-empty, light-empty |
| F5 | P2 | Coluna "Ação" exibe chaves técnicas do backend (`tenant.suspend`) em vez de rótulos humanos | — (dado fixture) |
| F6 | P2 | `R$ 48.200` quebra em duas linhas no MetricCard (28px/minWidth 180px) | light-default — card MRR com "R$" na primeira linha e "48.200" na segunda |
| F7 | P2 | Skeleton de loading usa grid diferente do real (200px vs 180px; 8 itens vs 7 cards) → layout shift | dark-loading |
| F8 | P2 | Breadcrumb duplicado: "Painel Admin / Painel Admin" na topbar | dark-default, light-default — visível no topo |
| F9 | P3 | `AdminLayout.tsx:96` early-return antes dos hooks — risco de violação da regra de hooks | código |

### Findings novos

*(nenhum — nenhuma regressão visual introduzida pelo WS1 nesta tela)*
