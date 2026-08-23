# ADR-0064 — Caminho detecções edge→cloud: relay `det:*` → buffer → `/api/v1/edge/events/ingest` (ingest único, só violações)

**Status:** Proposta (2026-08-23) · **Autor:** Vitor Emanuel (Logikos) · **Estende:** ADR-0002
(Redis pub/sub como transporte de detecções), ADR-0019 (device token RS256 com escopos), ADR-0055
§7 ("um contrato por canal: `/edge/detections` vs `/events/ingest` — um morre"), ADR-0056 (daemon
supervisionado do agente). **Fecha** a decisão já registrada em
`docs/edge/INTEGRACAO_EDGE_F0F2_2026-07-19.md` §1 (canônico = `/events/ingest`; `/edge/detections`
não é implementado) e o item F3 de `tools/agent-driver/tasks/task-116-edge-f3-commands-e2e.md`.

## Contexto

Achado do mapa (PR #523, `edge-fleet.json` P1; `socketio-env.md` A4), confirmado no código
(C-04):

- `services/edge-sync-agent/app/uploader.py:45` montava `f"{cloud_url}/api/v1/edge/detections"` e
  postava `{device_id, detections: [linhas cruas do buffer]}`. Essa rota **nunca existiu** na API
  — no Flask real o POST cai no catch-all `serve_frontend` e responde **405** (provado pelo teste
  `tests/security/test_edge_events_ingest_tenant_isolation.py` antes da correção). O uploader
  então faz `mark_failed` e reenvia para sempre.
- O único ingest é `POST /api/v1/edge/events/ingest`
  (`services/api/app/api/v1/edge_events/routes.py:32`): `require_device_scope("events:write")`,
  corpo `{"events": [...]}` com ≤500 itens, `X-Batch-Id` opcional (senão uuid4),
  `dedup_key = X-Batch-Id + ":" + sha256(json(evento))[:16]`, `INSERT ... ON CONFLICT
  (tenant_id, dedup_key) DO NOTHING` em `public.edge_events` (migration 070). Não publica nada no
  Redis (não alimenta `det:*`, logo o evento SocketIO `detection` de `/monitor` continua sem fonte
  em `DEPLOYMENT_MODE=edge` — fora do escopo daqui).
- Repoint ingênuo da URL **não bastava** e seria pior: a rota lê `body["events"]`, então
  `{"detections": ...}` daria **200 com `ingested=0`** e o uploader faria `mark_sent` — perda
  silenciosa. Além disso o item cru do buffer carrega `attempts`, que muda a cada tentativa →
  `sha256(evento)` diferente por reenvio → o dedup do servidor **nunca** casaria.
- Nada no agente chamava `SQLiteBuffer.enqueue` fora dos testes. O produtor descrito em
  `AGENT.md` §3 (`mqtt_consumer.py`/Mosquitto) **nunca existiu** no repo. O transporte real de
  detecções é Redis pub/sub local (ADR-0002; `deployments/edge/redis-edge.conf`,
  `edge.env.example` `DETECTIONS_CHANNEL_TEMPLATE=detections:{camera_id}`), publicado pelo probe do
  DeepStream que roda nos runners `jetson-experiments/mm` do box — **fora deste repo** — e que, no
  diagnóstico de 2026-07-21, ainda não publicava.

## Decisão

1. **Um contrato por canal (ADR-0055 §7) — o canônico é `/api/v1/edge/events/ingest`;
   `/api/v1/edge/detections` morre (não é criado).** O `Uploader` passa a postar nessa rota com
   corpo `{"events": [{event_type, camera_id, payload, occurred_at}]}`: só os campos que a rota lê,
   `occurred_at` = `created_at` do buffer em ISO-8601 UTC (coluna `TIMESTAMPTZ`), **nada de
   contabilidade do buffer** (`id`/`attempts`) no fio — o evento serializa idêntico em todo reenvio,
   o que é a condição para o dedup `X-Batch-Id + sha256(evento)` do servidor funcionar. `X-Batch-Id`
   continua determinístico (sha256 dos ids ordenados). `batch_size` é recortado a 500 (teto da rota;
   maior seria 422 eterno = lote-veneno).
2. **Produtor = `detection_relay.py`**, 5º loop supervisionado do daemon (`main.run_daemon`),
   **opt-in por `EDGE_REDIS_URL`** (sem a variável o daemon sobe exatamente como antes). Assina
   `det:*` (nome usado pelos publicadores do repo — `services/inference`, task Celery
   `inference.py` — e pelo `socket_bridge` da API) **e** `detections:*` (nome do ADR-0002/`edge.env`),
   porque os dois nomes coexistem na documentação e o probe do box ainda não fixou um.
3. **Só frame com `has_violation=true` vira evento.** `det:*` é tráfego de overlay ao vivo (5 FPS ×
   N câmeras, efêmero por ADR-0002); relayar todo frame encheria um buffer que **nunca descarta**
   (`sqlite_buffer.py`) num box onde disco cheio é intertravamento (CLAUDE.md "Evidência"). O payload
   publicado vai inteiro como `payload` JSONB — sem reshaping no edge.
4. **Sem reconexão caseira no relay:** erro de transporte sobe, `main._supervise` reinicia com backoff
   e refaz o pubsub (mesmo mecanismo dos outros loops).

## Consequências

- O caminho detecções→cloud deixa de ser morto **no agente**: com `EDGE_REDIS_URL` e um publicador
  em `det:*`/`detections:*`, violação no box → `public.edge_events` na nuvem, idempotente. O que
  fica pendente e **não é inventado aqui**: o probe do DeepStream publicar no Redis local do box
  (fora do repo) e um consumidor de `GET /api/v1/edge/events` no frontend (não existe).
- Dependência nova no agente: `redis>=5.0` (puro Python, import tardio — só tocado com a flag).
- Dois nomes de canal assinados é dívida deliberada: quando o probe do box fixar o nome, reduzir a
  um (comentário `ponytail:` em `detection_relay.py`).
- Lote permanentemente rejeitado (ex.: `camera_id` que não é UUID → erro de INSERT → 500) continua
  sendo reenviado para sempre por desenho ("nunca descarta antes de confirmação") — dead-letter é
  decisão de produto pendente, não tratada aqui.
- `_VALID_EVENT_TYPES` em `edge_events/routes.py` é declarado mas **não validado** — o ingest aceita
  qualquer `event_type` não-vazio. Registrado, não alterado (fora do escopo).
