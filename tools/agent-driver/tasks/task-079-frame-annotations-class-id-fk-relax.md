# Task 079 — [SEC] FK obsoleta bloqueia fix da task-077 (frame_annotations.class_id → yolo_classes)

**Status**: CONCLUÍDA (2026-07-14) · **Risk**: security (P0 — bug de dados/persistência, exceção
constitucional à política de migrations)
**Branch**: fix/task-077-annotation-class-name-persistence (worktree a partir de origin/develop —
mesma branch da task-077, dependência direta)
**Fonte**: Passo 0 da task-077 (`tools/agent-driver/tasks/task-077-annotation-class-name-persistence.md`)
— achado durante a investigação obrigatória de schema real (C-04) antes de codar a task-077.
**Relaciona**: task-077, ADR-0017 (sem fallback silencioso), constitution.md C-02 (migrations)
e C-04 (verificar schema real).

## Problema (confirmado empiricamente, não por inferência)

`frame_annotations.class_id INTEGER NOT NULL REFERENCES yolo_classes(id) ON DELETE CASCADE`
(`infra/migrations/003_training.sql:47`) referencia uma tabela **semanticamente errada** para o
fluxo de anotação atual. O frontend (`AnnotationInterface.jsx`) carrega classes de
`GET /api/modules/<code>/classes` → tabela `module_classes` (índice 0-based *por módulo*: EPI
`0..7`, fueling `0..4` — `infra/migrations/009_module_classes.sql`) e envia esse índice como
`class_id` no payload de save. `yolo_classes.id` é `SERIAL` **global ao sistema inteiro** (não por
tenant, não por módulo), populado apenas via `POST /api/classes` (modal "+ Nova Classe" do próprio
`AnnotationInterface.jsx` — rota viva, `training/routes.py:128-152`). Os dois espaços de numeração
não têm nenhuma relação.

### Evidência empírica (ambiente sandboxed sem acesso ao Postgres real da RVB — ver nota abaixo)

Sem `DATABASE_URL` nem daemon Docker disponíveis neste ambiente para consultar o banco real,
subi um Postgres 16 local (`postgresql-16` já instalado no container), rodei as 101 migrations em
ordem (mesma lógica do `railway_start.py::run_migrations`) e testei o INSERT real:

```sql
-- Tenant/usuário/vídeo/frame novos, ZERO linhas em yolo_classes (cenário: tenant que nunca usou
-- o modal "+ Nova Classe")
INSERT INTO frame_annotations (frame_id, class_id, x_center, y_center, width, height)
VALUES ('<frame>', 0, 0.5, 0.5, 0.2, 0.2);
-- ERROR: insert or update on table "frame_annotations" violates foreign key constraint
--        "frame_annotations_class_id_fkey"
-- DETAIL: Key (class_id)=(0) is not present in table "yolo_classes".
```
Repetido para `class_id` 1 a 7 (todas as 8 classes EPI): **todas falham** com o mesmo erro nesse
cenário (tenant sem `yolo_classes` pré-existentes).

**Achado 1 — estrutural, independe de qualquer dado da RVB**: `yolo_classes.id` é `SERIAL`
(começa em 1). `class_id=0` ("Capacete", primeira classe EPI) **nunca** pode satisfazer essa FK,
para nenhum tenant, em nenhum momento — é matematicamente impossível sob o schema atual.

**Achado 2 — não-determinístico, depende de histórico**: para `class_id` 1-7 "funcionar" (mesmo
que com nome errado, reproduzindo o bug relatado — "empilhadeira"), é necessário que alguém, em
qualquer tenant do sistema (a FK não verifica tenant), já tenha criado custom classes suficientes
via `POST /api/classes` para que algum `yolo_classes.id` colida por acaso com o índice do módulo
enviado. Não é possível confirmar o estado exato da RVB sem acesso ao banco de produção/staging
real — mas o mecanismo estrutural bate exatamente com o sintoma relatado (nome trocado, não erro).

**Achado 3 — a suíte de testes atual não cobre isso**: todos os testes de anotação existentes
(`tests/unit/domain/test_annotation_service*.py`, `tests/unit/infrastructure/test_annotation_repository_tenant.py`)
usam `AnnotationRepository`/`AnnotationService` mockados (MagicMock) — nenhum bate no Postgres real,
então esse bug nunca apareceria em CI, só em uso real contra o banco.

### Por que bloqueia a task-077 como especificada

A validação nova da task-077 (`(module_code, class_id)` existe em `module_classes` → senão 422)
**passa** para `class_id` 0-7 (são entradas válidas ali). O INSERT subsequente bateria na mesma FK
quebrada, produzindo `psycopg2.errors.ForeignKeyViolation` não tratado (500 cru) em vez do save
funcionar — ou seja, do jeito que a task-077 foi especificada, o fix não resolve "Capacete" nunca
(sempre 500) e continua não-determinístico para as demais classes.

## Nota sobre acesso ao banco (C-04)

Este ambiente de execução é um container efêmero sem `DATABASE_URL` configurada e sem daemon
Docker ativo — não há caminho de rede para o Postgres real de staging/produção/RVB a partir daqui.
A verificação acima foi feita contra um Postgres local recém-provisionado, migrado do zero com o
histórico completo de `infra/migrations/`, o que confirma o **comportamento estrutural do schema**
com certeza (Achado 1 é uma prova matemática, não uma amostra), mas não reproduz o **conteúdo de
dados** específico da RVB (Achado 2). Recomendação: se possível, confirmar contra o banco real de
staging/produção antes do deploy final — mas a natureza estrutural do Achado 1 já é suficiente para
justificar a correção abaixo independentemente do estado de dados de qualquer tenant específico.

## Decisão (autorizada nesta sessão — ver nota de exceção constitucional)

Remover a FK `frame_annotations.class_id → yolo_classes(id)` via `ALTER TABLE ... DROP CONSTRAINT`.
**Não** remove a coluna `class_id`, **não** altera seu tipo, **não** altera `NOT NULL` — ela
continua obrigatória e continua guardando o índice 0-based do módulo (mesma semântica que a
task-077 já assume). Apenas o relacionamento físico com a tabela errada é removido. A validação de
que `(module_code, class_id)` é uma combinação real passa a ser feita em código de aplicação
(camada de serviço, task-077 Commit 2) — não é possível expressar essa validação como FK do
Postgres de qualquer forma, porque `module_classes` não tem hoje um `UNIQUE(module_code, class_id)`
(só `UNIQUE(module_code, class_name)` — `infra/migrations/009_module_classes.sql:14`), e criar essa
constraint nova está fora do escopo mínimo desta correção.

**`yolo_classes` não é removida nem descontinuada nesta task** — o modal "+ Nova Classe"
(`POST/PUT/DELETE /api/classes`) continua funcionando exatamente como antes; só deixa de ter
qualquer relação (correta ou incorreta) com `frame_annotations`. Avaliar a depreciação completa de
`yolo_classes` no fluxo de anotação é decisão separada, não tomada aqui (ver "Risco / Follow-up" na
task-077).

### Exceção constitucional (C-02) — registrada explicitamente

`constitution.md` C-02 permite **apenas** `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`,
`CREATE INDEX IF NOT EXISTS` em migrations; proíbe `DROP` sem exceção declarada.
`tenant_class_service.py` (docstring, achado de revisão adversarial anterior) já documentava que
remover/alterar essa mesma constraint "requer decisão humana explícita (exceção à política) antes
de qualquer migration". Essa exceção foi concedida nesta conversa: o achado foi reportado (task-077
Passo 0, mensagem de STOP), e a instrução recebida foi "pode redigir e continue até resolver" —
autorização explícita para prosseguir com o `DROP CONSTRAINT` como o menor exceção possível
(**apenas a constraint, não a coluna, não a tabela**) necessária para desbloquear a task-077.
Registrado aqui para rastreabilidade; reversível (a FK pode ser recriada em migration futura se a
decisão for revista).

## Escopo

`infra/migrations/103_frame_annotations_drop_class_id_fk.sql` (commit próprio, sozinho):
```sql
ALTER TABLE public.frame_annotations
    DROP CONSTRAINT IF EXISTS frame_annotations_class_id_fkey;
```
Idempotente por natureza (`IF EXISTS`) — testado 2x localmente sem erro na segunda passada.

## Teste (falha-antes/passa-depois)

- **Antes** (migration 102 aplicada, 103 não): INSERT de `frame_annotations` com `class_id=0` em
  tenant sem `yolo_classes` prévias → `ForeignKeyViolation`.
- **Depois** (103 aplicada): mesmo INSERT → sucesso, linha persistida com `class_id=0`,
  `class_name='Capacete'`, `module_code='epi'`.
- Rodar harness de migration 2x (idempotência) — ver `tests/harness/migrations/run.sh`.

## Aceite

- FK removida sem tocar coluna/tabela; INSERT de `class_id=0..7` passa a funcionar independente de
  histórico de `yolo_classes`; harness 2x verde; ruff+pytest verde; PR para `develop`; **STOP** —
  não mergear, não promover para staging/main sem revisão humana (mesma gate da task-077, risco
  compartilhado).

## Execução — 2026-07-14

Ver commits na PR da task-077/078 (branch `fix/task-077-annotation-class-name-persistence`) para o
detalhamento final — este arquivo documenta a decisão e a investigação; o registro de execução
(testes rodados, resultados) fica no corpo da PR para evitar duplicação.
