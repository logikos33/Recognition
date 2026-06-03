# Agent Driver — Fase D3

Driver headless que orquestra o Claude Code (`claude -p`) numa tarefa fechada, ponta a ponta,
sem copy-paste. Lê uma spec, monta contexto, chama o modelo, roda a eval, faz loop com retry,
checa guard-rails e abre PR pra `develop`. **Nunca mergeia, nunca toca `main`, nunca força push.**

Nível **L1**: humano só revisa o PR.

## Pré-requisitos

- Rodar a partir da raiz do repo. O driver assume CWD do projeto.
- `gh` autenticado (`gh auth status`).
- Claude Code CLI no PATH (`claude --version`).
- Docker em execução (necessário pra eval `harness`).
- Python 3.11+ com `pyyaml` (já presente no projeto).

## Como rodar

```bash
# A partir da raiz do repo:
git checkout -b feature/<nome-da-tarefa>
python tools/agent-driver/driver.py tools/agent-driver/tasks/<spec>.md

# Modo seguro pra inspecionar antes do PR:
python tools/agent-driver/driver.py tools/agent-driver/tasks/<spec>.md --dry-run
```

Saída de auditoria por execução: `tools/agent-driver/runs/<timestamp>.log` (gitignored).

## O que o driver faz

1. **Lê a spec** (markdown com front-matter YAML opcional: `eval`, `title`, `commit_message`).
2. **Monta o prompt** injetando: `constitution.md`, `git ls-files`, `git diff HEAD`, e o body da spec.
3. **Chama `claude -p`** com `--permission-mode acceptEdits` e `--allowedTools` da `config.yaml`
   (Read/Edit/Write + Bash restrito a prefixos seguros). **Não** usa `--dangerously-skip-permissions`.
4. **Roda a eval** declarada na spec (`default` ou `harness`).
5. **Loop com retry** (até `max_retries`): se a eval vermelha, reinjeta o output do erro.
6. **Guard-rail** antes de qualquer `git push`:
   - aborta se branch atual ∈ `protected_branches` (default: `main`);
   - aborta se o diff toca `protected_paths` (default: `infra/migrations/`, `.github/workflows/`, `railway_start.py`).
7. **Commit + `gh pr create --base develop`**. NUNCA `gh pr merge`.
8. **Budget**: para se exceder `budget_minutes` no `config.yaml`.

## O que o driver NÃO faz

- Não mergeia PR. Humano revisa e aprova.
- Não cria branch — a sessão humana cria antes de invocar.
- Não roda contra produção/staging. Eval `harness` é Postgres efêmero local.
- Não usa `--dangerously-skip-permissions`. Allowlist é o trilho.
- Não toca `main`, não faz force-push, não toca `infra/migrations/*.sql` já aplicadas
  (qualquer um desses pára o driver com exit ≠ 0).

## Specs de tarefa

Em `tasks/`:

- `_TEMPLATE.md` — modelo para criar novas tarefas.
- `task-001-harness-final-state-assert.md` — dogfood: adicionar asserts ao harness
  provando que as migrations toleradas como legadas (038/039) autocorrigem.

Para criar uma nova spec, copiar `_TEMPLATE.md`, preencher os campos do front-matter
(principalmente `eval`) e o objetivo.

## Limites de segurança (resumo)

| Trilho | Onde | O que protege |
|---|---|---|
| `--allowedTools` | `config.yaml` → `allowed_tools` | Limita comandos shell por prefixo |
| `protected_branches` | `config.yaml` → `guard_rails` | Nunca commitar/empurrar em `main` |
| `protected_paths` | `config.yaml` → `guard_rails` | Nunca tocar migrations aplicadas / CI |
| `budget_minutes` | `config.yaml` | Para o loop antes de gastar muito |
| `gh pr merge` | NÃO está na allowlist | Driver não mergeia (sequer tenta) |
| `.claudeignore` | raiz do repo | `.env`, segredos, storage, models, venvs |

## Exit codes

| Code | Significado |
|---|---|
| 0 | Eval verde + PR aberto (ou `--dry-run` ok) |
| 2 | Spec não encontrada |
| 3 | Budget de tempo estourado |
| 4 | Eval falhou após `max_retries` |
| 5 | Guard-rail abortou push (branch ou path protegido) |
| 6 | Commit/push/PR falhou |

## Dogfood

Depois que este PR (o driver) for mergeado em `develop`:

```bash
git checkout develop && git pull
git checkout -b feature/harness-task-001
python tools/agent-driver/driver.py tools/agent-driver/tasks/task-001-harness-final-state-assert.md
# → claude -p edita test_migrations_harness.py, roda run.sh, abre PR sozinha.
```
