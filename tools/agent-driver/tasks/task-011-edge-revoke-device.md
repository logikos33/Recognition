---
title: "Edge revoke device (controle de acesso)"
pr_title: "feat(edge): POST /api/v1/edge/devices/<id>/revoke — revogação de device"
commit_message: "feat(edge): revoke device token (tenant-scoped, idempotente, auditado)"
eval: default
budget_minutes: 60
risk: security
---

# Tarefa 011 — Revogar um device

## Objetivo
POST /api/v1/edge/devices/<device_pk>/revoke: revoga um device (device_tokens.revoked=true), cortando o
acesso dele (o heartbeat já barra revoked). Controle de acesso → classe security. Tabela existente. Sem migration.

## Contexto (LER antes — C-01, C-05)
- app/api/v1/edge/routes.py (heartbeat já checa device.revoked — manter compatível), app/core/auth.py.
- migration 051 (device_tokens: revoked, revoked_at, revoked_by, revocation_reason).
- _helpers_tenant.py (task-006).

## Comportamento
- Rota: POST /api/v1/edge/devices/<device_pk>/revoke (JWT admin/superadmin; tenant de get_tenant_id()).
- O device DEVE pertencer ao tenant do JWT (lookup por id AND tenant_id; senão 404 — não revoga cross-tenant, não vaza existência).
- UPDATE public.device_tokens SET revoked=true, revoked_at=now(), revoked_by=<user>, revocation_reason=<body opcional>
  WHERE id=%s AND tenant_id=%s.
- Idempotente: revogar device já revogado → 200 (no-op), não erro.
- Auditar (logger sem PII): quem revogou, device, quando.

## Arquivos (NÃO tocar fora; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py
- edge_site_repository.py (método revoke_device(device_pk, tenant_id, revoked_by, reason))
- tests novos em services/api/tests/

## Eval (default) — testes SÃO o critério
- revogar device do tenant → 200, revoked=true no banco, revoked_at/revoked_by setados.
- idempotência: revogar 2x → 200 nas duas, sem erro.
- isolamento: revogar device de OUTRO tenant → 404 e o device do outro tenant continua revoked=false (C-01).
- integração: após revogar, um heartbeat com o token desse device → 403 (reusar o fluxo da task-002 no teste).
- role insuficiente → 403; sem JWT → 401.

## Critérios de aceitação
- [ ] Tenant-scoped (id AND tenant_id); cross-tenant → 404, nada alterado no outro tenant (C-01).
- [ ] Idempotente; auditado; revogação efetiva (heartbeat passa a 403).
- [ ] Testes acima verdes (incl. cross-tenant e a integração heartbeat→403); ruff + pytest + tsc verdes; SQL parametrizado.
- [ ] PR para develop.

## NEEDS CLARIFICATION
- Nenhuma. Se o identificador na URL deve ser o id (UUID) do device_tokens ou o device_id textual, usar o id
  (UUID) por padrão; se houver convenção diferente no projeto, segui-la (ler antes, não assumir).

## Checkpoint
- Só PR (humano revisa — classe security/controle de acesso). Sem produção. Sem migration.
