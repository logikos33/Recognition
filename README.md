# Recognition

> **Plataforma multi-módulo de reconhecimento de cenários via IA** — visão computacional em CCTV para ambientes industriais e comerciais.

Anteriormente chamado *EPI Monitor V2*.  
Repositório: `github.com/logikos33/Recognition` · Desenvolvido por **Logikos / Vitor Emanuel**.

---

## O que é

**Recognition** é uma plataforma SaaS de código fechado que transforma câmeras CCTV em sensores inteligentes configuráveis. Um único motor de detecção alimenta **N cenários** — cada câmera recebe seu próprio cenário (o que detectar, onde na imagem, o que fazer com o resultado) sem criar novos pipelines de ML.

O sistema opera em dois modos complementares:

- **Cloud:** processamento centralizado no Railway; ideal para câmeras com boa conectividade.
- **Edge:** inferência local no site do cliente (NVIDIA Jetson Orin NX Super) via DeepStream + TensorRT; tolerante a falhas de rede, latência mínima. Os eventos são sincronizados para a nuvem pelo `edge-sync-agent`.

A plataforma é **multi-tenant** por princípio (C-01): cada operador vê apenas seus próprios dados; toda tabela carrega `tenant_id` e toda query filtra por ele.

---

## Módulos

| Módulo | `module_code` | Operation-type | O que entrega |
|--------|---------------|----------------|---------------|
| **EPI** (Equipamentos de Proteção Individual) | `epi` | `epi_zone` | Alerta quando EPI obrigatório está ausente em uma zona configurada (capacete, colete, luvas, óculos) |
| **Qualidade** (inspeção de esteira) | `quality` | `defect_trigger` | Inspeção automática + OCR de peça + contagem única via DeepSORT |
| **Contagem / Estacionamento** | — | `counting_line` | Contagem de cruzamentos por linha configurável (DeepSORT track único) |
| **Fueling** (controle de abastecimento) | `fueling` | — | Em evolução — controle de abastecimento e movimentação de veículos |

Cada módulo usa o mesmo framework de **operações configuráveis por câmera** (`op_class` + `validate_config` + hot-reload via Redis). A configuração visual (desenhar zonas, linhas, pontos sobre o frame) é feita no editor de cenários do frontend.

---

## Arquitetura

```
╔══════════════════════════════════════════════════════════════════╗
║                     CLOUD  (Railway)                            ║
║                                                                 ║
║  ┌─────────────┐  ┌──────────┐  ┌───────────────────────────┐  ║
║  │  api (Flask │  │  worker  │  │  inference                │  ║
║  │  + SocketIO)│  │ (Celery) │  │  (GPU cloud, opcional)    │  ║
║  └──────┬──────┘  └────┬─────┘  └───────────────────────────┘  ║
║         │              │ Redis pub/sub                          ║
║  ┌──────▼──────────────▼─────────────────────────────────────┐  ║
║  │ PostgreSQL · Cloudflare R2 (storage) · Redis              │  ║
║  └───────────────────────────────────────────────────────────┘  ║
║                                                                 ║
║  ┌──────────────┐  ┌────────────────┐  ┌────────────────────┐  ║
║  │  frontend    │  │  landing       │  │ pre-annotation     │  ║
║  │  React 18    │  │  Astro + ONNX  │  │ (DINO + SAM)       │  ║
║  │  + Vite      │  │  demo browser  │  │                    │  ║
║  └──────────────┘  └────────────────┘  └────────────────────┘  ║
║                                                                 ║
║  Serviços auxiliares: camera-gateway · scheduler-service       ║
║                       training-service · ws-gateway            ║
║                       auth-service                             ║
╚══════════════════════════════════════════════════════════════════╝
                              ▲ ▼  HTTPS + edge-sync-agent
╔══════════════════════════════════════════════════════════════════╗
║                  EDGE  (site do cliente)                        ║
║                                                                 ║
║  Câmeras RTSP ──► DeepStream (TensorRT INT8) ──► Eventos       ║
║  (Intelbras / Hikvision / ONVIF)   epi | quality | fueling     ║
║                                          │                     ║
║  NVIDIA Jetson Orin NX Super 16GB        │                     ║
║  (Palit Pandora AI — ADR-0025)           ▼                     ║
║                               edge-sync-agent                  ║
║                               (SQLite buffer · backoff         ║
║                                · config poller)                ║
║                                                                 ║
║  Rede: MikroTik + Tailscale + cloudflared (ADR-0020)          ║
╚══════════════════════════════════════════════════════════════════╝
```

Referências: [`EDGE_DEPLOYMENT_PLAN.md`](./EDGE_DEPLOYMENT_PLAN.md) · [`docs/architecture/EDGE_AGENT_ARCHITECTURE.md`](./docs/architecture/EDGE_AGENT_ARCHITECTURE.md) · [`docs/architecture/PLATAFORMA_CENARIOS.md`](./docs/architecture/PLATAFORMA_CENARIOS.md)

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| **API** | Flask + Flask-SocketIO + gunicorn/eventlet |
| **Worker** | Celery + Redis pub/sub |
| **Frontend** | React 18 + TypeScript + Vite · Zustand · Radix UI · HLS.js |
| **Landing** | Astro 4 + React + ONNX (demo de inferência no browser) |
| **Banco de dados** | PostgreSQL — psycopg2 + RealDictCursor, **sem ORM** |
| **Storage** | Cloudflare R2 (boto3) |
| **Pré-anotação** | DINO + SAM (`pre-annotation-service`) |
| **Edge — inferência** | DeepStream + TensorRT INT8 no Jetson Orin NX Super |
| **Edge — sync** | `edge-sync-agent` (Python, SQLite, backoff, config poller) |
| **Deploy cloud** | Railway (Nixpacks — build ~2–3 min) |
| **Deploy edge** | Docker Compose + supervisord no Jetson |

> **Detector:** o motor atual usa YOLOv8 (Ultralytics / AGPL-3.0). A migração para um detector
> **Apache 2.0** (candidatos: YOLOX, RF-DETR) está em andamento — benchmark no Orin NX Super pendente.
> Ver `docs/architecture/LICENSING_COMMERCIALIZATION.md` e ADR-0024 (arquivos pendentes de commit).

---

## Estrutura do monorepo

```
apps/
├── frontend/          # React 18 + TS + Vite (UI, editor de cenários, anotação)
└── landing/           # Astro + ONNX demo no browser

services/
├── api/               # Flask API + Celery worker
│   ├── app/api/v1/    # Blueprints por domínio (auth, cameras, scenarios, ...)
│   ├── app/core/      # responses, auth, exceptions, validators
│   ├── app/domain/    # services, models (dataclasses)
│   ├── app/infrastructure/  # database (pool + repositories), storage, queue
│   └── migrations/    # migrations do serviço API (legado — usar infra/migrations/)
├── inference/         # serviço de inferência independente
└── edge-sync-agent/   # agente edge→cloud (buffer SQLite, uploader, config poller)

deepstream/            # pipelines DeepStream por módulo
├── epi/   fueling/   quality/   shared/

camera-gateway/        # gateway de câmeras
scheduler-service/     # agendador de tarefas
training-service/      # serviço de treinamento
ws-gateway/            # WebSocket gateway
pre-annotation-service/ # DINO + SAM

infra/
└── migrations/        # SQL idempotente, forward-only (001 → 080)

shared/                # código compartilhado entre serviços
models/                # modelos YOLO / pesos
tools/                 # agent-driver (fila autônoma de tasks)
scripts/               # smoke_test.sh, seed_rvb.py
docs/                  # arquitetura, ADRs, roadmap, runbooks
```

---

## Endpoints principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/api/auth/login` | Login — retorna JWT |
| `POST` | `/api/auth/register` | Registro de usuário |
| `GET/POST` | `/api/cameras` | Listar / criar câmeras |
| `GET/POST` | `/api/edge/sites` | Listar / criar sites edge |
| `GET/POST` | `/api/devices` | Dispositivos edge (enrollment) |
| `POST` | `/api/edge/events` | Ingestão de eventos do edge (batch, idempotente) |
| `GET` | `/api/edge/commands` | Polling de comandos pelo edge-sync-agent |
| `GET/POST` | `/api/scenarios` | Cenários por câmera (leitura + escrita) |
| `GET/POST` | `/api/operations` | Operações configuráveis (ROI, linha, zona) |
| `GET` | `/api/alerts` | Alertas (com filtros, export CSV) |
| `POST` | `/api/counting/sessions` | Sessões de contagem |
| `POST` | `/api/v1/videos/upload-url` | Presigned URL para upload de vídeo |
| `GET` | `/api/training/videos/{id}/frames` | Frames para anotação |
| `POST` | `/api/training/frames/{id}/annotations` | Salvar anotações YOLO |
| `GET` | `/api/v1/storage/health` | Health do R2 |
| `GET` | `/health` | Health geral da API |
| `GET` | `/api/v1/docs` | Swagger UI |

---

## Desenvolvimento local

```bash
# 1. Clonar e preparar variáveis
git clone https://github.com/logikos33/Recognition.git
cd Recognition
cp services/api/.env.example services/api/.env  # preencher DATABASE_URL, REDIS_URL, JWT_SECRET_KEY

# 2. API (services/api)
cd services/api
python -m venv venv && source venv/bin/activate
pip install -r ../../requirements/api.txt
export SERVICE_TYPE=api
python ../../railway_start.py          # ou: gunicorn "app:create_app()"
# API em http://localhost:5001

# 3. Frontend (apps/frontend)
cd apps/frontend
npm install
npm run dev    # http://localhost:3000 — proxy para localhost:5001

# 4. Worker Celery
cd services/api
celery -A app.infrastructure.queue.celery_app:celery worker \
  --loglevel=info --queues=extraction,quality,inference
```

**Simulador RTSP** (sem câmera física): usa MediaMTX + FFmpeg.
Ver script em `services/api/scripts/rtsp_simulator.py` ou o README detalhado no arquivo.

> Para detalhes completos de desenvolvimento, ver [`CLAUDE.md`](./CLAUDE.md), [`AGENT.md`](./AGENT.md) e [`docs/`](./docs/).

---

## Deploy Railway

```bash
# Push para staging — Railway builda automaticamente (~2–3 min)
git push origin staging

# Após o push, redeployar os serviços afetados
railway redeploy -s api-v3 -y
railway redeploy -s worker -y
railway redeploy -s frontend -y   # se frontend mudou

# Monitorar logs
railway logs --service api-v3
railway logs --service worker

# Health checks de produção
curl https://api-v3-production-2b22.up.railway.app/health
curl https://api-v3-production-2b22.up.railway.app/api/v1/storage/health
```

**URLs de produção:**

| Serviço | URL |
|---------|-----|
| API | `https://api-v3-production-2b22.up.railway.app` |
| Frontend | `https://frontend-production-bf96.up.railway.app` |
| Landing | `https://landing-page-production-b659.up.railway.app` |
| Pré-anotação | `https://pre-annotation-service-production.up.railway.app` |

---

## Princípios & Convenções

O projeto segue uma **constitution** com princípios inegociáveis. Resumo:

| Código | Princípio |
|--------|-----------|
| **C-01** | Multi-tenant sempre — toda tabela tem `tenant_id`; toda query filtra por ele |
| **C-02** | Migrations forward-only e idempotentes — apenas `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS`; nunca `DROP` |
| **C-03** | `psycopg2` + `RealDictCursor`, zero ORM — SQL explícito nos repositories |
| **C-04** | Zero SQL com f-string de input do usuário |
| **C-05** | `CORS` nunca bare — sempre com `origins=config.CORS_ORIGINS` |
| **C-06** | Zero `print()` no backend — `logging.getLogger(__name__)` |
| **C-07** | TypeScript strict — zero `any` implícito |
| **C-08** | Harness de migrations obrigatório — toda alteração de schema passa pelo harness D1 |

Ver [`constitution.md`](./constitution.md) para o texto completo e fontes.

**Branching:**
```
feat/nome  fix/nome  →  staging / develop  →  (PR)  →  main
```
Nunca push direto em `main`. Conventional Commits: `feat(scope):`, `fix(scope):`, `refactor(scope):`, `docs(scope):`.

---

## Roadmap

### ✅ Concluído
- Fundação: monorepo, constitution, ADRs 0001–0027, harness de migrations (D1)
- Schema edge: sites, devices, heartbeat, token RS256 (ADR-0019)
- APIs cloud: sites, devices, enrollment, heartbeat, health, fleet overview, histórico
- Editor visual de cenários (frontend) + API de cenários + catálogo de operation-types
- White-label e branding por tenant (design system, ColorPicker, BrandingPreview)
- Contagem por sessão (DeepSORT), alertas com export CSV, módulo Fueling (base)
- Per-camera liveness heartbeat, seleção de modelo por câmera, tuning por câmera (zonas de exclusão, perfil dia/noite)
- Hardware edge definido: Palit Pandora AI · Jetson Orin NX Super 16GB (ADR-0025)

### 🔄 Em andamento / próximo
- **edge-sync-agent:** core lógico (SQLite buffer, uploader com backoff, config poller)
- **Benchmark do detector Apache 2.0** (YOLOX / RF-DETR no Orin NX) — ADR-0024
- **Events batch ingest** (Fase 2) — migration `edge_events` + endpoint idempotente
- **Command queue** — migration `edge_commands` + API + polling pelo edge
- **PgBouncer / pool de conexões** — escalabilidade de DB (ADR-0022)
- **Pipeline de treinamento E2E** — ADR-0023
- **Harness D2:** RTSP sintético + cenários baseline/isolamento (sem GPU)

### 🔴 Aguardando hardware (Mini PC / Orin NX no site)
- DeepStream pipelines EPI / Quality / Counting + TensorRT INT8 + calibração
- Edge stack plug-and-play (Docker Compose, nvidia, Tailscale, cloudflared, UFW + MikroTik)
- Provisionamento RVB Isolantes (Blumenau/SC) + runbook on-site

Ver [`docs/ROADMAP_GO_LIVE.md`](./docs/ROADMAP_GO_LIVE.md) para o índice completo de tasks.

---

## Licença

SaaS de **código fechado**. O stack é licenciado internamente por Logikos.

O detector atual (YOLOv8 / Ultralytics) é AGPL-3.0; a migração para um detector permissivo (Apache 2.0)
está em curso — ver `docs/architecture/LICENSING_COMMERCIALIZATION.md` e ADR-0024 (arquivos pendentes de commit).
⚠️ As notas de licenciamento neste repositório não constituem aconselhamento jurídico.
