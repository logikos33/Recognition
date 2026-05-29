# Sprint 0.6 — Database Schema Repair — Complete

**Data:** 2026-05-29
**Branch staging SHA final:** `2084538`
**Version:** 0.0.5
**ADRs:** `docs/decisions/adr/0017-tenant-isolation-enforcement.md`,
`docs/decisions/adr/0018-counting-deepsort-rebuild.md`
**PRs:** #10 (schema repair), #11 (counting rebuild)

---

## Resumo

Reparo de 4 módulos quebrados (operations, counting, fueling, health)
descobertos pós-deploy da Sprint 0.5. Estabelecimento de acesso real
ao banco de produção (`railway run psql` via DATABASE_PUBLIC_URL +
serviço Postgres linkado) — fim da era de inferência de schema.

## Estado anterior (problemas em produção)

| Módulo | Sintoma | Causa raiz |
|--------|---------|------------|
| operations | 500 em todos endpoints, `relation "operations" does not exist` | Migration 038: `camera_id INTEGER REFERENCES ip_cameras(id)` — INTEGER errado (padrão = UUID) + ip_cameras renomeada para cameras em 013 |
| counting | 500 em todos endpoints | Tabela `counting_sessions` em produção tinha schema fueling legado (truck_plate, bay_id) de `migrations/004_rules_engine.sql`; 015 sempre fazia rollback (CREATE TABLE IF NOT EXISTS no-op + CREATE INDEX em coluna ausente); `counting_events` nunca persistiu |
| fueling | 500 em todos endpoints | `pool.getconn()` / `pool.putconn()` não existem em DatabasePool (API correta: `pool.get_connection()` context manager) + `row[0]` em RealDictCursor |
| health/metrics | warning silencioso, métrica zerada | `row[0]` em RealDictCursor — `KeyError(0)` mascarado por bare except |

## Commits aplicados (11)

| SHA | Descrição |
|-----|-----------|
| `13d1c78` | feat(migrations): 047 — repair operations module (UUID FK + cameras) |
| `c8c8d4a` | fix(operations): camera_id UUID type alignment (routes + repository + frontend) |
| `b1a257e` | feat(migrations): 048 — add tenant_id to counting tables *(depois neutralizada)* |
| `476ccb9` | fix(fueling): correct DB pool API + RealDictCursor access |
| `d647209` | fix(health): RealDictCursor access + verbose except |
| `56aedc7` | test(repair): regression tests for Sprint 0.6 fixes |
| `f1110ae` | test(repair): adjust 048 test for schema-qualified names |
| `44800cb` | docs(adr): ADR-0018 — counting DeepSORT schema rebuild |
| `4602dbe` | feat(migrations): 049 — rebuild counting tables with DeepSORT schema |
| `6576836` | refactor(migrations): neutralize 015 + 048 as documented no-ops |
| `4d739ed` | test(counting): update regression tests for 049 rebuild |

## Migrations finais

| # | Status |
|---|--------|
| 015_counting_sessions | **no-op** (SUPERSEDED → 049) |
| 038_operations | falha histórica, ignorada (SUPERSEDED → 047) |
| 039_operation_results | falha histórica, ignorada (SUPERSEDED → 047) |
| 047_operations_repair | ✅ aplicada — operations + operation_results com UUID FK para cameras |
| 048_counting_sessions_tenant_id | **no-op** (SUPERSEDED → 049) |
| 049_counting_deepsort_rebuild | ✅ aplicada — DROP zumbis + CREATE schema DeepSORT correto |

## Validação real (banco de produção, 2026-05-29)

Via `railway run bash -c 'psql "$DATABASE_PUBLIC_URL" ...'`:

- `counting_sessions`: 8 colunas DeepSORT (id, tenant_id, camera_id, module_code, status, total_counts, started_at, ended_at) ✅
- `counting_events`: 9 colunas (id, session_id, tenant_id, track_id, class_name, confidence, first_seen_at, last_seen_at, created_at) + UNIQUE(session_id, track_id) ✅
- `session_events`: removida ✅
- `operations` + `operation_results`: existem ✅
- `operations.camera_id`: UUID ✅

## Endpoints validados (eram 500, agora respondem)

| Endpoint | Antes | Depois |
|----------|-------|--------|
| `/api/v1/health` | warning + 0 | `{"status":"healthy"}` ✅ |
| `/api/counting/sessions` | 500 | 401 (auth) ✅ |
| `/api/v1/operations/...` | 500 | 200 ✅ |
| `/api/fueling/events` | 500 | 401 (auth) ✅ |

Runtime logs `--since 2m`: zero `does not exist`, `KeyError`, `getconn`, `500 Internal`, `traceback`.

## Decisão arquitetural: DROP em tabelas zumbi

ADR-0018 documenta exceção consciente à regra "migrations never DROP":
ambas as tabelas (`counting_sessions` fueling-schema + `session_events`)
tinham 0 rows e 0 referências no código. DROP confirmado via query
direta antes de qualquer ação.

## Acesso ao banco estabelecido

Setup para inspeção real (sem inferência):
1. `railway service Postgres` (link ao serviço Postgres do projeto)
2. `DATABASE_PUBLIC_URL` exposta via proxy TCP (`interchange.proxy.rlwy.net:10344`)
3. `railway run bash -c 'psql "$DATABASE_PUBLIC_URL" -c "..."'`

Antes desta sprint, schema era inferido por leitura de migrations —
levou a 2 erros (ip_cameras inexistente, counting_events fueling).
Agora há canal direto para validar verdade do banco.

## Testes

- 26 testes de regressão da Sprint 0.6 (4 arquivos)
- 28 testes totais incluindo TestSupersededMigrationsAreNoOps
- CI 4/4 verde nas duas PRs (#10 e #11)

## Backups

- `backup/staging-pre-sprint-0.6-20260529` — pré-deploy schema repair
- `backup/staging-pre-counting-rebuild-20260529` — pré-deploy counting rebuild

## Próximo

**Fase 1 — Edge schema foundation**
- Migrations 042-045 reservadas
- Schema `recognition_shared`
- `site_id` em cameras + heartbeats
- Ver `EDGE_DEPLOYMENT_PLAN.md`
