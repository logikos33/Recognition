# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**EPI Monitor V2** — Sistema de Monitoramento CCTV com IA para Baias de Carregamento da Ambev.

Sistema de visão computacional que usa câmeras CCTV existentes para:
- Detectar automaticamente quando um caminhão entra na baia
- Capturar a placa do veículo via OCR
- Contar cada produto carregado em tempo real (YOLOv8)
- Encerrar a sessão quando o caminhão sai
- Enviar para validação do operador
- Gerar relatórios em Excel e KPIs em dashboard

### V2 vs V1 — Why Rewrite

A V1 chegou a ~90% mas acumulou débitos técnicos:
- `api_server.py` com 3900 linhas (impossível manter)
- Vazamentos de conexão com banco (`next(get_db())`)
- FFmpeg e YOLO no mesmo container da API
- Polls com `setInterval` fixo (flood de requests)
- Tudo em um único serviço Railway ($150/mês para 5 câmeras)

**V2**: Arquitetura de microserviços, ~$70/mês para 5 câmeras com performance superior.

---

## Tech Stack

### Backend
- Python 3.11 + Flask (framework web)
- Flask-JWT-Extended (auth)
- Flask-SocketIO + Eventlet (WebSocket real-time)
- psycopg2-binary (PostgreSQL)
- bcrypt (hash de senhas)
- cryptography/Fernet (criptografia de senhas de câmeras)
- redis (event bus)
- gunicorn + eventlet (produção)

### AI/ML (Worker)
- YOLOv8 via Ultralytics
- FFmpeg (RTSP → HLS)
- OpenCV + PyTorch

### Frontend
- React 18 + TypeScript + Vite
- React Router (SPA)
- Recharts (dashboard charts)

### Database
- PostgreSQL 15
- Migrations SQL numeradas (`001_`, `002_`)
- UUIDs como primary keys
- `user_id` em TODAS as tabelas desde o início

### Infra
- Railway (PaaS)
- Nixpacks (build com FFmpeg)
- GitHub branches: `develop` / `staging` / `main`

---

## Architecture — Microservices

```
┌─────────────────┐         ┌─────────────────┐
│  API Flask      │◄───────►│   PostgreSQL    │
│  (routes, auth, │         │   (dados)       │
│   dashboard)    │         └─────────────────┘
└────────┬────────┘                 ▲
         │                          │
         │ Redis                    │
         │ (event bus)              │
         ▼                          │
┌─────────────────┐         ┌─────────────────┐
│   Worker        │         │      Redis      │
│  (FFmpeg+YOLO)  │         │   (event bus)   │
│                 │         └─────────────────┘
└─────────────────┘
```

**Scale**: 1 Worker por 3-4 câmeras (~1.5GB RAM por instância)

---

## Development Commands

### Local Development
```bash
# Backend (API)
export FLASK_ENV=development
export SERVICE_TYPE=api
python3 -m api.app  # ou gunicorn api.app:app

# Worker
export SERVICE_TYPE=worker
export WORKER_ID=worker-1
python3 worker/worker_server.py

# Frontend
cd frontend && npm run dev

# Migrations manual
for f in migrations/*.sql; do
  psql $DATABASE_URL -f "$f"
done
```

### Testing & Validation
```bash
# Smoke test (obrigatório antes de merge para staging/main)
./scripts/smoke_test.sh http://localhost:5001

# Teste em staging
./scripts/smoke_test.sh $RAILWAY_URL
```

### Git Workflow
```
develop  → desenvolvimento ativo
staging  → Railway staging (pré-produção)
main     → produção (apenas via PR de staging)
```

**NEVER** push direto em `main`. Sempre PR de `staging` para `main`.

---

## ABSOLUTE RULES — NEVER VIOLATE

### Backend
- ❌ `next(get_db())` → ✅ **SEMPRE** `with get_db_connection() as conn:`
- ❌ Arquivos >200 linhas → ✅ Blueprints por domínio
- ❌ Secrets hardcoded → ✅ **SEMPRE** `os.environ.get()`
- ❌ PORT hardcoded → ✅ `int(os.environ.get('PORT', 5001))`
- ❌ `postgres://` direto → ✅ corrigir `postgresql://` no startup
- ❌ `DROP TABLE` / `RENAME` → ✅ **APENAS** `ADD COLUMN IF NOT EXISTS`
- ❌ Endpoint sem `try/except` → ✅ handler em todo endpoint

### Frontend
- ❌ `setInterval` fixo → ✅ **exponential backoff** em TODOS os polls (use `usePolling` hook)
- ❌ Token com chave diferente → ✅ `getToken()` centralizado
- ❌ `api.logout()` (pode não existir) → ✅ `handleLogout` inline
- ❌ Dados mockados → ✅ zero mock — tudo conectado ao backend
- ❌ `App.tsx` >100 linhas → ✅ máx 100 linhas, lógica em hooks
- ❌ Componente >200 linhas → ✅ dividir em componentes menores

### Database
- ❌ `DROP` em produção → ✅ **APENAS** `CREATE IF NOT EXISTS`
- ❌ Tabelas sem `user_id` → ✅ **TODAS** as tabelas têm `user_id` desde o início
- ❌ `SELECT *` sem filtro de user → ✅ operator vê apenas seus dados, admin vê tudo

### Railway
- ❌ Nome de módulo errado no gunicorn → ✅ verificar `api.app:app` antes
- ❌ Frontend servido pelo Vite em produção → ✅ `npm build` + Flask serve estático
- ❌ Tudo em um container → ✅ API (`SERVICE_TYPE=api`) e Worker (`SERVICE_TYPE=worker`) separados

---

## Project Structure

```
├── api/
│   ├── app.py                 # Flask app factory — entry point para gunicorn
│   ├── blueprints/
│   │   ├── auth/              # register, login, me
│   │   ├── cameras/           # CRUD + stream control
│   │   ├── training/          # upload, frames, anotação, YOLO
│   │   ├── rules/             # rules engine, templates
│   │   ├── dashboard/         # KPIs, Excel export
│   │   └── streams/           # status público (sem JWT)
│   └── utils/
│       ├── auth.py            # hash_password, check_password, get_current_user
│       ├── responses.py       # success(), error()
│       └── worker_proxy.py    # API→Worker via Redis
├── worker/
│   └── worker_server.py       # FFmpeg+YOLO isolado, Redis events
├── services/shared/
│   ├── database.py            # get_db_connection() context manager
│   └── events.py              # EventPublisher (Worker), EventConsumer (API)
├── frontend/
│   └── src/
│       ├── components/        # componentes reutilizáveis
│       ├── hooks/             # usePolling, useAuth, etc.
│       ├── pages/             # Login, Cameras, Training, Rules, Dashboard
│       ├── services/          # api.ts (centralizado)
│       └── types/             # TypeScript types
├── migrations/                # 001_users.sql, 002_cameras.sql, etc.
├── storage/                   # training_videos, frames, streams, models
├── scripts/
│   └── smoke_test.sh          # testes obrigatórios antes de merge
├── nixpacks.toml              # build config (inclui FFmpeg)
├── railway.toml               # deploy config
└── railway_start.py           # inicialização Railway robusta
```

---

## Security Requirements

1. **Senhas de câmeras**: Criptografia Fernet (AES-128) no banco. **NUNCA** retornar na API.
2. **Secrets**: 100% via variáveis de ambiente. `.env` no `.gitignore`.
3. **JWT**: Todos os endpoints exceto `/health` e `/api/streams/status`.
4. **Isolamento**: `user_id` em todas as queries. Operator vê só seus dados.
5. **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, etc.
6. **CORS**: Configurável via `CORS_ORIGINS` env var. **NUNCA** `*` em produção.

---

## Common Patterns

### Database Connection (OBRIGATÓRIO)
```python
from services.shared.database import get_db_connection

# ✅ CORRETO — sempre fecha a conexão
with get_db_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT ...", (param,))
    result = cur.fetchall()

# ❌ ERRADO — causa pool exhaustion (90% dos crashes V1)
conn = next(get_db())
```

### Frontend Polling (OBRIGATÓRIO)
```typescript
import { usePolling } from '@/hooks/usePolling'

usePolling(
  async () => { await fetchData() },
  5000,  // intervalo base
  { maxInterval: 60000 }  // backoff máximo
)
```

### API Response (OBRIGATÓRIO)
```python
from api.utils.responses import success, error

return success(data, status=201)
return error('Mensagem', status=400)
```

---

## Environment Variables

### API
- `SERVICE_TYPE=api` — define que este serviço é a API
- `JWT_SECRET_KEY` — segredo para tokens JWT
- `SECRET_KEY` — segredo Flask
- `CAMERA_SECRET_KEY` — chave Fernet para senhas de câmeras
- `CORS_ORIGINS` — origins permitidas (separadas por vírgula)
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `FLASK_ENV` — `development` ou `production`

### Worker
- `SERVICE_TYPE=worker` — define que este serviço é Worker
- `WORKER_ID` — identificador único (`worker-1`, `worker-2`, etc.)
- `YOLO_MODEL_PATH` — caminho para modelo YOLO
- `DATABASE_URL` — PostgreSQL (compartilhado)
- `REDIS_URL` — Redis (event bus)

### Admin (criado automaticamente no primeiro deploy)
- `ADMIN_EMAIL` — padrão: `admin@epimonitor.com`
- `ADMIN_PASSWORD` — padrão: `EpiMonitor@2024!`
- `ADMIN_NAME` — padrão: `Administrador`

---

## Railway Deployment

### API Service
```bash
railway up --service-type api
# Variáveis: SERVICE_TYPE=api
```

### Worker Service (adicionar quando necessário)
```bash
railway add --service worker
# Variáveis: SERVICE_TYPE=worker, WORKER_ID=worker-1
```

### Health Check
Railway usa `/health` para healthcheck. Retorna:
- `200` — database OK
- `503` — database com problema

---

## Database URL Fix (Railway)

Railway retorna `postgres://` mas `psycopg2` precisa `postgresql://`. Correção automática em `railway_start.py`:

```python
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)
```

---

## Default Admin Credentials

```
Email: admin@epimonitor.com
Senha: EpiMonitor@2024!
```

**IMPORTANTE**: Alterar em produção.

---

## Cost Structure

- Sem câmeras ativas: ~$30/mês (API + PostgreSQL + Redis)
- Com 1 Worker (3-4 câmeras): ~$70/mês
- Com 2 Workers (7-8 câmeras): ~$110/mês

Versus V1: $150/mês para apenas 5 câmeras com problemas.
