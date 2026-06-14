# GSD — Global System Document
# Recognition Platform

**Versão:** 1.0
**Data:** 2026-05-28
**Status:** Ativo
**Owner:** Logikos / Vitor Emanuel

---

## Visão

Recognition é uma plataforma multi-tenant de monitoramento de EPIs (Equipamentos de Proteção Individual) baseada em visão computacional. Câmeras CCTV existentes no cliente são consumidas por pipelines de inferência YOLOv8/DeepStream, que geram alertas em tempo real quando violações de EPI são detectadas. O operador acessa um dashboard React para monitorar câmeras ao vivo, histórico de alertas, métricas e configuração de regras.

**Proposta de valor central:** o cliente não precisa trocar câmeras nem instalar SDKs proprietários — a plataforma conecta via RTSP ao DVR existente e entrega compliance EPI com latência < 3 s na LAN.

### Dois modos de deployment

| Modo | Onde roda a inferência | Caso de uso |
|------|----------------------|-------------|
| **Edge** (produção) | Mini PC na fábrica com GPU | Plantas industriais com intranet, 5–30 câmeras |
| **Cloud-only** (suportado, sem cliente ativo) | Railway inference service | Ambientes com câmeras com IP público ou VPN |

No modo Edge, o cloud (Railway) armazena dados históricos, treina modelos e serve o dashboard. O edge executa inferência e envia resultados em batch.

---

## Stakeholders

| Stakeholder | Papel | Interesses |
|-------------|-------|-----------|
| **Logikos** | Builder & operador da plataforma | Entregar produto funcional, escalar para múltiplos clientes industriais |
| **Vitor Emanuel** | Arquiteto / desenvolvedor principal | Decisões técnicas, qualidade do código, roadmap |
| **RVB Isolantes** (Blumenau/SC) | Primeiro cliente / tenant âncora | Monitoramento de EPIs em 28 câmeras Intelbras, zero downtime, baixa latência na LAN |
| **Futuros clientes industriais** | Tenants adicionais | Onboarding simples (plug-and-play), módulos configuráveis por tenant |

---

## Arquitetura

### Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────────┐
│  EDGE (fábrica cliente)                                         │
│                                                                 │
│  DVR Intelbras (28 câm) ──RTSP──► MediaMTX                     │
│                                       │                        │
│                                    RTSP restream               │
│                                       │                        │
│                              DeepStream Pipeline                │
│                              (TensorRT INT8, GPU)               │
│                                       │                        │
│                              Redis local (det:*, frame:*)       │
│                                       │                        │
│                              MQTT Mosquitto (eventos críticos)  │
│                                       │                        │
│                              edge-sync-agent                    │
│                              ├── SQLite buffer (offline)        │
│                              ├── heartbeat → cloud              │
│                              ├── batch POST detecções → cloud   │
│                              └── mirror-api (LAN fallback)      │
│                                       │                        │
│                              ws-gateway-local (live LAN)        │
└───────────────────────────────────────┼─────────────────────────┘
                                        │ HTTPS / Cloudflare Tunnel
                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  CLOUD (Railway)                                                │
│                                                                 │
│  api-v3 (Flask + SocketIO)                                      │
│  ├── /api/v1/edge/*    (heartbeat, enrollment, sync)            │
│  ├── /api/v1/cameras/* (CRUD, alertas, regras)                  │
│  ├── /api/v1/modules/* (epi, fueling)                           │
│  ├── socket_bridge     (Redis → WebSocket → frontend)           │
│  └── Celery client     (dispatch: inference, training, quality) │
│                   │                  │                         │
│            PostgreSQL          Redis (pub/sub + broker)         │
│            (schema-per-tenant)                                  │
│                                      │                         │
│  worker (Celery)                     │                         │
│  ├── inference queue (YOLOv8)        │◄── inference service     │
│  ├── training queue (Roboflow/local) │                         │
│  ├── quality queue                   │                         │
│  └── versioning queue                │                         │
│                                                                 │
│  frontend (React SPA + Vite)                                    │
│  landing-page (Astro + ONNX demo browser)                       │
└─────────────────────────────────────────────────────────────────┘
```

### Serviços Railway

| Serviço | `SERVICE_TYPE` | Função |
|---------|---------------|--------|
| `api-v3` | `api` | Flask REST + SocketIO, controller central |
| `worker` | `worker` / `celery-worker` | Celery Worker (inference, training, quality, versioning) |
| `frontend` | — | React SPA (Vite, Nginx) |
| `inference-service` | — | YOLOv8 cloud-only inference (modo cloud) |
| `pre-annotation-service` | `pre-annotation` | DINO + SAM para pré-anotação de frames |
| `landing-page` | `landing-page` | Astro 4 + demo ONNX no browser |
| `PostgreSQL` | — | Plugin Railway, schema-per-tenant |
| `Redis` | — | Plugin Railway, pub/sub + Celery broker |

### Multi-tenancy

Cada tenant tem um `tenant_schema` (ex.: `rvb`, `demo`) no PostgreSQL. O JWT de usuário carrega `tenant_id` e `tenant_schema`. Toda query é precedida por `SET search_path TO {tenant_schema}, public`. O schema `public` contém apenas tabelas globais (tenants, system_config).

---

## Fluxo Principal

### Cloud-only (modo simplificado)

```
1. Câmera envia RTSP
2. inference-service captura frame (5 FPS)
3. YOLOv8 detecta EPIs/violações
4. Publica no Redis: det:{camera_id}
5. socket_bridge na api-v3 assina det:* via Redis pub/sub
6. api-v3 faz broadcast via SocketIO para rooms do tenant
7. Frontend recebe evento WebSocket → atualiza overlay de bounding boxes
8. Se violação: alert_service insere em alerts (PostgreSQL) + emite alert:{tenant_id}
9. Frontend exibe notificação + armazena em AlertsHistoryPage
```

### Edge (modo produção RVB)

```
1. DVR Intelbras transmite RTSP → MediaMTX redistribui localmente
2. DeepStream pipeline consome RTSP, roda TensorRT INT8
3. Publica no Redis local: det:{camera_id}
4. MQTT Mosquitto recebe eventos críticos (alertas de violação)
5. edge-sync-agent consome MQTT, persiste em SQLite (offline buffer)
6. edge-sync-agent envia batch POST → api-v3 /api/v1/edge/detections
7. ws-gateway-local broadcast para dashboard LAN (< 1s latência)
8. Frontend detecta modo edge via useDualMode.ts → conecta ao mirror-api LAN
9. Periodicamente: heartbeat, poll de config, download de novo modelo
10. Cloud armazena histórico, processa treino incremental
```

---

## Decisões Arquiteturais

As decisões registradas abaixo são referenciadas por ADR. Os arquivos completos ficam em `docs/decisions/adr/`.

| ADR | Título | Decisão resumida |
|-----|--------|-----------------|
| [0001](../decisions/adr/0001-deepstream-vs-ultralytics.md) | DeepStream vs Ultralytics no Edge | DeepStream + TensorRT INT8 no edge; Ultralytics no cloud-only e dev |
| [0002](../decisions/adr/0002-roboflow-licensing.md) | Roboflow como licença comercial YOLO | Sub-licença Roboflow cobre uso comercial; todo treino passa por workspace Roboflow |
| [0003](../decisions/adr/0003-redis-mqtt-hybrid.md) | Redis vs MQTT — Híbrido no Edge | Redis pub/sub para fluxo interno frame→inference; MQTT para eventos críticos e sync queue |
| [0004](../decisions/adr/0004-http-polling-edge-cloud.md) | HTTP Polling Edge↔Cloud | Edge faz POST batch + GET poll periódicos; sem WebSocket persistente edge↔cloud |
| [0005](../decisions/adr/0005-monorepo-structure.md) | Estrutura de Monorepo | `services/` + `apps/` + `shared/` + `deployments/` + `docs/` |
| [0006](../decisions/adr/0006-frontend-dual-mode.md) | Frontend Dual Mode (LAN Fallback) | Frontend detecta queda do cloud e faz fallback para `edge.{site}.local` via `useDualMode.ts` |
| [0007](../decisions/adr/0007-deployment-modes.md) | Deployment Modes por Tenant | Coluna `deployment_mode` em tenants: `edge` (produção) ou `cloud_only` |
| [0008](../decisions/adr/0008-device-tokens-rs256.md) | Device Tokens com RS256 e Escopos | Edge usa JWT RS256 com escopos limitados, separado do JWT de usuários |
| [0009](../decisions/adr/0009-mediamtx.md) | MediaMTX como RTSP multiplexer | MediaMTX redistribui streams do DVR localmente; suporta restream para múltiplos consumers |
| [0010](../decisions/adr/0010-test-harness.md) | Test Harness Local para RVB | `tests/harness/` simula edge+cloud localmente; cenários de aceitação antes de produção |
| [0011](../decisions/adr/0011-schema-per-tenant.md) | Schema-per-tenant PostgreSQL | Cada tenant em schema separado; `SET search_path` em todas as queries |
| [0012](../decisions/adr/0012-celery-worker.md) | Celery como fila de tarefas | Celery Worker com Redis broker; filas: inference, training, quality, versioning |
| [0013](../decisions/adr/0013-raw-sql-psycopg2.md) | Raw SQL com psycopg2 | Sem ORM; psycopg2 + RealDictCursor; SQL explícito nos repositories |
| [0014](../decisions/adr/0014-railway-deployment.md) | Railway como plataforma cloud | Nixpacks build (2-3 min); `SERVICE_TYPE` env var roteia startup |
| [0015](../decisions/adr/0015-deepsort-tracking.md) | DeepSORT para anti-duplicate | DeepSORT por câmera para track_ids únicos; evita contagens duplicadas |
| [0016](../decisions/adr/0016-sqlite-offline-buffer.md) | SQLite como buffer offline no edge | edge-sync-agent usa SQLite local como WAL para garantir entrega mesmo sem conectividade |

---

## Módulos do Produto

| Módulo | `module_code` | Status | Classes YOLO |
|--------|--------------|--------|-------------|
| EPI Monitor | `epi` | Ativo | helmet, no_helmet, vest, no_vest, gloves, no_gloves, glasses, no_glasses |
| Fueling Control | `fueling` | Placeholder | truck, plate, fuel_nozzle, product_box, pallet |
| Quality | `quality` | Em desenvolvimento | — |

Cada tenant ativa módulos via `tenant_modules`. Queries de câmeras, alertas e frames filtram por `module_code` além de `tenant_id`.

---

## Restrições e Premissas

- **Câmeras**: protocolo RTSP obrigatório (DVRs Intelbras são o caso primário; genérico ONVIF suportado)
- **GPU no edge**: NVIDIA RTX 5060 Ti ou equivalente; TensorRT requer CUDA 12+
- **Conectividade edge↔cloud**: Cloudflare Tunnel; degradação graciosa com SQLite buffer
- **Branch protegida**: `main` nunca recebe push direto; fluxo é `feature/*` → `develop` → `staging` → `main`
- **Segredos**: nunca em código; sempre em Railway env vars ou Docker secrets no edge
- **Compliance LGPD**: imagens de câmeras não são armazenadas no cloud (apenas metadados de detecção); retenção de alertas configurável por tenant
