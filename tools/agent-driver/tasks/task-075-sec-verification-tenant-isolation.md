# Task 075 — [SEC] `verification/queue` + `review` sem tenant_id (achado #14)

**Status**: PENDING · **Risk**: security (P0 — cross-tenant, verificar)
**Branch**: fix/sec-verification-tenant-isolation (worktree a partir de origin/develop)
**Fonte**: docs/API_CONTRACT_MAP.md achado #14 · **Relaciona**: ADR-0017, C-01.

## Problema (produção)
`GET /api/v1/verification/queue`, `/queue/count` e `POST /api/v1/verification/<id>/review` não têm
`tenant_id` visível na assinatura, contrariando a regra do projeto. Primeiro **confirmar** se o
`VerificationService` filtra internamente; se não, é leitura/edição cross-tenant da fila de revisão.

## Fix
- Se o service não filtrar: adicionar `get_tenant_id()` em queue/count/review. Item de outro tenant no
  `review` → 404. O `human_review` grava o `tenant_id` correto.

## Teste (falha-antes/passa-depois)
- Fila só traz itens do tenant; review cross-tenant → 404; contagem por tenant. (Se já filtrava,
  adicionar o teste de regressão que prova o isolamento e fechar.)

## Aceite
- Isolamento por `tenant_id` confirmado/implementado + teste; ruff+pytest verde; PR develop; STOP.

## Execução — 2026-07-12

**Status**: CONCLUÍDA — vulnerabilidade real confirmada (não era falso-positivo) e corrigida.

### Investigação

Leitura completa de `services/api/app/api/v1/verification/routes.py` (3 handlers) e
`services/api/app/domain/services/verification_service.py` (`VerificationService`, chamado
diretamente pelas rotas via SQL cru — sem repository intermediário). Nenhum dos dois níveis
filtrava por `tenant_id`:

- `get_human_queue()`: `SELECT ... FROM alerts a WHERE a.verification_status = 'needs_human'` —
  sem `AND a.tenant_id = %s`. Vazava a fila `needs_human` de **todos os tenants** para qualquer
  operador autenticado.
- `get_queue_count()`: `SELECT COUNT(*) FROM alerts WHERE verification_status = 'needs_human'` —
  contagem global, não por tenant.
- `human_review()`: `UPDATE alerts SET ... WHERE id = %s AND verification_status = 'needs_human'`
  — sem checar posse por tenant. Um operador do tenant B podia aprovar/rejeitar
  (`approve`/`reject`) um alerta do tenant A via IDOR de escrita — não só leitura.

Achado colateral (fora do escopo de tenant, mas na mesma query): o `LEFT JOIN` usava
`ip_cameras`, tabela renomeada para `cameras` na migration `013_consolidate_cameras.sql`. Contra
o schema real, essa query falhava (`relation "ip_cameras" does not exist`), era capturada pelo
`except Exception` do service e retornava `[]` silenciosamente — ou seja, o endpoint de fila
estava (por acidente, não por design) sempre vazio em produção antes deste fix. Corrigido junto
por estar na mesma linha alterada (anti-padrão já documentado no CLAUDE.md do projeto).

### Fix

- `services/api/app/api/v1/verification/routes.py`: as 3 rotas agora extraem
  `tenant_id = str(get_tenant_id())` do JWT (import de `app.core.auth`) e repassam ao service;
  `except EpiMonitorError: raise` adicionado antes do catch genérico (mesmo padrão de
  `alerts/routes.py`) para que token sem claim `tenant_id` responda 401 via
  `AuthenticationError`, não 500.
- `services/api/app/domain/services/verification_service.py`: `tenant_id` passou a ser parâmetro
  obrigatório em `get_human_queue`, `get_queue_count` e `human_review`; toda query SQL ganhou
  `tenant_id = %s`. `human_review` continua retornando `False` quando 0 linhas são afetadas — a
  rota já mapeava isso para 404, então alerta de outro tenant (rowcount 0 pelo novo filtro) cai
  automaticamente em 404, nunca 200.
- Join corrigido de `ip_cameras` para `cameras`.

### Teste

Não havia "falha antes / passa depois" executável em runtime real porque o join quebrado tornava
a fila sempre vazia (ver achado colateral) — a prova é a nível de SQL/parâmetros, seguindo o
mesmo padrão já usado no repo para o fix cross-tenant equivalente de alertas
(`services/api/tests/security/test_alert_repo_tenant_isolation.py`, P0-03):

- `services/api/tests/security/test_verification_tenant_isolation.py` (novo) — para os 3 métodos
  do `VerificationService`: `tenant_id` obrigatório, SQL contém `tenant_id = %s`, params do
  tenant B nunca incluem o tenant A, e `human_review` com alerta de outro tenant retorna `False`
  (simulando rowcount 0).
- `services/api/tests/unit/domain/test_verification_service.py` — testes existentes atualizados
  para passar `tenant_id` (agora obrigatório); adicionados testes de `TypeError` sem `tenant_id`,
  filtro de `tenant_id` no SQL e regressão do join `cameras`/`ip_cameras`.
- `services/api/tests/unit/api/test_verification_routes.py` — testes novos confirmando que a
  rota extrai `tenant_id` do JWT e o repassa ao service (`test_tenant_id_forwarded_from_jwt`),
  que tenants diferentes repassam seus próprios IDs, que token sem claim `tenant_id` responde 401
  sem chamar o service, e que um `human_review` cross-tenant (mockado para retornar `0` — o
  resultado real do filtro `tenant_id` no WHERE) responde 404, não 200
  (`test_cross_tenant_review_returns_404_not_200`).

### Validação

- `ruff check services/api/` — 0 findings.
- `pytest services/api/tests/ -q --cov=app --cov-fail-under=60` — 3448 passed, 47 skipped
  (baseline pré-existente), cobertura 66.67%.
- Skill `security-review` executada sobre o diff antes do PR (ver corpo do PR para o resumo).
