# Mutirão — prompt único, execução autônoma por prioridade

> **Você executa esta fila inteira sozinha, em ordem.** Não peça confirmação a cada passo. Há **exatamente dois
> pontos** onde você PARA e espera o Vitor — estão marcados com 🛑. Fora deles, decida e siga, registrando a
> decisão no PR.

## Setup

Trabalhe em **worktree a partir de `origin/develop`** (nunca num checkout `wip/*`).
Há **outra sessão ativa** em `services/edge-sync-agent/**` — **não toque nesse diretório**. Achado lá vira
relatório com `file:line`, não código.

⛔ **NUNCA rode `git clean`** (nem `-fd`/`-fdx`). Já apagou ADR, runbooks e um `.pptx` nesta árvore.

---

## 🎛️ Roteamento de modelos e economia de tokens

**Padrão: o modelo forte ORQUESTRA, os modelos baratos EXECUTAM.** A sessão principal roda em **Fable** e não gasta
o contexto dela lendo arquivo — ela planeja, cria worktree, decide e **delega**.

| Atividade | Modelo | Por quê |
|---|---|---|
| **Setup do worktree, plano da fila, decisões de risco, redação dos PRs** | **Fable** | Poucos tokens, alto valor de julgamento |
| **Varredura, grep, listagem, confirmar estado, ler log** | **Haiku** (subagente) | Trabalho mecânico. ~10× mais barato que Fable |
| **Implementação das fases 1 e 2** | **Sonnet** (subagente) | Escopo fechado, `file:line` já dado — não precisa de raciocínio caro |
| **Fase 3.5 (desenho do backfill) e qualquer decisão irreversível** | **Fable** ou **Opus** | Toca produção, sem rollback fácil |
| **Revisão final / verificação de aceite** | **Sonnet** (subagente) | |

### Regras de economia (siga sem exceção)

1. **Delegue varredura, não faça você mesma.** Qualquer "quantos arquivos têm X", "onde está Y", "confirme se Z
   ainda existe" vai para subagente **Haiku**, que devolve a **conclusão** — não o dump dos arquivos.
2. **Não releia arquivo que já leu.** Se precisa de um trecho, leia só o trecho (offset/limit), não o arquivo todo.
3. **Não cole código no relatório.** Cite `file:line`. Três linhas relevantes valem mais que cinquenta.
4. **Não repita contexto entre fases.** O que já está neste documento não precisa ser reescrito no seu resumo.
5. **Um subagente por tarefa independente, em paralelo.** Se três verificações não dependem entre si, dispare as
   três de uma vez em vez de sequenciar.
6. **Relatórios curtos.** O Vitor quer o resultado e o `file:line`, não a narrativa do caminho.
7. **Não use `ultrathink`/raciocínio estendido em tarefa mecânica.** Reserve para o passo 3.5 e para qualquer
   momento em que você estiver prestes a fazer algo sem rollback.

⚠️ **Se em algum momento a economia entrar em conflito com a correção, a correção ganha.** Melhor gastar um
subagente a mais do que implementar contra um `file:line` que você supôs em vez de confirmar.

## Regras invioláveis

- **Não promova** para `staging` nem `main` — gate humano. Abra PR e siga.
- Não exponha em log/commit/PR: `DATABASE_URL`, JWT, tokens, senhas, chaves R2. Env var se reporta
  **presente/ausente**, nunca o valor.
- Produção (host `interchange`): **somente leitura**, exceto o passo 3.5 (autorizado).
- Migrations são **forward-only**: nada de `DROP`, `ALTER COLUMN TYPE`, `DELETE FROM`, `TRUNCATE`. Nunca edite
  migration já aplicada.
- **Verifique o live view antes e depois de cada fase** (segmento chegando em bytes, `m3u8` 200, os 3 serviços do
  box `active`). **Se regredir, PARE e reporte** — isso substitui os portões manuais.
- Um PR por tema. `ruff check .` limpo · `npx tsc --noEmit` se tocar front · conventional commits.

## Contexto — o que já foi diagnosticado

Tudo abaixo tem `file:line` confirmado. Você **implementa**, não investiga do zero.
Detalhe: `docs/REGISTRO_DIVIDA_TECNICA.md`, `docs/CADERNO_SOLUCOES_MUTIRAO.md`,
`docs/OBSERVABILIDADE_CONSUMO_API.md` (PR #259).

**O tema das fases 1 e 2:** a maioria destes bugs não é "o sistema quebra", é **"o sistema quebra e responde 200"**.
A regra: *fail-fast em configuração (no boot); fail-soft em dependência de runtime — sempre com sinal.* Um fallback
só é legítimo se o modo degradado **ainda cumpre o contrato prometido**.

---

# PASSO 0 — duas verificações (2 min, faça antes de escrever código)

**0.1 — Envs de R2 em produção.** `local_storage.py:109-127` cai para `LocalStorage` (disco **efêmero**) se faltar
`R2_ENDPOINT`, `R2_KEY` ou `R2_SECRET`. Upload devolve **201** e o arquivo some no redeploy — e é o caminho dos
frames de coleta da RVB, com encenação agendada.
🛑 **Se faltar alguma, PARE e avise imediatamente.** Bloqueia a coleta do cliente.

**0.2 — Testes de integração rodam no CI?** `tests/integration/conftest.py:33-38` faz `pytest.skip` sem
`INTEGRATION_DATABASE_URL`/`HARNESS_DATABASE_URL`; o job principal (`ci.yml:69`) define só `DATABASE_URL`. Confirme
contra um **run real**, não lendo o YAML. Se estiverem skipados, **plugar isso é o item 2.0** — sem teste rodando,
o resto é afirmação, não prova.

*(Se algum achado deste documento já tiver sido corrigido na develop atual, **diga e siga** — não reimplemente.)*

---

# FASE 1 — Destravar o live view e fechar o gargalo real

### 1.1 🔴 Deadlock de cold start (o live view está quebrado agora)
`GET stream.m3u8` → **404**, `epi:stream:{id}:active` → `0`, zero segmentos, com o edge saudável polando `/wanted`.

```
sem segmento → edge_fed=False → guarda do :319 não entra → lazy-start falha
  → 404 no :393 → a chave :active NUNCA é criada
  → /wanted volta vazio → edge nunca transmite → sem segmento ↺
```
O que antes acordava o edge era **efeito colateral** do lazy-start criar a `:active`. Correção no PR #259 (~2 linhas).

⚠️ **Já descartado, não reabra:** não é o token de playback do #255 (`HLS_REQUIRE_PLAYBACK_TOKEN` não está setada
no DEV, logo o 404 não vem da linha 214); não é regressão do #257.

**Aceite:** do estado frio, abrir o live view e o stream subir **sem intervenção manual**. Teste de regressão
obrigatório.

### 1.2 🔴 Introspecção de recursos
Rota **autenticada** de diagnóstico expondo: `ru_maxrss` (`resource.getrusage`) — é o que separa **platô de
vazamento**; RSS atual; uptime; **contador de requisições servidas**; **backend de storage ativo** (`r2`|`local`);
**worker class** em uso; e contadores do live view (segmentos, bytes, tamanho médio).

Sem isso a próxima investigação repete cega — três das cinco lacunas do PR #259 têm essa causa raiz.

### 1.3 🟠 Reciclagem do worker está matando o WebSocket
1 worker + `--max-requests 500 --jitter 50`. Só o upload dá ~12,5 req/s com 25 câmeras → **recicla a cada ~40 s**,
e cada reciclo **derruba todas as conexões SocketIO**. Morde antes da memória.

⚠️ **Não delete o `--max-requests`** — ele existe para conter vazamento, e é isso que ainda não sabemos se existe.
Ordem: **1.2 primeiro** → **elevar** o valor documentando a conta no código → medir `ru_maxrss` depois.

### 1.4 🟠 Guarda `edge_fed` no `start_stream`
`stream_handlers.py:85-104` — o #250 blindou **só** o `serve_hls`; `start_stream` vai direto ao
`LocalStreamManager.start()` (linha 101), disparando FFmpeg que tenta discar RTSP **através da VLAN isolada**.
Com 25 câmeras: **25 FFmpeg condenados** por abertura da grade. Aplicar a mesma guarda, **sem quebrar `cloud_only`**.

### 1.5 🟠 Validar tamanho ANTES de ler o corpo
`edge/routes.py:586` — `data = file.read()` puxa tudo; a validação de 5 MB só vem na **589**. **O teto não protege
memória nenhuma.** Checar `Content-Length`/`MAX_CONTENT_LENGTH` antes, consumir em chunks, rejeitar com **413**.

### 1.6 🟠 Redis sem teto (`maxmemory:0` + `noeviction`)
Se encher, **as escritas falham** e derrubam tudo que depende do Redis.

⚠️ **NÃO use `allkeys-lru`.** O mesmo Redis guarda o blocklist de JWT revogado (`revoked_jti:*`); sob pressão ele
despejaria uma revogação e **um token revogado voltaria a valer**. **Decisão já tomada, siga sem perguntar:**
separe os segmentos de vídeo em **DB Redis distinto** do estado de segurança. Se por limitação de infra não der,
use `volatile-ttl` e garanta TTL do `jti` ≥ vida restante do token — e registre o porquê no PR.

### 1.7 🟡 `serve_hls` em chunks
`stream_handlers.py:226,243` devolve `Response(bytes)` com o segmento inteiro. Trocar por generator
(`stream_with_context`). Par simétrico do 1.5.

**Ao fim da fase 1:** verifique o live view, reporte antes/depois com número, e **siga para a fase 2**.

---

# FASE 2 — O sistema tem que avisar quando quebra

### 2.0 Plugar o CI (só se o passo 0.2 confirmou o problema) — vem antes de tudo nesta fase

### 2.1 `get_storage()` fail-fast
`local_storage.py:109-127`. Produção sem env de R2 → **o processo não sobe**, com mensagem dizendo o que falta e o
que aconteceria; saia com código `78` (`EX_CONFIG`) para separar "config errada" de "crash" no log do Railway.
**Inverta o default:** efêmero exige `ALLOW_EPHEMERAL_STORAGE=1` explícito, **proibido em produção**. Warning no
caminho local. **Preflight real** (`head_bucket` no boot) — env presente com credencial expirada passa em qualquer
validação de schema.

⚠️ Resolva junto: `quality_training.py:34`, `quality_cep.py:35`, `quality_annotation.py:30`,
`quality_inference.py:95,376` importam `R2Storage` **direto** e estouram se R2 faltar — comportamento oposto ao
fallback. Escolha um.

### 2.2 Deletar o `except ImportError` do worker
`railway_start.py:151-159` — sem gevent cai para worker `sync`, que **não suporta WebSocket**: app sobe, health
200, Railway promove, SocketIO morto. **O gunicorn já falha sozinho**; o `try/except` é o que remove essa garantia.
**Delete.** Veja também `:140-148` (mesma família).

### 2.3 Health check honesto
Hoje `health/routes.py:41` devolve **200 com Redis morto**, e o health do worker Celery
(`railway_start.py:456-466`) é `{"status":"ok"}` **hardcoded**.

| rota | escopo | regra |
|---|---|---|
| `/livez` | processo vivo | **nunca** toca DB/R2/Redis |
| `/readyz` | dependências **+ invariantes de config** | **cacheado** por greenlet de fundo, com campo `stale` |
| `/status` | diagnóstico | nunca consumido por automação que reinicia |

⚠️ Não cheque dependência no **liveness** (banco tosse → restart loop).
⚠️ **Railway só chama o healthcheck na promoção do deploy**, não continuamente. Logo o `/readyz` é a **única**
barreira contra promover deploy degradado: **reprove duro** `worker_class=sync` e `storage_backend=local`
(invariantes determinísticos), mas dê **retry com backoff** a dependência transitória, senão Redis instável impede
deploy. O campo `stale` é obrigatório: se o greenlet morrer, o cache congela num "ready" mentiroso.

### 2.4 Sinal de degradação
Todo fallback sobrevivente emite **métrica com label** + log estruturado `degraded=true` **no momento da decisão**.
Alerta dispara em `> 0`, não em taxa. Inclua **alarme por ausência de sinal** (há quanto tempo o coletor não tem
sucesso) — nenhum alerta de `rate(errors)` enxerga processo que parou quieto.

### 2.5 `assistant_service.py:53-65` — RAG morto em silêncio
`with db_pool.getconn()` → `DatabasePool` não expõe `getconn` → `AttributeError` engolido pelo `except Exception`
da linha 68 → **RAG retorna `[]` para sempre**. Corrija usando o `get_connection()` existente.
⚠️ **Não** adicione `getconn`/`putconn` ao wrapper: criaria conexão que **não passa pelo `conn.reset()`**, e é esse
reset (`connection.py:119-135`) que impede vazamento de `search_path` entre tenants.

### 2.6 Validação de faixa da config
`Field(ge=, le=)` nos numéricos críticos: fora do domínio → falha alta no boot. Fecha a família que já matou a
coleta **3×** em silêncio.
⚠️ **Não migre a base inteira para `pydantic-settings`** — são **157** ocorrências de `os.environ` e tasks Celery
leem env em *import time*; big-bang quebra. Valide só o necessário para 2.1, 2.3 e 2.6.

### 2.7 `/andon/<camera_id>` — RELATÓRIO, não mudança
`quality/routes.py:719-745` — sem JWT (só filtro de IP), abre conexão fora do pool e **itera todos os schemas de
tenant**. Pode ser requisito de produto (painel de chão de fábrica). Descreva o risco e proponha; **não altere**.

**Ao fim da fase 2:** verifique o live view, reporte as provas (env incompleta → não sobe; sem gevent → falha;
`/readyz` 503 com storage local; RAG devolvendo resultado), e **siga para a fase 3**.

---

# FASE 3 — Migrations (a mais perigosa; leia inteira antes de começar)

**Existem dois runners divergentes, e o de produção é o pior:**

| | `infra/migrations/run_migrations.py` | `railway_start.py:55-89` ← **produção** |
|---|---|---|
| Tabela de controle | ✅ `schema_migrations` | ❌ **nenhuma** — reexecuta os 50+ SQLs a cada boot |
| Advisory lock | ❌ | ❌ |
| Falha aborta o boot? | — | ❌ **não** — loga e continua; **API sobe com schema incompleto** |
| Quem chama | **ninguém** | `railway_start.py:486` |

Mais: fallback de diretório (`:61-70`) entre `infra/migrations/` e `migrations/` da raiz, que **existem com
conteúdo diferente**; **6 arquivos no prefixo `052`**; 16 números ausentes; `051:44` e `080:64` criam ambos
`device_claim_codes.code_hash`. A ADR-0021 registra que colisão de numeração **já derrubou o startup da API**.

### 3.1 Guard-rail de CI (faça primeiro — ~30 min)
Falhar o build em: **prefixo duplicado**; **dois diretórios** de migration; e aplicar em banco limpo **2×**
(idempotência) com diff do schema resultante.

### 3.2 Unificar os runners + falha aborta o boot
Um runner só. Migration que falha **para o boot**. Matar o fallback de diretório e **arquivar** (não deletar) o
`migrations/` da raiz.
⚠️ A heurística que trata `"already exists"`/`"duplicate"` como sucesso **morre junto** — ela mascara divergência de
schema. Idempotência vem do **ledger**, não da mensagem de erro.

### 3.3 Ledger
`public.schema_migrations (tenant_schema, version, checksum, installed_rank, installed_on, success)` com
**`UNIQUE (tenant_schema, version)`** — essa constraint sozinha teria matado o bug dos 6× `052`.

### 3.4 Advisory lock — armadilha
Use **`pg_advisory_xact_lock`**, **não** `pg_advisory_lock`.
⚠️ O lock de **sessão** vive na conexão: pegar numa conexão do pool e liberar em outra faz o unlock virar **no-op**;
a conexão volta ao pool segurando o lock e **todo boot futuro trava para sempre**. A variante `_xact_` libera no fim
da transação.

### 3.5 🛑 BACKFILL — PARE AQUI E ESPERE O VITOR
A `schema_migrations` chega **vazia** num banco que já tem tudo aplicado. Sem backfill, o runner novo tentaria
**reaplicar os 50+ SQLs** — e o que hoje segura isso é justamente a heurística que o 3.2 remove.

Ordem obrigatória: **(1)** `INSERT` de todas as versions já aplicadas em cada ambiente; **(2)** provar que o runner
novo aplica **zero** migration contra esse banco; **(3)** só então o cutover.

Rode o **harness 2×** (`services/api/tests/harness/migrations/`) e feche a PEND do README dele (*"unificar o loop de
apply do railway_start com o runner.py do harness"*) — hoje o harness **espelha** o código de produção, então
unificar é o que faz o teste valer.

🛑 **Prepare tudo, rode em dev e staging, mostre o script e o resultado — e AGUARDE autorização explícita do Vitor
antes de tocar em produção.** Este é o único ponto da fila onde você escreve em produção.

### ⛔ Não faça o CDRB
Baseline único + renumeração por timestamp exige congelamento e reconciliação entre três ambientes — é operação
humana coordenada. **Deixe proposto em `docs/`**, não execute.

---

# Fora desta fila (por decisão, não esquecimento)

| O quê | Por quê |
|---|---|
| Credenciais, rotação, senha que se auto-restaura | Decisão do Vitor: entra na varredura do dia do embarque final |
| Convite de tenant, recuperação de senha, `token_version` | Depende do item acima |
| Arquitetura de vídeo (MediaMTX × R2+CDN) | Depende da medição que o 1.2 destrava. Números em `CADERNO_SOLUCOES_MUTIRAO.md` § D-09 |
| Cursores / `base.py`, qualificar `public.` nos 14 repos | `base.py` tem **208 chamadores**; PR isolado depois |
| Migrar para Alembic/Atlas/dbmate | Só faz sentido depois que o ledger existir |

# Resumo dos pontos de parada

🛑 **Passo 0.1** — se faltar env de R2 em produção (bloqueia o cliente).
🛑 **Passo 3.5** — antes do backfill em produção.
🛑 **Qualquer regressão do live view** — em qualquer ponto.

Fora desses três, **decida e siga**. Registre a decisão no PR.
