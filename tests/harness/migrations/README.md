# Harness de Migrations — Fase D1

Primeiro eval do Recognition. Valida que as migrations (atualmente 001→106) aplicam corretamente
e são idempotentes, imitando o comportamento do `railway_start.py:run_migrations()` em produção.

**Referências:** [`/constitution.md`](../../../constitution.md) | [`docs/EVALS.md`](../../../docs/EVALS.md)

## Um comando

```bash
bash tests/harness/migrations/run.sh
```

Pré-requisito: Docker em execução e Python 3.11+.

## O que faz

1. Sobe `postgres:15-alpine` efêmero na porta 55432 (tmpfs — zero persistência local).
2. Aplica `infra/migrations/*.sql` em ordem lexicográfica (passada 1 — banco limpo).
3. Aplica novamente (passada 2 — idempotência). Runner deve sair com código 0.
4. Roda pytest com os asserts de schema.
5. Derruba o container (trap garante cleanup mesmo em falha).

## Variáveis de ambiente

| Variável | Padrão (run.sh) | Descrição |
|----------|-----------------|-----------|
| `HARNESS_DATABASE_URL` | `postgresql://harness:harness@localhost:55432/recognition_harness` | DSN do banco efêmero |

## Asserts e princípios protegidos

| Teste | O que verifica | Princípio |
|-------|---------------|-----------|
| `test_first_pass_clean_db` | Passada adicional do runner: exit 0 | C-02 |
| `test_second_pass_idempotent` | Segunda passada adicional: exit 0 | C-02 |
| `test_phase1_tables_in_public[edge_sites]` | Tabela existe em public | C-04 |
| `test_phase1_tables_in_public[device_tokens]` | Tabela existe em public | C-04 |
| `test_phase1_tables_in_public[enrollment_tokens]` | Tabela existe em public | C-04 |
| `test_phase1_tables_in_public[edge_heartbeats]` | Tabela existe em public | C-04 |
| `test_site_id_columns[cameras]` | Coluna site_id UUID em public.cameras | C-04 |
| `test_site_id_columns[alerts]` | Coluna site_id UUID em public.alerts | C-04 |
| `test_site_id_columns[counting_events]` | Coluna site_id UUID em public.counting_events | C-04 |
| `test_site_id_columns[operations]` | Coluna site_id UUID em public.operations | C-04 |
| `test_tenants_deployment_mode_column` | Coluna existe com default 'cloud' | C-04 |
| `test_tenants_deployment_mode_check` | CHECK IN (cloud, edge, hybrid) | C-04 |
| `test_create_tenant_schema_has_site_id` | Função referencia site_id | C-04 |
| `test_anti_regression_ip_cameras` | public.ip_cameras NÃO existe | anti-padrão |
| `test_schema_migrations_created_by_001` | public.schema_migrations EXISTE (criada pela 001, não é o tracker) | paridade prod |
| `test_legacy_tolerance_is_scoped_to_038` | Tolerância a erro legado não vaza para outras migrations | anti-padrão |
| `test_legacy_tolerated_migrations_autocorrect[operations\|operation_results]` | Estado final correto após 038/039 tolerados + 047 corrige | C-02 |
| `test_training_pipeline_tables_in_public[...]` (093–101) | Tabelas do pipeline MLOps (datasets, recorders, model_deployments, model_evaluations, model_drift_metrics) existem em public | C-04 |
| `test_training_pipeline_tables_tenant_id_not_null[...]` / `test_training_pipeline_tables_tenant_id_fk[...]` | tenant_id NOT NULL + FK para tenants em todas as tabelas do pipeline | C-04 |
| `test_training_pipeline_columns[...]` | Colunas específicas (training_frames, yolo_classes, frame_annotations, dataset_versions, training_jobs, trained_models) | C-04 |
| `test_training_pipeline_check_constraints[...]` | CHECK constraints do pipeline (source, protocol) | C-04 |
| `test_training_frames_recorder_fk` | FK training_frames → recorders | C-04 |

## Erro legado conhecido (KNOWN_LEGACY_ERRORS)

`runner.py` tolera quatro erros conhecidos em banco virgem (forward-reference que se resolve
por uma migration posterior):

| Migration | Erro em banco virgem | Resolvido por |
|---|---|---|
| `038_operations.sql` | FK para `ip_cameras` (renomeada para `cameras` na `013_consolidate_cameras.sql`) | `047_operations_repair.sql` recria `operations` com FK correta |
| `039_operation_results.sql` | `operations` inexistente (pois a 038 falhou) | idem — `047_operations_repair.sql` |
| `011_active_learning.sql` | DML usa `quality_status` antes de a coluna existir | migration posterior cria a coluna |
| `021_reset_empty_pre_annotations.sql` | DML usa `pre_annotated_at` antes de a coluna existir | migration posterior cria a coluna |

Comportamento do runner: loga como `⚠️ LEGADO CONHECIDO` e continua. O estado final está
correto (verificado pelos asserts de schema).

**Não corrigir essas migrations** — regra C-02 (migrations forward-only). Abrir nova migration
se necessário.

> PEND: unificar o loop de apply do `railway_start.run_migrations()` com o `runner.py` do harness
> para eliminar a duplicação. Não fazer agora — risco de alterar comportamento de produção.

## CI

Job `migrations-harness` em `.github/workflows/ci.yml`. Roda em cada PR e push.
Bloqueia merge se vermelho. Esperado: < 2 min.
