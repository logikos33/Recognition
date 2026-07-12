---
title: "Edge enrollment token management (listar + revogar)"
pr_title: "feat(edge): listar e revogar enrollment tokens (status, sem plaintext)"
commit_message: "feat(edge): enrollment token mgmt — list com status derivado + revoke (tenant-scoped)"
eval: default
budget_minutes: 60
risk: security
---

# Tarefa 012 — Gestão de enrollment tokens (listar + revogar)

## Objetivo
Permitir ao operador ver e invalidar enrollment tokens de um site. Lifecycle de token → classe security.
Tabela existente (enrollment_tokens). Sem hardware, sem migration.

## Contexto (LER antes — C-01, C-05)
- app/api/v1/edge/routes.py (a criação de token já existe — task-003), app/core/auth.py.
- migration 051 (enrollment_tokens: token_hash, expires_at, used_at, used_by_device_id, created_at).
- _helpers_tenant.py (task-006).

## Comportamento
- GET /api/v1/edge/sites/<site_id>/enrollment-tokens (JWT admin; tenant de get_tenant_id()):
  - site_id pertence ao tenant (senão 404).
  - lista tokens do site com STATUS DERIVADO: `used` (used_at != null), `expired` (expires_at <= now e não usado),
    `active` (não usado e não expirado). Campos: id, created_at, expires_at, used_at, used_by_device_id, status.
  - NUNCA retornar token_hash nem qualquer plaintext (o plaintext nem existe mais — só foi mostrado na criação) (C-05).
- POST /api/v1/edge/enrollment-tokens/<token_id>/revoke (JWT admin; tenant-scoped):
  - invalida um token AINDA não usado: UPDATE ... SET expires_at = now() WHERE id=%s AND tenant_id=%s AND used_at IS NULL.
  - token já usado → 409 (não dá pra revogar enrollment consumado); inexistente/cross-tenant → 404.
  - idempotente para token já expirado/revogado (200/no-op).

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py
- edge_site_repository.py (list_enrollment_tokens, revoke_enrollment_token)
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- list: retorna status correto (active/used/expired) para 3 tokens semeados; token_hash/plaintext AUSENTES da resposta.
- revoke de token active → 200; depois, enroll usando esse token (fluxo task-004) → 401 (token inutilizado).
- revoke de token já usado → 409.
- isolamento: list/revoke de site/token de OUTRO tenant → 404; nada alterado no outro tenant (helper cross-tenant).
- role insuficiente → 403; sem JWT → 401.

## Critérios de aceitação
- [ ] Status derivado correto; nunca expõe hash/plaintext (C-05).
- [ ] Revoke torna o token inutilizável (enroll → 401); usado → 409; tenant-scoped (C-01).
- [ ] Testes acima verdes (incl. cross-tenant e revoke→enroll 401); ruff + pytest + tsc verdes; SQL parametrizado.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Nenhuma.

## Checkpoint
- Só PR (humano revisa — classe security/lifecycle de token). Sem produção. Sem migration.
