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
2. Aplica `infra/migrations/*.sql` em ordem lexicográfica (passada 1 — banco limpo) + dump de schema (`pg_dump --schema-only`, normalizado).
3. Aplica novamente (passada 2 — idempotência). Runner deve sair com código 0. Dump de schema de novo.
4. **Diffa os dois dumps** (`schema_diff_check.py`, com baseline). Exit code 0 nas duas passadas prova só que nenhum arquivo lançou erro fatal — não prova que o schema final é o mesmo. Uma migration com DDL condicional dependente de ordem (ou um `DROP ... CASCADE` sem guarda) pode "passar" nas duas passadas e ainda produzir estados diferentes. Delta NOVO fora de `.schema-diff-baseline` = falha do job (C-02 em profundidade).
5. Roda pytest com os asserts de schema.
6. Derruba o container (trap garante cleanup mesmo em falha).

### Achado real ao implementar o diff (2026-08-02)

Rodando o diff pela primeira vez contra o estado real de `infra/migrations/`, ele
**pegou 2 divergências reais e pré-existentes** entre passada 1 e passada 2 (não
hipotéticas — reproduzidas com o harness de verdade, banco limpo):

- `011_active_learning.sql` depende de `module_code`/`quality_status` existirem em
  `training_frames` para o `CREATE INDEX idx_frames_priority` final não falhar. Em
  banco virgem essas colunas ainda não existem (são criadas por `010`/`017`, mas o
  `CREATE INDEX` está no MESMO `cur.execute()` que os `ADD COLUMN` anteriores — um
  erro no fim da transação faz rollback de tudo). Resultado: na passada 1,
  `pre_annotations`, `pre_annotated_at`, `uncertainty_score`, `priority_rank` e
  `idx_frames_priority` **não são criados** (tolerado como erro legado conhecido,
  `runner.KNOWN_LEGACY_ERRORS`). Na passada 2 as colunas de dependência já existem
  (persistidas da passada 1), então a migration roda inteira e cria tudo. Diferente
  de `038`/`039`, não existe uma migration de reparo posterior para `011` — o
  harness nunca verificou isso porque os asserts de schema testam objetos
  específicos, não o diff completo.
- `005_multi_tenant.sql` só cria `idx_cameras_tenant` se a tabela `cameras` já
  existir naquele ponto da sequência — em banco virgem ela ainda se chama
  `ip_cameras` (renomeada só na `013`), então o índice fica de fora da passada 1 e
  aparece na passada 2.
- **`049_counting_deepsort_rebuild.sql` (mais grave):** faz
  `DROP TABLE IF EXISTS public.counting_sessions CASCADE;` incondicional antes de
  recriar a tabela. Isso era intencional como *"exceção consciente à regra
  no-DROP"* para uma limpeza única de tabelas zumbi — mas como produção
  (`railway_start.py::run_migrations()`) reaplica **todo** `infra/migrations/*.sql`
  em **todo** deploy, sem `schema_migrations`, esse DROP CASCADE roda de novo a
  cada redeploy. Na passada 2 do harness ele derruba a FK
  `counting_events_session_id_fkey` (dependente da tabela recriada) — em produção,
  o mesmo padrão apaga o histórico real de `counting_sessions` a cada redeploy do
  serviço `api`. **Achado crítico, fora do escopo deste guard-rail — não corrigido
  aqui; precisa de triagem e uma migration nova dedicada** (forward-only: não editar
  a `049`).

Nenhuma dessas 3 é causada pelo mecanismo de diff em si — são bugs reais, só
nunca detectados porque nada antes comparava o schema resultante das duas
passadas linha a linha.

### Baseline de dívida conhecida (`.schema-diff-baseline`)

**Decisão de triagem (2026-08-02):** os achados 011/005/049 acima vão para
triagem humana — não foram corrigidos aqui (correção = migration de reparo
dedicada, forward-only). Mas o guard-rail não pode nascer vermelho por dívida
antiga, senão bloqueia todos os PRs. Solução: o mesmo padrão do
`.duplicate-prefix-baseline` do check de prefixo.

`schema_diff_check.py` compara as **linhas materiais** do diff (linhas +/- com
DDL real; ignora vazias, comentários SQL e deslocamentos de contexto) com
`.schema-diff-baseline` (8 linhas: 6 `+` das migrations 011/005 — colunas de
active learning e 2 índices que só materializam na 2ª passada — e 2 `-` da 049
— a FK `counting_events_session_id_fkey` derrubada pelo DROP CASCADE):

- diff vazio → **verde** (dívida quitada; remova a baseline);
- diff ⊆ baseline → **verde** (só dívida conhecida);
- qualquer linha nova fora da baseline → **vermelho**, imprimindo apenas o
  delta novo.

A baseline deve **ENCOLHER, nunca crescer** — divergência nova se corrige na
migration nova, não se adiciona à baseline. Remover o arquivo inteiro quando o
ledger de migrations fizer o cutover. Manutenção: rode
`schema_diff_check.py PASS1 PASS2 --print-material` para ver as linhas atuais
ao encolher a baseline.

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
| `test_schema_migrations_created_by_001` | public.schema_migrations existe (criada pela 001) | paridade prod |

## Erro legado conhecido (KNOWN_LEGACY_ERRORS)

A migration `038_operations.sql` cria a tabela `operations` com FK para `ip_cameras`,
que foi renomeada para `cameras` na migration `013_consolidate_cameras.sql`. Em banco virgem,
a 038 falha com `relation "ip_cameras" does not exist`.

Comportamento do runner: loga como `⚠️ LEGADO CONHECIDO` e continua. A migration
`047_operations_repair.sql` recria `operations` com FK correta para `cameras(id)`. O estado
final está correto (verificado pelos asserts de schema).

**Não corrigir a 038** — regra C-02 (migrations forward-only). Abrir nova migration se necessário.

> ~~PEND: unificar o loop de apply do `railway_start.run_migrations()` com o `runner.py` do harness~~
> **FEITO** (mutirão, itens 3.2/3.3/3.4): `railway_start.py` e este `runner.py` agora importam a
> mesma implementação de `infra/migrations/runner_core.py`. Por padrão roda o loop legado
> (byte-a-byte o comportamento anterior de produção); com `MIGRATIONS_LEDGER_CUTOVER=1` roda o
> runner novo com ledger (`public.migrations_ledger`) + `pg_advisory_xact_lock` + falha de boot
> em erro real/checksum divergente. Cutover em produção exige backfill antes
> (`infra/migrations/backfill_schema_migrations.py`) — gate humano (item 3.5 do mutirão).

## CI

Dois jobs em `.github/workflows/ci.yml`:

- **`migrations-hygiene`** — sem banco, roda `scripts/ci/check_migrations_hygiene.py`:
  prefixo `NNN` duplicado fora de `infra/migrations/.duplicate-prefix-baseline`, e
  segundo diretório `migrations/` na raiz do repo (ADR-0010/ADR-0021). Segundos, não minutos.
- **`migrations-harness` (D1)** — passada 1 → dump → passada 2 → dump → diff de
  schema com baseline (C-02, `schema_diff_check.py`) → pytest. Roda em cada PR
  e push. Bloqueia merge se vermelho. Esperado: < 2 min.

> ⚠️ **Estado conhecido (2026-08-02):** o passo de diff de schema, ao ser
> introduzido, revelou divergências reais pré-existentes entre passada 1 e
> passada 2 (ver "Achado real" acima — `011`/`005` são cosméticos, `049` é
> crítico/dados). Elas estão registradas em `.schema-diff-baseline` (o job fica
> **verde** enquanto a divergência for exatamente essa dívida, e vermelho para
> qualquer delta novo). A triagem humana do achado da `049` segue pendente e
> urgente (risco de perda de dados em produção a cada redeploy) — a baseline
> rastreia a dívida, não a quita.
