# Diretriz de Operação — Claude Code (Recognition)

> **Autoridade:** este documento rege COMO o Claude Code atua no projeto. Em caso de conflito,
> a ordem de precedência é: **`constitution.md` (C-01..C-08) → esta diretriz → `CLAUDE.md`**.
> **Data:** 2026-07-14 · **Dono:** Vitor Emanuel (Logikos).

## 0. Princípio regente
O Claude Code tem **total liberdade para investigar, decidir e trazer a solução** — desde que **siga e
respeite as ADRs**, **registre** o que decidiu, **evidencie** o que entregou e **deixe histórico** do que
foi feito. Liberdade de execução, disciplina de registro. Nada de solução sem rastro.

---

## 1. Fluxo de ambientes (inegociável)

**Toda resolução NASCE em `develop`.** Nunca começa em `staging`, nunca em `main`, nunca num checkout `wip/*`.

```
worktree (de origin/develop) → develop → staging (= PRODUÇÃO) → main
```

- Trabalho novo **sempre** num worktree criado a partir de `origin/develop`.
- `develop` = trabalho ativo · `staging` = **produção** (auto-deploy Railway) · `main` = estável + gráfico
  de contribuições.
- `develop→staging` e `staging→main` são **gates humanos**. O Code prepara e para; **quem promove é o Vitor**.
- Merge para `staging`/`main` = **merge commit, NUNCA squash** (runbook
  `docs/runbooks/GITHUB_CONTRIBUTIONS_MERGE_MAIN.md`).
- **Higiene de branch (obrigatória):** após o merge, **excluir a branch** (local e remota) para não poluir o
  repositório — `git branch -d <branch>` + `git push origin --delete <branch>` — e **remover o worktree**
  correspondente (`git worktree remove ...` / `git worktree prune`). Não deixar branches `agent/*`, `fix/*`,
  `chore/*` órfãs vivas depois de mergeadas. As branches de longa duração (`develop`, `staging`, `main`) nunca
  são apagadas.

## 2. Equalização de ambientes (obrigatória após cada atividade que sai de `develop`)

Depois que qualquer atividade sobe de `develop`, os ambientes **precisam ficar equalizados** — nenhuma branch
pode ficar à frente da outra silenciosamente (já houve `staging` 40 commits à frente de `develop`, com prod
correta e as demais atrasadas: **não repetir**).

Procedimento ao fechar uma promoção:
1. `git fetch --all --prune`
2. Medir o delta das três pontas:
   - `git rev-list --count origin/develop..origin/staging` e `origin/staging..origin/develop`
   - `git rev-list --count origin/main..origin/develop` e `origin/develop..origin/main`
3. **Reconciliar** até o conteúdo convergir (portar órfãos únicos, descartar duplicados via `git cherry`).
4. Se sobrar divergência intencional, **documentá-la** (não deixar implícita) em
   `docs/HANDOFF_CONTINUIDADE.md`.
5. Registrar o estado final das pontas no handoff.

> Regra prática: ao terminar, `develop`, `staging` e `main` devem contar a **mesma história de conteúdo**;
> qualquer diferença tem que estar escrita e justificada.

## 3. ADRs — respeitar e registrar

- **Antes de decidir:** ler as ADRs relevantes (`docs/decisions/adr/`). A solução tem que **respeitá-las**.
- **Decisão arquitetural nova ou que muda rumo → vira ADR** (novo arquivo `NNNN-titulo.md`, status
  `Proposta`/`Aceito`).
- **Para contrariar uma ADR existente:** nunca silenciosamente. Criar ADR que a **supersede** e marcar a antiga
  como `Superseded by ADR-XXXX`. O "porquê" fica no ADR.
- **Referenciar o número da ADR** no commit e no corpo do PR quando a mudança se apoia numa decisão.
- Decisões menores (não-arquiteturais) que mudam comportamento → registrar em `docs/DECISIONS.md`.

## 4. PRs — evidência obrigatória

Todo PR precisa **provar** o que fez. Corpo do PR deve conter:
- **Link da task** (`tools/agent-driver/tasks/task-NNN-*.md`) e ADRs referenciadas.
- **Teste falha-antes/passa-depois** para bug/feature (mostrar o vermelho e o verde).
- **Evidência de execução:** saída de `pytest` + `ruff check .` + `tsc --noEmit` (conforme a área);
  para migration, saída do **harness rodado 2x** (idempotência); para smoke, saída do `scripts/smoke_test.sh`.
- **Screenshots antes/depois** para qualquer mudança de UI (usar o harness de front — task-021).
- `risk:security` → **security-review** anexado e **STOP-for-review** (o Code para; humano revisa e mergeia).
- Um PR por área/assunto (não misturar frentes).

## 5. Histórico — sempre deixar rastro

Ao fechar uma atividade, atualizar (o que se aplicar):
- **Status da task** no próprio arquivo `task-NNN-*.md` (PENDING → PR #NN → merged/DEFERRED).
- **`docs/CHANGELOG.md`** — o que mudou, com nº do PR.
- **`docs/HANDOFF_CONTINUIDADE.md`** — estado atual, decisões pendentes, próximo passo (é o ponto de retomada).
- **`docs/DATABASE.md`** — sempre que tocar schema (colunas/tabelas novas).
- **ADR/`DECISIONS.md`** — conforme §3.
- Fila: comentar a linha concluída em `tools/agent-driver/queue.txt`.

## 6. Disciplinas técnicas (herdadas da constitution/CLAUDE.md — valem sempre)

- **C-04:** validar o estado real no código/git/banco. **Nunca confiar em CLAUDE.md nem em memória.**
- **Verificar antes de implementar:** conferir git/gh/tasks se já não foi feito (ex.: a task-066 já estava
  resolvida). Não reconstruir o que existe.
- **Migrations forward-only:** só `CREATE/ADD ... IF NOT EXISTS`; NUNCA `DROP`/`ALTER TYPE`/`DELETE`/`TRUNCATE`;
  **migration e lógica em commits separados**; harness **2x**.
- **Multi-tenant:** toda query filtra o tenant de `get_tenant_schema()`; cross-tenant → **404** (C-01); sem
  fallback silencioso de tenant (ADR-0017).
- **Detector servido = ONNX Apache 2.0** (YOLOX/RF-DETR); **ZERO ultralytics/AGPL** no caminho servido.
- **Sem fallback silencioso** em geral: entrada inválida falha alto (não "chuta" um default).
- Zero f-string com input do usuário em SQL (inclusive `search_path`); zero `print()` no backend
  (`logging.getLogger(__name__)`); `CORS` com origins explícitas; `RTSPUrlValidator` antes de qualquer URL.
- **Conventional commits** (`feat|fix|refactor(scope): ...`).

## 7. Definição de concluído
Compila · zero lint (`ruff`/`tsc`) · testes da área verdes · migration idempotente (2x) quando houver ·
commit no padrão · PR aberto para `develop` **com as evidências da §4** · histórico atualizado (§5) ·
ADRs respeitadas/registradas (§3) · ambientes equalizados se houve promoção (§2) · **branch e worktree
excluídos após o merge (§1)** · **STOP-for-review** em `risk:security` — sem merge/promoção sem gate humano.

---

*Se algo nesta diretriz divergir do código/estado real, o real vence — corrija esta diretriz e registre.*
