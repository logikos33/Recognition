# Estratégia de Testes

> Fontes verificadas nesta versão: `.github/workflows/ci.yml`, `.github/workflows/security-scan.yml`,
> `services/api/pyproject.toml`, `services/api/tests/conftest.py`, `services/api/tests/integration/conftest.py`,
> `services/api/tests/security/`, `tests/harness/migrations/`, `apps/frontend/vitest.config.ts`,
> `apps/frontend/playwright.config.ts`, `tools/agent-driver/tasks/task-021-frontend-test-harness.md`,
> `constitution.md` (C-01, C-02, C-04, C-08). Não usar CLAUDE.md como fonte de verdade de comandos —
> pode estar desatualizado; em caso de divergência, este documento segue o que foi lido diretamente do repo.

## 1. Pirâmide de testes

O projeto tem quatro camadas, sem mock de banco na maior parte delas (ver seção 2):

| Camada | Onde vive | O que valida | Roda contra |
|---|---|---|---|
| Unit (backend) | `services/api/tests/unit/` | Funções e classes isoladas (domain, core, infra) | Mocks (`mock_db_pool`, `mock_storage` em `services/api/tests/conftest.py`) |
| Integration (backend) | `services/api/tests/integration/`, `services/api/tests/quality/`, `services/api/tests/admin/` | Rotas Flask fim-a-fim (`client` fixture) e repositórios contra SQL real | App Flask real (`create_app("testing")`) com `DatabasePool` real; alguns testes ainda fazem `patch()` da camada de serviço quando o objetivo é testar só o handler HTTP |
| Segurança / tenant isolation | `services/api/tests/security/` | Isolamento cross-tenant (C-01), invariantes de schema edge, permission gates | Helpers dedicados (`_helpers_tenant.py`) + Postgres real via `HARNESS_DATABASE_URL`/DB do job |
| Migrations harness (D1) | `tests/harness/migrations/` | Migrations aplicam limpo e são idempotentes (C-02), asserts de schema pós-migração | Postgres efêmero real (`docker-compose.harness.yml`, porta 55432) |
| Frontend unit/componente | `apps/frontend/src/test/components/` | Render, estados de loading/erro, lógica de serviço (Vitest + React Testing Library + jsdom) | jsdom, sem backend |
| Frontend e2e / smoke | `apps/frontend/src/test/e2e/` | Fluxos de UI ponta-a-ponta em navegador real (Playwright, projeto `chromium`) | App servida via `vite --port 3001` (webServer do Playwright), sem depender de API real |
| Outros runners cobertos no CI | `pre-annotation-service/tests/`, `training/vast/test_remote_train.py` | Suíte do serviço de pré-anotação (conexões mockadas) e testes do runner remoto de treino (Vast.ai) | Mocks — sem dependência de torch/ML no CI |

Não existe (ainda) um diretório de e2e visual dedicado tipo `src/test/e2e/visual-audit/` neste worktree — os specs de e2e atuais são
`smoke.spec.ts`, `scenario-editor.spec.ts`, `sites-health.spec.ts`, `task-063-visual.spec.ts` e `task-078-visual.spec.ts`, todos em
`apps/frontend/src/test/e2e/`.

## 2. Política "DB real, não mock"

O padrão do projeto — referenciado em várias tasks (`tools/agent-driver/tasks/task-016-*.md`, `task-017-*.md`, `task-018-*.md`,
`task-022-*.md`, `task-024-*.md`, `task-040-*.md`, `task-043-*.md`, `task-045-*.md`) como **"padrão PR #25"** — é: testes de
repositório/integração que dependem de comportamento real do Postgres (agregações, `FILTER`/`DISTINCT ON`, isolamento de
`tenant_id`, RLS/schema) rodam contra um **Postgres real**, não contra um mock de cursor. Não foi possível localizar o PR #25
em si neste worktree (é referência histórica citada nas specs de task); tratamos a convenção como já praticada e observável
diretamente no código de teste e no CI, não como afirmação sobre o conteúdo daquele PR específico.

Evidência concreta no repo:

- `services/api/app/config.py` (`TestingConfig.DATABASE_URL`) cai para `DATABASE_TEST_URL` ou `DATABASE_URL` do ambiente — ou
  seja, a fixture `app`/`client` (definida em `services/api/tests/conftest.py`) inicializa um `DatabasePool` **real** via
  `_init_database_pool()` (`services/api/app/__init__.py`) sempre que há uma `DATABASE_URL` no ambiente, como acontece no job
  `pytest` do CI.
- `services/api/tests/integration/conftest.py` (usado por `test_camera_create_search_path.py`,
  `test_compliance_report_aggregation.py`, `test_liveness_time_gate.py`, `test_rvb_operation_types.py`, `test_scenario_api.py`
  etc.) conecta via `psycopg2` direto em `INTEGRATION_DATABASE_URL` ou `HARNESS_DATABASE_URL`, cria um tenant efêmero e faz
  `DELETE ... CASCADE` no teardown. Se nenhuma das duas variáveis estiver setada, os testes são pulados (`pytest.skip`) — hoje
  o job `pytest` do CI **não** exporta `INTEGRATION_DATABASE_URL`/`HARNESS_DATABASE_URL` (só `DATABASE_URL`), então essa
  sub-suíte específica de integração roda localmente/harness, não automaticamente nesse job.
- `services/api/tests/security/` usa Postgres real via helpers de tenant para provar isolamento cross-tenant (C-01).
- Only `services/api/tests/unit/` e `services/api/tests/quality/` usam mock explícito de pool/cursor
  (`mock_db_pool`, `mock_pool` em `services/api/tests/quality/conftest.py`) — por design, para testar lógica isolada sem custo
  de I/O.

### Como rodar com banco real localmente

Opção A — `docker-compose.dev.yml` (sobe Postgres 15 + Redis + api + inference + frontend):

```bash
docker compose -f docker-compose.dev.yml up -d postgres redis
export DATABASE_URL=postgresql://recognition:recognition@localhost:5432/recognition_dev
export REDIS_URL=redis://localhost:6379
export JWT_SECRET_KEY=dev-secret-key-change-in-production-32
cd services/api && python -m pytest tests/ -v --tb=short -q
```

Opção B — Postgres efêmero do harness de migrations (mesma base de dados usada pelos testes de integração via
`HARNESS_DATABASE_URL`):

```bash
bash tests/harness/migrations/run.sh
# sobe postgres:15-alpine efêmero na porta 55432 (tmpfs), roda as 2 passadas + pytest, e derruba tudo no final
```

Para rodar os testes de `services/api/tests/integration/` (os que usam `pg_pool`/`pg_raw`/`tenant_id`) contra esse mesmo
banco, exporte `HARNESS_DATABASE_URL` (ou `INTEGRATION_DATABASE_URL`) apontando para uma instância real antes de chamar o
pytest desses módulos.

## 3. Harness de frontend (Vitest + RTL + Playwright)

Formalizado pela `task-021-frontend-test-harness.md` (`tools/agent-driver/tasks/`). Configuração real encontrada em
`apps/frontend/`:

- `vitest.config.ts`: `environment: 'jsdom'`, `setupFiles: ['./src/test/setup.ts']`, exclui `src/test/e2e/**` (não confundir
  suíte de componente com a de e2e).
- `playwright.config.ts`: `testDir: './src/test/e2e'`, projeto único `chromium`, `webServer` sobe `vite --port 3001
  --strictPort` e reusa servidor existente fora do CI.
- Scripts em `apps/frontend/package.json`: `"test": "vitest run"` e `"test:e2e": "playwright test"`.
- Testes de componente hoje em `apps/frontend/src/test/components/` (ex.: `StatusBadge.test.tsx`, `CameraPlayer.test.tsx`,
  `ScenarioEditor.test.tsx`, `EdgeFleetPanel.test.tsx`, `edgeService.test.ts`, `labels.test.ts`).
- Testes e2e hoje em `apps/frontend/src/test/e2e/` (`smoke.spec.ts`, `scenario-editor.spec.ts`, `sites-health.spec.ts`,
  `task-063-visual.spec.ts`, `task-078-visual.spec.ts`).

Como rodar localmente:

```bash
cd apps/frontend
npm ci --legacy-peer-deps
npx tsc --noEmit          # type check
npm run test              # vitest run — componentes
npx playwright install --with-deps chromium   # só na 1ª vez / máquina nova
npm run test:e2e          # playwright test — e2e smoke, sobe seu próprio dev server
```

No CI, o job `frontend` (`.github/workflows/ci.yml`) faz exatamente essa sequência (tsc → `npm run test` → instala browsers
do Playwright com cache → `npm run test:e2e`), separado do job `tsc` (que roda só o type check, sem os outros testes).

## 4. Meta de cobertura

O gate real de cobertura hoje é **`--cov-fail-under=60`**, aplicado de duas formas redundantes:

- CLI do job `pytest` em `.github/workflows/ci.yml`: `pytest services/api/tests/ ... --cov=app --cov-report=term-missing
  --cov-fail-under=60 --cov-config=services/api/pyproject.toml`.
- `[tool.pytest.ini_options].addopts` em `services/api/pyproject.toml` também trai `--cov-fail-under=60` (com o comentário
  no próprio arquivo: *"Meta aspiracional: 60%. CI usa baseline atual via workflow (.github/workflows/ci.yml). Subir
  gradualmente: 30 → 40 → 50 → 60."*).

Ou seja, o número travado no CI **hoje** é 60%, mas o comentário no `pyproject.toml` deixa claro que esse valor é a meta
final de uma escalada gradual — não necessariamente a cobertura real medida em todo o código a qualquer momento (o
`[tool.coverage.run]` do mesmo arquivo `omit`e explicitamente tasks Celery, migrations e dataclasses de domínio do cálculo).

Separadamente, o `CLAUDE.md` do worktree traz um débito técnico anotado na sprint 2026-04-13: **"Cobertura de testes ~55%"**
com meta de 60% e áreas descobertas citadas (`validation_handlers`, `versioning`, `training dispatch`). Esse número (~55%)
é uma nota de débito técnico de sprint, não o valor do gate de CI — trate-o como snapshot histórico a confirmar rodando
`pytest --cov` localmente, não como garantia atual.

## 5. Como rodar tudo localmente

```bash
# Backend — lint
cd services/api && python -m ruff check .

# Backend — testes com cobertura (precisa de Postgres/Redis reais, ver seção 2)
cd services/api && python -m pytest tests/ -v --tb=short -q \
  --cov=app --cov-report=term-missing --cov-fail-under=60 --cov-config=pyproject.toml

# Suíte do pre-annotation-service (mockada, sem deps de ML)
pytest pre-annotation-service/tests/ -v --tb=short -q -p no:cacheprovider --override-ini addopts=

# Testes do runner remoto de treino (Vast.ai) — fake mínimo, sem torch
pytest training/vast/test_remote_train.py -v --tb=short -q

# Frontend — type check + unit + e2e
cd apps/frontend && npx tsc --noEmit && npm run test && npm run test:e2e

# Migrations harness (D1) — idempotência (C-02)
bash tests/harness/migrations/run.sh

# Secrets (paridade com o job security-scan.yml / gitleaks)
gitleaks detect --source . -v
```

## 6. Regras do `constitution.md` que os testes devem respeitar

- **C-01 — Multi-tenant sempre**: toda tabela nova tem `tenant_id`, toda query filtra por ele. Testes de
  `services/api/tests/security/` (via `_helpers_tenant.py`, `make_two_tenant_contexts` +
  `assert_response_only_contains_tenant`) são o mecanismo concreto que prova isso — qualquer endpoint novo sob
  `/api/v1/edge/` (e por convenção, qualquer endpoint multi-tenant) deve ganhar ao menos um teste cross-tenant nesse padrão.
- **C-02 — Migrations forward-only e idempotentes**: apenas `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` /
  `CREATE INDEX IF NOT EXISTS`; nunca `DROP`/`DELETE FROM`/`TRUNCATE`/`ALTER COLUMN TYPE`. O harness de
  `tests/harness/migrations/` roda toda a sequência de `infra/migrations/*.sql` duas vezes (passada 1 = banco limpo,
  passada 2 = idempotência) e falha o CI (`migrations-harness` job) se a 2ª passada produzir um erro não conhecido como
  legado (lista `KNOWN_LEGACY_ERRORS` em `runner.py`, documentada também no "Adendo" do `constitution.md`).
- **C-04 — Ver schema real antes de assumir**: nunca inferir schema a partir de migrations antigas/memória; em caso de
  dúvida, consultar `information_schema` ou rodar `bash tests/harness/migrations/run.sh` contra um banco real. Testes de
  integração (`services/api/tests/integration/`, `services/api/tests/security/`) seguem esse princípio por construção —
  rodam contra SQL real em vez de assumir o retorno de um mock.
- **C-08 — Eval-driven para mudanças de schema**: toda nova migration ou `CREATE OR REPLACE FUNCTION` passa pelo harness D1
  antes do merge; se a 2ª passada falhar, a mudança volta. Nunca editar uma migration já aplicada — nova migration numerada
  para corrigir (ver também a nota de memória sobre "migrations append-only").

## 7. Gaps conhecidos (não corrigidos por este documento)

- O job `pytest` do CI não define `INTEGRATION_DATABASE_URL`/`HARNESS_DATABASE_URL` — os testes de
  `services/api/tests/integration/*` que dependem dessas variáveis (`test_camera_create_search_path.py`,
  `test_compliance_report_aggregation.py`, `test_liveness_time_gate.py`, `test_rvb_operation_types.py`,
  `test_scenario_api.py`) ficam `pytest.skip`ados nesse job específico; rodam com sinal verde no harness de migrations ou
  localmente com a variável exportada (seção 2).
- Não há e2e visual dedicado (`visual-audit/`) neste worktree — apenas os specs listados na seção 1.
- Cobertura publicada/badge no CI ainda não existe (`docs/BENCHMARK_BOAS_PRATICAS.md` § 5 já lista essa lacuna como P3).
