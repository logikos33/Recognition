# Contribuindo com o Recognition

Projeto privado (Logikos / Vitor Emanuel). Este guia resume como trabalhar no repo. **A referência completa de
como atuar é [`docs/DIRETRIZ_OPERACAO_CLAUDE_CODE.md`](./docs/DIRETRIZ_OPERACAO_CLAUDE_CODE.md)** — aqui está o essencial.

Precedência de regras: **`constitution.md` (C-01..C-08) → diretriz de operação → `CLAUDE.md`**.

## Setup rápido
```bash
# API local
cd services/api
export SERVICE_TYPE=api DATABASE_URL=... REDIS_URL=... JWT_SECRET_KEY=...
python3 ../../railway_start.py

# Frontend
cd apps/frontend && npm run dev
```
Variáveis em `.env.example`. Nunca commite `.env` nem segredos.

## Fluxo de branch (inegociável)
```
worktree (de origin/develop) → develop → staging (= PRODUÇÃO) → main
```
- Trabalho novo **sempre** em worktree a partir de `origin/develop`. Nunca em `wip/*`.
- `develop→staging` e `staging→main` são **gates humanos**. Merge para staging/main = **merge commit, nunca squash**.
- **Após o merge, exclua a branch** (local + remota) e remova o worktree — não poluir o repo.
- Depois de promover, **equalize os ambientes** (ver diretriz §2): nenhuma branch à frente de outra em silêncio.

## Commits
Conventional Commits: `feat(scope): …`, `fix(scope): …`, `refactor(scope): …`, `docs(scope): …`.
Scopes: `api, frontend, migration, railway, edge, inference, training, landing, cameras, alerts, modules, quality, counting`.

## Antes de abrir PR
- Testes da área afetada verdes · `ruff check .` (back) · `npx tsc --noEmit` (front).
- Migration (se houver): forward-only, **commit separado** da lógica, harness rodado **2x** (idempotência).
- Verifique se **já não foi feito** (git/gh/tasks) — não reconstrua o que existe.

## PR precisa de evidência
Use o template de PR. Todo PR traz: link da task/ADR, teste **falha-antes/passa-depois**, saída de testes/lint
(e do harness 2x se migration), **screenshots antes/depois** para UI. `risk:security` → security-review + STOP-for-review.

## Registro
Ao concluir: atualizar status da task, `docs/CHANGELOG.md`, `docs/HANDOFF_CONTINUIDADE.md`, `docs/DATABASE.md`
(se tocou schema) e ADR/`DECISIONS.md` conforme a decisão. Comentar a linha concluída em `tools/agent-driver/queue.txt`.

## Definição de concluído
Compila · zero lint · testes verdes · migration idempotente (2x) quando houver · PR com evidência · histórico
atualizado · ADRs respeitadas/registradas · branch/worktree excluídos após merge · sem promoção sem gate humano.
