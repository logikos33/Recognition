# Task 072 — [SEC] `quality/demo/seed` destrutivo sem gate de admin (achado #5)

**Status**: CONCLUÍDA (2026-07-12) · **Risk**: security (P0 — apagava dados reais em produção)
**Branch**: fix/sec-quality-demo-seed-admin-gate (worktree a partir de origin/develop)
**Fonte**: docs/API_CONTRACT_MAP.md achado #5 · **Relaciona**: ADR-0017 (tenant isolation), C-01.

## Problema (produção)
`POST /api/v1/quality/demo/seed?force=true` executa `DELETE FROM quality_reworks/quality_pieces/
quality_stations` e recria dados fake. Hoje **qualquer usuário autenticado** do tenant com o módulo
`quality` habilitado pode disparar — **apaga dados reais de produção**.

## Fix
- Exigir **role admin/superadmin** (não só JWT do tenant) no endpoint.
- `force=true` (destrutivo) só com superadmin + confirmação explícita; sem `force`, no-op se já houver dados.
- Considerar mover seed de demo pra trás de feature flag `demo_mode` (ADR-0035), OFF por padrão.

## Teste (falha-antes/passa-depois)
- Usuário comum do tenant → 403 (antes: 200 + apaga). Admin → ok. `force` sem superadmin → 403.

## Aceite
- Rota não destrói dado sem admin; teste prova o 403; ruff+pytest verde; PR pra develop; STOP p/ revisão.

## Execução — 2026-07-12

- **Fix** em `services/api/app/api/v1/quality/routes.py::demo_seed` (linha ~1950):
  - Adicionado `role = get_role()` (via `app.core.auth`) logo após `_require_jwt()`, dentro do
    mesmo bloco `try/except` — token sem claim `role` (tokens antigos) cai no `except` → 401,
    fail-closed.
  - Novo gate: `role not in ("admin", "superadmin")` → 403 antes de qualquer acesso ao pool de
    conexões.
  - `force=true`: exige `role == "superadmin"` (admin de tenant comum **não** pode, mesmo sendo
    admin) → 403 caso contrário; e exige confirmação explícita no body JSON `{"confirm": true}`
    (mesmo padrão já usado em `admin/routes_versions.py::rollback_version`) → 400 se ausente.
    Todos os checks ocorrem **antes** de `pool.get_connection()` — nenhum caminho de negação toca
    o banco.
  - Comportamento pré-existente preservado: sem `force`, é no-op (200, `seeded: false`) se já
    houver bancadas — já estava correto, coberto por teste de regressão.
- **Feature flag `demo_mode` (ADR-0035)**: avaliada e **não implementada** nesta task — o gate de
  role + confirmação explícita já fecha a vulnerabilidade real (achado #5) com uma mudança
  cirúrgica; introduzir a flag exigiria plumbing de config por tenant (fora do escopo do fix de
  segurança). Registrado como sugestão de follow-up no PR, não como débito bloqueante.
- **Teste** `services/api/tests/quality/test_demo_seed_auth.py` (novo, 8 casos) — falha-antes/
  passa-depois confirmado manualmente:
  - Antes do fix (arquivo revertido via `git stash` temporário): 3 testes falham exatamente como
    esperado — operator recebe 200 em vez de 403; admin com `force=true` recebe 200 em vez de 403;
    superadmin com `force=true` sem `confirm` recebe 200 (executa o DELETE) em vez de 400.
  - Depois do fix: 8/8 passando.
- **Validação**: `ruff check services/api/` limpo; suíte completa
  `pytest services/api/tests/` → 3434 passed, 47 skipped, cobertura 66.94% (gate ≥60%).
- **Security review**: skill `security-review` invocada; o pré-processamento automático da skill
  capturou o diff do checkout principal compartilhado (branch errada, cwd padrão da sessão) em vez
  do worktree desta task — revisão refeita manualmente sobre o diff correto (30 linhas em
  `quality/routes.py`). Nenhum achado HIGH/MEDIUM: mudança é puramente hardening de autorização
  fail-closed, sem SQL/eval/deserialização nova, sem entrada de usuário não confiável nos novos
  branches de decisão (role/modules vêm de claims JWT assinadas no login).
