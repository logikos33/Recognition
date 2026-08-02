# CHAT 1 / 3 — Bloco A: destravar o live view e fechar o gargalo real

> **Como usar:** abra um chat NOVO do Claude Code e mande:
> *"Leia e execute `tools/agent-driver/tasks/CHAT-1-BLOCO-A-DESTRAVAR-PROMPT.md`."*
> Ao chegar no PORTÃO A, ele reporta e **para**. Esse relatório é o insumo do CHAT 2.

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

> **Modelo: Sonnet 5.** · **Base:** PR #259 (`docs/OBSERVABILIDADE_CONSUMO_API.md`) — tudo aqui já foi
> diagnosticado com `file:line`; esta tarefa **implementa**.
> **Contexto da fila:** `tools/agent-driver/tasks/MUTIRAO-FILA-COMPLETA-PROMPT.md` (índice dos 3 chats).

## Por que este bloco existe

O levantamento não conseguiu responder "platô ou vazamento" (a `api-v3` do DEV redeployou 5× no dia, zerando o RSS,
e o Railway CLI não expõe métricas), **mas achou coisa melhor**: o gargalo de 25 câmeras não é memória, é
**requisições por segundo** — e o live view está quebrado agora.

---

## 🔴 PASSO ZERO — antes de qualquer código (2 minutos, reporte já)

**Z.1 — As envs de R2 estão presentes em produção?**
`services/api/app/infrastructure/storage/local_storage.py:109-127` cai para `LocalStorage` (disco **efêmero** do
container) se faltar `R2_ENDPOINT`, `R2_KEY` ou `R2_SECRET`. Upload devolve **201** e o arquivo some no redeploy.
É o caminho exato dos frames de coleta da RVB, e a encenação do lote 1 está agendada.
**Reporte presente/ausente — nunca o valor.** Se faltar alguma, **avise imediatamente**: bloqueia a coleta.

**Z.2 — Os testes de integração rodam mesmo no CI?**
`services/api/tests/integration/conftest.py:33-38` faz `pytest.skip` sem `INTEGRATION_DATABASE_URL` /
`HARNESS_DATABASE_URL`. O job principal (`.github/workflows/ci.yml:69`) define só `DATABASE_URL`. Se os 23 arquivos
de integração estiverem skipados em silêncio, **a rede de segurança não está plugada** — inclusive o teste de
regressão de vazamento cross-tenant. Confirme contra um **run real**, não lendo o YAML.
*(Se estiverem skipados: **não corrija agora** — anote e reporte. É o item B0 do CHAT 2.)*

**Z.3 — Confirme o estado da develop.** Parte desta análise saiu de uma árvore defasada (#238). Se algum achado
já foi corrigido, **diga e siga** — não reimplemente.

---

## A1 🔴 P0 · Deadlock de cold start do live view

**Sintoma no DEV:** `GET stream.m3u8` → **404** (3×), `epi:stream:{id}:active` → `0`, zero segmentos — com o edge
saudável polando `/wanted` a cada 2,25 s.

```
sem segmento → edge_fed=False → a guarda do :319 não entra → lazy-start falha
   → 404 no :393 → a chave :active NUNCA é criada
   → /wanted volta vazio → o edge nunca transmite → sem segmento ↺
```

O que antes acordava o edge era **efeito colateral** do lazy-start criar a `:active`. Com o lazy-start falhando, o
sistema não sai do estado inicial sozinho. Correção descrita no PR #259 (~2 linhas).

⚠️ **Duas hipóteses já descartadas — não reabra:**
- **Não** é o token de playback do #255 — `HLS_REQUIRE_PLAYBACK_TOKEN` não está setada no DEV, logo o 404 não vem
  da linha 214.
- **Não** é regressão do #257 (gatilho por pessoa), que é de outra trilha.

**Aceite:** partindo do frio (sem segmento, sem `:active`), abrir o live view no front e o stream subir **sem
intervenção manual**. Mostrar a sequência: `:active` criada → `/wanted` retornando a câmera → segmento chegando
(bytes) → `m3u8` 200. **Teste de regressão obrigatório** — é o tipo de bug que volta.

## A2 🔴 P0 · Introspecção de recursos

Três das cinco lacunas do levantamento têm a mesma causa raiz: **não há como ler consumo de dentro do container**.
Isso precisa deixar de ser verdade antes de qualquer decisão de arquitetura.

Expor em rota **autenticada** de diagnóstico (não pública):
- `ru_maxrss` via `resource.getrusage(RUSAGE_SELF)` — o high-water mark; é o que separa **platô de vazamento**
- RSS atual (`/proc/self/status`), uptime do processo, **contador de requisições servidas** (para cruzar com o
  reciclo do gunicorn)
- **Backend de storage ativo** (`r2` | `local`) e **worker class** em uso — os dois invariantes que hoje falham mudos
- Live view: nº de segmentos recebidos, bytes acumulados, tamanho médio do segmento

Isto destrava a decisão de arquitetura de vídeo e alimenta o `/readyz` do CHAT 2.

## A3 🟠 P1 · A reciclagem do worker está matando o WebSocket

**O achado mais importante do levantamento.** Gunicorn com **1 worker** e `--max-requests 500 --jitter 50`. Só o
upload de segmento dá ~12,5 req/s com 25 câmeras → **o worker recicla a cada ~40 s**, e cada reciclo **derruba
todas as conexões SocketIO**. Isso morde **antes** da memória e explica instabilidade em tempo real que nenhuma
métrica de RAM mostraria.

⚠️ **Não delete o `--max-requests`.** Ele existe para conter vazamento de memória — e é exatamente isso que ainda
não sabemos se existe. Sequência obrigatória:
1. **A2 entregue primeiro**;
2. **Elevar** o valor para não reciclar a cada 40 s, **documentando a conta no código**;
3. Acompanhar `ru_maxrss` por uma janela; platô → remover de vez; crescimento → há vazamento e a conversa é outra.

Registre no PR o número escolhido **e a conta que o justifica**.

## A4 🟠 P1 · Guarda `edge_fed` no `start_stream`

`services/api/app/api/v1/cameras/stream_handlers.py:85-104` — o PR #250 blindou **só** o `serve_hls`; o
`start_stream` vai direto ao `LocalStreamManager.start()` (linha 101). Para câmera alimentada pelo edge, dispara um
FFmpeg que tenta discar o RTSP **através da VLAN isolada** e morre em timeout. Com 25 câmeras: **25 FFmpeg
condenados** por abertura da grade de monitoramento.

Aplicar a mesma guarda que já existe no `serve_hls`. **Sem quebrar o caminho `cloud_only`**, que legitimamente
precisa do FFmpeg local.

## A5 🟠 P1 · Validar o tamanho ANTES de ler o corpo

`services/api/app/api/v1/edge/routes.py:586` — `data = file.read()` puxa o corpo inteiro para a memória, e a
validação de 5 MB só acontece na linha **589**, depois. **O teto não protege memória nenhuma**: um corpo de 500 MB
é integralmente carregado antes de ser rejeitado.

Checar `Content-Length` / `MAX_CONTENT_LENGTH` do Flask **antes**, consumir em chunks com corte no limite, e
rejeitar com **413**, não 400.

## A6 🟠 P1 · Redis sem teto

`maxmemory:0` + `noeviction`: se o Redis encher, **as escritas passam a falhar** e derrubam tudo que depende dele.
*(O TTL de 20 s funciona e não há chave órfã — a higiene está boa; falta o teto.)*

⚠️ **Armadilha de segurança — não use `allkeys-lru`.** O Redis também guarda o blocklist de JWT revogado
(`revoked_jti:*`). Sob pressão de memória ele pode **despejar uma entrada de revogação**, e um token que você
revogou volta a ser aceito — uma correção de capacidade virando vulnerabilidade. Ordem de preferência:
1. **Separar**: segmentos de vídeo em DB/instância Redis distinta do estado de segurança. É o desenho correto —
   cache efêmero e estado de autorização não deveriam dividir o mesmo teto.
2. Se ficar num só: `volatile-ttl` ou `volatile-lru` (só despeja chave **com** TTL) **e** garantir que o `jti`
   revogado tenha TTL ≥ vida restante do token.

**Reporte a decisão antes de aplicar em produção.**

## A7 🟡 P2 · `serve_hls` sem streaming

`stream_handlers.py:226,243` devolve `Response(bytes)` com o segmento inteiro lido do Redis. Trocar por generator
(`stream_with_context`). Ganho menor que os itens acima; é o par simétrico do A5.

---

## ⛔ Fora de escopo deste chat

- **Decidir a arquitetura de vídeo** (MediaMTX × R2+CDN × manter) — depende da medição que o A2 destrava. Números
  já levantados em `docs/CADERNO_SOLUCOES_MUTIRAO.md` § D-09.
- **Corrigir o CI** dos testes de integração — é o B0 do CHAT 2. Aqui só se **constata**.
- Migrations (CHAT 3) · credenciais/rotação (Onda 0) · `pydantic-settings` na base inteira (157 ocorrências de
  `os.environ`; big-bang quebra tasks Celery) · cursores/`base.py` (208 chamadores, Onda 5).

## 🚪 PORTÃO A — reporte e PARE

- Resultado do PASSO ZERO (Z.1, Z.2, Z.3)
- **Live view sai do cold start sozinho** — este é o critério que libera o resto
- `ru_maxrss` visível e coerente
- Antes/depois **com número** de cada item: segmento chegando (bytes), `m3u8` 200, os 3 serviços do box `active`
- O que ficou fora e por quê

Um PR por tema (A1+A2 podem ir juntos). `ruff check .` limpo · `npx tsc --noEmit` se tocar front · conventional
commits. **Não promover para `staging`/`main`** — gate humano.

## Segurança

- Não expor em log/commit/PR: `DATABASE_URL`, JWT, tokens, senhas, chaves R2. Env var se reporta
  **presente/ausente**, nunca o valor.
- Produção (host `interchange`): **somente leitura**.
- Deste chat **não sai migration**.
