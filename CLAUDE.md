# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Identidade do Projeto

**EPI Monitor V2** — Sistema de monitoramento de EPIs (Equipamentos de Proteção Individual) via câmeras CCTV com detecção YOLOv8. Desenvolvido por  (Logikos)  Vitor Emanuel.

**Stack produção (Railway — 13 serviços)**:
- `api-v3` → Flask + SocketIO + gunicorn/eventlet (`SERVICE_TYPE=api`)
- `worker` → Celery Worker: inference YOLO, training, extraction, quality, versioning (`SERVICE_TYPE=worker`)
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
./scripts/smoke_test.sh https://api-v3-production-2b22.up.railway.app

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
│   │   └── AnnotationInterface.jsx  # UI de anotação (modificável com cuidado)
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

### Redis → WebSocket Bridge
```python
# Redis pub/sub bridge para SocketIO (real-time events)
# Implementado em app/core/socket_bridge.py
# Worker V1 (services/shared/events) foi DEPRECATED — ver worker/DEPRECATED.md
# Servicos atuais: inference-service, scheduler-service, training-service
```

---

## Regras Absolutas

### AnnotationInterface.jsx
`AnnotationInterface.jsx` pode ser modificado com cuidado. Criar backup antes de alterações grandes. Testar exaustivamente após mudanças.

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
- `worker` / `celery-worker` → Celery worker consumindo filas: extraction, quality, versioning, inference, training
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
- API: `https://api-v3-production-2b22.up.railway.app`
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

## Migration Protocol

### Criar Migration
1. Checar ultima: `ls backend/app/infrastructure/database/migrations/*.sql | sort | tail -1`
2. Proxima numeracao: sequencial (atualmente 014)
3. **APENAS permitido**:
   - `CREATE TABLE IF NOT EXISTS`
   - `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
   - `CREATE INDEX IF NOT EXISTS`
4. **NUNCA permitido**: `DROP`, `ALTER COLUMN TYPE`, `DELETE FROM`, `TRUNCATE`
5. Toda nova tabela DEVE ter `tenant_id UUID REFERENCES tenants(id)`
6. Testar idempotencia: rodar arquivo 2x sem erro

### Apos Executar Migration (checklist obrigatoria)
- [ ] Migration executada sem erros
- [ ] Model/dataclass atualizado em `domain/models/`
- [ ] Repository atualizado em `infrastructure/database/repositories/`
- [ ] Service atualizado em `domain/services/`
- [ ] Route/handler atualizado em `api/v1/`
- [ ] Types/interfaces frontend atualizados (se exposto na API)
- [ ] Testes atualizados para novos campos
- [ ] `docs/DATABASE.md` atualizado

### NUNCA em Migrations
- Criar migration e nao executar
- Alterar migration ja executada (criar nova para corrigir)
- Criar campo no banco sem refletir em model+repository+service
- Migration + mudanca de logica no mesmo commit

---

## Classificacao de Impacto

| Nivel | Escopo | Verificacao | Exemplos |
|-------|--------|-------------|----------|
| P0-CRITICO | Multi-servico, risco de dados | Manual + testes + e2e | Migration, auth, tenant isolation |
| P1-ALTO | Servico unico, user-facing | Testes obrigatorios | Novo endpoint, componente UI |
| P2-MEDIO | Refactor interno | Self-review | Cleanup, logging |
| P3-BAIXO | Documentacao | Nenhum | Typos, README |

Classificar ANTES de qualquer mudanca. Quantidade de verificacao e PROPORCIONAL ao nivel.

---

## Débitos Técnicos P3 — Sprint 2026-04-13

Anotar para próxima sprint. **NÃO corrigir nesta sprint.**

- **tenant_id ausente em queries de validação**: `count_validated()` e `get_annotated_by_video()` em `frame_repository.py` não filtram por `tenant_id` — risco de cross-tenant data exposure em deploy multi-tenant real
- **AnnotationPage usa fetch() raw**: `frontend/src/pages/AnnotationPage.tsx` usa `fetch()` diretamente para chamadas de validação em vez do wrapper `api.ts` (sem retry, sem auth header automático)
- **Cobertura de testes ~55%**: Target é 60%. Áreas descobertas: validation_handlers, versioning, training dispatch
- **2 testes falhando pré-existentes**: `test_invalid_scheme` (validators) e `test_upload_file_calls_upload_file` (r2_storage) — falham por mudanças de interface, não por regressão nova
- **Worker eventlet deprecated**: Gunicorn v26 remove suporte a eventlet. Migrar para gevent ou threading worker antes do upgrade
- **_dispatch_vast_ai é simulação**: `training.py` tem fallback Vast.ai que ainda não executa SSH real — apenas redireciona para simulação com log de warning

---

## Session Protocol

### Iniciando Sessao
1. Ler CLAUDE.md (automatico)
2. Checar branch: `git branch --show-current`
3. Health check: `cd backend && python -m pytest tests/ -v --tb=short -q`

### Antes de Commitar
1. Rodar testes da area afetada
2. `cd frontend && npx tsc --noEmit` (se frontend mudou)
3. `cd backend && python -m ruff check .` (se backend mudou)
4. Conventional commits: `feat|fix|refactor|docs(scope): descricao`

---

## Definição de "Concluído"

- [ ] Código implementado e testável manualmente
- [ ] TypeScript compila sem erros (`npx tsc --noEmit`)
- [ ] Zero erros de lint (ruff no backend, eslint no frontend)
- [ ] Commit no padrão Conventional Commits
- [ ] Push para `staging` e health check 200

*Em caso de conflito entre este arquivo e qualquer outro documento, este prevalece.*
