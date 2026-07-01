---
title: "Edge list devices por site (Fase 2/O1)"
pr_title: "feat(edge): GET /api/v1/edge/sites/<id>/devices — lista de devices do site"
commit_message: "feat(edge): list devices por site (tenant-scoped, sem segredos)"
eval: default
budget_minutes: 60
risk: low
---

# Tarefa 010 — Listar devices de um site

## Objetivo
GET /api/v1/edge/sites/<site_id>/devices: lista os devices (device_tokens) cadastrados num site, para o
operador ver o que está enrollado e o estado de cada um. Read-only, tabela existente (device_tokens).
Sem hardware, sem migration.

## Contexto (LER antes — C-04; C-01)
- app/api/v1/edge/routes.py, app/core/auth.py (get_tenant_id, roles), edge_site_repository.py.
- migration 051 (device_tokens: device_id, device_name, revoked, last_seen_at, enrolled_at, fingerprint, public_key_pem).
- _helpers_tenant.py (task-006) para teste cross-tenant.

## Comportamento
- Rota: GET /api/v1/edge/sites/<site_id>/devices (JWT admin/superadmin; tenant de get_tenant_id()).
- Validar site_id pertence ao tenant (senão 404).
- Retornar por device: id, device_id, device_name, revoked, last_seen_at, enrolled_at.
  NÃO expor public_key_pem nem fingerprint (não são necessários ao operador; minimizar exposição — C-05).
- Filtrar SEMPRE por tenant_id + site_id.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py
- edge_site_repository.py (método list_devices(tenant_id, site_id))
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- lista devices do site do tenant; campos esperados presentes; public_key_pem/fingerprint AUSENTES da resposta.
- isolamento: device de outro tenant nunca aparece; site de outro tenant → 404 (helper cross-tenant).
- role insuficiente → 403; sem JWT → 401.

## Critérios de aceitação
- [ ] Tenant+site-scoped; cross-tenant → 404; sem vazamento (C-01).
- [ ] Resposta minimiza exposição (sem public_key/fingerprint) (C-05).
- [ ] Teste cross-tenant com _helpers_tenant; ruff + pytest + tsc verdes; SQL parametrizado; sem print.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Nenhuma.

## Checkpoint
- Só PR. Sem produção. Sem migration.
