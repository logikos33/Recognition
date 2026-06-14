# AGENT.md — services/edge-sync-agent

**Serviço:** Edge Sync Agent
**Status:** Placeholder — implementação na Fase 4
**Responsabilidade:** Sincronizar estado do edge com o cloud API (heartbeats, model manifest, enrollment, batch upload de detecções)

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

---

## Status: Placeholder

Este serviço ainda não está implementado. A estrutura de diretórios e Dockerfile são placeholders criados na Fase 0.

**Implementação:** Fase 4 do `EDGE_DEPLOYMENT_PLAN.md`
**Dependências de migrations:** 042 (`device_tokens`), 043 (`edge_heartbeats`), 044 (`model_manifests`)
**Dependências de API:** blueprint `/api/v1/edge/*` (Fase 2)

**ADRs relacionados:**
- ADR-0004: HTTP Polling Edge↔Cloud
- ADR-0007: Deployment Modes por Tenant
- ADR-0008: Device Tokens RS256
- ADR-0009: MediaMTX como RTSP multiplexer
- ADR-0016: SQLite como buffer offline
