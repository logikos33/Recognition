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
# A partir da raiz do repo, com working tree LIMPO e na branch base (default: develop):
git checkout develop && git pull
python tools/agent-driver/driver.py tools/agent-driver/tasks/<spec>.md

# Modo seguro pra inspecionar antes do PR:
python tools/agent-driver/driver.py tools/agent-driver/tasks/<spec>.md --dry-run
```

O driver **cria sozinho** uma branch `agent/<stem-da-spec>-<timestampUTC>` a partir de
`develop`, e todo trabalho do claude + commit acontece nela. Você nunca precisa criar
branch antes.

**Pré-condição de tree estrita:** a working tree deve estar **totalmente limpa** antes de
rodar — sem arquivos modificados, staged OU untracked não-gitignored. Se não estiver,
o driver aborta com exit 7. Arquivos gitignored não bloqueiam (não aparecem no porcelain).

Saída de auditoria por execução: `tools/agent-driver/runs/<timestamp>.log` (gitignored).

## O que o driver faz

1. **Isola a execução** antes de qualquer edit:
   - exige working tree **limpo** (`git status --porcelain` vazio);
   - exige branch atual = `base_branch` (default `develop`);
   - cria `agent/<stem-da-spec>-<timestampUTC>` via `git checkout -b`.
   Assim é impossível commitar direto em `develop`/`main`/`staging`.
2. **Lê a spec** (markdown com front-matter YAML opcional: `eval`, `title`, `commit_message`).
3. **Monta o prompt** injetando: `constitution.md`, `git ls-files`, `git diff HEAD`, e o body da spec.
4. **Chama `claude -p`** com `--model <config.model>`, `--permission-mode acceptEdits` e
   `--allowedTools` da `config.yaml` (Read/Edit/Write + Bash restrito a prefixos seguros).
   **Não** usa `--dangerously-skip-permissions`. **Não** dá `git add`/`git commit` ao claude.
5. **Roda a eval** declarada na spec (`default` ou `harness`).
6. **Loop com retry** (até `max_retries`): se a eval vermelha, reinjeta o output do erro.
7. **Guard-rail** antes de qualquer `git push`:
   - aborta se branch atual ∈ `protected_branches` (default: `main`, `develop`, `staging`);
   - aborta se o diff toca `protected_paths` (default: `infra/migrations/`, `.github/workflows/`, `railway_start.py`).
8. **Commit + `gh pr create --base <base_branch>`** (head = `agent/*`). NUNCA `gh pr merge`.
9. **Budget**: para se exceder `budget_minutes` no `config.yaml`.

## O que o driver NÃO faz

- Não mergeia PR. Humano revisa e aprova.
- Não commita em `develop`/`main`/`staging` — cria `agent/*` antes de tocar arquivos.
- Não roda contra produção/staging. Eval `harness` é Postgres efêmero local.
- Não usa `--dangerously-skip-permissions`. Allowlist é o trilho.
- Não dá `git add`/`git commit` ao claude — só ferramentas de leitura de contexto.
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
| 7 | Working tree sujo (commit/stash antes de rodar) |
| 8 | Branch atual ≠ `base_branch` (rode `git checkout develop` primeiro) |
| 9 | Falha ao criar a branch de trabalho `agent/*` |

## Dogfood

Depois que este PR (o driver) for mergeado em `develop`:

```bash
git checkout develop && git pull
python tools/agent-driver/driver.py tools/agent-driver/tasks/task-001-harness-final-state-assert.md
# → driver cria agent/task-001-...-<ts>, claude -p edita test_migrations_harness.py,
#    roda run.sh, abre PR sozinha pra develop.
```
