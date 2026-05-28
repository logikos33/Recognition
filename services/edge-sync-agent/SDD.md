# SDD — Software Design Document
# services/edge-sync-agent — Agente de Sincronização Edge↔Cloud

**Versão:** 1.0
**Data:** 2026-05-28
**Status:** Placeholder — implementação na Fase 4
**Referência:** `EDGE_DEPLOYMENT_PLAN.md` seção "Fase 4"

---

## Visão Geral

O `edge-sync-agent` é o componente de borda que mantém o mini PC do cliente sincronizado com o cloud (Railway). Roda continuamente no mini PC ao lado dos pipelines DeepStream, com quatro responsabilidades principais:

1. **Upstream:** coletar eventos do Mosquitto MQTT local e enviá-los em batch para a API cloud
2. **Downstream:** receber configurações atualizadas (câmeras, regras, modelos) da API cloud
3. **Heartbeat:** reportar saúde do edge a cada 60 segundos
4. **Mirror API:** expor endpoints essenciais na LAN para que o frontend opere em modo offline

O design prioriza **resiliência offline**: usando SQLite como WAL (Write-Ahead Log) local, detecções nunca são perdidas mesmo com horas de indisponibilidade de rede.

---

## Componentes

### 1. Entry Point (`app/main.py`)

Inicializa todos os loops em threads ou tarefas asyncio:

```python
# Threads paralelas:
Thread(target=mqtt_consumer.run)           # Subscribe MQTT local
Thread(target=uploader.run)                # Upload batch periódico
Thread(target=config_poller.run)           # Poll de config
Thread(target=heartbeat.run)               # Heartbeat
Thread(target=stream_reporter.run)         # Relatório de streams
Thread(target=mirror_api.run)              # FastAPI LAN na porta 8080

# Shutdown graceful via signal.SIGTERM
```

### 2. MQTT Consumer (`app/mqtt_consumer.py`)

Assina tópicos do Mosquitto local (mesma máquina):

```python
# Tópicos assinados:
events/detection/{camera_id}    # Detecções do DeepStream
events/critical/{camera_id}     # Alertas de violação
events/stream/{camera_id}       # Status de pipelines
```

Ao receber mensagem:
1. Valida schema do payload (Pydantic)
2. Chama `sqlite_buffer.enqueue(event_type, payload)`
3. Se erro MQTT: backoff 5s → 30s → 120s com reconexão

**Config Mosquitto:**
- Host: `localhost:1883`
- TLS: certificado self-signed por site (Fase S2)
- Auth: `requirepass` + credenciais em Docker secret

### 3. SQLite Buffer (`app/sqlite_buffer.py`)

Buffer persistente WAL para resiliência offline:

```sql
-- Tabela principal
CREATE TABLE event_buffer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,          -- 'detection', 'alert', 'stream_status'
    camera_id   TEXT NOT NULL,
    payload     TEXT NOT NULL,          -- JSON
    created_at  REAL NOT NULL,          -- Unix timestamp
    sent_at     REAL,                   -- NULL até confirmação de envio
    attempts    INTEGER DEFAULT 0
);

CREATE INDEX idx_unsent ON event_buffer(sent_at) WHERE sent_at IS NULL;
```

```python
class SQLiteBuffer:
    def enqueue(self, event_type: str, camera_id: str, payload: dict) -> int: ...
    def dequeue_batch(self, limit: int = 500) -> list[dict]: ...
    def mark_sent(self, ids: list[int]) -> None: ...
    def mark_failed(self, ids: list[int]) -> None: ...  # incrementa attempts
    def purge_old(self, days: int = 7) -> int: ...      # limpa enviados > 7 dias
```

**SQLite em WAL mode** (`PRAGMA journal_mode=WAL`) para leituras e escritas simultâneas das threads.

**Capacidade estimada (RVB 28 câmeras a 5 FPS):**
- ~140 detecções/segundo
- ~500 KB/minuto de buffer
- ~700 MB/dia — ok em disco de 128GB do mini PC
- Purge automático de registros enviados com > 7 dias

### 4. Uploader (`app/uploader.py`)

Loop periódico que drena o SQLite buffer para a API cloud:

```python
# Loop principal
while True:
    batch = buffer.dequeue_batch(limit=500)
    if not batch:
        sleep(UPLOAD_INTERVAL_S)      # 30s padrão
        continue

    try:
        response = httpx.post(
            f"{CLOUD_API_URL}/api/v1/edge/detections",
            json={"device_id": DEVICE_ID, "detections": batch},
            headers={"Authorization": f"Bearer {token_manager.get_token()}"},
            timeout=30,
        )
        if response.status_code == 200:
            buffer.mark_sent([e["id"] for e in batch])
            backoff.reset()
        else:
            buffer.mark_failed([e["id"] for e in batch])
            backoff.wait()
    except (httpx.ConnectError, httpx.TimeoutException):
        backoff.wait()   # 30s → 60s → 120s → 300s
```

**Backoff:** exponencial com jitter, máximo 300s entre tentativas.
**Ordering:** batch ordenado por `created_at` para entrega cronológica.

### 5. Config Poller (`app/config_poller.py`)

Faz polling periódico de configurações do cloud:

```python
# A cada 5 minutos:
response = GET /api/v1/edge/config/poll?device_id=...&current_model_sha256=...

# Resposta:
{
  "cameras": [...],              # câmeras atualizadas para este device
  "rules": [...],                # regras de alerta
  "model": {
    "sha256": "abc...",
    "url": "https://...",        # URL assinada (R2 ou equivalente)
    "engine_type": "pt"          # "pt" para Ultralytics, "engine" para TensorRT
  } | null                       # null se modelo atual está ok
}
```

Se `model` presente e `sha256` diferente do atual:
→ delega para `model_manager.download_and_swap(url, sha256, engine_type)`

### 6. Model Manager (`app/model_manager.py`)

Gerencia download, validação e swap de modelos YOLO:

```python
def download_and_swap(url: str, sha256: str, engine_type: str) -> None:
    # 1. Download para arquivo temporário
    tmp_path = f"/tmp/model_download_{uuid4()}.{engine_type}"
    httpx.stream("GET", url) → tmp_path

    # 2. Valida SHA256
    if sha256_of(tmp_path) != sha256:
        raise ModelCorruptError(f"SHA256 mismatch: {sha256}")

    # 3. Move atomicamente para YOLO_MODELS_DIR
    dest = f"{YOLO_MODELS_DIR}/model_{sha256[:8]}.{engine_type}"
    os.replace(tmp_path, dest)   # rename atômico no mesmo filesystem

    # 4. model_watcher do inference service detecta o novo arquivo
    # e recarrega o modelo no próximo frame (sem restart de processo)
    logger.info("model_swapped: sha256=%s", sha256)
```

**Validação:** SHA256 obrigatório; modelo corrompido nunca substitui o anterior.
**Atomicidade:** `os.replace()` é atômico no Linux — o inference service nunca vê arquivo parcialmente escrito.

### 7. Heartbeat (`app/heartbeat.py`)

Reporta saúde do edge a cada `HEARTBEAT_INTERVAL_S` (padrão 60s):

```python
payload = {
    "device_id": DEVICE_ID,
    "timestamp": utcnow(),
    "metrics": {
        "cpu_percent": psutil.cpu_percent(),
        "gpu_util_percent": get_gpu_util(),     # nvidia-smi
        "gpu_temp_c": get_gpu_temp(),
        "ram_used_gb": psutil.virtual_memory().used / 1e9,
        "disk_free_gb": shutil.disk_usage("/").free / 1e9,
        "buffer_events_pending": buffer.count_unsent(),
        "pipelines_active": stream_reporter.count_active(),
    }
}
POST /api/v1/edge/heartbeat → {device_id, metrics, timestamp}
```

API cloud insere em `edge_heartbeats`. Se 3 heartbeats consecutivos falharem: API marca device como offline e emite alerta para o operador.

### 8. Mirror API (`app/mirror_api.py`)

FastAPI rodando na porta 8080 da LAN, para que o frontend opere em modo offline:

```python
app = FastAPI(title="Recognition Edge Mirror API")

@app.get("/health")
def health():
    return {"status": "ok", "device_id": DEVICE_ID, "mode": "edge"}

@app.get("/alerts/recent")
def recent_alerts():
    # Lê últimos 50 alertas do SQLite local
    return buffer.get_recent(event_type="alert", limit=50)

@app.get("/cameras")
def cameras():
    # Retorna câmeras configuradas localmente (cacheadas do último config poll)
    return config_cache.get_cameras()

@app.get("/streams/status")
def streams_status():
    # Lê status dos pipelines DeepStream (Redis local)
    return redis_client.get_all_stream_statuses()
```

Frontend usa `useDualMode.ts`: se `GET ${CLOUD_URL}/health` timeout em 2s, conecta em `http://edge.{tenant_schema}.local:8080`.

### 9. Auth: Token Manager (`app/auth/token_manager.py`)

```python
class TokenManager:
    def get_token(self) -> str:
        """Lê device token do filesystem seguro. Renova se próximo de expirar."""
        token = self._load_from_secret()
        if self._expires_in(token) < timedelta(days=7):
            token = self._renew_token()
        return token

    def _load_from_secret(self) -> str:
        # Lê de /run/secrets/device_token (Docker secret)
        return Path(DEVICE_TOKEN_PATH).read_text().strip()

    def _renew_token(self) -> str:
        # POST /api/v1/edge/token/renew com token atual
        # Retorna novo token; persiste em /run/secrets/device_token
        ...
```

### 10. Enrollment (`app/auth/enrollment.py`)

Executado uma única vez por dispositivo (setup inicial):

```python
def enroll(one_time_token: str, site_id: str) -> None:
    device_id = str(uuid4())
    response = httpx.post(
        f"{CLOUD_API_URL}/api/v1/edge/enroll",
        json={
            "device_id": device_id,
            "one_time_token": one_time_token,
            "site_id": site_id,
        },
        timeout=30,
    )
    # API invalida one_time_token imediatamente após uso
    device_token = response.json()["device_token"]

    # Persiste device_id e token
    Path("/run/secrets/device_id").write_text(device_id)
    Path("/run/secrets/device_token").write_text(device_token)
    logger.info("enrollment_complete: device_id=%s", device_id)
```

---

## Interfaces

### Endpoints Cloud Consumidos

| Método | Endpoint | Frequência |
|--------|---------|-----------|
| `POST` | `/api/v1/edge/enroll` | Uma vez (enrollment) |
| `POST` | `/api/v1/edge/heartbeat` | A cada 60s |
| `POST` | `/api/v1/edge/detections` | A cada 30s (batch) |
| `GET` | `/api/v1/edge/config/poll` | A cada 5min |
| `POST` | `/api/v1/edge/streams/report` | A cada 60s |
| `POST` | `/api/v1/edge/token/renew` | A cada 53 dias |

### Mirror API Exposta (LAN)

| Método | Endpoint | Consumidor |
|--------|---------|-----------|
| `GET` | `/health` | Frontend `useDualMode.ts` |
| `GET` | `/alerts/recent` | Frontend (modo offline) |
| `GET` | `/cameras` | Frontend (modo offline) |
| `GET` | `/streams/status` | Frontend (modo offline) |

### MQTT Tópicos Consumidos (local)

| Tópico | Publicador | Conteúdo |
|--------|-----------|---------|
| `events/detection/{camera_id}` | DeepStream pipeline | Detecção YOLO |
| `events/critical/{camera_id}` | DeepStream pipeline | Violação de EPI |
| `events/stream/{camera_id}` | DeepStream / MediaMTX | Status de stream |

---

## Fluxo de Dados

### Fluxo normal (conectado)

```
DeepStream pipeline
  → MQTT Mosquitto local (events/detection/{cam})
  → mqtt_consumer.py
  → sqlite_buffer.enqueue()
  → uploader.py (a cada 30s)
  → POST /api/v1/edge/detections (cloud)
  → sqlite_buffer.mark_sent()
  → api cloud insere em edge_detections_buffer
  → Celery worker processa → insere em alerts
```

### Fluxo offline (sem conectividade)

```
DeepStream pipeline
  → MQTT → mqtt_consumer → sqlite_buffer.enqueue()
  [uploader falha, backoff 30s→300s]
  [buffer cresce no SQLite, até 72h de capacidade]

Mirror API LAN:
  Frontend → GET http://edge.rvb.local:8080/alerts/recent
  → sqlite_buffer.get_recent(event_type="alert")
  → exibe alertas locais sem cloud

Ao reconectar:
  uploader.run() → flush completo do SQLite em ordem cronológica
```

### Enrollment (uma vez)

```
Operador: docker exec edge-sync-agent python -m app.auth.enrollment \
          --token <ONE_TIME_TOKEN> --site-id rvb
  → POST /api/v1/edge/enroll
  → API cria device_token RS256
  → persiste em Docker secrets
  → token_manager usa para todas as chamadas subsequentes
```

---

## Dependências

| Dependência | Uso |
|------------|-----|
| `paho-mqtt` | Cliente MQTT para Mosquitto local |
| `httpx` | HTTP client async com retry |
| `fastapi` | Mirror API LAN |
| `uvicorn` | ASGI server para FastAPI |
| `pydantic` | Validação de schemas de eventos |
| `psutil` | Métricas de CPU/RAM para heartbeat |
| `sqlite3` | Stdlib Python — buffer WAL |

**Variáveis de ambiente:**
```
CLOUD_API_URL                              # obrigatório
DEVICE_ID                                  # gerado no enrollment
DEVICE_TOKEN_PATH=/run/secrets/device_token
MQTT_BROKER_URL=mqtt://localhost:1883
SQLITE_BUFFER_PATH=/var/edge-sync/buffer.db
REDIS_URL=redis://localhost:6379
MIRROR_API_PORT=8080
HEARTBEAT_INTERVAL_S=60
UPLOAD_BATCH_SIZE=500
YOLO_MODELS_DIR=/models
```

---

## Decisões Relevantes

| ADR | Impacto |
|-----|---------|
| ADR-0004 | HTTP Polling: sem WebSocket persistente edge↔cloud; POST batch + GET poll |
| ADR-0007 | Deployment mode `edge` ativado no tenant; `deployment_mode` em `tenants` |
| ADR-0008 | Device token RS256: `token_manager.py` carrega/rotaciona de Docker secret |
| ADR-0009 | MediaMTX: redistribui RTSP do DVR para DeepStream e para este agente |
| ADR-0016 | SQLite WAL: buffer offline com capacidade de 72h para RVB 28 câmeras |
| ADR-0006 | Mirror API: habilita `useDualMode.ts` no frontend para fallback LAN |
| ADR-0003 | MQTT: Mosquitto local para eventos críticos (Redis local para frame pipeline) |

---

## Status: Placeholder

Este SDD descreve o design planejado. Nenhum código de implementação existe ainda além de arquivos de estrutura.

**Gate de início:** blueprint `/api/v1/edge/*` funcionando (Fase 2) + migrations 042-044 executadas (Fase 1).

**Próximo passo:** ver prompt de Fase 4 em `EDGE_DEPLOYMENT_PLAN.md` seção "Apêndice B".
