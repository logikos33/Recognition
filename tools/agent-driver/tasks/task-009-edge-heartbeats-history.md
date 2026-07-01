---
title: "Edge heartbeats history read (O1)"
pr_title: "feat(edge): GET /api/v1/edge/sites/<id>/heartbeats — histórico paginado"
commit_message: "feat(edge): heartbeats history read por site (tenant-scoped, paginado)"
eval: default
budget_minutes: 60
risk: low
---

# Tarefa 009 — Histórico de heartbeats por site (O1)

## Objetivo
GET /api/v1/edge/sites/<site_id>/heartbeats: série temporal recente de edge_heartbeats de um site, para
gráficos de tendência no painel. Read-only, tabela existente (edge_heartbeats). Sem hardware, sem migration.

## Contexto (LER antes — C-04; C-01 multi-tenant)
- app/api/v1/edge/routes.py (rotas existentes), app/core/auth.py (get_tenant_id, jwt_required_custom, roles).
- edge_site_repository.py / o repo de heartbeat (padrão psycopg2 + RealDictCursor).
- migration 053 (campos de edge_heartbeats: received_at, status, métricas).
- services/api/tests/security/_helpers_tenant.py (task-006) — reusar nos testes cross-tenant.

## Comportamento
- Rota: GET /api/v1/edge/sites/<site_id>/heartbeats?limit=&before= (JWT de usuário; tenant de get_tenant_id()).
- Validar que site_id pertence ao tenant do JWT (senão 404 — não vaza existência cross-tenant).
- Query: SELECT ... FROM public.edge_heartbeats WHERE tenant_id=%s AND site_id=%s [AND received_at < %s]
  ORDER BY received_at DESC LIMIT %s. limit default 100, máximo 500 (clamp).
- Retornar lista de heartbeats com received_at + métricas-chave (status, inference_fps, cameras_online/total,
  cpu/gpu/queue_depth, edge_version). Paginação por `before` (cursor temporal).

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py
- repo de heartbeat/site (método list_heartbeats(tenant_id, site_id, limit, before))
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- site do tenant com N heartbeats → retorna em ordem received_at DESC, respeitando limit.
- `before` filtra corretamente (cursor).
- limit acima do máximo é clampado (não retorna 10000).
- isolamento: GET de site de OUTRO tenant → 404; resposta nunca inclui heartbeat de outro tenant (usar helper cross-tenant).
- sem JWT → 401.

## Critérios de aceitação
- [ ] Tenant-scoped (tenant_id do JWT); site_id validado; cross-tenant → 404 (C-01).
- [ ] Ordenação received_at DESC, limit com clamp, cursor `before` funcionando.
- [ ] Teste cross-tenant usando _helpers_tenant; ruff + pytest + tsc verdes; SQL parametrizado; sem print.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Nenhuma. Se houver dúvida sobre o formato do cursor de paginação, ler como outras listagens do projeto paginam antes de assumir.

## Checkpoint
- Só PR. Sem produção. Sem migration.
