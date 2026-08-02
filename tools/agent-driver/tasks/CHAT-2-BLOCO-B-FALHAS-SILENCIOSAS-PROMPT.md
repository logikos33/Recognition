# CHAT 2 / 3 — Bloco B (Onda 1): o sistema tem que avisar quando quebra

> **Como usar:** abra um chat NOVO do Claude Code e mande:
> *"Leia e execute `tools/agent-driver/tasks/CHAT-2-BLOCO-B-FALHAS-SILENCIOSAS-PROMPT.md`."*
> **Cole junto o relatório do PORTÃO A** (CHAT 1) — ele traz o resultado do Z.1/Z.2, que muda o escopo daqui.
> Ao chegar no PORTÃO B, reporte e **pare**.

```
[SESSÕES PARALELAS — leia antes de tudo]
Há OUTRA sessão do Code ativa em services/edge-sync-agent/**.
- VOCÊ é dona de: services/api/** , apps/frontend/** , railway_start.py
- NÃO TOQUE em: services/edge-sync-agent/** e infra/migrations/**
- Antes de editar, confirme que a develop não mudou no arquivo desde sua cópia (git fetch + diff).
  Teste existente falhando de forma inesperada = sinal de colisão: PARE e reporte.
- Achado fora do seu diretório = RELATÓRIO com file:line, não código.
- ⛔ NUNCA rode `git clean` (nem -fd/-fdx). Já apagou ADR, runbooks e um .pptx nesta árvore.
```

> **Modelo: Sonnet 5.** · **Referências:** `docs/CADERNO_SOLUCOES_MUTIRAO.md` (seção 1 e Onda 1),
> `docs/REGISTRO_DIVIDA_TECNICA.md`. **Pré-requisito:** CHAT 1 concluído.

## O tema

Sete bugs, uma família só: **o sistema entra em modo degradado e não avisa ninguém**. Não é "quebrou" — é
"quebrou, respondeu 200, e seguiu". A regra que os resolve:

> **Fail-fast em configuração** (no boot, antes de aceitar tráfego). **Fail-soft em dependência de runtime** —
> sempre com sinal.
> Um fallback só é legítimo se o modo degradado **ainda cumpre o contrato prometido**. R2 fora → gravar em disco
> efêmero e responder **201 Created** não cumpre: 201 promete durabilidade.

---

## B0 · Plugar a rede de segurança (só se o Z.2 do CHAT 1 confirmou o problema)

Se os testes de integração estiverem sendo **skipados** no CI por falta de `INTEGRATION_DATABASE_URL` /
`HARNESS_DATABASE_URL`, **este é o primeiro item** — antes de qualquer correção. Sem teste rodando, tudo abaixo é
afirmação, não prova. Inclui o teste de regressão de vazamento cross-tenant
(`tests/integration/test_camera_create_search_path.py`), que hoje pode nunca ter executado.

## B1 · `get_storage()` — fail-fast em vez de fallback mudo
`services/api/app/infrastructure/storage/local_storage.py:109-127`

- Produção sem env de R2 → **o processo não sobe**, com mensagem dizendo o que falta **e o que aconteceria**
  (arquivo perdido no redeploy). Código de saída distinto de crash (`78` = `EX_CONFIG`) ajuda a separar
  "config errada" de "quebrou" no log do Railway.
- **Inverter o default:** modo efêmero passa a exigir `ALLOW_EPHEMERAL_STORAGE=1` explícito, **proibido em
  produção** pelo validador. Default perigoso é a raiz do bug.
- No caminho local (dev), **logar warning** dizendo que os arquivos serão perdidos.
- **Preflight real:** `head_bucket` no boot. Env presente com credencial expirada passa em qualquer validação de
  schema — só a chamada prova.

⚠️ Resolver junto a inconsistência: 5 tasks de quality (`quality_training.py:34`, `quality_cep.py:35`,
`quality_annotation.py:30`, `quality_inference.py:95,376`) importam `R2Storage` **direto** e estouram se R2 faltar —
comportamento oposto ao fallback. Escolher um comportamento e aplicar nos dois lugares.

*Raio: 11 call sites de `get_storage()` e 18 pontos de escrita de arquivo, mas a mudança é em 1 função; os testes
já mockam `get_storage` inteiro. Risco baixo.*

## B2 · Deletar o `except ImportError` do worker
`railway_start.py:151-159`

Sem `gevent`/`gevent-websocket`, cai para worker `sync` — que **não suporta WebSocket**. O app sobe, o health
responde 200, o Railway promove o deploy, e SocketIO/live view estão mortos com um `log.warning` como único sinal.

**O gunicorn já falha sozinho** se não conseguir importar a worker class. O `try/except` é exatamente o código que
remove essa garantia. **Deletar.** Correção trivial, impacto alto.

Verificar também `railway_start.py:140-148` — segunda degradação silenciosa no mesmo arquivo (se `app` não existir,
tenta `api.app` da V1).

## B3 · Health check que não mente
`services/api/app/api/v1/health/routes.py`

Hoje `:41` devolve **HTTP 200 com Redis morto** (`status: "degraded"`) — o Railway não tira de rotação. E o health
do worker Celery (`railway_start.py:456-466`) é `{"status":"ok"}` **hardcoded**: não verifica broker, DB, nem se o
worker está vivo.

Separar em três (padrão da Amazon Builders' Library):

| rota | escopo | consumidor | regra |
|---|---|---|---|
| `/livez` | processo vivo | reinício | **nunca** toca DB/R2/Redis |
| `/readyz` | dependências **+ invariantes de config** | tirar de rotação / gate de deploy | **cacheado** por greenlet de fundo |
| `/status` | diagnóstico rico | humano | nunca consumido por automação que reinicia |

⚠️ **Antipadrão a evitar:** checar dependência no **liveness**. Banco tosse 10 s → processo reinicia → tempestade de
cold start sobre um banco já sofrendo.

⚠️ **Particularidade do Railway que muda o desenho:** o healthcheck **só é chamado na promoção do deploy**, não em
monitoramento contínuo. Consequências:
- O `/readyz` é a **única** barreira automática contra promover deploy degradado — **precisa reprovar**
  `worker_class = sync` e `storage_backend = local`. São invariantes **determinísticos**: falhe duro neles.
- Dependência **transitória** (Redis piscando) precisa de **retry com backoff** antes de reprovar, senão Redis
  instável impede deploy. Trate config e dependência com rigor diferente.

O `/readyz` deve expor o campo **`stale`**: se o greenlet que atualiza o estado morrer, o cache congela num "ready"
mentiroso — trocaria uma falha silenciosa por outra.

O health do worker Celery deve verificar de verdade (broker alcançável, última task processada). Risco baixo,
valor alto.

## B4 · Sinal de "estou em modo degradado"
Todo fallback que sobreviver emite **métrica com label** e log estruturado com `degraded=true` **no momento da
decisão** — não um `log.info` perdido. O alerta dispara em `> 0`, **não em taxa**: fallback de configuração é
binário, não estatístico.

Expor no `/readyz`: backend de storage ativo, worker class, e **há quanto tempo o coletor não tem sucesso**.
**Alarme por ausência de sinal** é o único jeito de pegar processo que parou quieto — nenhum alerta baseado em
`rate(errors)` enxerga isso.

## B5 · `assistant_service.py:53-65` — RAG morto em silêncio
```python
with db_pool.getconn() as conn:   # DatabasePool NÃO expõe getconn
    ...
    db_pool.putconn(conn)          # dentro do with: não roda se houver exceção
```
`AttributeError` → engolido pelo `except Exception` da linha 68 → **o RAG retorna `[]` para sempre**, sem erro
visível. Corrigir usando o `get_connection()` que já existe.

⚠️ **Não** adicione `getconn`/`putconn` ao wrapper para "fazer funcionar": criaria conexão que **não passa pelo
`conn.reset()`**, e é esse reset (`connection.py:119-135`) que impede vazamento de `search_path` entre tenants.

## B6 · Validação de faixa da config
`Field(ge=..., le=...)` nos parâmetros numéricos críticos: valor fora do domínio → **falha alta no boot**. Fecha a
família de bugs que já matou a coleta **três vezes** em silêncio (limiar `8.0` contra ruído medido 0.39; `2.0` numa
variável que virou fração 0–1; `TARGET_FRAMES=17` do experimento esquecido no lugar).

⚠️ **Não migre a base inteira para `pydantic-settings` agora.** São **157** ocorrências de `os.environ` em
`services/api/app/` (só 35 no `config.py`, que é usado em apenas 2 lugares), e tasks Celery leem env em *import
time* — big-bang quebra. Valide **apenas** o necessário para B1, B3 e B6. O resto é incremental depois.

## B7 · Reportar (não mudar) o `/andon/<camera_id>`
`services/api/app/api/v1/quality/routes.py:719-745` — endpoint **sem JWT** (só filtro de IP) que abre conexão fora
do pool e **itera todos os schemas de tenant** fazendo `SET search_path` até achar a câmera. É enumeração
cross-tenant por desenho, e o `conn.close()` não roda em todos os caminhos de exceção.

**Pode ser requisito de produto** (painel Andon em tela de chão de fábrica). Descreva o risco e proponha correção —
**não altere o comportamento sem confirmação**.

---

## ⛔ Fora de escopo deste chat

- **Migrations** — o loop do `railway_start.py:55-89` é o **CHAT 3**, que o reescreve inteiro. Não mexa; fazer duas
  vezes é retrabalho.
- **Credenciais / rotação de senha** — Onda 0, decisão do Vitor sobre quando.
- **Arquitetura de vídeo** — Onda 4, depende da medição do A2.
- **Cursores / `base.py`** — Onda 5. São **208 chamadores em 29 arquivos**; não misturar.

## 🚪 PORTÃO B — reporte e PARE

Provar com antes/depois, não afirmar:
1. **Storage**: subir com env de R2 incompleta → o processo **não sobe** (exit code + mensagem). Com env completa,
   sobe normal. **Teste de regressão que trave isso** — sem ele, alguém reintroduz o fallback em 6 meses.
2. **Worker**: sem gevent, o boot **falha** em vez de degradar.
3. **Health**: `/readyz` retornando **503** com `storage_backend=local`, e 200 no caminho bom. Mostrar o campo
   `stale`.
4. **Assistant**: RAG devolvendo resultado real onde antes retornava `[]`.

**Live view continua funcionando** — verifique antes, durante e depois (segmento chegando em bytes, `m3u8` 200, os
3 serviços do box `active`). Pegou regressão nas ondas anteriores.

Um PR por correção (B1+B2+B3 podem ir juntos, são o mesmo tema). `ruff check .` limpo · `npx tsc --noEmit` se tocar
front · conventional commits. **Não promover para `staging`/`main`** — gate humano.

## Segurança

- Não expor em log/commit/PR: `DATABASE_URL`, JWT, tokens, senhas, chaves R2. Env var se reporta
  **presente/ausente**, nunca o valor.
- Produção (host `interchange`): **somente leitura**.
- Deste chat **não sai migration**.
