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

## Revisor Adversarial (task-008)

O `reviewer.py` é um **agente READ-ONLY** que avalia cada PR antes do merge, tentando
falsificar os invariantes da constitution. Roda em **Claude Opus** (modelo separado do
implementador) para diversidade de perspectiva.

### Fluxo completo (implementa → revisa → CI → merge)

```
driver.py       →  PR aberto
reviewer.py     →  Opus avalia diff (READ-ONLY, allowedTools restritos)
queue_runner    →  combina veredito + risk + safeguard paths → decisão
                   ├── APPROVE + low + CI verde → auto-merge
                   ├── REQUEST_CHANGES → re-roda driver com findings como feedback
                   │   (até reviewer.max_retries; se persistir → ESCALATE)
                   └── ESCALATE → para, PR aberto para humano
```

### Salvaguardas inegociáveis

- **Separação de funções:** revisor é READ-ONLY — `allowedTools` não contém Edit/Write/merge.
- **Modelo diferente:** Opus para o revisor, Sonnet para o implementador.
- **Anti self-weakening:** PR que toca qualquer `safeguard_path` → ESCALATE automático,
  independente do veredito (não pode auto-aprovar mudança no próprio gate).
- **Fail-safe:** saída do revisor não parseável como JSON → ESCALATE.

### Safeguard paths (config.yaml → reviewer.safeguard_paths)

Qualquer PR que altere estes caminhos → ESCALATE:
- `constitution.md`
- `services/api/tests/edge/` (suíte de invariantes)
- `tools/agent-driver/reviewer.py`, `driver.py`, `queue_runner.py`
- `infra/migrations/`
- `.github/`
- `railway_start.py`

### Flywheel de eval

Quando o revisor propõe testes (`proposed_tests`), eles são salvos em
`runs/proposed-tests-<pr>.md` e, no caso de REQUEST_CHANGES, realimentados ao driver.
Todo gap encontrado vira eval permanente.

---

## Queue Runner (L2) — auto-merge gateado

O `queue_runner.py` executa um **lote ordenado** de specs sequencialmente, com auto-merge
automático apenas para tarefas de baixo risco com CI verde e aprovação do revisor.
Tarefas de segurança param o lote para revisão humana.

### Como rodar

```bash
# Usando queue.txt (um caminho de spec por linha):
echo "tools/agent-driver/tasks/task-foo.md" > tools/agent-driver/queue.txt
python tools/agent-driver/queue_runner.py

# Passando specs diretamente como argumentos:
python tools/agent-driver/queue_runner.py \
  tools/agent-driver/tasks/task-foo.md \
  tools/agent-driver/tasks/task-bar.md
```

### Comportamento por `risk`

| `risk` | O que o queue runner faz |
|--------|--------------------------|
| `low` | Roda o driver → **chama revisor Opus** → se APPROVE: aguarda CI → **auto-mergeia** se CI verde e base = `develop`. Se REQUEST_CHANGES: re-roda driver com feedback (até `reviewer.max_retries`). Se ESCALATE ou safeguard path tocado: para com exit 5. |
| `security` | Roda o driver → **PARA** o lote e loga "aguardando revisão humana" (exit 1). O revisor não é chamado — já é ESCALATE por definição. |
| *(ausente)* | Tratado como `security` (fail-safe). |

### Princípios de segurança (inegociáveis)

- **Default fail-safe:** spec sem `risk` → `security`. NUNCA auto-mergeia.
- Auto-merge só com: `risk: low` + todos os checks = success + base = `develop`.
- **NUNCA** auto-mergeia em `main` ou `staging`.
- **NUNCA** usa `--admin`, bypass de checks ou force-merge.
- Se o número do PR não puder ser extraído do output do driver → para com erro (não adivinha).

### Exit codes do queue_runner

| Code | Significado |
|------|-------------|
| 0 | Lote completo (todas as tasks processadas) |
| 1 | Pausado — task `security` aguarda revisão humana |
| 2 | Pausado — CI falhou numa task `low` |
| 3 | Driver falhou para uma spec |
| 4 | Nenhuma spec fornecida e `queue.txt` ausente |
| 5 | Revisor ESCALOU — PR aberto para revisão humana |

### Convenção de risco (`risk`)

Adicionar ao front-matter da spec:

```yaml
risk: low       # ou: security (default quando ausente)
```

| Valor | Quando usar |
|-------|-------------|
| `security` | Toca auth, multi-tenant, tokens, migrations, dados de cliente, ou qualquer invariante de segurança. **Default quando ausente.** |
| `low` | Leitura pura, docs, display/frontend sem nova lógica de auth, utilitários sem acesso a dados sensíveis. |

> **Regra de ouro:** em dúvida → `security`. O custo de uma revisão extra é menor que um
> auto-merge inadequado.

---

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
