---
title: "API de Cenário (leitura) + catálogo de operation-types"
pr_title: "feat(scenarios): GET cenário composto por câmera + catálogo de operation-types por módulo"
commit_message: "feat(scenarios): leitura do cenário (cameras+module+operations+rules+schedule) + operation-types"
eval: default
budget_minutes: 60
risk: low
---

# Tarefa 022 — API de Cenário (leitura) + catálogo de operation-types

## Objetivo
Expor o "cenário" de uma câmera como uma unidade (compondo o que já existe) e listar os operation-types
disponíveis por módulo — base que o editor visual (task-023) vai consumir. Read-only, tabelas existentes.
Sem hardware, sem migration. Ver `docs/architecture/PLATAFORMA_CENARIOS.md`.

## Contexto (LER antes — C-04; C-01)
- public.cameras (+site_id), module_classes, tenant_modules, operations (type_id+config JSONB),
  alert_rules, camera_modules_schedule. app/core/auth.py (get_tenant_id).
- operations/routes.py já tem `GET /modules/<module_id>/operation-types` — reusar/estender, não duplicar.
- services/api/tests/security/_helpers_tenant.py + fixture de Postgres efêmero (padrão PR #25).

## Comportamento
- GET /api/v1/cameras/<camera_id>/scenario (JWT; tenant de get_tenant_id()):
  compõe e retorna o cenário da câmera = { camera (id, nome, site_id), módulo(s) habilitado(s) + classes,
  operações (type_id + config), regras (alert_rules aplicáveis), agenda }. Tudo filtrado por tenant_id.
  Câmera de outro tenant → 404.
- GET /api/v1/scenarios/operation-types?module=<code> : catálogo dos tipos por módulo
  (ex: epi_zone, defect_trigger, counting_line) com o schema de `config` esperado (pra o front saber qual
  ferramenta de desenho usar e quais campos pedir). Reusar o registro de op_class existente.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/ (rota de scenario read; reusar operations para operation-types)
- repo(s) existentes (compor leitura; sem nova tabela)
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério (banco REAL, padrão PR #25)
- seed (câmera + módulo + operação + regra + agenda) num Postgres efêmero → GET scenario compõe tudo certo.
- isolamento: câmera de outro tenant → 404; resposta nunca inclui dado de outro tenant (helper cross-tenant).
- operation-types: lista os tipos do módulo com o schema de config; módulo inválido → vazio/404 coerente.
- sem JWT → 401.

## Critérios de aceitação
- [ ] Cenário composto e 100% tenant-scoped (C-01); cross-tenant → 404.
- [ ] Catálogo de operation-types por módulo com schema de config.
- [ ] Testes contra Postgres REAL (não mock); cross-tenant com _helpers_tenant; ruff + pytest + tsc verdes.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Se a forma exata de "regras aplicáveis à câmera" não estiver clara no schema de alert_rules, LER como o
  rules engine associa regra↔câmera/módulo antes de assumir; não inventar associação.

## Checkpoint
- Só PR. Sem produção. Sem migration.
