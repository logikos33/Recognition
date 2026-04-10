# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Identidade do Projeto

**EPI Monitor V2** — Sistema de monitoramento de EPIs (Equipamentos de Proteção Individual) via câmeras CCTV com detecção YOLOv8. Desenvolvido por  (Logikos)  Vitor Emanuel.

**Stack produção (Railway — 13 serviços)**:
- `api-v2` → Flask + SocketIO + gunicorn/eventlet (`SERVICE_TYPE=api`)
- `worker` → FFmpeg + inferência YOLOv8 (`SERVICE_TYPE=worker`)
- `frontend` → React 18 + TypeScript + Vite
- `auth-service`, `camera-gateway`, `inference-service`, `scheduler-service`, `training-service`, `ws-gateway`
- `pre-annotation-service` → DINO + SAM (`SERVICE_TYPE=pre-annotation`)
- `landing-page` → Astro + ONNX demo no browser (`SERVICE_TYPE=landing-page`)
- `PostgreSQL`, `Redis` — plugins Railway

**Branch ativa**: `staging` (deploys automáticos no Railway). NUNCA push direto em `main`.

---

## Comandos de Desenvolvimento

```bash
# Backend API (rodar localmente)
cd backend
export SERVICE_TYPE=api DATABASE_URL=... REDIS_URL=... JWT_SECRET_KEY=...
python3 railway_start.py          # usa nixpacks.toml / railway_start.py
# OU diretamente:
python3 -c "from app import create_app; app = create_app(); app.run(port=5001, debug=True)"

# Frontend
cd frontend && npm run dev         # porta 3000, proxy para localhost:5001

# Linting backend
cd backend && python -m ruff check .
cd backend && python -m mypy app/ --ignore-missing-imports

# TypeScript check
cd frontend && npx tsc --noEmit

# Migrations manuais (Railway roda automaticamente no startup)
psql $DATABASE_URL -f backend/app/infrastructure/database/migrations/NNN_nome.sql

# Smoke test antes de merge para staging/main
./scripts/smoke_test.sh https://api-v2-production-131a.up.railway.app

# Deploy (automático via push)
git push origin staging            # Railway builda e deploya
```

---

## Estrutura Real do Projeto

```
backend/
├── app/
│   ├── __init__.py              # create_app() — Application Factory
│   ├── config.py                # Config por ambiente (dev/test/prod)
│   ├── constants.py             # Enums: UserRole, R2Prefix, EpiClass
│   ├── extensions.py            # jwt, socketio
│   ├── api/v1/                  # Blueprints por domínio
│   │   ├── auth/routes.py       # POST /api/auth/login|register
│   │   ├── cameras/routes.py    # CRUD /api/cameras + stream control
│   │   ├── alerts/routes.py     # GET /api/alerts (filtros, export CSV)
│   │   ├── rules/routes.py      # Alert rules engine
│   │   ├── modules/routes.py    # GET /api/modules/{code}/classes|stats
│   │   ├── reports/routes.py    # GET /api/reports/home
│   │   ├── frames/routes.py     # POST /api/frames/{id}/pre-annotate
│   │   ├── dashboard/routes.py  # KPIs, Excel export
│   │   ├── training/routes.py   # Jobs, modelos, datasets
│   │   └── health/routes.py     # GET /health
│   ├── core/
│   │   ├── auth.py              # get_current_user_id(), get_tenant_id()
│   │   ├── responses.py         # success(data), error(msg, status)
│   │   ├── exceptions.py        # EpiMonitorError hierarchy
│   │   └── validators.py        # RTSPUrlValidator
│   ├── domain/
│   │   ├── models/              # Dataclasses por entidade
│   │   └── services/            # camera_service, module_service, report_service...
│   └── infrastructure/
│       ├── database/
│       │   ├── connection.py    # DatabasePool (ThreadedConnectionPool singleton)
│       │   ├── repositories/    # Um por entidade (BaseRepository)
│       │   └── migrations/      # 001_initial → 012_camera_fields.sql
│       └── storage/             # R2Storage (boto3)
├── tests/
└── requirements-legacy.txt      # histórico (não usar — ver requirements/)

requirements/                    # Separado por serviço
├── base.txt                     # Flask, psycopg2, boto3, redis...
├── api.txt                      # -r base.txt (sem ML/torch)
├── worker.txt                   # -r base.txt + torch + ultralytics + ffmpeg
├── inference.txt                # -r base.txt + torch + ultralytics
├── training.txt                 # -r base.txt + torch + tensorboard
└── pre-annotation.txt           # -r base.txt + torch + supervision + transformers

nixpacks.toml                    # pip install -r requirements/api.txt; cmd: python3 railway_start.py
railway_start.py                 # Router por SERVICE_TYPE: api|worker|pre-annotation|landing-page

frontend/src/
├── App.tsx                      # Auth gate + BrowserRouter (≤100 linhas)
├── AppRoutes.tsx                # Todas as rotas
├── components/
│   ├── annotation/
│   │   └── AnnotationInterface.jsx  # ← CONGELADO — nunca tocar
│   └── shared/                  # ErrorBoundary, LoadingSpinner, StatusBadge
├── hooks/                       # useAuth, usePolling, useModules, useMonitoringSocket
├── pages/
│   ├── HomePage.tsx             # Dashboard global (reports + module cards)
│   ├── epi/                     # EpiDashboard, EpiCameras, EpiAlerts
│   ├── fueling/                 # FuelingPlaceholder (Em breve)
│   ├── CamerasPage.tsx, AlertsHistoryPage.tsx, MonitoringPage.tsx...
├── services/                    # api.ts (fetch wrapper), moduleService, reportService...
└── types/

pre-annotation-service/src/      # DINO + SAM service independente
landing-page/                    # Astro 4 + React + yolov8n-demo.onnx
services/shared/
├── database.py                  # get_db_connection() context manager (legado/worker)
└── events.py                    # EventPublisher / EventConsumer (Redis pub/sub)
```

---

## Padrões Críticos

### Database (OBRIGATÓRIO)
```python
# repositories usam DatabasePool — NUNCA conexão avulsa
from app.infrastructure.database.connection import DatabasePool

def _get_repo() -> MyRepository:          # padrão em todas as routes
    pool = DatabasePool.get_instance()
    return MyRepository(pool)

# BaseRepository expõe:
# _execute(query, params) → list[dict]
# _execute_one(query, params) → Optional[dict]
# _execute_mutation(query, params) → Optional[dict]  # INSERT/UPDATE com RETURNING
```

### API Response (OBRIGATÓRIO)
```python
from app.core.responses import success, error
# Retorna: {"status": "success"|"error", "data": {...}}
return success({"cameras": items})
return error("Câmera não encontrada", 404)
```

### Frontend API Client
```typescript
// api.ts retorna o envelope completo {status, data}
// Para acessar dados: const res = await api.get<{status:string; data:T}>(path); res.data
import { api } from '../services/api'
```

### Redis (eventos Worker → API)
```python
# Worker publica, API consome via EventConsumer.subscribe_all()
# NUNCA Worker emite WebSocket diretamente — sempre via Redis pub/sub
from services.shared.events import EventPublisher  # no worker
from services.shared.events import EventConsumer   # na API
```

---

## Regras Absolutas

### Componente CONGELADO
`AnnotationInterface.jsx` nunca é modificado, renomeado, movido ou refatorado. Qualquer integração se adapta ao seu contrato.

### Banco de dados
- `psycopg2` direto, sem SQLAlchemy, sem ORM
- `RealDictCursor` como padrão
- Todo SQL nos repositories (`infrastructure/database/repositories/`)
- Migrations: **APENAS** `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` — nunca `DROP`

### Multi-tenant
- Toda query filtra por `tenant_id` — operator vê só seus dados
- `get_tenant_id()` em `app/core/auth.py` extrai do JWT (default: `00000000-0000-0000-0000-000000000001`)
- Toda nova tabela deve ter `tenant_id UUID REFERENCES tenants(id)`

### Segurança
- `CORS(app, origins=config.CORS_ORIGINS)` — nunca `CORS(app)` bare
- `RTSPUrlValidator` antes de qualquer URL chegar ao FFmpeg
- Zero SQL com f-string com input do usuário

### Qualidade
- TypeScript strict: true — zero any implícito
- Zero `print()` no backend — `logging.getLogger(__name__)`
- Bounding boxes: `pointerEvents: 'none'`, zero `onClick`

### Vite (path com espaço)
```typescript
// vite.config.ts obrigatório:
server: { usePolling: true, cacheDir: '/tmp/vite-cache-epi' }
```

---

## Railway / Deploy

### Roteamento por SERVICE_TYPE
`railway_start.py` roteia com base em `SERVICE_TYPE`:
- `api` → gunicorn `app:create_app()` (backend/)
- `worker` → `worker/worker_server.py`
- `pre-annotation` → gunicorn `src.main:app` (pre-annotation-service/)
- `landing-page` → Flask static server com `/health` endpoint

### Requirements separados por serviço
A API não instala torch/ultralytics. Serviços de ML usam `requirements/worker.txt` ou `requirements/inference.txt`.

### Criar novo serviço Railway
```bash
railway add --service nome-do-servico
railway variable set SERVICE_TYPE=... --service nome-do-servico --skip-deploys
railway up --service nome-do-servico --detach
railway domain --service nome-do-servico   # gerar URL pública
```

### Migrations
São executadas automaticamente por `railway_start.py` em `SERVICE_TYPE=api`. Arquivos em `backend/app/infrastructure/database/migrations/NNN_nome.sql`. Última: `012_camera_fields.sql`.

### URLs produção
- API: `https://api-v2-production-131a.up.railway.app`
- Frontend: `https://frontend-production-bf96.up.railway.app`
- Landing: `https://landing-page-production-b659.up.railway.app`
- Pre-annotation: `https://pre-annotation-service-production.up.railway.app`

---

## Módulos (Sprint 5)

O sistema é multi-módulo. Cada tenant tem acesso a módulos via `tenant_modules`:

| Módulo | `module_code` | Status | Classes YOLO |
|--------|--------------|--------|--------------|
| EPI Monitor | `epi` | Ativo | helmet/no_helmet/vest/no_vest/gloves/no_gloves/glasses/no_glasses |
| Fueling Control | `fueling` | Placeholder | truck/plate/fuel_nozzle/product_box/pallet |

Toda query em câmeras/alertas/frames filtra por `module_code` além de `tenant_id`.

---

## Branching e Commits

```
feat/nome  fix/nome  →  staging  →  (PR)  →  main
```

```
feat(scope): descrição
fix(scope): descrição
refactor(scope): sem mudança de comportamento
```

Scopes: `api, frontend, backend, migration, railway, pre-annotation, landing, events, cameras, alerts, modules`

---

## Definição de "Concluído"

- [ ] Código implementado e testável manualmente
- [ ] TypeScript compila sem erros (`npx tsc --noEmit`)
- [ ] Zero erros de lint (ruff no backend, eslint no frontend)
- [ ] Commit no padrão Conventional Commits
- [ ] Push para `staging` e health check 200

*Em caso de conflito entre este arquivo e qualquer outro documento, este prevalece.*
