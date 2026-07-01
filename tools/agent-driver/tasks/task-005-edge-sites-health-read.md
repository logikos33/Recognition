---
title: "Edge sites health read + offline rule (O1)"
pr_title: "feat(edge): GET /api/v1/edge/sites/health — status derivado + regra offline"
commit_message: "feat(edge): sites health read com derivação de status offline a partir de edge_heartbeats"
eval: default
budget_minutes: 60
risk: low
---

# Tarefa 005 — Leitura de saúde dos sites + regra de offline (O1)

## Objetivo
GET /api/v1/edge/sites/health: para o tenant do JWT, lista cada edge_site com o último heartbeat e um
status DERIVADO — se o heartbeat mais recente for mais antigo que um limiar (offline), reporta 'offline';
senão usa o status do heartbeat. É o lado de leitura da observabilidade (Fase O1): o que deixa você ver
remotamente a saúde da RVB. Read-only, tabelas existentes (edge_sites, edge_heartbeats). Sem hardware.

## Contexto (LER antes — C-04)
- /constitution.md (C-01), CLAUDE.md, app/api/v1/edge/routes.py (task-002), app/core/auth.py (get_tenant_id).
- migrations 050 (edge_sites) e 053 (edge_heartbeats: received_at, status, métricas).
- recognition_shared (SiteStatus, HeartbeatStatus) — reusar enums.
- Um repository existente como referência (JOIN/última linha por grupo em SQL puro).

## Comportamento
- Rota: GET /api/v1/edge/sites/health (JWT de usuário; tenant_id de get_tenant_id()).
- Para cada edge_site do tenant, pegar o heartbeat mais recente (maior received_at) em edge_heartbeats
  filtrando por tenant_id + site_id.
- Derivar status:
  - sem nenhum heartbeat → 'offline' (ou 'unknown' se o enum tiver) ;
  - último received_at mais antigo que OFFLINE_THRESHOLD (default 120s, ler de config/env com fallback) → 'offline';
  - caso contrário → status do heartbeat (healthy|degraded|critical).
- Resposta por site: site_id, name, deployment_mode, derived_status, last_heartbeat_at, e métricas-chave do
  último heartbeat (inference_fps, cameras_online, cameras_total, cpu_pct, gpu_pct, queue_depth, edge_version).
- Tudo filtrado por tenant_id (C-01) — um tenant nunca vê site/heartbeat de outro.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py (rota de health)
- app/infrastructure/database/repositories/ (estender edge_site/heartbeat repo: query de "último heartbeat por site")
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- site com heartbeat recente (received_at = agora, status healthy) → derived_status 'healthy'.
- site com heartbeat antigo (received_at = agora - 10min) → derived_status 'offline'.
- site sem nenhum heartbeat → 'offline'/'unknown'.
- isolamento: seed 2 tenants; a resposta do tenant_a NÃO inclui sites nem métricas do tenant_b (C-01).
- métricas do último heartbeat retornadas corretamente (não de um heartbeat antigo).

## Critérios de aceitação
- [ ] status derivado correto nos 3 casos (recente / stale / sem heartbeat).
- [ ] "último heartbeat por site" correto (não pega linha antiga).
- [ ] tudo filtrado por tenant_id; zero vazamento cross-tenant (C-01).
- [ ] limiar de offline configurável (env/config, com default).
- [ ] testes verdes; ruff + pytest + tsc verdes; SQL parametrizado; sem print.
- [ ] PR para develop.

## Checkpoint
- Só PR. Sem produção. Sem migration. Faltou contexto → ler os arquivos.
