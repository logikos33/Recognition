# AGENT.md — services/edge-sync-agent

**Serviço:** Edge Sync Agent
**Status:** Parcialmente implementado. `config_poller.py`, `command_poller.py`, `sqlite_buffer.py`,
`uploader.py`, a **mini-API de evidência** (`evidence_api.py` + `evidence_auth.py` + `recorder_client.py`,
task-090), o **RecorderClient real ONVIF/RTSP** (`onvif_recorder_client.py` + `rtsp_timestamp_recorder_client.py`
+ `recorder_factory.py` + `rtsp_validator.py` + `rtsp_clip_stream.py`, task-091) e o **scanner de descoberta
ONVIF/WS-Discovery** (`onvif_discovery.py` + `discovery_api.py`, task-096) já existem e têm testes em `tests/`.
`main.py` agora sobe, num único processo Flask/porta, a mini-API de evidência (com o RecorderClient real) E a
API de descoberta — o restante descrito abaixo (`mqtt_consumer.py`, `model_manager.py`, `heartbeat.py`,
`stream_reporter.py`, `mirror_api.py`, `auth/`) segue placeholder — ver seção "Status: Placeholder" no fim deste
arquivo pro que falta.
**Responsabilidade:** Sincronizar estado do edge com o cloud API (heartbeats, model manifest, enrollment, batch upload de detecções) + servir evidência local/remota sob demanda (ADR-0045) + descobrir câmeras ONVIF no subnet isolado sem IP hard-coded (ADR-0020, task-096)

---

## Mini-API de evidência (task-090 — implementado)

`evidence_api.py` expõe uma API Flask local (`/api/v1/edge/evidence/{health,timeline,clip}`), servindo
evidência a partir do **gravador do site** (recorder-first, ADR-0045), nunca dos 128GB do edge. Acessível de
dois jeitos — LAN local do site OU cloud fazendo proxy através do túnel WireGuard (ADR-0020) — pelo mesmo
código, já que a diferença é só o caminho de rede até a porta (`validate_bind_host()` proíbe bind em
`0.0.0.0`/`::`, nunca exposta à internet pública).

- **Auth:** RS256 obrigatória em TODO endpoint (nenhum aberto) — `evidence_auth.py::TrustAnchor`, chave pública
  de um par mantido pelo cloud (chave privada nunca chega ao edge). Design completo: **ADR-0050**.
- **RecorderClient:** interface abstrata (`recorder_client.py`, `typing.Protocol`). `NotConfiguredRecorderClient`
  é o default de produção quando nada é injetado (falha alto, nunca finge servir dado real);
  `InMemoryRecorderClient` é só para testes. A implementação real está descrita na próxima seção.

---

## RecorderClient real ONVIF/RTSP (task-091 — implementado)

Fala com o gravador de verdade do site (ONVIF Profile G ou RTSP-com-timestamp), satisfazendo o `Protocol
RecorderClient` de `recorder_client.py`.

**C-04 — o que já existia:** um client ONVIF/RTSP maduro já existe em
`services/api/app/infrastructure/nvr/` (`onvif_client.py`, `hikvision_isapi_client.py`,
`generic_rtsp_client.py`, `factory.py`), construído pra outro consumidor (WS-B1, replay cloud-side de frames de
treino, ADR-0034) — mesmos envelopes SOAP, mesma cascata de protocolo, mesma limitação ("nunca validado contra
hardware real"). `onvif_recorder_client.py` e `rtsp_timestamp_recorder_client.py` **portam** essa lógica
(ONVIF + fallback RTSP) em vez de importá-la: `services/edge-sync-agent` e `services/api` são processos com
deploy/`requirements.txt` independentes, e não há precedente no repo de código de protocolo/I/O compartilhado
entre `services/*` — o único pacote compartilhado hoje (`shared/python/recognition_shared`) é só DTOs Pydantic,
sem lógica de rede. Manter os dois lados sincronizados manualmente é o trade-off aceito (ver PR da task-091 para
a análise completa). Hikvision ISAPI **não** foi portado — nenhum cliente RVB usa Hikvision (CLAUDE.md); a
factory recusa (`RecorderError`) qualquer protocolo não suportado em vez de mapear silenciosamente pra outro
client.

- **`onvif_recorder_client.py`** — ONVIF Profile G real (SOAP cru via `httpx`, sem WSDL): `GetSystemDateAndTime`
  (health), `FindRecordings`+`GetRecordingSearchResults` (timeline → `RecorderEvent`), `GetReplayUri` (URL de
  playback) → `rtsp_clip_stream.py` pra puxar os bytes.
- **`rtsp_timestamp_recorder_client.py`** — fallback RTSP-com-timestamp (dialeto Dahua, formato
  `YYYY_MM_DD_HH_MM_SS`), usado quando o gravador não expõe API de busca dedicada. **É o protocolo real da RVB
  (Intelbras)** — sem índice de timeline de verdade: `list_events` sempre devolve um único evento sintético
  cobrindo a janela pedida; se não houver gravação ali, a falha aparece em `stream_clip`, não na busca
  (limitação herdada do ADR-0034, documentada no módulo, não fingida como resolvida).
- **`rtsp_validator.py`** — porte do `RTSPUrlValidator` do monolito (SSRF/command-injection guard), usado antes
  de qualquer URL chegar a um client de rede (SOAP HTTP ou ffmpeg).
- **`rtsp_clip_stream.py`** — pull de bytes de uma URL RTSP de playback já resolvida, via subprocess `ffmpeg`
  (`-c copy`, remux fragmentado, sem tocar disco), compartilhado pelos dois clients. **Nova dependência de
  runtime**: `ffmpeg` precisa estar no PATH do container/host do edge-sync-agent (não era necessário antes desta
  task).
- **`recorder_factory.py`** — resolve protocolo → client concreto. `build_recorder_client_from_env()` lê
  `RECORDER_PROTOCOL`/`RECORDER_HOST`/`RECORDER_PORT`/`RECORDER_USERNAME`/`RECORDER_PASSWORD`/
  `RECORDER_CHANNEL_MAP` (JSON `{camera_id: canal}`) — configuração **local ao device**, não vem do
  `public.recorders` do cloud (essa tabela serve o fluxo WS-B1, não tem mapeamento câmera→canal, e não está
  cabeada em `GET /api/v1/edge/config/poll` hoje; threadear isso seria uma mudança maior, fora do escopo desta
  task).
- **`main.py`** — entrypoint mínimo (`python -m app.main`): monta o `RecorderClient` real +
  `TrustAnchor` (lê `EVIDENCE_TRUST_PUBLIC_KEY_PATH`, `TENANT_ID`, `SITE_ID`) e sobe `evidence_api` via
  `run_server`. Não inicia os outros loops (heartbeat/config-poll/uploader) — isso é escopo futuro (o daemon
  completo da Fase 4).

**Sem validação em hardware real** — mesma limitação documentada no `onvif_client.py` do monolito: cobertura só
por SOAP/RTSP mockado e subprocess `ffmpeg` fake, spec-compliant por leitura da especificação pública ONVIF /
dialeto Dahua conhecido, nunca exercitado contra um gravador real. Validação real é escopo do go-live
(task-095/task-097).
- **Sem persistência:** `GET /clip` faz streaming puro (generator) direto do recorder pra resposta HTTP — nada
  é gravado em disco no edge.
- **Sem validação em hardware real** (Jetson/NVR) — só testes automatizados com chaves RSA efêmeras e recorder
  mockado.

---

## Descoberta ONVIF/WS-Discovery (task-096 — implementado)

Descobre câmeras ONVIF no subnet isolado atrás do MikroTik **sem IP hard-coded** (ADR-0020, "Portabilidade de
rede"), diferente do `onvif_recorder_client.py` (task-091), que fala com o gravador cujo host **já é conhecido**
via `RECORDER_HOST`.

**C-04 — o que já existia:** nada. Não havia nenhum código de descoberta ONVIF/WS-Discovery no monolito nem no
edge antes desta task — greenfield. WS-Discovery (multicast UDP 239.255.255.250:3702) é um protocolo diferente
do ONVIF Profile G usado em `onvif_recorder_client.py` (que fala direto com um host conhecido via SOAP/HTTP).

- **`onvif_discovery.py`** — `discover_devices()` envia um probe SOAP WS-Discovery mínimo (`socket.socket`
  injetável via `sock_factory`, mesmo estilo DI do `popen` injetável em `rtsp_clip_stream.py`), coleta respostas
  `ProbeMatch` até `timeout_seconds` (wall clock) OU `max_responses` (cap de datagramas — resistência a flood
  UDP forjado), o que vier primeiro. Parsing **defensivo por regex** (mesma disciplina do
  `onvif_recorder_client.py` — sidesteps XXE por construção: nenhum parser DOM/SAX roda sobre bytes de rede não
  confiáveis), um datagrama malformado é logado e pulado, nunca derruba o scan. `build_suggested_rtsp_url()`
  monta uma URL RTSP sugerida a partir do IP de origem do pacote e **valida via `RTSPUrlValidator` antes de
  retornar** — um IP de origem forjado (loopback/link-local/multicast/reservado) faz a sugestão vir `None`, nunca
  uma URL não validada. `fetch_device_information()` é enriquecimento opcional (GetDeviceInformation ONVIF) —
  best-effort, nunca derruba a descoberta se um device específico não responder.
- **`discovery_api.py`** — `GET /api/v1/edge/discovery/scan`, protegido pelo MESMO `TrustAnchor`/
  `EvidenceScope` RS256 do task-090 (novo scope `discovery:read` — ver docstring do enum em `evidence_auth.py`
  pra por que não foi criado um módulo de auth paralelo). Retorna a lista de dispositivos **crus** descobertos
  (IP, XAddrs, tipos, escopos, URL RTSP sugerida já validada, info de hardware best-effort) — **não** tenta
  associar a câmeras já cadastradas (essa associação depende de `cameras`/`ip_cameras`, que vivem no schema do
  tenant na nuvem; este processo edge não tem acesso a esse DB — ver docstring do módulo pra decisão completa).
  Registrado no MESMO app Flask/porta da mini-API de evidência em `main.py` (não é um segundo processo/porta).
- **Sem validação em rede/hardware real** — mesma limitação do resto do RecorderClient ONVIF: cobertura só via
  socket UDP fake e SOAP mockado; nunca exercitado contra multicast real ou câmera física. Depende de
  **task-095** (rede portátil, MikroTik físico), bloqueada por hardware (`queue-hardware.txt`) — esta task-096
  foi categorizada pelo dono do projeto como "Bloco 7 (parte cloud)" na fila principal, ou seja, construída e
  testada isoladamente da task-095, com a validação em subnet real explicitamente adiada pro go-live
  (task-095/097), mesmo padrão já aplicado nas tasks 090/091.

---

## Propósito

O `edge-sync-agent` é o ponto de contato entre o mini PC de edge do cliente e o cloud (Railway). Roda ao lado dos pipelines DeepStream, consumindo eventos MQTT locais, bufferizando em SQLite para resiliência offline e enviando em batch para a API cloud quando há conectividade.

Também expõe uma `mirror-api` na LAN para que o frontend possa operar em modo offline quando o cloud está inacessível (ADR-0006: Frontend Dual Mode).

---

## Stack Planejado

| Componente | Tecnologia |
|-----------|-----------|
| Runtime | Python 3.11 |
| MQTT client | `paho-mqtt` (Mosquitto local) |
| Buffer offline | SQLite (WAL mode) |
| HTTP client | `httpx` com retry + backoff exponencial |
| Mirror API | FastAPI (endpoints essenciais para LAN) |
| Auth | JWT RS256 (device token, ADR-0008) |
| Container | Docker (Ubuntu 22.04 base) |

---

## Estrutura de Diretórios (Planejada)

```
services/edge-sync-agent/
├── app/
│   ├── __init__.py
│   ├── main.py               # Entry point: inicia todos os loops em threads/asyncio
│   ├── mqtt_consumer.py      # Subscribe MQTT local: events/critical, events/detection
│   ├── sqlite_buffer.py      # Buffer persistente: enqueue, dequeue, mark_sent
│   ├── uploader.py           # POST batch para /api/v1/edge/detections com backoff
│   ├── config_poller.py      # GET /api/v1/edge/config/poll (câmeras, regras, módulos)
│   ├── model_manager.py      # Download, validação SHA256, swap de modelos YOLO
│   ├── heartbeat.py          # POST /api/v1/edge/heartbeat a cada 60s
│   ├── stream_reporter.py    # POST /api/v1/edge/streams/report (status dos pipelines)
│   ├── mirror_api.py         # FastAPI: espelha /health, /alerts/recent, /cameras
│   └── auth/
│       ├── enrollment.py     # Processo de enrollment com one-time token
│       └── token_manager.py  # Carrega device token do filesystem seguro, rotaciona
├── tests/
├── Dockerfile
├── requirements.txt
├── AGENT.md                  # Este arquivo
└── SDD.md
```

---

## Responsabilidades Principais

### 1. Enrollment (uma vez por dispositivo)

```
Operador fornece ONE_TIME_TOKEN (gerado na API cloud)
  → enrollment.py POST /api/v1/edge/enroll {device_id, one_time_token, site_id}
  → API valida token, cria registro em device_tokens
  → API retorna device JWT RS256 assinado
  → token_manager.py persiste em /run/secrets/device_token (Docker secret)
  → ONE_TIME_TOKEN invalidado imediatamente
```

**Tabela cloud:** `device_tokens` (migration 042+)

### 2. Heartbeats

```
heartbeat.py loop a cada 60s:
  → lê métricas locais (CPU, GPU util, temperatura, FPS dos pipelines)
  → POST /api/v1/edge/heartbeat {device_id, metrics, timestamp}
  → API insere em edge_heartbeats
  → Se 3 heartbeats perdidos → API marca device como offline → alerta para operador
```

**Tabela cloud:** `edge_heartbeats` (migration 043+)

### 3. Batch Upload de Detecções

```
mqtt_consumer.py assina events/detection no Mosquitto local
  → sqlite_buffer.py enfileira detecção (WAL SQLite)
  → uploader.py loop a cada 30s:
      → lê lote de até 500 registros do SQLite
      → POST /api/v1/edge/detections {device_id, detections: [...]}
      → Se 200: mark_sent(ids)
      → Se erro de rede: backoff exponencial (30s → 60s → 120s → 300s)
      → Registros nunca deletados antes de confirmação
```

**Buffer local:** SQLite em `/var/edge-sync/buffer.db`
**Tabela cloud:** `edge_detections_buffer` → processado para `alerts` pelo worker

### 4. Model Manifest Pull

```
config_poller.py loop a cada 5 min:
  → GET /api/v1/edge/config/poll {device_id, current_model_sha256}
  → Se model_sha256 diferente:
      → model_manager.py baixa novo .pt/.engine de URL assinada
      → Valida SHA256
      → Coloca em YOLO_MODELS_DIR (monitorado pelo model_watcher do inference)
      → Inference service carrega novo modelo sem restart
  → Também recebe atualizações de câmeras e regras
```

**Tabela cloud:** `model_manifests` (migration 044+)

### 5. Mirror API (LAN Fallback)

```
mirror_api.py expõe FastAPI na porta 8080 da LAN:
  GET  /health           → status local do edge
  GET  /alerts/recent    → últimos 50 alertas do SQLite local
  GET  /cameras          → lista câmeras configuradas localmente
  GET  /streams/status   → status dos pipelines DeepStream
```

O frontend usa `useDualMode.ts`: se cloud inacessível, conecta em `http://edge.{site}.local:8080`.

---

## Auth: Device Token RS256

- **Algoritmo:** RS256 (assimétrico)
- **Chave privada:** armazenada apenas no cloud (Railway secret)
- **Chave pública:** distribuída para o edge no enrollment
- **Escopos no token:** `heartbeat:write`, `detection:write`, `config:read`, `stream:report`
- **Validade:** 60 dias; renovação automática via `token_manager.py`
- **Separação:** completamente separado dos JWT HS256 de usuários

Ver ADR-0008 para detalhes da spec.

---

## Resiliência Offline

```
Conectividade OK:
  SQLite buffer → uploader → cloud → mark_sent

Sem conectividade (buffer SQLite):
  Capacidade: ~72h de detecções a 5 FPS (estimativa RVB 28 câmeras)
  Ao reconectar: flush automático em ordem cronológica
  Nunca perde dados enquanto disco disponível

Mirror API LAN:
  Continua operando normalmente
  Frontend LAN vê alertas em tempo real via mirror_api + Redis local
```

---

## Variáveis de Ambiente

| Variável | Descrição |
|---------|-----------|
| `CLOUD_API_URL` | URL base da API cloud |
| `DEVICE_ID` | UUID do dispositivo edge (gerado no enrollment) |
| `DEVICE_TOKEN_PATH` | Path para o device JWT (padrão: `/run/secrets/device_token`) |
| `MQTT_BROKER_URL` | URL do Mosquitto local (padrão: `mqtt://localhost:1883`) |
| `SQLITE_BUFFER_PATH` | Path do SQLite (padrão: `/var/edge-sync/buffer.db`) |
| `REDIS_URL` | Redis local para mirror_api |
| `MIRROR_API_PORT` | Porta da mirror API LAN (padrão: `8080`) |
| `HEARTBEAT_INTERVAL_S` | Intervalo de heartbeat em segundos (padrão: `60`) |
| `UPLOAD_BATCH_SIZE` | Tamanho do lote de upload (padrão: `500`) |
| `RECORDER_PROTOCOL` | Protocolo do gravador: `onvif`, `intelbras`, `dahua` ou `rtsp` (task-091) |
| `RECORDER_HOST` / `RECORDER_PORT` | Endereço do gravador na LAN do site (task-091) |
| `RECORDER_USERNAME` / `RECORDER_PASSWORD` | Credenciais do gravador (task-091) |
| `RECORDER_CHANNEL_MAP` | JSON `{camera_id: canal}` — mapeamento local, não vem do cloud (task-091) |
| `EVIDENCE_TRUST_PUBLIC_KEY_PATH` | Path da chave pública do trust anchor (padrão: `/run/secrets/evidence_trust_public_key.pem`, ADR-0050) |
| `EVIDENCE_API_BIND_HOST` | IP da interface WireGuard/LAN pra `evidence_api` — nunca `0.0.0.0`/`::` |
| `EVIDENCE_API_PORT` | Porta da mini-API de evidência (padrão: `8443`) |
| `ONVIF_DISCOVERY_TIMEOUT_S` | Timeout (segundos) do scan WS-Discovery por request (padrão: `3.0`, task-096) |
| `ONVIF_DISCOVERY_MAX_RESPONSES` | Cap de datagramas UDP processados por scan — resistência a flood forjado (padrão: `50`, task-096) |
| `ONVIF_DISCOVERY_ENRICH_DEVICE_INFO` | `true`/`false` — se o scan tenta `GetDeviceInformation` best-effort por device (padrão: `true`, task-096) |

---

## Status: Parcialmente placeholder

O restante do que está descrito acima (`mqtt_consumer.py`, `model_manager.py`, `heartbeat.py`,
`stream_reporter.py`, `mirror_api.py`, `auth/enrollment.py`, `auth/token_manager.py`) ainda não está
implementado — nenhum desses loops é iniciado por `main.py` hoje. `config_poller.py`, `command_poller.py`,
`sqlite_buffer.py`, `uploader.py`, a mini-API de evidência (`evidence_api.py`/`evidence_auth.py`/
`recorder_client.py`, task-090), o RecorderClient real ONVIF/RTSP (`onvif_recorder_client.py`/
`rtsp_timestamp_recorder_client.py`/`recorder_factory.py`/`rtsp_validator.py`/`rtsp_clip_stream.py`, task-091), o
scanner de descoberta ONVIF (`onvif_discovery.py`/`discovery_api.py`, task-096) e um `main.py` que sobe, no
mesmo processo/porta, a mini-API de evidência com o RecorderClient real E a API de descoberta (task-091/096) JÁ
existem — ver seções acima.

**Implementação:** Fase 4 do `EDGE_DEPLOYMENT_PLAN.md`
**Dependências de migrations:** 042 (`device_tokens`), 043 (`edge_heartbeats`), 044 (`model_manifests`)
**Dependências de API:** blueprint `/api/v1/edge/*` (Fase 2)

**ADRs relacionados:**
- ADR-0004: HTTP Polling Edge↔Cloud
- ADR-0007: Deployment Modes por Tenant
- ADR-0008: Device Tokens RS256
- ADR-0009: MediaMTX como RTSP multiplexer
- ADR-0016: SQLite como buffer offline
- ADR-0019: Device Tokens RS256 (versão em produção do ADR-0008)
- ADR-0020: MikroTik/WireGuard — camada de rede que restringe quem alcança a mini-API de evidência
- ADR-0045: Evidência recorder-first — motivação da mini-API de evidência
- ADR-0050: Auth cloud/local → edge (trust anchor RS256 invertido, mini-API de evidência)
- ADR-0052: Descoberta ONVIF/WS-Discovery — onde roda, formato de resultado, associação a câmeras cadastradas
