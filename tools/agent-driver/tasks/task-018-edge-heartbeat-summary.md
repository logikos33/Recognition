---
title: "Edge heartbeat summary/agregados por site"
pr_title: "feat(edge): GET /api/v1/edge/sites/<id>/heartbeat-summary — agregados por janela"
commit_message: "feat(edge): heartbeat summary (uptime %, fps médio/máx, último status) por janela"
eval: default
budget_minutes: 60
risk: low
---

# Tarefa 018 — Resumo de heartbeats por site (agregados)

## Objetivo
GET /api/v1/edge/sites/<site_id>/heartbeat-summary?window=: métricas agregadas de saúde de um site numa
janela (uptime %, FPS médio/máx, latência média, último status, contagem de heartbeats). Complementa a
task-009 (histórico bruto) com a visão resumida para cards/KPIs. Read-only, edge_heartbeats. Sem migration.

## Contexto (LER antes — C-04; C-01)
- app/api/v1/edge/routes.py, app/core/auth.py, repo de heartbeat. migration 053 (campos de edge_heartbeats).
- _helpers_tenant.py (task-006). Limiar/derivação de offline consistente com task-005.

## Comportamento
- Rota: GET /sites/<site_id>/heartbeat-summary?window=<duração, ex 24h> (JWT admin; tenant de get_tenant_id()).
- site_id pertence ao tenant (senão 404). window default 24h, clamp em um máximo (ex 7d).
- Agregar edge_heartbeats WHERE tenant_id AND site_id AND received_at >= now()-window:
  count, avg/max inference_fps, avg inference_latency_ms, uptime_pct (heartbeats com status saudável / total),
  último status e último received_at.
- Sem heartbeats na janela → resposta coerente (zeros/null + status offline), não erro.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py
- repo de heartbeat (summary_for_site(tenant_id, site_id, window))
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- **Banco REAL, não mock (padrão PR #25):** os agregados (avg/max/uptime) rodam contra Postgres efêmero
  seedado (reusar o fixture do harness/conftest), validando o SQL de agregação de verdade. Não mockar o repo.
- com seed conhecido → agregados corretos (avg/max/uptime/contagem) na janela.
- window filtra corretamente; window acima do máximo é clampada.
- site sem heartbeat na janela → resposta coerente (não 500).
- isolamento: dados de outro tenant nunca entram no agregado; site de outro tenant → 404 (helper cross-tenant).
- sem JWT → 401.

## Critérios de aceitação
- [ ] Agregados corretos validados contra Postgres REAL (não mock); window com clamp; tenant+site-scoped; cross-tenant → 404 (C-01).
- [ ] Janela vazia tratada sem erro; offline pelo helper compartilhado (concorda com 005/016).
- [ ] Teste cross-tenant; ruff + pytest + tsc verdes; SQL parametrizado.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Reusar o fixture de Postgres efêmero criado pela task-016 (não recriar). Se não existir, criar mínimo em conftest.

## Checkpoint
- Só PR. Sem produção. Sem migration.
