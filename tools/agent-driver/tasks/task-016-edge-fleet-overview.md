---
title: "Edge fleet overview (dashboard tenant-wide)"
pr_title: "feat(edge): GET /api/v1/edge/overview — visão de frota do tenant"
commit_message: "feat(edge): fleet overview (contagens de sites/devices/saúde por tenant)"
eval: default
budget_minutes: 60
risk: low
---

# Tarefa 016 — Visão geral da frota edge (overview)

## Objetivo
GET /api/v1/edge/overview: contagens agregadas da frota do tenant para a tela inicial do painel —
total de sites e por status, total de devices / online / revogados, e quantos sites estão offline.
Read-only, tabelas existentes (edge_sites, device_tokens, edge_heartbeats). Sem hardware, sem migration.

## Contexto (LER antes — C-04; C-01)
- app/api/v1/edge/routes.py, app/core/auth.py (get_tenant_id), repos de edge.
- migrations 050/051/053. _helpers_tenant.py (task-006) para teste cross-tenant.
- A derivação de "site offline" deve ser consistente com a task-005 (mesmo limiar; reusar a lógica se já existir).

## Comportamento
- Rota: GET /api/v1/edge/overview (JWT admin/superadmin; tenant de get_tenant_id()).
- Agregar SOMENTE dados do tenant: sites_total, sites_por_status {active/inactive/maintenance/provisioning},
  devices_total, devices_online (last_seen recente), devices_revoked, sites_offline.
- **Offline = UMA fonte de verdade (correção revisor PR #25):** extrair a derivação de offline da task-005 para
  um helper compartilhado e fazer o overview usar EXATAMENTE a mesma regra/limiar. SQL e Python NÃO podem divergir.
- **Sites em `provisioning` NÃO contam como offline (PR #25):** provisioning é estado de setup, não falha;
  só status operacionais entram em sites_offline.
- Tudo via queries tenant-scoped (WHERE tenant_id=%s). Nada de outro tenant.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py
- repo de edge (métodos de contagem agregada tenant-scoped)
- helper compartilhado de derivação de offline (reusado por task-005 e task-016 — fonte única)
- tests novos em services/api/tests/ (+ fixture de Postgres efêmero, ver Eval)

## Eval (default) — testes SÃO o critério
- **Teste com banco REAL (correção revisor PR #25):** semear um Postgres efêmero (reusar o do harness de
  migrations / um fixture de conftest que sobe Postgres + aplica migrations) e validar o SQL de verdade
  (FILTER/DISTINCT ON). **NÃO mockar o repositório** nos testes de contagem — mock esconde bug de SQL.
- com seed conhecido (N sites, M devices, K offline) → contagens corretas (contra o banco real).
- provisioning: site em `provisioning` → NÃO entra em sites_offline.
- consistência: 005 e 016 avaliados sobre os MESMOS dados → mesmo resultado de offline.
- isolamento: contagens NÃO incluem sites/devices de outro tenant (seed 2 tenants, helper cross-tenant).
- role insuficiente → 403; sem JWT → 401.

## Critérios de aceitação
- [ ] Offline por UM helper compartilhado (005 e 016 concordam); sem lógica duplicada divergente.
- [ ] Sites em `provisioning` não contam como offline.
- [ ] Testes de contagem rodam contra Postgres REAL (não mock do repo); cobrem FILTER/DISTINCT ON.
- [ ] `.claude/scheduled_tasks.lock` no .gitignore (não versionar locks de runtime).
- [ ] Contagens 100% tenant-scoped (C-01); teste cross-tenant com _helpers_tenant.
- [ ] ruff + pytest + tsc verdes; SQL parametrizado. PR para develop.

## NEEDS CLARIFICATION
- Se o suite da API ainda não tiver fixture de Postgres efêmero, criar um mínimo em conftest (reusando o
  Postgres do harness de migrations). NÃO voltar pra mock só pra passar. Se virar grande, PARAR e reportar.

## Checkpoint
- Só PR. Sem produção. Sem migration.
