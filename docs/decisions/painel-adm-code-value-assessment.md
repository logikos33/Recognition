# painel-adm — Avaliação de Valor do Código por Serviço

**Data:** 2026-05-27
**Branch de referência:** `archive/microservices-attempt-1` (commit a24fe5f)
**Propósito:** Informar decisão OQ-006 — Reescrever vs Portar os serviços
removidos de staging.

---

## Resumo Executivo

| Serviço | LOC | Disposição | Valor único |
|---------|-----|------------|------------|
| `camera-gateway` | ~544 | **PORTAR** | Pipeline FFmpeg RTSP→HLS + frame publisher Redis |
| `training-service` | ~535 | **PORTAR** | UltralyticsHubClient customizado + job orchestration |
| `ws-gateway` | ~271 | **REFERÊNCIA** | Padrão psubscribe→socketio já replicado em api-v3 |
| `scheduler-service` | ~213 | **REFERÊNCIA** | check_cameras_health() via Redis TTL tem lógica útil |
| `auth-service` | — | **DESCARTAR** | api-v3 tem auth nativo completo com multi-tenant |
| `pre-annotation-service` | — | **DESCARTAR** | DINO+SAM nunca usado em produção |
| `inference-service` | ~572 | **IGNORAR** | SHA idêntico ao em staging — mesma versão |

---

## 1. camera-gateway — PORTAR

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

### Por que PORTAR (não reescrever)

O pipeline FFmpeg + frame publisher tem decisões não-óbvias que levaram tempo:
- Parâmetros FFmpeg específicos para latência baixa (`ultrafast`, segments de 1s, playlist 3)
- Lógica de auto-restart com backoff exponencial (máx 3 tentativas, depois alerta)
- Frame publisher usa `cv2.VideoCapture` do stream HLS local (não RTSP diretamente),
  evitando double-decode
- Redis publish com serialização eficiente (JPEG comprimido, não raw)

Reescrever isso do zero arriscaria regredir em latência e estabilidade.

### Adaptações necessárias para Fase 3

- Multi-tenancy: `camera_id` precisa incluir `tenant_id`
- Database: trocar chamadas diretas para API interna (remover dependência de psycopg2)
- Logging: adaptar para padrão do monorepo
- Health endpoint: adicionar `/health` para Railway
- Estimativa: **3–5 dias** de adaptação

---

## 2. training-service — PORTAR

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

### Por que PORTAR (não reescrever)

`hub_client.py` é o mais valioso: a Ultralytics Hub API não é documentação
pública completa — o cliente foi construído por reverse engineering da API.
Inclui tratamento de rate limiting, autenticação OAuth específica do Hub,
e lógica de retry para downloads de modelos grandes.

`job_manager.py` tem estado em Redis com transições de estado complexas
(QUEUED → TRAINING → DOWNLOADING → READY → FAILED) com recovery de crashes.

### Adaptações necessárias para Fase 3

- Multi-tenancy: jobs isolados por tenant
- Substituir Flask por chamadas diretas do api-v3 (ou manter como microserviço)
- MinIO URL configurável por ambiente (dev vs. edge)
- Estimativa: **4–6 dias** de adaptação

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

## 4. scheduler-service — REFERÊNCIA

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

### Por que REFERÊNCIA (não portar)

O api-v3 já usa Celery Beat (worker). As tasks podem ser adicionadas ao worker
existente em vez de criar um serviço separado.

**Valor específico:** A lógica de `camera_health.py` — detectar câmera offline
via expiração do TTL Redis de `frame:{camera_id}` — é elegante e não-óbvia.
Útil quando implementar alertas de câmera offline no api-v3.

---

## 5. auth-service — DESCARTAR

### Por que descartar

- `api-v3` tem auth completo: JWT, bcrypt, multi-tenant, refresh tokens
- O `auth-service` da branch `painel-adm` não tem multi-tenancy
- O frontend nunca foi integrado com esse auth-service (usava api-v3 direto)
- Zero valor incremental em relação ao que já existe

---

## 6. pre-annotation-service — DESCARTAR

### Por que descartar

- Implementava DINO + SAM para auto-anotação de bounding boxes
- **Nunca foi usado em produção** — a decisão de não usar veio de Vitor
  (custo computacional alto vs. qualidade de anotação insuficiente)
- Roboflow (tooling atual de anotação) substitui completamente essa funcionalidade

---

## 7. Próximos Passos (pós-decisão OQ-006)

Se aprovado PORTAR camera-gateway e training-service na Fase 3:

1. Checkout temporário da tag para leitura:
   ```bash
   git show archive/microservices-attempt-1:camera-gateway/ > /tmp/camera-gateway-review/
   ```
2. Criar `services/camera-gateway/` do zero com estrutura nova
3. Portar módulos de forma incremental, adaptando multi-tenancy e logging
4. Idem para `services/training/`

Se aprovado REESCREVER do zero:
- Ignorar o código da tag
- Usar apenas os documentos de arquitetura como referência conceitual

---

## Referências

- `archive/microservices-attempt-1` — código completo dos serviços
- ADR-0014 — contexto histórico da tentativa de microsserviços
- ADR-0011 — como acessar o código arquivado
- `docs/decisions/inference-migration-feasibility.md` — análise detalhada do inference-service
- OQ-006 — questão aberta sobre estratégia para Fase 3
