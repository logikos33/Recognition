# Observabilidade — consumo da API-V3 (live view / segmentos)

**Data:** 2026-07-31 · **Ambiente medido:** DEV (`api-v3-desenvolvimento`) · **Natureza:** levantamento read-only, nenhum código alterado.

---

## 1. Veredito em 3 linhas

1. **Não consegui responder platô × vazamento** — o Railway CLI não expõe métricas de RAM e o processo foi reiniciado 5× hoje por deploy, então não existe janela contínua de 24–48h para medir. A pergunta central do documento fica **em aberto por falta de fonte**, não por falta de tentativa.
2. **O caminho do byte está confirmado e é o esperado pela hipótese D:** upload lê o corpo inteiro em memória (`edge/routes.py:586`) e `serve_hls` carrega o segmento inteiro do Redis antes de responder (`stream_handlers.py:226,243`). Nenhum dos dois faz streaming. Com teto de 5 MB por segmento e 1 worker gunicorn, isso é high-water mark por construção.
3. **Achei algo mais urgente que a memória: o live view da câmera 1 está QUEBRADO no DEV agora** — deadlock de cold start, detalhado no §7. Recomendo tratar isso antes da decisão D/A/B.

> ⚠️ Sobre a hipótese: **não a confirmei**. O mecanismo que ela prevê existe no código (§3), mas o *número* que provaria high-water mark (curva de RAM) não foi obtido. Manter como hipótese plausível e não medida.

---

## 2. Bloco A — Curva de memória

| Item | Resultado | Fonte |
|---|---|---|
| Curva 24–48h (platô × monotônica) | ❌ **NÃO MEDIDO** | `railway --help` não tem subcomando de métricas |
| Restarts por OOM | ❌ **NÃO MEDIDO** | idem |
| Correlação degraus × live view | ❌ **NÃO MEDIDO** | depende da curva |
| Limite do plano / headroom | ❌ **NÃO MEDIDO** | idem |

**Fator que invalida a janela mesmo se houvesse métrica:** a `api-v3` do DEV redeploya a cada merge na develop. Só em 2026-07-31 houve deploy às `16:26`, `20:12`, `20:19`, `21:35` e `21:41` UTC (`railway deployment list -s API-V3 -e Desenvolvimento`). **Cada deploy zera o RSS.** Uma curva de 24–48h no DEV mediria cadência de merge, não comportamento de memória.

**Como obter (não executei — exige acesso/decisão do Vitor):**
- Dashboard do Railway → serviço API-V3 → aba Metrics, janela de 24–48h. É onde a resposta está.
- Ou medir em ambiente sem deploy contínuo (staging), com live view ativo por horas.

**Agravante estrutural para a leitura da curva:** o gunicorn roda com `--max-requests 500 --max-requests-jitter 50` (`railway_start.py:159-160`). O worker é reciclado a cada ~450–550 requests, **e a reciclagem zera o heap**. Consequência: se a curva mostrar RAM subindo e não voltando *apesar* dessa reciclagem, a explicação de high-water mark do CPython **não se sustenta** — seria vazamento fora do heap Python (ex.: buffers do gevent, fds, conexões). Esse é o teste discriminante que a métrica precisa responder.

---

## 3. Bloco B — Como o byte é recebido e devolvido

### B1. Upload do segmento — lê o corpo INTEIRO em memória ✅ confirmado

`services/api/app/api/v1/edge/routes.py`:

```
578:    file = request.files.get("file")
586:    data = file.read()          # <- corpo inteiro em memória
589:    if len(data) > _MAX_SEGMENT_BYTES:
596:    r.setex(f"epi:edge_hls:{camera_id}:{filename}", _HLS_SEGMENT_TTL, data)
```

Dois agravantes além do `read()`:

- **A validação de tamanho vem DEPOIS da leitura** (`589` valida o que já foi carregado em `586`). O teto de 5 MB não protege a memória — ele só rejeita depois de já ter alocado.
- **`request.files` já bufferizou antes**: o Werkzeug materializa o multipart antes da linha 586. Na prática o pico é ~2× o tamanho do segmento por request em voo (buffer do parser + `data`).

Constantes (`edge/routes.py:75-76`):
```
_MAX_SEGMENT_BYTES = 5 * 1024 * 1024   # 5 MB
_HLS_SEGMENT_TTL   = 20                # segundos
```

### B2. `serve_hls` — lê o segmento inteiro do Redis ✅ confirmado

`services/api/app/api/v1/cameras/stream_handlers.py`:

```
226:    edge_content = _r_edge.get(f"epi:edge_hls:{camera_id}:{filename}")
243:    return Response(edge_content, status=200, headers={"Content-Type": content_type})
```

`Response(bytes)` — sem generator, sem `stream_with_context`. O segmento inteiro vive na memória do worker durante a resposta.

### B3. Gunicorn (`railway_start.py:156-164`)

| Parâmetro | Valor |
|---|---|
| worker class | `geventwebsocket.gunicorn.workers.GeventWebSocketWorker` |
| workers | **1** |
| `--timeout` | 120 |
| `--keep-alive` | 5 |
| `--max-requests` | 500 |
| `--max-requests-jitter` | 50 |
| `worker_connections` | **não definido** (default do gevent: 1000) |

**Risco de escala independente de RAM:** com 1 worker e reciclagem a cada ~500 requests, o volume de requests é o gargalo antes da memória. O próprio código do edge já documenta o efeito medido em campo (`services/edge-sync-agent/app/live_view/live_view_loop.py`, docstring do módulo): *"a API roda com UM worker gunicorn e `--max-requests`, então tráfego contínuo recicla o worker — medido em campo, a versão contínua da LV-2 gerava ~2,5 req/s e reciclava o worker a cada ~3min, o que derruba as conexões SocketIO"*. Com 25 câmeras, esse número multiplica.

### B4. Distribuição real do tamanho de segmento

❌ **NÃO MEDIDO** — o live view não sobe (§7), então não há segmento novo para amostrar.

**Referência histórica** (medições minhas de hoje, antes da quebra, mesma câmera/substream): 12 amostras entre **260 944 e 279 932 bytes**, mediana ~276 000 B, para segmentos de ~2 s. Ou seja **~0,13 MB/s por câmera assistida**. O teto configurado de 5 MB é ~18× o segmento real — folga grande demais, e é ela que define o pico de alocação no pior caso.

---

## 4. Bloco C — Redis

`INFO memory` (DEV, sem live view ativo):

```
used_memory:1787408                used_memory_human:1.70M
used_memory_rss:14831616           used_memory_rss_human:14.14M
maxmemory:0                        maxmemory_human:0B
maxmemory_policy:noeviction
mem_fragmentation_ratio:8.30
```

| Pergunta | Resposta |
|---|---|
| `maxmemory` definido? | 🔴 **NÃO — `maxmemory:0` (ilimitado)** |
| Política de evicção | 🔴 **`noeviction`** |
| TTL nas chaves de segmento | ✅ Sim — `_HLS_SEGMENT_TTL = 20s` (`edge/routes.py:76`) |
| Chaves `epi:edge_hls:*` agora | 0 (nenhuma transmissão ativa) |
| Chaves órfãs acumulando | ✅ **Não** — o TTL de 20 s cuida sozinho; sem transmissão, expiram |
| `DBSIZE` | 61 |

🔴 **Sinalizado, como pedido:** `maxmemory:0` + `noeviction` significa que o Redis **cresce até estourar a RAM do container e então recusa escrita** — não há descarte gracioso. Com 25 câmeras: 3 segmentos vivos × ~276 KB × 25 ≈ **20 MB** de estado esperado, o que é pequeno; o risco real não é o volume nominal, é **não haver teto** se algo travar a expiração (ex.: TTL removido num refactor, ou pico de segmentos grandes).

`mem_fragmentation_ratio: 8.30` parece alto, mas sobre 1,7 MB de dados é overhead do alocador — **não é sinal de problema** neste tamanho. Reavaliar quando o dataset crescer.

---

## 5. Bloco D — Custo por câmera assistida

❌ **NÃO MEDIDO — bloqueado pela quebra do §7.** Sem live view no ar não há MB/s de entrada, MB/s de saída, nem delta de RSS a medir.

**Além disso, o delta de RSS seria inatingível mesmo com o live view no ar:** medir RSS do processo exige `ps`/`/proc` **dentro do container** da Railway, e não há caminho de exec read-only disponível pelo CLI. Precisaria de um endpoint de introspecção na própria API (ex.: `/health` devolvendo `resource.getrusage().ru_maxrss`) — que **não existe hoje** e seria código novo, fora do escopo desta tarefa.

**Extrapolação para 25 câmeras — apenas o que dá para derivar dos números conhecidos, sem medir RAM:**

| Grandeza | 1 câmera | 25 câmeras |
|---|---|---|
| Banda de entrada (`POST /segment`) | ~0,13 MB/s | **~3,4 MB/s** |
| Banda de saída (`serve_hls`) | ~0,13 MB/s × espectadores | ~3,4 MB/s × espectadores |
| Requests de upload | ~0,5 req/s | **~12,5 req/s** |
| Reciclagem do worker (`max-requests 500`) | ~1 a cada 16 min | 🔴 **~1 a cada 40 s** |

**O número que preocupa não é MB, é req/s.** A 12,5 req/s só de upload, o worker único recicla a cada ~40 segundos — e cada reciclagem derruba as conexões SocketIO, exatamente o efeito já documentado em campo com muito menos tráfego. **Isso morde antes da memória.**

⚠️ Extrapolação linear a partir de 1 câmera e sem medição de RAM. Tratar como ordem de grandeza, não como capacity planning.

---

## 6. Bloco E — ffmpeg órfão e `/stream/start`

### E1. Processos ffmpeg vivos no container

❌ **NÃO MEDIDO** — mesma limitação do §5: sem exec no container da Railway. Precisaria de endpoint de introspecção.

### E2. `start_stream` ficou de fora da guarda `edge_fed` ✅ **CONFIRMADO — a suspeita procede**

A guarda do PR #250 foi aplicada **só** no `serve_hls` (`stream_handlers.py:223,229,319`). O `start_stream` **não tem guarda nenhuma** e vai direto ao FFmpeg local quando o gateway está offline:

```
stream_handlers.py:85    from .local_stream_manager import LocalStreamManager
stream_handlers.py:101   LocalStreamManager.get_instance().start(
stream_handlers.py:104   dispatch_mode = "local"
```

Para câmera alimentada pelo edge, esse FFmpeg **nunca conecta** (RTSP em VLAN isolada, ADR-0020) — é processo, CPU e memória desperdiçados, e é o que popula `ffmpeg_error` com timeout que não diz nada sobre a câmera.

### E3. Quantas chamadas de `/stream/start` por abertura de tela

⚠️ **PARCIAL.** Só dois pontos no frontend chamam `cameraService.start()`:

- `apps/frontend/src/components/cameras/CameraCard.tsx:67`
- `apps/frontend/src/pages/CamerasPage.tsx:119`

**A `MonitoringPage.tsx` não chama** — ela monta o `CameraPlayer` apontando direto para o `.m3u8` e depende do lazy-start do `serve_hls`. Portanto o indício de "5 chamadas em 13s" **não vem da tela de monitoramento**; se for real, vem da tela de Câmeras (re-render disparando o handler) ou de retry do player. **Não consegui reproduzir** — precisaria de sessão autenticada no browser, que não tenho.

---

## 7. 🔴 ACHADO FORA DE ESCOPO — live view da câmera 1 quebrado no DEV

**Não implementei correção (tarefa read-only). Reportando com `file:line`.**

### Sintoma medido

```
GET /api/cameras/eb1501db.../stream/stream.m3u8   -> 404   (3 tentativas seguidas)
redis EXISTS epi:stream:eb1501db...:active        -> 0
redis KEYS  epi:edge_hls:*                        -> 0 chaves
```

O edge está **saudável**: `edge-live-view` active, polando `GET /edge/live-view/wanted` a cada ~2,25 s e recebendo `200 OK`. Ele simplesmente nunca é informado de que há espectador.

### Causa — deadlock de cold start

Verifiquei que **não** é o token de playback: `HLS_REQUIRE_PLAYBACK_TOKEN` não está setada no DEV, então `playback_enforced()` é falso e o 404 da linha `214` não dispara. O 404 vem da **linha 393**.

O ciclo, em `stream_handlers.py`:

1. `223-229` — estado frio, sem segmento no Redis → `edge_fed = False`
2. `319` — `if edge_fed:` não entra (a guarda só protege quem **já** está transmitindo)
3. `327-382` — cai no lazy-start; o `LocalStreamManager` tenta FFmpeg contra RTSP inalcançável e falha → `_lazy_started` fica `False`
4. `393` — `return error("Stream não disponível", 404)`
5. **`epi:stream:{camera_id}:active` nunca é criada** → `/wanted` devolve `[]` → o edge não sobe transcoder → não há segmento → `edge_fed` continua `False` → **volta ao passo 1, para sempre**

A guarda `edge_fed` resolve o desperdício de FFmpeg **depois** que o edge já está empurrando, mas **não consegue dar o boot**. O gatilho que acordava o edge era justamente o efeito colateral do lazy-start criar a chave `:active`.

### Correção identificada (descrita, não implementada)

Criar/renovar `epi:stream:{camera_id}:active` **no topo** do `serve_hls`, antes de qualquer decisão de caminho — pedir a playlist **é** a declaração de que existe espectador. Ponto de inserção: `stream_handlers.py`, logo após a validação de `filename` (~linha 198), no mesmo formato já usado em `238` e `291`:

```python
_get_redis().setex(f"epi:stream:{camera_id}:active", _HLS_INACTIVITY_TTL, "1")
```

**Esforço:** ~2 linhas + 1 teste de regressão (estado frio → chave criada → 425, não 404). **Baixo.**
**Risco de não corrigir:** live view inoperante para qualquer câmega de edge a partir do estado frio — que é o estado após cada TTL de 20 s sem espectador.

---

## 8. Bloco F — Latência baseline

❌ **NÃO MEDIDO.**

- `#EXT-X-TARGETDURATION` e contagem de segmentos: indisponível, playlist retorna 404 (§7).
- Latência ponta a ponta com relógio na frente da câmera: **exige presença física na RVB**. Não é medível remotamente por mim.

**Referência histórica** (playlists que capturei hoje antes da quebra): `#EXT-X-TARGETDURATION:2`, `hls_list_size = 3`. O player está configurado com `liveSyncDurationCount: 2` (`apps/frontend/src/components/monitoring/CameraPlayer.tsx`), ou seja **~2 segmentos ≈ 4 s de buffer** antes de tocar, somados ao tempo de trânsito edge→nuvem→browser.

**Piso teórico ≈ 4–6 s.** É estimativa a partir da configuração, **não medição** — e o prompt pede o número medido. Só um teste presencial com relógio fecha isso.

---

## 9. O que NÃO foi possível medir (lacunas declaradas)

| Bloco | Item | Motivo |
|---|---|---|
| A | Curva de RAM 24–48h, OOM, headroom | Railway CLI sem subcomando de métricas; e deploys reiniciam o processo várias vezes ao dia no DEV |
| B4 | Distribuição de tamanho de segmento | Live view quebrado (§7); só há referência histórica |
| D | MB/s in/out, delta de RSS, CPU% | Live view quebrado + sem exec no container para ler RSS |
| E1 | ffmpeg vivos e RSS de cada | Sem exec no container |
| E3 | 5 chamadas em 13 s | Precisa de sessão autenticada no browser |
| F | Latência ponta a ponta medida | Exige relógio físico na frente da câmera, na RVB |

---

## 10. Correções identificadas — descritas, NÃO implementadas

| # | O quê | `file:line` | Esforço | Efeito esperado |
|---|---|---|---|---|
| 1 | 🔴 Criar `:active` no topo do `serve_hls` — destrava o cold start | `stream_handlers.py` ~198 | ~2 linhas + teste | Live view volta a funcionar (§7) |
| 2 | Guarda `edge_fed` também no `start_stream` | `stream_handlers.py:85-104` | baixo | Elimina FFmpeg condenado no start explícito (§6 E2) |
| 3 | Validar tamanho **antes** de materializar o corpo | `edge/routes.py:586` vs `589` | médio | Teto de 5 MB passa a proteger memória de verdade |
| 4 | Não bufferizar: `stream_with_context` no `serve_hls` | `stream_handlers.py:243` | médio | Opção **D** — corta o pico por response |
| 5 | Baixar `_MAX_SEGMENT_BYTES` de 5 MB para ~1 MB | `edge/routes.py:75` | trivial | Segmento real é ~276 KB; 5 MB é 18× a folga necessária |
| 6 | Definir `maxmemory` + política de evicção no Redis | infra Railway | trivial | Remove o risco de crescimento sem teto (§4) |
| 7 | Endpoint de introspecção de recursos (`ru_maxrss`) no `/health` | `services/api/app/api/v1/health` | baixo | **Destrava os blocos A, D e E1** em qualquer medição futura |

**Sugestão de ordem:** #1 (o live view está fora do ar) → #7 (sem ele, esta investigação se repete cega) → então decidir D/A/B **com a curva na mão**.

---

## 11. Recomendação sobre D / A / B

**Não recomendo escolher agora.** Os números que separam as três opções — a curva de RAM e o delta de RSS por câmera — são exatamente os que não consegui obter. Escolher entre D e B sem eles é trocar uma intuição por outra.

O que os números disponíveis **já** sustentam:

- **A** (correções pontuais) tem itens de custo trivial e benefício claro — #2, #5 e #6 valem por si, independentemente da decisão maior.
- **D** (não bufferizar) é coerente com o código encontrado (§3): os dois lados carregam o corpo inteiro. Mas o volume medido (~0,13 MB/s, segmento ~276 KB) é **pequeno** — só a curva dirá se esse pico explica o crescimento observado.
- **B** (segmento direto no R2) resolveria também o gargalo de **req/s** do worker único (§5), que é o limite que aparece antes da memória na conta para 25 câmeras. É o argumento mais forte a favor de B, e ele **não é sobre memória**.

**Próximo passo mínimo:** aplicar #1, abrir a aba Metrics do Railway com live view ativo por algumas horas e trazer a curva. Com ela, a decisão fica óbvia — sem ela, é palpite.
