# AGENT.md — services/edge-sync-agent

**Serviço:** Edge Sync Agent
**Status:** Parcialmente implementado. `config_poller.py`, `command_poller.py`, `sqlite_buffer.py`,
`uploader.py`, a **mini-API de evidência** (`evidence_api.py` + `evidence_auth.py` + `recorder_client.py`,
task-090), o **RecorderClient real ONVIF/RTSP** (`onvif_recorder_client.py` + `rtsp_timestamp_recorder_client.py`
+ `recorder_factory.py` + `rtsp_validator.py` + `rtsp_clip_stream.py` + `rtsp_frame_capture.py`, task-091/092), o
**scanner de descoberta ONVIF/WS-Discovery** (`onvif_discovery.py` + `discovery_api.py`, task-096), a
**pré-anotação zero-shot de onboarding** (`zero_shot_detector.py` + `zero_shot_pre_annotation.py`, task-098) e o
**coletor de frames motion-triggered** (`app/collector/`, task-093, Onda 2 shadow mode) já existem e têm testes
em `tests/`. Identidade (`auth/`, PR-A), heartbeat (`heartbeat.py`, PR-B) e o daemon orquestrador supervisionado
(`main.py`'s `run_daemon()`, PR-C) também já existem e têm teste — `python -m app.main` sobe, num único
processo, a mini-API de evidência (RecorderClient real) + a API de descoberta + os quatro loops de sincronia,
cada um numa thread supervisionada (restart com backoff, shutdown gracioso em SIGTERM/SIGINT); o coletor de
frames (`python -m app.collector`) é um processo **separado**, com sua própria unit systemd. O restante
descrito abaixo (`mqtt_consumer.py`, `model_manager.py`, `stream_reporter.py`, `mirror_api.py`) segue
placeholder — ver seção "Status: Placeholder" no fim deste arquivo pro que falta.
**Responsabilidade:** Sincronizar estado do edge com o cloud API (heartbeats, model manifest, enrollment, batch upload de detecções) + servir evidência local/remota sob demanda (ADR-0045) + descobrir câmeras ONVIF no subnet isolado sem IP hard-coded (ADR-0020, task-096) + pré-anotar frames via zero-shot no onboarding de tenant novo (ADR-0047)

---

## Pré-anotação zero-shot de onboarding (task-098 — implementado)

Lote sob demanda (não um loop contínuo, não serving de produção) rodado pelo operador durante o onboarding
de um tenant novo, antes de ele ter qualquer modelo custom treinado: dado um diretório de frames + uma
lista de labels de texto (a taxonomia de classes do tenant, ADR-0031 estágio CLASSES), roda um detector
zero-shot (guiado por texto, não por classes fixas de treino) e produz sugestões no MESMO formato de
`pre_annotations` que `annotation_service.get_frame_annotations` já sabe ler — revisão humana acontece na
MESMA tela `AnnotationInterface.jsx`, nenhuma UI nova. Ver ADR-0047 (adendo 2026-07-15) para a análise
completa (licença, por que não é o mesmo transporte do `PreAnnotationBackend` cloud, flag reaproveitada).

- **`zero_shot_detector.py`** — `ZeroShotDetector` (`typing.Protocol`, mesmo padrão de
  `recorder_client.py::RecorderClient`): `detect(image_bytes, text_labels) -> list[ZeroShotDetection]`.
  `NotConfiguredZeroShotDetector` é o default que falha alto; `StubZeroShotDetector` é determinístico só
  para teste; `OwlVitZeroShotDetector` é o backend real (NanoOWL/TensorRT — **Apache-2.0, licença
  verificada na fonte primária**, ver ADR-0047), com import tardio do `nanoowl` pra não exigir a
  dependência pesada (TensorRT) só para importar o módulo.
- **`zero_shot_pre_annotation.py`** — `is_zero_shot_enabled(feature_flags)` (exige
  `pre_annotation_enabled: true` E `pre_annotation_backend: "zero_shot"`, sem fallback de env var),
  `to_pre_annotation_dict(s)` (conversão pro formato `{"bbox": {cx,cy,w,h}, "class", "confidence"}`),
  `run_onboarding_pre_annotation(...)` (orquestra o lote, aborta no primeiro erro por padrão ou
  `continue_on_frame_error=True` pra pular e registrar), e um CLI (`python -m app.zero_shot_pre_annotation
  --frames-dir ... --text-labels ... --feature-flags '...' --engine-path ... --output out.json`).
- **Não integrado:** a persistência de fato em `training_frames.pre_annotations` (endpoint HTTP aceitando
  esse payload) é trabalho futuro — este lote produz o JSON no formato certo, não escreve no banco cloud
  (o edge não tem acesso direto ao Postgres do tenant, só via API).
- **Sem validação em hardware real** (Jetson/TensorRT) — mesma limitação de toda a fila 090/091/096.
  `OwlVitZeroShotDetector` nunca é exercitado contra um engine TensorRT real nos testes; cobertura é por
  leitura da API pública do NanoOWL, nunca contra hardware.

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
  playback) → `rtsp_clip_stream.py` pra puxar os bytes. `capture_frame` (task-092) resolve a URL AO VIVO via
  Media `GetStreamUri` (serviço ONVIF diferente do Replay), mesmo `channel_map`.
- **`rtsp_timestamp_recorder_client.py`** — fallback RTSP-com-timestamp (dialeto Dahua, formato
  `YYYY_MM_DD_HH_MM_SS`), usado quando o gravador não expõe API de busca dedicada. **É o protocolo real da RVB
  (Intelbras)** — sem índice de timeline de verdade: `list_events` sempre devolve um único evento sintético
  cobrindo a janela pedida; se não houver gravação ali, a falha aparece em `stream_clip`, não na busca
  (limitação herdada do ADR-0034, documentada no módulo, não fingida como resolvida). `capture_frame`
  (task-092) usa a convenção Dahua-OEM `/cam/realmonitor?channel=N&subtype=0` (stream principal ao vivo),
  irmã do `/cam/playback` já existente.
- **`rtsp_frame_capture.py`** — irmão de `rtsp_clip_stream.py` (task-092): `ffmpeg -frames:v 1 -f mjpeg pipe:1`
  pra um único frame do stream AO VIVO, sem tocar disco. Diferente do streaming de clipe, é uma chamada
  bloqueante única com timeout explícito (`communicate(timeout=...)` + `kill()`) — sem isso um RTSP que nunca
  conecta travaria o coletor (próxima seção) indefinidamente.
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
- **`main.py`** — dois entrypoints (PR-C, feito):
  - `main()` — só a evidence/discovery API: monta o `RecorderClient` real + `TrustAnchor` (lê
    `EVIDENCE_TRUST_PUBLIC_KEY_PATH`, `TENANT_ID`, `SITE_ID`) e sobe via `run_server`. Comportamento
    inalterado desde task-090/096, testes intactos.
  - `run_daemon()` — **o daemon completo, é o que `python -m app.main` roda agora**: a evidence API acima
    numa thread + `config_poller`/`command_poller`/`uploader`/`heartbeat` cada um na própria thread com um
    `stop_event` compartilhado. Identidade via `token_manager` (PR-A, `ensure_enrolled` roda uma vez no
    boot — idempotente); `_AutoAuthHttpClient` cunha um bearer novo a cada request pros 3 loops que só
    aceitam `token: str` estático no construtor (`config_poller`/`command_poller`/`uploader` — não foram
    alterados, só embrulhados). `heartbeat` já toma o `token_manager` direto (PR-B). Loop que crasha (ou
    retorna sozinho, ex. heartbeat após um 403) é reiniciado com backoff (5/15/30/60s) — nunca derruba o
    daemon. `SIGTERM`/`SIGINT` seta o `stop_event` e dá `join` nas threads (timeout 35s).

**Sem validação em hardware real** — mesma limitação documentada no `onvif_client.py` do monolito: cobertura só
por SOAP/RTSP mockado e subprocess `ffmpeg` fake, spec-compliant por leitura da especificação pública ONVIF /
dialeto Dahua conhecido, nunca exercitado contra um gravador real. Validação real é escopo do go-live
(task-095/task-097).
- **Sem persistência:** `GET /clip` faz streaming puro (generator) direto do recorder pra resposta HTTP — nada
  é gravado em disco no edge.
- **Sem validação em hardware real** (Jetson/NVR) — só testes automatizados com chaves RSA efêmeras e recorder
  mockado.

---

## Coletor de frames motion-triggered (task-093 — implementado)

Onda 2 shadow-mode pilot (2 câmeras + NVR reais da RVB): constrói o pool inicial de treino subindo frames do
feed AO VIVO das câmeras — coleta pura, sem inferência. `app/collector/` (subpacote, mesmo padrão de
`app/ota/`):

- **`motion_detector.py`** — `MotionDetector`/`frame_diff_score`: diferença média de pixel (0-255) entre
  thumbnails cinza reduzidos (64×48), só Pillow (sem numpy/opencv — wheel do opencv-python em ARM/Jetson é
  landmine conhecida, o JetPack já tem o próprio build). Sem eventos ONVIF de motion confirmados no hardware
  da RVB (investigação da task-092) — frame-diffing é o único sinal disponível. Pura função/classe, sem I/O.
- **`frame_uploader.py`** — `upload_frame()`: multipart pra `POST /api/v1/edge/frames` (mesmo contrato do
  endpoint cloud, task-089), auth via bearer fresco (`token_source.get_bearer()` a cada upload, mesmo padrão
  do `HeartbeatLoop`).
- **`collector_loop.py`** — `CollectorLoop`: máquina de estado por câmera (idle → poll → motion → burst →
  cooldown), sequencial (sem concorrência por câmera — correto e simples pro piloto de 2 câmeras, documentado
  como limitação de escala pra quando a RVB for pros ~28 canais). Burst captura `COLLECTOR_BURST_COUNT` frames
  espaçados por `COLLECTOR_BURST_INTERVAL_S`, dedup contra o último frame enviado (limiar bem mais estrito que
  o de disparo — só pula repetição quase exata). Contador de frames por câmera (`COLLECTOR_TARGET_FRAMES_PER_CAMERA`,
  padrão 1000) é **em memória** — reseta a cada restart do processo (aceitável pro piloto: pior caso coleta um
  pouco A MAIS que o alvo, nunca menos).
- **`__main__.py`** — `python -m app.collector`: lê a identidade já enrolada (não enrola sozinho, mesmo padrão
  do `app/ota/__main__.py`), monta o `RecorderClient` real (`recorder_factory.py`) e roda `CollectorLoop.run()`
  até `SIGTERM`/`SIGINT`.

**Por que processo próprio, NÃO uma 5ª thread em `run_daemon()`:** decisão de produto na largada da Onda 2 —
carga mais pesada/em rajada (decode JPEG + diff a cada poll tick) e precisa poder ser parado/reiniciado sem
tocar identidade/heartbeat/config-sync. Unit systemd --user separada:
`deploy/edge-frame-collector.service` (mesmo `Type=simple`/`Restart=always` do daemon principal).

**Config nova:** `RECORDER_CLOUD_ID` (UUID do `public.recorders` na nuvem — diferente de `RECORDER_HOST`/`PORT`,
que são a conexão local; obrigatório, sem default). Câmeras monitoradas = as chaves de `RECORDER_CHANNEL_MAP`
(reaproveitado do `recorder_factory.py`, sem lista separada pra não divergir).

**Sem validação em hardware real** — mesma disciplina do resto da fila 090-093: cobertura só via
`RecorderClient`/`upload_fn`/relógio fake, nunca exercitado contra câmera física ou o endpoint cloud de
verdade. Calibração de `COLLECTOR_MOTION_THRESHOLD` contra cena real da RVB é go-live (task-097).

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
│   └── auth/                 # PR-A, feito — identidade do device (ver seção "Enrollment" abaixo)
│       ├── enrollment.py     # POST /edge/enroll idempotente, one-time token, backoff em falha de rede
│       └── token_manager.py  # Gera/guarda o par RSA do device, cunha JWT RS256 auto-assinado
├── tests/
├── Dockerfile
├── requirements.txt
├── AGENT.md                  # Este arquivo
└── SDD.md
```

---

## Responsabilidades Principais

### 1. Enrollment (uma vez por dispositivo) — `app/auth/` (PR-A, feito)

**Contrato REAL (não o antigo descrito abaixo neste histórico) — provado por `scripts/edge_artery_probe.py`
(PR #227) e reproduzido em produção por `app/auth/token_manager.py` + `app/auth/enrollment.py`:** o **device é
dono da chave**, não o cloud.

```
token_manager.py gera par RSA-2048 na 1ª execução → persiste a PRIVADA em disco (chmod 600)
  → enrollment.py POST /api/v1/edge/enroll {enrollment_token, device_id, device_name, public_key_pem}
  → API valida o enrollment_token (one-time), cria registro em device_tokens/devices
  → API retorna 201 {tenant_id, site_id, device_id, scopes} — NÃO retorna JWT
  → token_manager.py persiste a identidade (identity.json, chmod 600, ao lado da chave)
  → dali em diante, get_bearer() AUTO-ASSINA um JWT RS256 curto (~5min) com a privada —
    o cloud só verifica a assinatura com a pública recebida no enroll (ADR-0019 S7)
```

**Guarda de chave:** `EDGE_DEVICE_KEY_PATH` (default `/var/lib/recognition-edge/keys/device_key.pem`), fora do
repo, `chmod 600`, dono = usuário do serviço. Chave e `enrollment_token`/JWT nunca são logados. Rotação/revogação
de chave: previsto, não implementado (só o flag `revoked` na identidade, que já bloqueia `get_bearer()` —
consumo do `403` de device revogado no heartbeat é PR-B).

**Dependência operacional:** RS256 com `iat`/`exp` exige **relógio correto no device** → NTP é obrigatório no
Jetson (enforcement no deploy é PR-D).

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
- **Chave privada:** gerada e armazenada **no device** (`app/auth/token_manager.py`) — o cloud NUNCA emite
  token nem guarda a privada. (Corrige a versão anterior deste doc, que descrevia o inverso — drift real, ver
  C-04 no CLAUDE.md raiz.)
- **Chave pública:** enviada ao cloud no enroll (`public_key_pem` no `POST /edge/enroll`); é o que o servidor usa
  pra verificar a assinatura de cada JWT recebido.
- **Escopos no token:** `heartbeat:write`, `detection:write`, `config:read`, `stream:report` — os que o enroll
  devolve em `scopes`.
- **Validade:** curta por token (~5 min, auto-assinado a cada uso via `get_bearer()`), não 60 dias — não há
  "renovação", cada chamada cunha um JWT novo.
- **Separação:** completamente separado dos JWT HS256 de usuários

Ver ADR-0019 (S7) para a reconciliação da spec.

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
| `DEVICE_ID` | ID do dispositivo edge — obrigatório, definido antes do enrollment (não gerado por ele) |
| `DEVICE_NAME` | Nome amigável do device pro enroll (padrão: igual a `DEVICE_ID`) |
| `EDGE_API_URL` | URL base da API cloud pro enroll (padrão DEV: `api-v3-desenvolvimento`, nunca produção por default) |
| `ENROLLMENT_TOKEN` | Token one-time do admin — só necessário no 1º enroll (idempotente: pulado se já há identidade) |
| `EDGE_DEVICE_KEY_PATH` | Path da chave privada RS256 do device (padrão: `/var/lib/recognition-edge/keys/device_key.pem`, chmod 600) |
| `MQTT_BROKER_URL` | URL do Mosquitto local (padrão: `mqtt://localhost:1883`) |
| `SQLITE_BUFFER_PATH` | Path do SQLite (padrão: `/var/edge-sync/buffer.db`) |
| `REDIS_URL` | Redis local para mirror_api |
| `MIRROR_API_PORT` | Porta da mirror API LAN (padrão: `8080`) |
| `EDGE_HEARTBEAT_INTERVAL_S` | Intervalo de heartbeat em segundos (padrão: `45`, PR-B) |
| `EDGE_VERSION` | Versão do stack edge — vai no heartbeat, opcional (PR-B) |
| `UPLOAD_BATCH_SIZE` | Tamanho do lote de upload (padrão: `500`) |
| `RECORDER_PROTOCOL` | Protocolo do gravador: `onvif`, `intelbras`, `dahua` ou `rtsp` (task-091) |
| `RECORDER_HOST` / `RECORDER_PORT` | Endereço do gravador na LAN do site (task-091) |
| `RECORDER_USERNAME` / `RECORDER_PASSWORD` | Credenciais do gravador (task-091) |
| `RECORDER_CHANNEL_MAP` | JSON `{camera_id: canal}` — mapeamento local, não vem do cloud (task-091); também usado pelo coletor (task-093) como lista de câmeras |
| `RECORDER_CLOUD_ID` | UUID do `public.recorders` na nuvem — obrigatório só pro coletor (task-093), diferente de `RECORDER_HOST`/`PORT` |
| `COLLECTOR_MODULE_CODE` | Módulo do frame enviado (padrão: `epi`, task-093) |
| `COLLECTOR_POLL_INTERVAL_S` | Intervalo entre polls de motion por câmera, segundos (padrão: `3.0`, task-093) |
| `COLLECTOR_MOTION_THRESHOLD` | Limiar de diferença média de pixel (0-255) pra disparar burst (padrão: `8.0`, task-093, não calibrado contra hardware real) |
| `COLLECTOR_BURST_COUNT` | Frames capturados por disparo de movimento (padrão: `8`, task-093) |
| `COLLECTOR_BURST_INTERVAL_S` | Espaçamento entre frames do burst, segundos (padrão: `1.0`, task-093) |
| `COLLECTOR_COOLDOWN_S` | Tempo sem repollar movimento após um burst, segundos (padrão: `30.0`, task-093) |
| `COLLECTOR_TARGET_FRAMES_PER_CAMERA` | Alvo de frames por câmera antes de parar de coletar — contador em memória, reseta a cada restart (padrão: `1000`, task-093) |
| `EVIDENCE_TRUST_PUBLIC_KEY_PATH` | Path da chave pública do trust anchor (padrão: `/run/secrets/evidence_trust_public_key.pem`, ADR-0050) |
| `EVIDENCE_API_BIND_HOST` | IP da interface WireGuard/LAN pra `evidence_api` — nunca `0.0.0.0`/`::` |
| `EVIDENCE_API_PORT` | Porta da mini-API de evidência (padrão: `8443`) |
| `ONVIF_DISCOVERY_TIMEOUT_S` | Timeout (segundos) do scan WS-Discovery por request (padrão: `3.0`, task-096) |
| `ONVIF_DISCOVERY_MAX_RESPONSES` | Cap de datagramas UDP processados por scan — resistência a flood forjado (padrão: `50`, task-096) |
| `ONVIF_DISCOVERY_ENRICH_DEVICE_INFO` | `true`/`false` — se o scan tenta `GetDeviceInformation` best-effort por device (padrão: `true`, task-096) |

---

## Status: Parcialmente placeholder

O restante do que está descrito acima (`mqtt_consumer.py`, `model_manager.py`, `stream_reporter.py`,
`mirror_api.py`) ainda não está implementado — não faz parte do daemon hoje. `auth/enrollment.py` +
`auth/token_manager.py` (identidade — PR-A), `heartbeat.py` (PR-B) e `main.py`'s `run_daemon()` (orquestrador
supervisionado — PR-C) JÁ existem, têm teste, e `python -m app.main` sobe tudo isso junto (evidence API +
`config_poller`/`command_poller`/`uploader`/`heartbeat`, cada um supervisionado com restart+backoff). `sqlite_buffer.py`, a mini-API de evidência (`evidence_api.py`/`evidence_auth.py`/
`recorder_client.py`, task-090), o RecorderClient real ONVIF/RTSP (`onvif_recorder_client.py`/
`rtsp_timestamp_recorder_client.py`/`recorder_factory.py`/`rtsp_validator.py`/`rtsp_clip_stream.py`, task-091) e o
scanner de descoberta ONVIF (`onvif_discovery.py`/`discovery_api.py`, task-096) JÁ existem — ver seções acima.
**Falta:** validação em hardware real (PR-D — systemd, NTP; gate 1.6 no pandora) e lease de licença (4.2).

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
- ADR-0047: Pipeline de treino LGPD-clean + zero-shot no onboarding — pré-anotação zero-shot de onboarding
  (task-098), licença NanoOWL/OWL-ViT verificada

## Deploy (PR-D)

`deploy/edge-sync-agent.service` (systemd **--user**, sem sudo) + `deploy/edge-sync-agent.env.example` +
`deploy/install.sh`. Runbook completo (por quê `--user` e não unit de sistema, passo a passo, gate 1.6):
`docs/runbooks/edge-sync-agent-deploy.md`.

## OTA — canal de software (ADR-0057 item 10)

`app/ota/` (`release_manager.py`, `client.py`, `updater.py`, `__main__.py`) + `deploy/edge-sync-agent-updater.{service,timer}`.
Bare-metal (sem Docker): "versão" é git ref, release = `git worktree` + venv própria, `current` é um symlink
trocado atomicamente. Unit **separada** do daemon principal (de propósito — ver `updater.py`'s docstring:
`systemctl --user restart` mataria a própria checagem se ela rodasse dentro do daemon). `edge-sync-agent.service`
(PR-D) agora usa `%h/recognition/current` no `ExecStart`/`WorkingDirectory`, não mais um checkout fixo. Runbook:
`docs/runbooks/edge-ota.md`.

## Coletor de frames — deploy (task-093)

`deploy/edge-frame-collector.service` (systemd **--user**, mesmo padrão sem sudo do PR-D) + as mesmas
`deploy/edge-sync-agent.env.example`/`deploy/install.sh` (instala as 4 units juntas: daemon, updater timer,
collector). Exige `RECORDER_*` completo + `RECORDER_CLOUD_ID` no `.env` antes de habilitar — ver seção
"Coletor de frames motion-triggered" acima.
