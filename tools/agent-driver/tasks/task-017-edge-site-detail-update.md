---
title: "Edge site detail + update"
pr_title: "feat(edge): GET e PATCH /api/v1/edge/sites/<id> — detalhe e edição de site"
commit_message: "feat(edge): site detail (com saúde + nº devices) e update parcial (tenant-scoped)"
eval: default
budget_minutes: 60
risk: low
---

# Tarefa 017 — Detalhe e edição de um site

## Objetivo
GET /api/v1/edge/sites/<site_id> (detalhe do site + nº de devices + saúde derivada) e
PATCH /api/v1/edge/sites/<site_id> (editar name/location/status/deployment_mode). Tabela existente
(edge_sites). Sem hardware, sem migration.

## Contexto (LER antes — C-04; C-01)
- app/api/v1/edge/routes.py (criação/listagem de sites já existem — task-003), app/core/auth.py.
- migration 050 (edge_sites: campos e CHECKs de deployment_mode/status). _helpers_tenant.py (task-006).

## Comportamento
- GET /sites/<site_id> (JWT admin; tenant de get_tenant_id()): site do tenant (senão 404), com nº de devices
  e status de saúde derivado (consistente com task-005). 
- PATCH /sites/<site_id> (JWT admin; tenant-scoped): atualização PARCIAL de name, location, status,
  deployment_mode. Validar enums (status, deployment_mode) — valor inválido → 400. UPDATE ... WHERE id=%s AND
  tenant_id=%s; site de outro tenant → 404 (não edita cross-tenant). tenant_id NUNCA muda (não aceitar do body).
- Auditar a edição (logger sem PII): quem, quando, o que mudou.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py
- edge_site_repository.py (get_site_detail, update_site parcial tenant-scoped)
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- **Banco REAL, não mock (padrão PR #25):** testes de GET detalhe (nº devices + saúde derivada) rodam contra
  Postgres efêmero seedado (reusar o fixture do harness/conftest), validando o SQL real. Não mockar o repo.
- GET detalhe do site do tenant → 200 com campos + nº devices + saúde; site de outro tenant → 404.
- saúde derivada usa o **mesmo helper compartilhado de offline da task-005/016** (sem regra divergente).
- PATCH altera só os campos enviados; enum inválido → 400; tenant_id do body é ignorado (não muda o tenant).
- isolamento: PATCH em site de outro tenant → 404 e nada muda no outro tenant (helper cross-tenant).
- role insuficiente → 403; sem JWT → 401.

## Critérios de aceitação
- [ ] GET/PATCH tenant-scoped (id AND tenant_id); cross-tenant → 404 (C-01); tenant_id imutável via body.
- [ ] Saúde derivada pelo helper compartilhado (concorda com 005/016); testes de query contra Postgres REAL.
- [ ] PATCH parcial; enums validados; auditado.
- [ ] Teste cross-tenant; ruff + pytest + tsc verdes; SQL parametrizado.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Reusar o fixture de Postgres efêmero criado pela task-016 (não recriar). Se não existir, criar mínimo em conftest.

## Checkpoint
- Só PR. Sem produção. Sem migration.
