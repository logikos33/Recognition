# painel-adm — Avaliação de Valor do Código por Serviço

**Data:** 2026-05-27
**Branch de referência:** `archive/microservices-attempt-1` (commit a24fe5f)
**Propósito:** Informar decisão OQ-006 — Reescrever vs Portar os serviços
removidos de staging.

---

## Resumo Executivo

| Serviço | LOC | Disposição | Justificativa |
|---------|-----|------------|--------------|
| `camera-gateway` | ~544 | **REFERÊNCIA** | Arquitetura nova usa MediaMTX + DeepStream; FFmpeg→Redis não se aplica |
| `ws-gateway` | ~271 | **REFERÊNCIA** | Padrão psubscribe→socketio já replicado em api-v3 |
| `training-service` | ~535 | **ARCHIVE** | Workflow migrou para Roboflow + Colab; código Hub client não se aplica |
| `scheduler-service` | ~213 | **ARCHIVE** | Celery Beat no worker já cobre; sem funcionalidade nova |
| `auth-service` | — | **ARCHIVE** | api-v3 tem auth nativo completo com multi-tenant |
| `pre-annotation-service` | — | **ARCHIVE** | DINO+SAM nunca usado em produção |
| `inference-service` | ~572 | **IGNORAR** | SHA idêntico ao em staging — mesma versão |

> **Decisão final (OQ-006, 2026-05-27):** Referência pura. Para desenvolvimento da
> Fase 3, consultar apenas `camera-gateway` e `ws-gateway` como referência de padrões
> arquiteturais. Os demais estão arquivados sem consulta prevista.

---

## 1. camera-gateway — REFERÊNCIA

### O que faz
Transcodifica streams RTSP de câmeras IP para HLS e publica frames no Redis
para o inference-service consumir.

### Arquitetura

```
IP Camera (RTSP)
    → stream_manager.py (spawna FFmpeg)
    → HLS segments (m3u8 + .ts em disco)
    → frame_publisher.py (captura frame via OpenCV, publica em Redis)
    → Redis canal frame:{camera_id}
```

### Módulos principais

| Arquivo | LOC | Função |
|---------|-----|--------|
| `stream_manager.py` | ~180 | Spawna/monitora processos FFmpeg; auto-restart; health check |
| `frame_publisher.py` | ~150 | Captura frame a 5 FPS via `cv2.VideoCapture`; serializa; publica Redis |
| `rtsp_builder.py` | ~80 | Gera URLs RTSP por fabricante (Intelbras, Hikvision, ONVIF) |
| `health_reporter.py` | ~60 | Métricas: uptime, restart count, FPS real |
| `config.py` | ~40 | Vars de ambiente, validação |
| `main.py` | ~34 | Entrypoint, inicialização, graceful shutdown |

### Por que REFERÊNCIA (não portar)

A arquitetura de edge usa **MediaMTX** (RTSP re-streaming server) + **DeepStream
`nvurisrcbin`** (leitura direta do stream RTSP na pipeline GStreamer). O pipeline
`FFmpeg → HLS → Redis` do camera-gateway original **não se aplica** à nova arquitetura.

O código permanece como referência para entender:
- Padrões de health check de stream (auto-restart, backoff exponencial)
- Lógica de detecção de câmera offline
- Tratamento de fabricantes (Intelbras, Hikvision, ONVIF)

Esses padrões serão reimplementados na nova arquitetura MediaMTX, não portados.

---

## 2. training-service — ARCHIVE

### O que faz
Orquestra treinamentos de modelos YOLO via Ultralytics Hub, monitora jobs,
faz download do modelo treinado e publica no MinIO.

### Arquitetura

```
API interna → POST /train
    → job_manager.py (cria job, valida dataset)
    → hub_client.py (Ultralytics Hub API)
    → Ultralytics Cloud Training
    → hub_client.py (polling status)
    → model_downloader.py (baixa .pt do Hub)
    → MinIO (armazena modelo treinado)
```

### Módulos principais

| Arquivo | LOC | Função |
|---------|-----|--------|
| `job_manager.py` | ~180 | Orquestração: criar/pausar/cancelar jobs; estado em Redis |
| `hub_client.py` | ~150 | UltralyticsHubClient customizado: auth, upload dataset, poll status, download |
| `model_downloader.py` | ~80 | Download do .pt treinado; upload para MinIO |
| `dataset_validator.py` | ~60 | Valida formato YOLO antes de upload |
| `config.py` | ~35 | Vars de ambiente |
| `main.py` | ~30 | Entrypoint Flask para receber requests da API |

### Por que ARCHIVE (não portar)

O workflow de treinamento migrou para **Roboflow + Google Colab**. O
`hub_client.py` (Ultralytics Hub API) não se aplica a esse pipeline.
`job_manager.py` gerenciava jobs no Ultralytics Cloud — sem equivalente
no novo workflow.

O código está preservado na tag `archive/microservices-attempt-1` mas
sem consulta prevista para a Fase 3.

---

## 3. ws-gateway — REFERÊNCIA

### O que faz
Consome detecções do Redis (`det:{camera_id}`) e faz broadcast via WebSocket
para clientes conectados.

### Módulos principais

| Arquivo | LOC | Função |
|---------|-----|--------|
| `bridge.py` | ~120 | `redis.psubscribe('det:*')` → `socketio.emit('detection', ...)` |
| `connection_manager.py` | ~80 | Rastreia conexões por câmera; filtra broadcasts |
| `main.py` | ~40 | Flask-SocketIO server |
| `config.py` | ~31 | Vars de ambiente |

### Por que REFERÊNCIA (não portar)

`api-v3` já tem `socket_bridge.py` com funcionalidade equivalente — o mesmo
padrão `psubscribe('det:*')` → `socketio.emit`. O código do ws-gateway serviu
de base para essa implementação.

**Valor:** A lógica de `connection_manager.py` (filtrar quais clientes recebem
quais câmeras) pode ser útil se o api-v3 precisar de granularidade maior.

---

## 4. scheduler-service — ARCHIVE

### O que faz
Celery Beat com tasks periódicas: health check de câmeras, limpeza de streams
mortos, relatórios de métricas.

### Módulos principais

| Arquivo | LOC | Função |
|---------|-----|--------|
| `tasks.py` | ~90 | Tasks Celery: `check_cameras_health`, `cleanup_dead_streams`, `report_metrics` |
| `celery_app.py` | ~50 | Configuração Celery + Beat schedule |
| `camera_health.py` | ~40 | Lógica: verifica Redis TTL de `frame:{camera_id}`; câmera offline se TTL expirado |
| `config.py` | ~33 | Vars de ambiente |

### Por que ARCHIVE (não consultar)

O api-v3 já usa Celery Beat (worker) e cobre as tasks periódicas. Sem
funcionalidade nova que justifique consulta. Código preservado na tag.

---

## 5. auth-service — ARCHIVE

### Por que descartar

- `api-v3` tem auth completo: JWT, bcrypt, multi-tenant, refresh tokens
- O `auth-service` da branch `painel-adm` não tem multi-tenancy
- O frontend nunca foi integrado com esse auth-service (usava api-v3 direto)
- Zero valor incremental em relação ao que já existe

---

## 6. pre-annotation-service — ARCHIVE

### Por que descartar

- Implementava DINO + SAM para auto-anotação de bounding boxes
- **Nunca foi usado em produção** — a decisão de não usar veio de Vitor
  (custo computacional alto vs. qualidade de anotação insuficiente)
- Roboflow (tooling atual de anotação) substitui completamente essa funcionalidade

---

## 7. Uso na Fase 3 (pós OQ-006)

**Decisão (OQ-006, 2026-05-27):** Referência pura.

Para os serviços marcados **REFERÊNCIA** (camera-gateway, ws-gateway):
```bash
# Consulta pontual durante desenvolvimento da Fase 3
git show archive/microservices-attempt-1:camera-gateway/stream_manager.py
git show archive/microservices-attempt-1:ws-gateway/bridge.py
```

Para os serviços marcados **ARCHIVE** (training-service, scheduler-service,
auth-service, pre-annotation-service):
- Código preservado na tag, sem consulta prevista
- Ignorar durante Fase 3

---

## Referências

- `archive/microservices-attempt-1` — código completo dos serviços
- ADR-0014 — contexto histórico da tentativa de microsserviços
- ADR-0011 — como acessar o código arquivado
- `docs/decisions/inference-migration-feasibility.md` — análise detalhada do inference-service
- OQ-006 — questão aberta sobre estratégia para Fase 3
