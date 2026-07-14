# ADR-0043 — Renumeração de cinco migrations colidindo no prefixo "052"

**Status:** Aceito
**Data:** 2026-07-14
**Contexto:** validação de migrations pendentes (branch `claude/pending-migrations-validation-ov3aw9`)
**Relacionados:** ADR-0021 (migration-renumber-reconciliation) — mesma classe de bug

---

## Contexto

Uma auditoria de `infra/migrations/` encontrou seis arquivos distintos, todos numerados `052`:

| Arquivo | Mudança |
|---|---|
| `052_branding_tenants.sql` | `tenants.branding` JSONB |
| `052_camera_fps_quality.sql` | `cameras.fps_target`, `cameras.quality_preset` |
| `052_cameras_retention_days.sql` | `cameras.retention_days` + índice |
| `052_custom_roles.sql` | tabela `public.custom_roles` (com `tenant_id` FK) |
| `052_events_search_indexes.sql` | 3 índices em `alerts` |
| `052_model_scenario_config.sql` | `trained_models.scenario_config` + índice |

Todos os seis entraram no repositório no mesmo commit-raiz (squash-import do histórico,
`47515a4`), então o git log não permite reconstruir a ordem real de autoria — provavelmente
seis frentes de trabalho paralelas que escolheram "052" de forma independente, sem checar
arquivos irmãos antes do merge. É a mesma classe de bug que a ADR-0021 já corrigiu uma vez
(colisão entre branches em 050/051) — desta vez é uma colisão dentro do mesmo repositório,
seis-para-um em vez de duas-para-uma.

### Impacto verificado

O runner de produção (`railway_start.py:run_migrations()`, linhas 55–89) faz glob de
`infra/migrations/*.sql` e executa cada arquivo incondicionalmente a cada deploy — sem
rastreamento de versão. A colisão de prefixo não o afeta.

Já `infra/migrations/run_migrations.py` — documentado no CLAUDE.md, `docs/DATABASE.md`,
`services/api/app/infrastructure/database/AGENTS.md` e `tools/agent-driver/AUTORUN.md` como
a ferramenta para bootstrap manual de banco local/dev/teste — rastreia versões aplicadas em
`schema_migrations`, chave `filename.split("_")[0]`.

Reproduzido localmente (Postgres 16 limpo, ambiente isolado deste ADR): dos seis arquivos
`052_*`, apenas `052_branding_tenants.sql` (primeiro em ordem alfabética) teve seu SQL
efetivamente persistido. Os outros cinco tiveram o DDL executado e depois **revertido**: o
script tenta registrar `INSERT INTO schema_migrations (version) VALUES ('052')` após cada
arquivo, e essa inserção colide com a constraint de chave primária (versão "052" já
registrada pelo primeiro arquivo) — o erro de "duplicate key" é tratado pelo mesmo caminho
que trata "já existe" (`_is_idempotent_error`), então o script loga `[SKIP] (objetos já
existem)`, mas na prática o rollback desfaz também o DDL que tinha acabado de rodar com
sucesso. Confirmado por query direta pós-execução: `public.custom_roles` inexistente,
`cameras.fps_target`/`quality_preset` ausentes, os três índices de
`052_events_search_indexes.sql` ausentes, `trained_models.scenario_config` ausente —
apenas `tenants.branding` presente.

`tests/harness/migrations/runner.py` (o harness de CI) não expõe esse bug: por design,
ele nunca usa `schema_migrations` nem chama o script rastreado (ver seu próprio
docstring). CI está e permanece verde independente deste bug — não é evidência de
correção do caminho de bootstrap manual.

---

## Opções avaliadas

### Opção A — Documentar e deixar como está

**Prós:** zero mudança de arquivo.
**Contras:** qualquer bootstrap manual/local/CI-futuro via `run_migrations.py` continua
silenciosamente perdendo `custom_roles`, `cameras.fps_target`/`quality_preset`,
`cameras.retention_days` (via este arquivo — a coluna já existe por outra migration, mas o
índice específico deste arquivo não), os índices de busca de `alerts`, e
`trained_models.scenario_config`.

### Opção B — Renumerar cinco dos seis arquivos (escolhida)

Mesmo raciocínio da ADR-0021: solução durável, forward-only, sem intervenção manual em
banco de produção (o runner de produção nunca dependeu do número). Harness/CI continuam
funcionando sem alteração (glob dinâmico).

**Decisão: Opção B.**

---

## Implementação

`git mv` (histórico preservado via rename detection):

| Antes | Depois |
|---|---|
| `052_branding_tenants.sql` | **mantido como `052`** |
| `052_camera_fps_quality.sql` | `102_camera_fps_quality.sql` |
| `052_cameras_retention_days.sql` | `103_cameras_retention_days.sql` |
| `052_custom_roles.sql` | `104_custom_roles.sql` |
| `052_events_search_indexes.sql` | `105_events_search_indexes.sql` |
| `052_model_scenario_config.sql` | `106_model_scenario_config.sql` |

`052_branding_tenants.sql` foi o escolhido para manter o número por ser o único dos seis
cuja mudança de fato persiste hoje em qualquer ambiente já inicializado via
`run_migrations.py` — mantê-lo evita qualquer drift nesses ambientes. A ordem de
renumeração dos outros cinco é alfabética (arbitrária — a ordem real de autoria não é
reconstruível a partir do git log, ver Contexto).

Nenhum dos seis arquivos referencia outro dos seis (únicas FKs são para `tenants`/`users`,
que já existem desde a migration 001), então não há dependência de ordem entre eles.

**Nota sobre comentários de cabeçalho:** os comentários que auto-referenciam o nome antigo
do arquivo (ex.: `-- 052_camera_fps_quality.sql` como primeira linha) foram deixados
intactos — é o mesmo padrão já estabelecido pela própria ADR-0021, cujos arquivos
renomeados (`067_site_id_attribution.sql`, `069_create_tenant_schema_site_id.sql`) também
mantêm comentários de cabeçalho referenciando os números antigos (052/054) até hoje. Rename
puro, zero edição de conteúdo/lógica.

---

## Comportamento após o fix

| Cenário | Antes | Depois |
|---|---|---|
| `run_migrations.py` em banco novo | aplica só `052_branding_tenants.sql`; os outros 5 objetos nunca são criados | aplica os 6 arquivos (052, 102–106) individualmente — todos os objetos criados |
| `railway_start.py` (produção) | já aplicava todos os 6 (sem rastreamento por versão) | sem mudança de comportamento |
| Harness CI (`tests/harness/migrations/`) | verde (não exercita o bug) | continua verde |

---

## Lição registrada

Reforça o princípio já registrado na ADR-0021: **o próximo número de migration deve
partir do máximo aplicado entre TODOS os ambientes, nunca assumido.** Adendo específico
para esta classe de bug (colisão dentro do mesmo repositório, não só entre branches):

> Antes de mergear uma migration nova, checar colisão de prefixo entre os arquivos já
> presentes no branch de destino:
> ```bash
> ls infra/migrations | sed -E 's/_.*//' | sort | uniq -d
> ```
> Deve retornar vazio.

Esta checagem manual não está automatizada nesta correção (fora do escopo deste ADR —
seria uma segunda melhoria, ex. um passo de CI ou pre-commit hook, a avaliar
separadamente).

---

## Consequências

- Cinco arquivos renumerados (102–106); zero mudança de conteúdo SQL.
- Nenhuma ação em banco de produção necessária — produção nunca rastreou por número.
- Qualquer banco local/efêmero previamente inicializado via `run_migrations.py` com o bug
  presente é descartável (harness/dev/teste); não há dado de produção afetado.
- Próxima migration numerada: **107**.
