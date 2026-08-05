# Varredura estática — resolução de tenant sob contexto assumido

> Fecha a lacuna **sistemática** de contexto assumido. Não é um bug pontual: a
> impersonação por tenant (#279) foi adicionada e **só os caminhos que alguém
> exercitou foram corrigidos** (#302 câmeras → #313 frames). Todo repositório
> com escopo de tenant que ninguém abriu ainda era um **404 latente**.
>
> Base da varredura: `origin/develop @ 1776fed`. #313 (`claude/anotacao-tenant-404`,
> `risk:security`) **ainda não mergeado** — cobre a posse de frames/anotação.

## 1. A forma sancionada (fonte única de verdade)

| helper | `file:line` |
|---|---|
| `get_tenant_id()` | `services/api/app/core/auth.py:87` |
| `get_tenant_schema()` | `services/api/app/core/auth.py:113` |

Leem os claims `tenant_id` / `tenant_schema` do JWT. **Sem fallback** — levantam
`AuthenticationError` (ADR-0017).

**Como o contexto assumido funciona** — `assume_tenant_context`
(`app/api/v1/admin/tenant_context_routes.py:172-186`): o superadmin faz
`POST /api/v1/admin/tenant-context/tenants/<B>/assume` e recebe um JWT novo onde:

- `identity`/`sub` = **superadmin (tenant de casa A)** → `get_current_user_id()` = **A**
- claim `tenant_id` = **alvo B** → `get_tenant_id()` = **B** ✅
- claim `tenant_schema` = schema de B → `get_tenant_schema()` = schema de B ✅
- `role=superadmin`, `tenant_ctx=True`, `impersonated_by=A`

**Regra mecânica:** qualquer código que escopa/valida posse por
`get_tenant_id()` / `get_tenant_schema()` — encadeados handler → service →
repository como **parâmetro explícito** — está **CORRETO** (honra o contexto
assumido). O bug é derivar o tenant efetivo da **identidade de casa do
usuário**.

## 2. O anti-padrão (o "smoking gun")

```sql
... = (SELECT tenant_id FROM users WHERE id = <user_id>)   -- tenant DE CASA
```

Sob contexto assumido isso devolve **A** (casa do superadmin) mesmo quando o
tenant efetivo é **B**. Foi a causa-raiz de **#302** (live view) e **#313**
(frames). O mesmo vale para derivar o `tenant_schema` da linha do usuário em vez
do claim.

## 3. Classificação exaustiva

### 3.1 Derivações SQL de tenant a partir de `users` (grep de `SELECT tenant_id FROM users` — todas)

| # | `file:line` | método / contexto | área | veredito |
|---|---|---|---|---|
| A | `frame_repository.py:254` | `get_by_id_and_user` (posse, read) | frames | **BUG → corrigido por #313** (fila humana) |
| B | `frame_repository.py:278` | `mark_validated` (posse, read) | frames | **BUG → corrigido por #313** |
| C | `frame_repository.py:22` | `_TENANT_COALESCE` (INSERT tag, 3 níveis) | frames | Fallback latente; a coleta já passa `get_tenant_id()` explícito → OK na prática; área de #313 |
| D | `training_repository.py:62` | `create_job` (INSERT tag) | **treino** | **BUG (write mis-tag)** — corrigido: caller passa `get_tenant_id()` |
| E | `training_repository.py:155` | `create_model` (INSERT tag) | **treino/modelos** | **BUG (write mis-tag → 404 na registry)** — corrigido: caller passa contexto |
| F | `annotation_repository.py:30` | `create_class` (INSERT tag) | anotação/classes | **CORRETO no caminho vivo** — `tenant_class_service` (`annotation_handlers:186-190`) passa `get_tenant_id()`; `COALESCE` só p/ classes legadas NULL |
| G | `model_registry_repository.py:93` | `activate_for_tenant_module` (COALESCE legado NULL) | modelos | **CORRETO** — caller passa `get_tenant_id()`; subselect só p/ `tm.tenant_id` NULL legado |
| H | `versioning.py:54` | `build_dataset_version` **v1** | datasets | **LEGADO/MORTO** — a rota usa `build_dataset_version_v2` (threading correto de `get_tenant_id()`); v1 não é enfileirado |
| I | `admin/routes.py:963,1019,1066,1178` (+ `922`,`1116` c/ colunas extra) | gestão de usuário (target `user_id`) p/ audit | admin | **CORRETO** — `@require_superadmin`, `user_id` é path param do ALVO; tenant p/ log de auditoria, não escopo do caller |

`model_registry_repository.py:67` (`get_for_tenant`) usa a forma JOIN
`COALESCE(tm.tenant_id, u.tenant_id) = %s` — **CORRETO**: o caller
(`registry_handlers` 150/188/263/339/377/424, `model_config_handlers:118`)
sempre passa `get_tenant_id()`; o `u.tenant_id` cobre só linhas legadas NULL.

### 3.2 Resolução de schema

| `file:line` | como resolve | veredito |
|---|---|---|
| `quality/routes.py:53` (`_schema()`) | `get_tenant_schema()` | **CORRETO** (usado em 583/625/907; `run_quality_training.delay(job_id, tenant_schema)`) |
| `auth/routes.py:137` | `user.get("tenant_schema")` no **login** | **CORRETO** — no login o tenant de casa É o contexto |
| `admin/routes.py:640-654` | schema do **tenant alvo** p/ operação admin | **CORRETO** (admin-on-target) |

### 3.3 Blueprints sem `get_tenant_id()`/`get_tenant_schema()` (verificados)

| blueprint | como escopa | veredito |
|---|---|---|
| `videos/` | `get_current_user_id()` (posse por dono) | **CORRETO** — modelo de posse por usuário, consistente com #313 ("frame com vídeo segue via dono") |
| `storage/` | só `/health` + `/test-upload` | **N/A** — sem leitura escopada por tenant |
| `streams/` | `/status` por `current_user_id`; HLS via playback token (#255/#302) | **CORRETO** |
| `chat/` | assistant SSE; `retrieve_context` (pgvector) | **Fora do padrão** — possível escopo RAG cross-tenant, classe distinta (não é derivação casa-vs-assumido) — registrar à parte |
| `auth/` | login | **CORRETO** |

### 3.4 Derivação em Python (linha de usuário → tenant)

`grep` de `get_by_id(...user...)` + tenant só achou `tenant_context_routes.py:166`
(resolve o superadmin p/ `assume` — correto) e `impersonation_routes.py:119`
(resolve o ALVO p/ "ver como" — correto). **Nenhuma** derivação Python de tenant
de casa usada para escopo.

### 3.5 Achado adjacente (fora deste padrão, registrar à parte)

- `quality/routes.py:724` (`/andon`) varre **TODOS** os schemas
  (`SELECT schema_name FROM public.tenants`). Já rastreado em memória
  ("/andon cross-tenant") — **outra classe de bug** (agregação cross-tenant),
  não a derivação casa-vs-assumido desta varredura.

## 4. O que foi corrigido nesta rodada

**Treino/Modelos (D + E)** — a corrente do 404 latente. `fix(training): tag
training jobs/models with request tenant context` (PR separado, área treino):

- `job_handlers.create_job` passa `tenant_id=get_tenant_id()`.
- `training_service.create_job` aceita e repassa `tenant_id` ao repository.
- `socket_bridge._register_trained_model` herda `job["tenant_id"]` (callback
  fora do Flask context → a linha do job é a fonte correta do contexto).
- Testes falha-antes/passa-depois: `test_training_service.py`,
  `test_socket_bridge.py`, e integração `test_model_tag_assumed_tenant.py`
  (Postgres real: modelo taggeado casa A → `get_for_tenant(B)` None = 404;
  taggeado contexto B → visível sob B, invisível a partir de A).

Muda **de onde o tenant vem**, não a regra: cross-tenant continua **404**
(C-01), sem fallback silencioso de tenant (ADR-0017).

**Fora de escopo desta rodada (por design):**

- **Frames (A, B, C)** — território de **#313** (fila humana, `risk:security`).
  Não tocado aqui para não conflitar.
- **`versioning.py` v1 (H)** — código morto (v2 já correto). Registrado; não
  editado (remoção é limpeza separada).
- **`annotation_repository.create_class` (F)** — caminho vivo já correto.

## 5. A guarda que impede a 4ª vez

`services/api/tests/security/test_no_home_tenant_scoping.py` — auditoria
estática que **falha no CI** quando **qualquer** repository introduz
`SELECT tenant_id FROM users` como tenant de escopo fora do baseline
justificado. Varre todos os repositories **de uma vez** e aponta o
`file:line` do infrator. Baseline (allowlist com justificativa) cobre as
ocorrências legadas conhecidas (frames/#313, COALESCE legado-NULL de modelos,
classes legadas); **uma nova ocorrência não nasce** — o teste quebra antes.

O padrão sancionado (encadear `get_tenant_id()`/`get_tenant_schema()`) não é
detectável estaticamente como "errado"; por isso a guarda mira o **anti-padrão**
(derivação SQL do tenant de casa), que é inequívoco e foi a causa-raiz das três
rodadas.
