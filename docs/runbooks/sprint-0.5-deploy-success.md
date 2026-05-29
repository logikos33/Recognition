# Sprint 0.5 — Tenant Isolation Enforcement — Deploy Success

**Data:** 2026-05-28/29  
**Branch staging SHA:** `ac00b742`  
**ADR:** `docs/decisions/adr/0017-tenant-isolation-enforcement.md`  
**PR:** #7 (`fix/tenant-isolation-enforcement → develop`)

---

## Resumo da Sprint

Eliminação de 4 fallbacks silenciosos em `auth.py` que criavam vetor de
vazamento cross-tenant, desativação do tenant default legado, e migration
de limpeza de dados de teste.

### Commits aplicados (9)

| SHA | Descrição |
|-----|-----------|
| `3a2885d` | docs(adr): ADR-0017 — tenant isolation enforcement |
| `9a8a958` | fix(auth): login valida tenant claims + register sem token |
| `85086cf` | fix(tenant): whitelist sem "public" + set_search_path centralizado |
| `ec44e55` | fix(health): /metrics usa is_active + SET search_path parametrizado |
| `528bd41` | feat(migrations): migration 046 deactivate default tenant |
| `5a6c21f` | docs(runbook): PEND-009 + PEND-010 |
| `237c66f` | test(security): 21 testes ADR-0017 |
| `9406259` | fix(auth): get_tenant_schema/id/role raise AuthenticationError |
| `179b0c7` | test(security): set_search_path rejects 'public' |
| `c0b7742` | refactor(migrations): renomear 042 → 046 |

### Migration 046 aplicada com sucesso

```
infra/migrations/046_deactivate_default_tenant.sql... ✅
```

Dados do tenant default (00000000-0000-0000-0000-000000000001) limpos:
- `public.alerts` DELETE WHERE tenant_id = 0001 — sem erros
- `public.cameras` DELETE WHERE tenant_id = 0001 — sem erros
- `public.users` UPDATE is_active = false WHERE tenant_id = 0001 — sem erros
- `public.tenants` UPDATE is_active = false WHERE id = 0001 — sem erros

### 25 testes de segurança passando

- 8 testes: JWT claims sem fallback (get_tenant_schema/id/role/modules)
- 3 testes: login retorna 401 se user sem tenant/role
- 2 testes: register sem access_token
- 2 testes: whitelist exclui "public" (fail-closed)
- 6 testes: estrutura da migration 046
- 4 testes: set_search_path rejeita "public" (defense in depth)

### CI 4/4 verde

- Lint (ruff): ✅
- Secret detection (gitleaks): ✅
- Tests (pytest): ✅
- TypeScript check: ✅

### Validação pós-deploy

- Healthcheck `/api/v1/health`: `{"status":"healthy","checks":{"database":true,"redis":true}}`
- Runtime logs: zero `db_query_error` ou `column.*does not exist` após startup
- PEND-008 resolvido: `/api/v1/health/metrics` sem mais erro de `column "status"`

---

## PENDs criados

- **PEND-009**: audit `WHERE tenant_id` em queries de listagem de quality (defense-in-depth)
  - Runbook: `docs/runbooks/pend-009-audit-tenant-id-where-clauses.md`
- **PEND-010**: cleanup de dead tables em public schema (após ≥7 dias de estabilidade)
  - Runbook: `docs/runbooks/pend-010-dead-tables-cleanup.md`

---

## Backups preservados

- `/tmp/recognition-backup-20260528-221238/` — pré-execução Sprint 0.5
- `backup/staging-pre-sprint-0.5-20260528` — branch backup do staging pré-merge

---

## Próximo passo

**Fase 1 — Edge schema foundation**
- Migrations 042-045 (reservados para edge sites)
- Schema `recognition_shared`
- Ver `EDGE_DEPLOYMENT_PLAN.md`

---

## Smoke test browser (Vitor)

Pendente confirmação manual:
- Login com `superadmin@logikos.com.br` ou `vitor@logikos` → dashboard carrega
- Navegação por EPI dashboard, alertas — zero 401/403/500 no DevTools Network
