# AGENT.md — Recognition Platform Monorepo

**Produto:** Recognition — Plataforma de monitoramento de EPIs via IA
**Builder:** Logikos / Vitor Emanuel
**Repositório:** `github.com/logikos33/recognition` (privado)
**Branch ativa:** `staging` (deploys automáticos Railway)

---

## Identidade do Projeto

Recognition é um sistema multi-tenant de visão computacional para compliance de EPIs em ambientes industriais. Câmeras CCTV existentes são consumidas via RTSP; pipelines YOLO/DeepStream geram alertas em tempo real. O primeiro cliente é RVB Isolantes (Blumenau/SC) com 28 câmeras Intelbras em modo Edge.

---

## Layout do Monorepo

```
recognition/
├── AGENT.md                          # Este arquivo — mapa raiz para agentes IA
├── CLAUDE.md                         # Instruções detalhadas para Claude Code
├── README.md                         # Visão geral para humanos
├── EDGE_DEPLOYMENT_PLAN.md           # Plano executável fases 0-10
├── docker-compose.yml                # Stack local de desenvolvimento
│
├── services/                         # Serviços de runtime
│   ├── api/                          # Flask REST + SocketIO (controller central)
│   ├── inference/                    # YOLOv8/DeepStream inference
│   └── edge-sync-agent/              # Sync edge↔cloud (Fase 4, placeholder)
│
├── apps/                             # Interfaces de usuário
│   ├── frontend/                     # React 18 + TypeScript + Vite SPA
│   └── landing/                      # Astro 4 + ONNX demo browser
│
├── shared/                           # Código compartilhado entre serviços
│   ├── python/                       # Pacotes Python compartilhados
│   ├── proto/                        # Contratos OpenAPI/AsyncAPI
│   └── ts/                           # Tipos TypeScript compartilhados
│
├── infra/                            # Infraestrutura e configurações
│   └── migrations/                   # Migrations SQL (001 → 041+)
│
├── deployments/                      # Configs de deployment
│   ├── cloud/                        # Railway configs
│   ├── dev/                          # Docker compose dev
│   └── edge/                         # Edge box configs (UFW, Nginx, Cloudflare)
│
├── deepstream/                       # Pipelines DeepStream (Fase 5)
│   ├── epi/                          # Pipeline EPI Monitor
│   ├── fueling/                      # Pipeline Fueling Control
│   ├── quality/                      # Pipeline Quality
│   └── shared/                       # Componentes reutilizáveis
│
├── models/                           # Modelos YOLO treinados
│   └── manifests/                    # Manifests de versão de modelos
│
├── docs/                             # Documentação técnica
│   ├── architecture/
│   │   └── GSD.md                    # Global System Document
│   └── decisions/
│       ├── adr/                      # Architecture Decision Records (0001-0016)
│       └── open-questions.md         # Questões abertas pendentes de decisão
│
├── tests/                            # Testes do harness local
│   └── harness/                      # Simulação edge+cloud para aceitação RVB
│
└── scripts/                          # Scripts operacionais
    └── smoke_test.sh                 # Smoke test pré-merge
```

---

## Guia por Diretório

### `services/api/`
Flask REST API + SocketIO. Controller central da plataforma.
- Arquivo principal: `app/__init__.py` (create_app factory)
- Blueprints: `app/api/v1/` (auth, cameras, alerts, rules, modules, reports, training, edge, health)
- Padrão DB: `DatabasePool` singleton + `BaseRepository` + raw SQL psycopg2
- Multi-tenant: `SET search_path TO {tenant_schema}, public`
- AGENT.md: `services/api/AGENT.md`
- SDD: `services/api/SDD.md`

### `services/inference/`
Motor de inferência YOLO com DeepSORT anti-duplicate.
- Backend: Ultralytics (dev/cloud) ou DeepStream (edge, Fase 5)
- Publica em Redis: `det:{camera_id}`
- Consome de Redis: `frame:{camera_id}`
- AGENT.md: `services/inference/AGENT.md`
- SDD: `services/inference/SDD.md`

### `services/edge-sync-agent/`
Agente de sync edge↔cloud. Placeholder — implementação na Fase 4.
- Consome MQTT Mosquitto (eventos críticos)
- Buffer SQLite (offline resilience)
- POST batch para `/api/v1/edge/detections`
- Mirror API (LAN fallback para frontend)
- AGENT.md: `services/edge-sync-agent/AGENT.md`
- SDD: `services/edge-sync-agent/SDD.md`

### `apps/frontend/`
SPA React 18 + TypeScript + Vite para dashboard de monitoramento.
- Páginas principais: HomePage, EpiDashboard, MonitoringPage, AlertsHistoryPage, CamerasPage
- Dual mode: `useDualMode.ts` detecta cloud vs edge LAN
- AGENT.md: `apps/frontend/AGENT.md`

### `apps/landing/`
Site estático Astro 4 com demo ONNX rodando no browser.
- Demo YOLO client-side (yolov8n-demo.onnx via ONNX Runtime Web)
- Sem dependência de backend em runtime
- AGENT.md: `apps/landing/AGENT.md`

### `shared/python/`
Pacotes Python instaláveis compartilhados entre services.
- `recognition_shared/auth/`: jwt_user.py, jwt_device.py (RS256 para edge), decorators.py
- `recognition_shared/events/`: Pydantic models para detection, alert, heartbeat
- `recognition_shared/redis_helpers/`: make_redis factory
- `recognition_shared/mqtt_helpers/`: MQTT client helpers

### `infra/migrations/`
Migrations SQL idempotentes (001-041+). Executadas automaticamente por `railway_start.py` no startup do `SERVICE_TYPE=api`.
- Regra: apenas `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`
- Nunca: `DROP`, `ALTER COLUMN TYPE`, `DELETE FROM`, `TRUNCATE`
- Próxima migration disponível: verificar `ls infra/migrations/*.sql | sort | tail -1`

### `deployments/edge/`
Configurações para o mini PC de edge (Ubuntu 22.04 + GPU NVIDIA).
- UFW rules, Nginx config, Cloudflare Tunnel, Docker Compose edge stack
- Referência: ADR-0007 (deployment modes), ADR-0009 (MediaMTX)

### `docs/decisions/adr/`
Architecture Decision Records. Formato: `NNNN-titulo-kebab-case.md`.
- ADRs 0001-0016 documentados no GSD.md
- Template: Status | Contexto | Decisão | Consequências

---

## Estratégia de Branch

```
feature/nome  fix/nome  refactor/nome
       │
       ▼
   develop  (integração contínua)
       │
       ▼
   staging  (deploy automático Railway — branch ativa)
       │
       ▼
    main    (produção — apenas via PR aprovado)
```

**Regras:**
- NUNCA push direto em `main`
- Commits no padrão Conventional Commits: `feat|fix|refactor|docs(scope): descrição`
- Scopes válidos: `api, frontend, inference, edge, migration, railway, landing, events, cameras, alerts, modules`

---

## Fase Atual

**Fase 0 — Reorganização (concluída)**
- Monorepo estruturado: `services/`, `apps/`, `shared/`, `infra/`, `deployments/`
- CLAUDE.md atualizado com padrões do projeto

**Fase 1 — Próxima (Schema e Models de Edge)**
- Migrations 042-045: `device_tokens`, `edge_heartbeats`, `edge_detections_buffer`, `model_manifests`
- Dataclasses e repositories correspondentes
- Referência: `EDGE_DEPLOYMENT_PLAN.md` seção "Fase 1"

---

## Onde Encontrar

| O quê | Onde |
|-------|------|
| Migrations SQL | `infra/migrations/NNN_nome.sql` |
| ADRs | `docs/decisions/adr/NNNN-titulo.md` |
| Questões abertas | `docs/decisions/open-questions.md` |
| Plano de edge deployment | `EDGE_DEPLOYMENT_PLAN.md` |
| URLs de produção Railway | `deployments/cloud/railway-services.md` |
| Contratos OpenAPI/AsyncAPI | `shared/proto/` |
| Tipos compartilhados TS | `shared/ts/recognition-shared/` |
| Modelos YOLO | `models/manifests/` |

---

## Regras Absolutas para Agentes

1. **Multi-tenant obrigatório**: toda query filtra por `tenant_id` + `SET search_path`
2. **Raw SQL only**: sem ORM, sem SQLAlchemy; psycopg2 + RealDictCursor
3. **Responses padronizadas**: `success(data)` / `error(msg, status)` de `app/core/responses.py`
4. **Zero secrets no código**: Railway env vars ou Docker secrets no edge
5. **Migrations idempotentes**: sempre `IF NOT EXISTS`, nunca `DROP`
6. **TypeScript strict**: zero `any` implícito
7. **Zero print() no backend**: usar `logging.getLogger(__name__)`
8. **CORS explícito**: nunca `CORS(app)` bare; sempre whitelist por env
