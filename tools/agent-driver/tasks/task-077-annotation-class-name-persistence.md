---
title: "Fix: anotação salva com classe errada (empilhadeira/forklift) — persistir nome do módulo — MIGRATION"
pr_title: "fix(training): persistir class_name/module_code na anotação (corrige rótulo trocado)"
commit_message: "fix(training): anotação passa a gravar o nome da classe escolhida (fim do JOIN em yolo_classes)"
eval: default
budget_minutes: 120
risk: security
requires_migration: true
gate: STOP-for-review (fluxo de pipeline de treino — NÃO entra na queue.txt autônoma)
---

# Tarefa 077 — Anotação salva com a classe errada · MIGRATION + lógica (commits separados)

## Sintoma (relatado pelo Vitor)
Ao rotular um item desenhando a caixa num frame e escolher a classe, a anotação **não** fica salva com o nome
escolhido — reaparece como **"empilhadeira"/forklift** ou uma classe que não existe no modelo.

## Causa raiz (CONFIRMADA no código — C-04)
Dois espaços de numeração de classe incompatíveis:

1. O front carrega as classes de `GET /modules/<code>/classes` → tabela **`module_classes`**, onde `class_id`
   é o índice YOLO 0-based do módulo (EPI `0 capacete … 7 sem_óculos`; fueling `0 caminhão … 2 forklift`).
   Ver `apps/frontend/src/components/AnnotationInterface.jsx:116-136` e o payload em `:361-369`
   (`class_id: activeClass.id`, `class_name: activeClass.name`).
2. O save grava o número **cru** em `frame_annotations.class_id` e **descarta o `class_name`**:
   `services/api/app/infrastructure/database/repositories/annotation_repository.py:84-93`
   (INSERT só de `frame_id, class_id, x_center, y_center, width, height`).
3. Mas `frame_annotations.class_id` é **FK para `yolo_classes.id`** (`infra/migrations/003_training.sql:47`) —
   outra tabela, `id` SERIAL por usuário, sem relação com o índice do módulo.
4. Na leitura o nome é reconstruído por `JOIN yolo_classes c ON a.class_id = c.id`
   (`annotation_repository.py:52-54`). Como os espaços não têm relação, a anotação reaparece com o nome de
   qualquer `yolo_classes.id` colidente (às vezes forklift/empilhadeira de `041_update_fueling_classes.sql`).

**Segundo defeito, agravante:** `services/api/app/domain/services/annotation_service.py:65-83` faz **fallback
silencioso** — se o label não é encontrado, usa `classes[0]["id"]` ou `1` hardcoded. Viola ADR-0017
("sem fallback silencioso"): produz rótulo errado sem erro. Deve **falhar alto**.

## Decisão (Vitor, 2026-07-14): PERSISTIR O NOME DO MÓDULO
A classe que o usuário clicou é a fonte da verdade. Guardar `class_name` (+ `module_code`) na própria anotação;
leitura devolve o nome salvo; **parar de depender do JOIN em `yolo_classes`** (tabela legada nesse fluxo).
`class_id` continua sendo o índice 0-based do módulo (é o que o export YOLO precisa) — mas passa a ser
**interpretado no espaço do módulo**, não como FK de `yolo_classes`.

## Escopo

### Commit 1 — MIGRATION (aditiva, forward-only, SOZINHA no commit)
`infra/migrations/102_frame_annotations_class_name.sql`:
- `ALTER TABLE {tenant_schema}.frame_annotations ADD COLUMN IF NOT EXISTS class_name VARCHAR(100);`
- `ALTER TABLE {tenant_schema}.frame_annotations ADD COLUMN IF NOT EXISTS module_code VARCHAR(50);`
- **PROIBIDO** aqui: DROP, alterar/remover a FK existente, ALTER COLUMN TYPE (a FK legada
  `class_id → yolo_classes(id)` fica como está por ora — ver Risco/Follow-up).
- Rodar o harness **2x** (idempotência). Confirmar se `frame_annotations` é `public` ou `{tenant_schema}`
  antes (ADR-0016) e escrever a migration no escopo certo.

> ⚠️ **A FK atual é NOT NULL REFERENCES yolo_classes(id).** Antes de codar, CONFIRMAR no banco real (RVB) se o
> INSERT de índices de módulo hoje passa por acaso (yolo_classes por usuário com ids colidentes) ou se algo
> pré-cria essas linhas. Se a FK impedir o novo caminho, tratar a remoção/relaxamento da constraint como
> migration **própria e separada** (não neste commit) — decisão de Vitor, pois mexer em constraint é sensível.

### Commit 2 — LÓGICA (backend + frontend)
- **Save** (`annotation_repository.save_batch` + `annotation_handlers` + `annotation_service.save_annotations`):
  passar a gravar `class_name` e `module_code` recebidos no payload. Validar que `class_name` **não é vazio**
  e que `(module_code, class_id)` existe em `module_classes` — senão **422**, sem fallback.
- **Read** (`annotation_repository.get_by_frame`): retornar o `class_name`/`module_code` **armazenados**;
  remover o `JOIN yolo_classes` como fonte do nome (manter compat só se necessário para linhas antigas).
- **Remover o fallback silencioso** de `annotation_service.py:81-83`: label desconhecido → erro explícito
  (422/400) e log `logging.getLogger(__name__)`, nunca `classes[0]` nem `1`.
- **Export YOLO** (`annotation_service._export_yolo_labels`): índice = posição da classe na lista ordenada do
  módulo (`module_classes.class_id`), consistente com o treino. Confirmar que bate com a ordem usada no dataset.
- **Frontend** (`AnnotationInterface.jsx`): o payload já envia `class_name`; garantir leitura usando o nome
  retornado pelo backend (não recomputar por índice). Remover/neutralizar o `DEFAULT_CLASSES` (`:12-19`) que
  usa um TERCEIRO esquema de numeração e pode contaminar antes do `loadClasses()`.

## Multi-tenant / segurança (C-01, ADR-0017)
- Toda query no `{tenant_schema}` de `get_tenant_schema()`; cross-tenant → **404**.
- Zero f-string com input em SQL (nem em `search_path`). Zero `print()`.
- Sem fallback de classe: entrada inválida falha alto.

## Eval (default + harness front 021) — testes DB real (padrão PR #25)
- **Falha-antes/passa-depois:** teste que rotula uma caixa como "Capacete" (EPI class_id 0) e relê →
  ANTES volta com nome trocado (repro do bug); DEPOIS volta "Capacete".
- Salvar N anotações de classes diferentes do mesmo módulo → todas releem com o nome correto.
- `class_name` vazio ou `(module_code,class_id)` inexistente → **422** (sem fallback).
- Frame de outro tenant → **404**; sem JWT → 401.
- Export YOLO: índice de cada linha == `module_classes.class_id` da classe rotulada.
- `pytest` + `ruff check .` + `tsc --noEmit` verdes. Harness de migration **2x** verde.

## Arquivos
- `infra/migrations/102_frame_annotations_class_name.sql` (commit 1, sozinho)
- `services/api/app/infrastructure/database/repositories/annotation_repository.py`
- `services/api/app/domain/services/annotation_service.py`
- `services/api/app/api/v1/training/annotation_handlers.py`
- `apps/frontend/src/components/AnnotationInterface.jsx`
- testes novos (backend + front)
- `docs/DATABASE.md` (registrar as 2 colunas novas)

## Risco / Follow-up (fora desta task)
- A FK legada `class_id → yolo_classes(id)` continua existindo. Se a investigação do banco mostrar que ela
  atrapalha, abrir **task-079** só para relaxar/remover a constraint (migration própria). Avaliar depredação
  da tabela `yolo_classes` no fluxo de anotação (parece legada) — decisão separada.
- Backfill de anotações antigas (linhas sem `class_name`) — decidir se reprocessa ou deixa NULL com leitura
  tolerante. Não bloqueia o fix do bug novo.

## Checkpoint
- **STOP-for-review humano** (fluxo de pipeline de treino, não a queue.txt). Migration e lógica em **PRs/commits
  separados**. `risk:security` → PARA para revisão. Confirmar estado do banco RVB **antes** do commit 2.

## Execução — 2026-07-14

Passo 0 (C-04) confirmou empiricamente, contra Postgres local recém-migrado (sem acesso ao banco real —
ver nota na task-079), que a FK **impede o caminho novo**: `class_id=0` nunca satisfaz a FK sob nenhuma
circunstância (SERIAL começa em 1); `class_id` 1-7 dependem de colisão histórica não-determinística. Isso
gerou a **task-079** (remoção da FK obsoleta, `DROP CONSTRAINT` — exceção explícita a C-02, autorizada
nesta sessão). Ver `task-079-frame-annotations-class-id-fk-relax.md` para o detalhamento. Migrations 102
(este arquivo) e 103 (task-079) aplicadas em commits separados; lógica (Commit 2) implementada em seguida.
