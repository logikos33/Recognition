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
  devices_total, devices_online (last_seen recente), devices_revoked, sites_offline (sem heartbeat recente).
- Tudo via queries tenant-scoped (WHERE tenant_id=%s). Nada de outro tenant.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py
- repo de edge (métodos de contagem agregada tenant-scoped)
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- com seed conhecido (N sites, M devices, K offline) → contagens corretas.
- isolamento: contagens NÃO incluem sites/devices de outro tenant (seed 2 tenants, helper cross-tenant).
- limiar de offline consistente com task-005.
- role insuficiente → 403; sem JWT → 401.

## Critérios de aceitação
- [ ] Contagens corretas e 100% tenant-scoped (C-01).
- [ ] Offline derivado igual à 005 (sem duplicar lógica divergente).
- [ ] Teste cross-tenant com _helpers_tenant; ruff + pytest + tsc verdes; SQL parametrizado.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Nenhuma.

## Checkpoint
- Só PR. Sem produção. Sem migration.
