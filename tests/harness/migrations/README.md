# Harness de Migrations — Fase D1

Primeiro eval do Recognition. Valida que as 54 migrations aplicam corretamente e são idempotentes,
imitando o comportamento do `railway_start.py:run_migrations()` em produção.

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
| `test_no_schema_migrations_table` | public.schema_migrations NÃO existe | paridade prod |

## Erro legado conhecido (KNOWN_LEGACY_ERRORS)

A migration `038_operations.sql` cria a tabela `operations` com FK para `ip_cameras`,
que foi renomeada para `cameras` na migration `013_consolidate_cameras.sql`. Em banco virgem,
a 038 falha com `relation "ip_cameras" does not exist`.

Comportamento do runner: loga como `⚠️ LEGADO CONHECIDO` e continua. A migration
`047_operations_repair.sql` recria `operations` com FK correta para `cameras(id)`. O estado
final está correto (verificado pelos asserts de schema).

**Não corrigir a 038** — regra C-02 (migrations forward-only). Abrir nova migration se necessário.

> PEND: unificar o loop de apply do `railway_start.run_migrations()` com o `runner.py` do harness
> para eliminar a duplicação. Não fazer agora — risco de alterar comportamento de produção.

## CI

Job `migrations-harness` em `.github/workflows/ci.yml`. Roda em cada PR e push.
Bloqueia merge se vermelho. Esperado: < 2 min.
