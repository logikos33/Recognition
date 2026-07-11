# Auditoria Visual — Recognition (EPI Monitor V2)

> Auditoria estática completa do frontend React 18 + TypeScript + Vite + vanilla-extract.
> Temas auditados: `recognition-dark` (padrão) e white-label claro (superfícies por tenant).
> 54 telas, 526 screenshots, 369 findings confirmados.
> Branch: `develop` · Data: 2026-07-07 · Diff-aware contra baseline `staging`.
> Metodologia: Fable (planejamento de shards) + Sonnet (execução por shard), harness Playwright estendido (task-063), API mockada via page.route, supervisor de contraste WCAG.
> Para o relatório completo com defeitos sistêmicos, backlog em ondas e recomendação de guard-rail, ver [REPORT.md](REPORT.md).

---

## Sumário Rápido

| | |
|---|---|
| Telas | 54 (−3 removidas, +2 novas) |
| Screenshots | 526 |
| Findings confirmados | **369** |
| P0 (crítico) | **25** (−13 vs staging) |
| P1 (alto) | **104** (−1 vs staging) |
| P2 (médio) | **165** (+5 vs staging) |
| P3 (baixo) | **75** (−20 vs staging) |
| Refutados | 0 |
| Findings novos | 23 |
| Findings resolvidos | 18 |

### Telas Removidas (3)

Substituídas pela nova tela `admin-observability` (WS9/WS11 — pendente de implementação):
- `stream-health` (`/epi/health`)
- `sites-health` (`/epi/sites-health`)
- `admin-health` (`/admin/health`)

### Telas Novas (2)

| Tela | Rota | Status |
|---|---|---|
| Admin — Observability | `/admin/observability` | Não implementada (WS9/WS11 pendente) |
| Admin — Demo Events | `/admin/demo-events` | Não implementada (WS9/WS11 pendente) |

---

## Índice das 54 Telas

> Branch `develop` · 2026-07-07. Coluna "Confirmados" = P0 / P1 / P2 / P3 no estado atual.
> Telas sem findings listados = 0 findings naquela severidade.

| # | Tela | Rota | Dark | Light | Confirmados |
|---|---|---|---|---|---|
| 1 | Login | `/login` | [dark](screenshots/login/dark-default.png) | [light](screenshots/login/light-default.png) | P0×1 P1×1 P2×2 P3×2 |
| 2 | Seleção de Módulo | `/modulos` | [dark](screenshots/module-selection/dark-default.png) | [light](screenshots/module-selection/light-default.png) | P1×2 P2×2 P3×2 |
| 3 | EPI — Dashboard | `/epi/dashboard` | [dark](screenshots/epi-dashboard/dark-default.png) | [light](screenshots/epi-dashboard/light-default.png) | P0×1 P1×5 P2×2 P3×2 |
| 4 | EPI — Câmeras | `/epi/cameras` | [dark](screenshots/epi-cameras/dark-default.png) | [light](screenshots/epi-cameras/light-default.png) | P0×2 P1×3 P2×5 P3×1 |
| 5 | EPI — Operações | `/epi/operations` | [dark](screenshots/epi-operations/dark-default.png) | [light](screenshots/epi-operations/light-default.png) | P0×1 P1×3 P2×3 P3×1 |
| 6 | EPI — Editor de Cenário | `/epi/scenario-editor` | [dark](screenshots/epi-scenario-editor/dark-default.png) | [light](screenshots/epi-scenario-editor/light-default.png) | P0×1 P1×1 P2×6 P3×1 |
| 7 | EPI — Monitoramento | `/epi/monitoring` | [dark](screenshots/epi-monitoring/dark-default.png) | [light](screenshots/epi-monitoring/light-default.png) | P1×1 P2×3 P3×1 |
| 8 | EPI — Alertas | `/epi/alerts` | [dark](screenshots/epi-alerts/dark-default.png) | [light](screenshots/epi-alerts/light-default.png) | P0×1 P1×4 P2×6 P3×3 |
| 9 | EPI — Treino | `/epi/training` | [dark](screenshots/epi-training/dark-default.png) | [light](screenshots/epi-training/light-default.png) | P0×1 P1×4 P2×3 |
| 10 | EPI — Classes de Treino | `/epi/training/classes` | [dark](screenshots/training-classes/dark-default.png) | [light](screenshots/training-classes/light-default.png) | P0×1 P1×3 P2×1 P3×1 |
| 11 | EPI — Fila de Verificação | `/epi/verification` | [dark](screenshots/verification-queue/dark-default.png) | [light](screenshots/verification-queue/light-default.png) | P0×2 P1×3 P2×2 |
| 12 | Investigação | `/epi/investigation` | [dark](screenshots/investigation/dark-default.png) | [light](screenshots/investigation/light-default.png) | P1×3 P2×5 P3×4 |
| 13 | Contagem | `/counting` | [dark](screenshots/counting/dark-default.png) | [light](screenshots/counting/light-default.png) | P0×1 P1×2 P2×2 P3×3 |
| 14 | EPI — Relatórios | `/epi/reports` | [dark](screenshots/epi-reports/dark-default.png) | [light](screenshots/epi-reports/light-default.png) | P0×1 P2×1 P3×2 |
| 15 | Admin — Dashboard | `/admin` | [dark](screenshots/admin-dashboard/dark-default.png) | [light](screenshots/admin-dashboard/light-default.png) | P0×1 P1×2 P2×5 P3×1 |
| 16 | Admin — Tenants | `/admin/tenants` | [dark](screenshots/admin-tenants/dark-default.png) | [light](screenshots/admin-tenants/light-default.png) | P1×3 P2×7 |
| 17 | Admin — Detalhe do Tenant | `/admin/tenants/:id` | [dark](screenshots/admin-tenant-detail/dark-default.png) | [light](screenshots/admin-tenant-detail/light-default.png) | P1×6 P2×5 |
| 18 | Admin — Usuários | `/admin/users` | [dark](screenshots/admin-users/dark-default.png) | [light](screenshots/admin-users/light-default.png) | P1×3 P2×6 |
| 19 | Admin — Roles | `/admin/roles` | [dark](screenshots/admin-roles/dark-default.png) | [light](screenshots/admin-roles/light-default.png) | P1×2 P2×5 P3×1 |
| 20 | Admin — Planos | `/admin/plans` | [dark](screenshots/admin-plans/dark-default.png) | [light](screenshots/admin-plans/light-default.png) | P1×2 P2×4 P3×1 |
| 21 | Admin — Integrações | `/admin/integrations` | [dark](screenshots/admin-integrations/dark-default.png) | [light](screenshots/admin-integrations/light-default.png) | P1×2 P2×5 P3×1 |
| 22 | Admin — Configurações | `/admin/settings` | [dark](screenshots/admin-settings/dark-default.png) | [light](screenshots/admin-settings/light-default.png) | P1×1 P2×1 P3×2 |
| 23 | Admin — Feature Flags | `/admin/feature-flags` | [dark](screenshots/admin-feature-flags/dark-default.png) | [light](screenshots/admin-feature-flags/light-default.png) | P1×2 P2×1 P3×2 |
| 24 | Admin — Workers | `/admin/workers` | [dark](screenshots/admin-workers/dark-default.png) | [light](screenshots/admin-workers/light-default.png) | P1×1 P2×2 P3×3 |
| 25 | Admin — Versões | `/admin/versions` | [dark](screenshots/admin-versions/dark-default.png) | [light](screenshots/admin-versions/light-default.png) | P1×3 P2×5 |
| 26 | Admin — Changelog | `/admin/changelog` | [dark](screenshots/admin-changelog/dark-default.png) | [light](screenshots/admin-changelog/light-default.png) | P1×2 P2×4 P3×2 |
| 27 | Admin — Audit Log | `/admin/audit-log` | [dark](screenshots/admin-audit-log/dark-default.png) | [light](screenshots/admin-audit-log/light-default.png) | P1×1 P3×3 |
| 28 | Admin — Anúncios | `/admin/announcements` | [dark](screenshots/admin-announcements/dark-default.png) | [light](screenshots/admin-announcements/light-default.png) | P1×2 P2×3 P3×2 |
| 29 | Admin — Retenção | `/admin/retention` | [dark](screenshots/admin-retention/dark-default.png) | [light](screenshots/admin-retention/light-default.png) | P0×1 P1×2 P2×1 P3×1 |
| 30 | Admin — Tickets | `/admin/tickets` | [dark](screenshots/admin-tickets/dark-default.png) | [light](screenshots/admin-tickets/light-default.png) | P2×3 P3×2 |
| 31 | Admin — Inventário | `/admin/inventory` | [dark](screenshots/admin-inventory/dark-default.png) | [light](screenshots/admin-inventory/light-default.png) | P1×2 P2×4 |
| 32 | Admin — Test Console | `/admin/test-console` | [dark](screenshots/admin-test-console/dark-default.png) | [light](screenshots/admin-test-console/light-default.png) | P1×2 P2×3 P3×1 |
| 33 | Admin — Demo Videos | `/admin/demo-videos` | [dark](screenshots/admin-demo-videos/dark-default.png) | [light](screenshots/admin-demo-videos/light-default.png) | P0×1 P1×1 P2×3 P3×1 |
| 34 | Admin — Aprovações de Treino | `/admin/training-approvals` | [dark](screenshots/admin-training-approvals/dark-default.png) | [light](screenshots/admin-training-approvals/light-default.png) | P1×1 P2×3 P3×1 |
| 35 | Admin — Branding (Tenants) | `/admin/branding` | [dark](screenshots/admin-branding-tenants/dark-default.png) | [light](screenshots/admin-branding-tenants/light-default.png) | P0×1 P1×2 P2×3 P3×1 |
| 36 | Admin — Branding (Default) | `/admin/branding/default` | [dark](screenshots/admin-branding-default/dark-default.png) | [light](screenshots/admin-branding-default/light-default.png) | P0×1 P2×3 P3×4 |
| 37 | Admin — Branding (Editor) | `/admin/branding/editor` | [dark](screenshots/admin-branding-editor/dark-default.png) | [light](screenshots/admin-branding-editor/light-default.png) | P1×3 P2×1 P3×1 |
| 38 | Admin — Branding (Sandbox) | `/admin/branding/sandbox` | [dark](screenshots/admin-branding-sandbox/dark-default.png) | [light](screenshots/admin-branding-sandbox/light-default.png) | P0×1 P1×3 P2×2 P3×3 |
| 39 | Admin — Observability *(nova)* | `/admin/observability` | — | — | *Não implementada* |
| 40 | Admin — Demo Events *(nova)* | `/admin/demo-events` | — | — | *Não implementada* |
| 41 | Design System | `/design-system` | [dark](screenshots/design-system/dark-default.png) | [light](screenshots/design-system/light-default.png) | P0×2 P3×3 |
| 42 | Quality — Dashboard | `/quality/dashboard` | [dark](screenshots/quality-dashboard/dark-default.png) | [light](screenshots/quality-dashboard/light-default.png) | P1×1 P2×5 P3×1 |
| 43 | Quality — Câmeras | `/quality/cameras` | [dark](screenshots/quality-cameras/dark-default.png) | [light](screenshots/quality-cameras/light-default.png) | P1×3 P2×4 P3×1 |
| 44 | Quality — Configuração | `/quality/config` | [dark](screenshots/quality-config/dark-default.png) | [light](screenshots/quality-config/light-default.png) | P1×3 P2×4 P3×1 |
| 45 | Quality — Inspeções | `/quality/inspections` | [dark](screenshots/quality-inspections/dark-default.png) | [light](screenshots/quality-inspections/light-default.png) | P1×3 P2×4 P3×2 |
| 46 | Quality — Peças | `/quality/pieces` | [dark](screenshots/quality-pieces/dark-default.png) | [light](screenshots/quality-pieces/light-default.png) | P1×2 P2×3 P3×2 |
| 47 | Quality — Relatórios | `/quality/reports` | [dark](screenshots/quality-reports/dark-default.png) | [light](screenshots/quality-reports/light-default.png) | P1×2 P2×3 P3×2 |
| 48 | Quality — Retrabalho | `/quality/rework` | [dark](screenshots/quality-rework/dark-default.png) | [light](screenshots/quality-rework/light-default.png) | P2×5 P3×1 |
| 49 | Quality — Treino | `/quality/training` | [dark](screenshots/quality-training/dark-default.png) | [light](screenshots/quality-training/light-default.png) | P3×1 |
| 50 | Quality — Anotação | `/quality/annotation` | [dark](screenshots/quality-annotation/dark-default.png) | [light](screenshots/quality-annotation/light-default.png) | P1×2 P2×4 P3×1 |
| 51 | Quality — Andon | `/quality/andon` | [dark](screenshots/quality-andon/dark-default.png) | [light](screenshots/quality-andon/light-default.png) | P1×2 P2×2 P3×1 |
| 52 | Tablet Kiosk | `/tablet/:station` | [dark](screenshots/tablet-kiosk/dark-default.png) | [light](screenshots/tablet-kiosk/light-default.png) | P0×1 P2×3 P3×2 |
| 53 | Fueling — Principal | `/fueling` | [dark](screenshots/fueling/dark-default.png) | [light](screenshots/fueling/light-default.png) | P0×1 P1×2 P2×2 P3×1 |
| 54 | Fueling — Validação | `/fueling/validation` | [dark](screenshots/fueling-validation/dark-default.png) | [light](screenshots/fueling-validation/light-default.png) | P0×2 P1×1 P2×4 |

---

## Documentos Relacionados

| Documento | Descrição |
|---|---|
| [REPORT.md](REPORT.md) | Relatório completo: sistêmicos, inventário por tela, backlog em ondas, guard-rail |
| [design-system.md](design-system.md) | Auditoria do design system: tokens, tipografia, bridge white-label, componentes do kit |
| [.tmp/findings.json](.tmp/findings.json) | Dados estruturados: scores por tela, defeitos sistêmicos, delta vs staging |
