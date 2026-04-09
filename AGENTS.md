# AGENTS.md — EPI Monitor V2

**Last Updated:** 2026-04-09  
**Project:** EPI Monitor V2 — Sistema de monitoramento CCTV com IA para baias de carregamento da Ambev  
**Domain:** Visão computacional + detecção de EPIs (Equipamentos de Proteção Individual) via YOLOv8

---

## Project Purpose

EPI Monitor V2 é um sistema de monitoramento inteligente que usa câmeras CCTV existentes para:

- **Detectar automaticamente** quando um caminhão entra na baia (via YOLOv8)
- **Contar produtos** carregados em tempo real com bounding boxes em canvas
- **Validar conformidade** de EPIs (capacete, colete, luvas, óculos)
- **Gerar relatórios** em Excel com KPIs e evidências fotográficas
- **Treinar modelos customizados** de YOLO com datasets anotados

**Users:** Operadores de baia, supervisores, analistas de compliance, engenheiros ML.

---

## Architecture Overview

**11 Microservices** on Railway (PaaS):

```
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL + Redis                       │
│              (Railway Plugins: Postgres, Redis)              │
└─────────────────────────────────────────────────────────────┘
         ▲                       ▲              ▲
         │                       │              │
         ▼                       ▼              ▼
    Backend API          Worker              Frontend
  (Flask + ASGI)     (Redis pub/sub)     (React 18 SPA)
  ├─ auth-service      ├─ FFmpeg           ├─ AnnotationInterface
  ├─ camera-gateway    ├─ YOLO             └─ MonitoringDashboard
  ├─ inference-service └─ Celery
  ├─ ws-gateway
  ├─ training-service
  └─ scheduler-service
         │
         └──► Cloudflare R2 (Storage)
```

**Scale:** 5-12 câmeras IP simultâneas, latência < 3s, ~$200/mês.

---

## Root Level Files

| File | Purpose | Owner |
|------|---------|-------|
| `CLAUDE.md` | **CRITICAL** — AI agent instructions, ABSOLUTE RULES, patterns | Product Lead |
| `AGENTS.md` | This file — service catalog, AI guidelines, dependencies | Documentation |
| `README.md` | Quick start, tech stack, endpoints, local dev | Documentation |
| `railway.toml` | Root Railway config (builder=NIXPACKS) | DevOps |
| `nixpacks.toml` | Nixpacks build config (installs FFmpeg) | DevOps |
| `railway_start.py` | Railway startup entrypoint, DB URL fix | Backend |
| `requirements.txt` | Root Python dependencies (Flask, psycopg2, boto3, etc.) | Backend |
| `.env.example` | Environment variable template | Documentation |
| `worker-railway.toml` | Worker service Railway config (per-service) | DevOps |
| `frontend-railway.toml` | Frontend service Railway config (per-service) | DevOps |

---

## Subdirectories — 11 Services + 3 Shared

### Main Backend Service

| Directory | Files | Purpose | Language | Railway Config |
|-----------|-------|---------|----------|---|
| **backend/** | 230+ files | Main API (Flask), auth, camera mgmt, video ingestion | Python 3.11 | `backend/railway.toml` |
| `backend/app/` | | DDD structure: api/, core/, domain/, infrastructure/ | | |
| `backend/app/api/v1/` | `__init__.py`, `auth/`, `cameras/`, `videos/`, `training/`, `dashboard/` | Flask blueprints by domain | | |
| `backend/app/core/` | `auth.py`, `exceptions.py`, `responses.py`, `validators.py`, `middleware.py` | Cross-cutting concerns | | |
| `backend/app/domain/services/` | `video_service.py`, `camera_service.py`, `annotation_service.py` | Business logic (no DB) | | |
| `backend/app/infrastructure/` | `database/`, `storage/`, `queue/` | DB queries, R2 boto3, Celery tasks | | |
| `backend/tests/` | 316 tests, 80%+ coverage | pytest (unit + integration) | | |
| `backend/scripts/` | `rtsp_simulator.py` | Local RTSP simulator (MediaMTX + FFmpeg) | | |

### Microservices (Railway services)

| Service | Directory | Purpose | Runtime | Memory | Notes |
|---------|-----------|---------|---------|--------|-------|
| **API** | `backend/` | HTTP REST API, WebSocket, JWT auth, Swagger | `gunicorn -k eventlet` | 512MB | DDD Flask app, healthcheck `/api/v1/health` |
| **auth-service** | `auth-service/` | Isolated JWT token service (register, login, verify) | Flask | 256MB | Optional, can be merged into backend |
| **camera-gateway** | `camera-gateway/` | RTSP→HLS streaming, FFmpeg orchestration | Python + FFmpeg | 1GB | Connects to camera IPs, outputs HLS segments |
| **inference-service** | `inference-service/` | YOLOv8 inference loop, frame detection | Python + PyTorch | 2GB+ | GPU optional (RunPod), consumes frames from Redis |
| **ws-gateway** | `ws-gateway/` | WebSocket bridge (Redis pub/sub → Socket.IO) | Node.js + Socket.IO | 256MB | Real-time detection broadcast to browsers |
| **training-service** | `training-service/` | Kick off RunPod YOLOv8 training jobs | Python + RunPod SDK | 512MB | Manages job lifecycle, downloads trained model to R2 |
| **scheduler-service** | `scheduler-service/` | Celery Beat (cleanup, health checks, retention) | Python + Celery | 256MB | Runs cron jobs (e.g., delete old frames) |
| **worker/** | `worker/` | Redis consumer (legacy, being phased out) | Python | 512MB | Old single-service architecture, deprecated |
| **pre-annotation-service** | `pre-annotation-service/` | Auto-label frames before human review | Python + YOLOv8 | 1.5GB | Quality gate for dataset pipeline |
| **landing-page/** | `landing-page/` | Public landing page (marketing) | React/Next.js | 256MB | Static + SSR, separate from main frontend |
| **frontend/** | `frontend/` | React 18 SPA (monitoring, annotation, training, dashboard) | Node.js + React | 512MB | Vite dev, nginx prod, Socket.IO client |

### Shared Services

| Directory | Purpose | Owner |
|-----------|---------|-------|
| **services/shared/** | Shared Python utilities (database, events, logging) | Backend Team |
| **migrations/** | SQL idempotent migrations (001_, 002_, etc.) | Database Team |
| **docs/** | Architecture decisions, edge agent design | Documentation |

### Storage

| Directory | Purpose |
|-----------|---------|
| **storage/** | Local cache of R2 objects (videos, frames, models, evidence) — git-ignored |

---

## Key Files by Responsibility

### For Backend Engineers

- `backend/app/__init__.py` — Flask app factory, extension init, error handlers
- `backend/app/api/v1/__init__.py` — Blueprint registration (auth, cameras, videos, training)
- `backend/app/infrastructure/database/` — psycopg2 connection pool, repositories (no ORM)
- `backend/app/domain/services/` — Business logic (video processing, camera lifecycle)
- `backend/requirements.txt` — Dependencies (Flask, psycopg2, boto3, Celery)
- `backend/railway.toml` — Gunicorn start command, health check
- `backend/app/config.py` — Environment-based config (dev/staging/prod)

### For Frontend Engineers

- `frontend/src/components/AnnotationInterface.jsx` — **FROZEN** — never modify
- `frontend/src/components/MonitoringDashboard.tsx` — Real-time camera feed + detections
- `frontend/src/hooks/useSocket.ts` — Socket.IO connection + event listeners
- `frontend/src/services/api.ts` — Centralized REST client (with JWT auth)
- `frontend/src/types/` — TypeScript interfaces (Camera, Frame, Detection, etc.)
- `frontend/vite.config.ts` — Dev server config (must use polling for dev FS)
- `frontend/railway.toml` — Docker build, start command (nginx)

### For ML Engineers

- `inference-service/` — YOLOv8 model loading, frame inference, confidence scoring
- `training-service/` — RunPod job submission, model versioning, metrics tracking
- `backend/app/domain/services/annotation_service.py` — Label format, class mapping
- `migrations/` — Schema for storing model metadata, inference results

### For DevOps Engineers

- `railway.toml` — Root build config (NIXPACKS)
- `backend/railway.toml`, `frontend/railway.toml`, `worker-railway.toml` — Per-service Railway configs
- `nixpacks.toml` — Package manager + system deps (FFmpeg, FFprobe)
- `railway_start.py` — Startup script (DB URL fix, migrations runner)
- `backend/Dockerfile`, `frontend/Dockerfile.frontend` — Container definitions (if not using Nixpacks)

### For QA Engineers

- `backend/tests/` — pytest suite (unit, integration, E2E)
- `scripts/smoke_test.sh` — Basic health check (if exists)
- `backend/app/core/validators.py` — Input validation (RTSPUrlValidator, VideoUploadValidator)

---

## Absolute Rules for AI Agents

Read **CLAUDE.md** FIRST. These are inviolable:

### Backend (Python/Flask)

- ❌ Never `next(get_db())` → ✅ Always `with get_db_connection() as conn:`
- ❌ Never files >200 lines → ✅ Use Flask blueprints by domain
- ❌ Never secrets hardcoded → ✅ Always `os.environ.get()`
- ❌ Never `PORT` hardcoded → ✅ `int(os.environ.get('PORT', 5001))`
- ❌ Never `postgres://` → ✅ Use `postgresql://` (fixed in `railway_start.py`)
- ❌ Never `DROP TABLE` in migrations → ✅ Only `CREATE IF NOT EXISTS`
- ❌ Never endpoint without try/except → ✅ Global error handler in `__init__.py`
- ❌ Never SQL fmtstring with user input → ✅ Always parameterized queries
- ❌ Never psycopg2 via ORM → ✅ Direct psycopg2 with ThreadedConnectionPool

### Frontend (React/TypeScript)

- ❌ Never modify `AnnotationInterface.jsx` → ✅ Treat as frozen third-party component
- ❌ Never bare `setInterval` → ✅ Use exponential backoff (via custom hook)
- ❌ Never `import`/`export` from wrong location → ✅ Match `CLAUDE.md` structure
- ❌ Never mockData in prod → ✅ All data from live API or localStorage (JWT token)
- ❌ Never `App.tsx` >100 lines → ✅ Max 100 lines, split into custom hooks
- ❌ Never component >200 lines → ✅ Split into smaller components
- ❌ Never bare `CORS(app)` → ✅ Always explicit `CORS(app, origins=[...])`
- ❌ Never `any` in TypeScript → ✅ `strict: true` in tsconfig.json
- ❌ Never `console.log()` in prod → ✅ Use structured logging (via logger service)

### Database (PostgreSQL/psycopg2)

- ❌ Never SQLAlchemy ORM → ✅ Raw psycopg2 + repositories
- ❌ Never global connection → ✅ ThreadedConnectionPool with context manager
- ❌ Never `SELECT *` without user_id filter → ✅ Always isolate by owner
- ❌ Never schema without `user_id` column → ✅ Multi-tenant isolation from day 1
- ❌ Never NULL UUID → ✅ Always UUID v4 as primary key

### Security

- ❌ CORS never `*` in production → ✅ Explicit origins in env var
- ❌ Never bare JWT token in response → ✅ Always in `data.token` with 200 status
- ❌ Never camera password in API response → ✅ Always masked/hidden
- ❌ Never expose R2 credentials → ✅ Presigned URLs only, stored in env vars
- ❌ Never trace SQL errors to client → ✅ Log internally, return generic error

### Testing

- ❌ Never claim test count without running pytest → ✅ Run `pytest --cov=app` and report exact output
- ❌ Never <80% coverage in new modules → ✅ Minimum 80% by module
- ❌ Never skip flaky tests → ✅ Fix the root cause, add retry logic if needed
- ❌ Never mock the database for integration tests → ✅ Use test DB with real schema

### Deployment

- ❌ Never hardcode environment → ✅ Use `FLASK_ENV` / `NODE_ENV` env var
- ❌ Never manual database migrations in prod → ✅ Automated via `railway_start.py`
- ❌ Never forget health check endpoint → ✅ `/api/v1/health` (returns 200/503)
- ❌ Never dependencies in Dockerfile → ✅ Use Nixpacks (auto-detects requirements.txt, package.json)

---

## Testing & Verification

### Backend Tests

```bash
cd backend
python -m pytest tests/ -v --cov=app --cov-report=html
```

**Target:** 80%+ coverage, 316+ tests passing.

### Frontend Tests

```bash
cd frontend
npm test -- --coverage
```

**Target:** Key components (AnnotationInterface, MonitoringDashboard) tested.

### Local Smoke Test

```bash
# Start API locally
cd backend && python -m app

# In another terminal
curl http://localhost:5001/api/v1/health
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@epimonitor.com","password":"EpiMonitor@2024!"}'
```

### RTSP Simulator (Development)

```bash
cd backend/scripts
python rtsp_simulator.py start
# Opens rtsp://localhost:8554/camera1
```

---

## Dependencies & Deployment Stack

### Backend Dependencies (Python 3.11)

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | Latest | HTTP web framework |
| Flask-JWT-Extended | Latest | JWT token validation |
| Flask-SocketIO | Latest | WebSocket real-time |
| Flask-CORS | Latest | CORS handling (configured via env) |
| psycopg2-binary | Latest | PostgreSQL direct driver |
| bcrypt | Latest | Password hashing |
| cryptography | Latest | Fernet encryption (camera passwords) |
| gunicorn | Latest | WSGI server |
| eventlet | Latest | Async worker for SocketIO |
| redis | Latest | Redis pub/sub client |
| boto3 | Latest | S3/R2 (Cloudflare R2) |
| celery | Latest | Task queue (training, inference) |
| ultralytics | Latest | YOLOv8 model loading |
| torch, torchvision | Latest | ML inference |
| opencv-python-headless | Latest | Video frame processing |
| Pillow | Latest | Image manipulation |
| numpy | Latest | Numerical arrays |
| requests | Latest | HTTP client |
| structlog | Latest | Structured logging |
| python-dotenv | Latest | `.env` file loading |
| openpyxl | Latest | Excel export (reports) |
| Flasgger | Latest | Swagger UI generation |
| imagehash | Latest | Perceptual hash (frame dedup) |
| paramiko | Latest | SSH client (Vast.ai integration) |

**See:** `requirements.txt` (root) and `backend/requirements.txt`

### Frontend Dependencies (Node.js 18+)

| Package | Purpose |
|---------|---------|
| React 18 | UI framework |
| TypeScript | Type safety |
| Vite | Build tool + dev server |
| Socket.IO client | WebSocket real-time |
| Recharts | Dashboard charts |
| React Router | SPA navigation |
| Axios or Fetch API | HTTP client |

**See:** `frontend/package.json`

### Railway Plugins (Production)

| Plugin | Role |
|--------|------|
| **PostgreSQL** | Primary database (schema via migrations/) |
| **Redis** | Pub/sub event bus, WebSocket message queue |
| **Cloudflare R2** | Object storage (videos, frames, models) — accessed via boto3 |

### External Services

| Service | Purpose | Cost |
|---------|---------|------|
| **Railway** | PaaS (11 services) | ~$200/month |
| **PostgreSQL on Railway** | Database | Included |
| **Redis on Railway** | Cache + pub/sub | Included |
| **Cloudflare R2** | Object storage | $0.015/GB downloaded |
| **RunPod** (optional) | GPU training (YOLOv8) | Pay-as-you-go (~$0.50/hour A40) |
| **Vast.ai** (optional) | Alternative GPU provider | Pay-as-you-go (cheaper) |

---

## Environment Variables (Complete List)

### API Service (backend/)

```bash
# Core
FLASK_ENV=production
SERVICE_TYPE=api
SECRET_KEY=<min-32-chars-random>

# Database
DATABASE_URL=postgresql://user:pass@host:5432/epi_monitor
# (Injected by Railway PostgreSQL plugin)

# Redis
REDIS_URL=redis://user:pass@host:6379
# (Injected by Railway Redis plugin)

# JWT
JWT_SECRET_KEY=<min-32-chars-random>
JWT_ALGORITHM=HS256

# Camera Encryption
CAMERA_SECRET_KEY=<32-byte-base64-for-Fernet>

# CORS
CORS_ORIGINS=https://epi-frontend.railway.app,https://epi-dashboard.railway.app

# Storage (R2 / S3)
R2_ENDPOINT=https://{account_id}.r2.cloudflarestorage.com
R2_BUCKET=epi-monitor
R2_KEY=<cloudflare-access-key>
R2_SECRET=<cloudflare-secret-key>
R2_REGION=auto

# Logging
LOG_LEVEL=INFO

# Optional: Inference
YOLO_MODEL_PATH=models/yolov8m.pt
INFERENCE_CONFIDENCE_THRESHOLD=0.5
```

### Worker Service (worker/)

```bash
SERVICE_TYPE=worker
WORKER_ID=worker-1
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
YOLO_MODEL_PATH=models/yolov8m.pt
```

### Frontend Service (frontend/)

```bash
VITE_API_URL=https://epi-api.railway.app
VITE_WS_URL=wss://epi-api.railway.app
```

### Scheduler Service (scheduler-service/)

```bash
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
CLEANUP_INTERVAL_HOURS=24
```

---

## Common Patterns (DDD + Flask)

### API Route (api/v1/cameras/routes.py)

```python
from flask import Blueprint, request
from app.core.auth import jwt_required, get_current_user
from app.core.responses import success, error
from app.domain.services.camera_service import CameraService

cameras_bp = Blueprint('cameras', __name__, url_prefix='/api/v1/cameras')

@cameras_bp.route('', methods=['POST'])
@jwt_required()
def create_camera():
    try:
        user = get_current_user()
        payload = request.get_json()
        
        # Validate input
        if not payload.get('name'):
            return error('Name required', status=400)
        
        # Delegate to service
        camera = CameraService.create_camera(
            user_id=user['id'],
            name=payload['name'],
            host=payload['host'],
            port=payload['port']
        )
        return success(camera, status=201)
    except Exception as e:
        # Always catch, never expose stack trace
        logger.error('create_camera_failed', error=str(e), exc_info=True)
        return error('Failed to create camera', status=500)
```

### Service (domain/services/camera_service.py)

```python
from app.infrastructure.database.repositories.camera_repository import CameraRepository

class CameraService:
    @staticmethod
    def create_camera(user_id: str, name: str, host: str, port: int) -> dict:
        """Validate + create camera, return response dict."""
        
        # Validate
        RTSPUrlValidator.validate_host_port(host, port)
        
        # Persist
        camera = CameraRepository.create(
            user_id=user_id,
            name=name,
            host=host,
            port=port
        )
        return camera
```

### Repository (infrastructure/database/repositories/camera_repository.py)

```python
from services.shared.database import get_db_connection
from psycopg2.extras import RealDictCursor

class CameraRepository:
    @staticmethod
    def create(user_id: str, name: str, host: str, port: int) -> dict:
        """Insert camera, return as dict."""
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO cameras (id, user_id, name, host, port)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s)
                    RETURNING id, name, host, port, created_at
                """, (user_id, name, host, port))
                
                conn.commit()
                return dict(cur.fetchone())
```

### Frontend Hook (hooks/useCamera.ts)

```typescript
import { useState, useCallback } from 'react'
import { cameraService } from '@/services/cameraService'

export function useCamera() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchCameras = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await cameraService.listCameras()
      setCameras(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  return { cameras, loading, error, fetchCameras }
}
```

### Frontend Component (components/MonitoringDashboard.tsx)

```typescript
import { useCamera } from '@/hooks/useCamera'
import { useSocket } from '@/hooks/useSocket'

export function MonitoringDashboard() {
  const { cameras, fetchCameras } = useCamera()
  const { detections } = useSocket()

  useEffect(() => {
    fetchCameras()
  }, [fetchCameras])

  return (
    <div className="grid grid-cols-3 gap-4">
      {cameras.map(cam => (
        <CameraFeed key={cam.id} camera={cam} detections={detections[cam.id]} />
      ))}
    </div>
  )
}
```

---

## Database Schema (11 Core Tables)

```sql
-- users (authentication)
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR UNIQUE NOT NULL,
  password_hash VARCHAR NOT NULL,
  full_name VARCHAR,
  company_name VARCHAR,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- cameras (IP cameras for streaming)
CREATE TABLE cameras (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR NOT NULL,
  manufacturer VARCHAR,  -- 'intelbras', 'hikvision', 'generic'
  host VARCHAR NOT NULL,
  port INTEGER DEFAULT 554,
  username VARCHAR,
  password_encrypted VARCHAR,  -- Fernet encrypted
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- videos (uploaded video files)
CREATE TABLE videos (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  filename VARCHAR NOT NULL,
  r2_key VARCHAR,  -- Path in R2 storage
  size_bytes BIGINT,
  duration_seconds FLOAT,
  status VARCHAR,  -- 'uploaded', 'processing', 'ready'
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- frames (extracted from videos)
CREATE TABLE frames (
  id UUID PRIMARY KEY,
  video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
  frame_number INTEGER,
  r2_key VARCHAR,  -- Path in R2
  blur_score FLOAT,
  brightness_score FLOAT,
  status VARCHAR,  -- 'pending', 'annotated', 'rejected'
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- annotations (human labels on frames)
CREATE TABLE annotations (
  id UUID PRIMARY KEY,
  frame_id UUID REFERENCES frames(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  label_data JSONB,  -- {"helmet": true, "vest": false, ...}
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- datasets (collection of frames for training)
CREATE TABLE datasets (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR NOT NULL,
  status VARCHAR,  -- 'preparing', 'ready', 'training'
  frame_count INTEGER,
  version VARCHAR,  -- v1.0.0
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- training_jobs (YOLO training on RunPod)
CREATE TABLE training_jobs (
  id UUID PRIMARY KEY,
  dataset_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
  runpod_job_id VARCHAR,
  status VARCHAR,  -- 'pending', 'running', 'completed', 'failed'
  metrics JSONB,  -- {mAP: 0.85, precision: 0.92, ...}
  model_r2_key VARCHAR,  -- best.pt location
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- detections (real-time YOLO detections)
CREATE TABLE detections (
  id UUID PRIMARY KEY,
  camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
  timestamp TIMESTAMP WITH TIME ZONE,
  boxes JSONB,  -- [{x:100, y:200, w:50, h:80, class:'helmet', conf:0.95}, ...]
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- streams (HLS/WebSocket streams status)
CREATE TABLE streams (
  id UUID PRIMARY KEY,
  camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
  status VARCHAR,  -- 'active', 'paused', 'error'
  hls_url VARCHAR,
  last_heartbeat TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- evidence (screenshots/frames captured as proof)
CREATE TABLE evidence (
  id UUID PRIMARY KEY,
  camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
  detection_id UUID REFERENCES detections(id) ON DELETE CASCADE,
  r2_key VARCHAR,  -- Screenshot in R2
  timestamp TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- audit_logs (who did what, when)
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  action VARCHAR,  -- 'create_camera', 'upload_video', 'train_model'
  resource_id UUID,
  details JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Health Checks & Monitoring

### API Health

```bash
curl http://localhost:5001/api/v1/health
# Returns: { "status": "healthy", "checks": { "database": "ok", "redis": "ok", "r2": "ok" } }
```

**Status Codes:**
- `200 OK` — All systems operational
- `503 Service Unavailable` — One or more critical service down

### Logs

```bash
# Local development
tail -f backend/.logs/app.log

# Production (Railway)
railway logs --service API-V2
railway logs --service Worker
railway logs --service Frontend
```

---

## Decision Log (DECISIONS.md)

When making architectural decisions, record in a separate `DECISIONS.md` file:

```markdown
## [2026-04-09] — Microservice Architecture

**Context:** Original monolith `api_server.py` was 3900 lines, hard to maintain.

**Opti considered:** A) Keep monolith, B) Split into 11 services, C) Use Celery only

**Choice:** B — 11 services on Railway

**Reason:** Better scaling, independent deployment, fault isolation

**Impacted:** All services, Railway config, deployment time
```

---

## Running Locally (Complete Guide)

### 1. Prerequisites

```bash
python3.11 --version     # Must be 3.11+
ffmpeg -version          # For RTSP simulator
node --version           # For frontend (16+)
```

### 2. Clone & Setup

```bash
git clone https://github.com/your-repo/epi-monitor-v2.git
cd "EPI - CATH V2"

# Backend venv
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend deps
cd ../frontend
npm ci
```

### 3. Database (Railway)

```bash
# Use Railway CLI for easy access to production DB
railway link  # Select project
railway env   # Get env vars

# Or local PostgreSQL
brew install postgresql
createdb epi_monitor
export DATABASE_URL=postgresql://localhost/epi_monitor
```

### 4. Start Services

**Terminal 1 — API:**
```bash
cd backend
export FLASK_ENV=development
export $(cat .env.local | xargs)
python -m app
# → http://localhost:5001
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
# → http://localhost:3000
```

**Terminal 3 — RTSP Simulator (optional):**
```bash
cd backend/scripts
python rtsp_simulator.py start
# → rtsp://localhost:8554/camera1
```

### 5. Test

```bash
# Backend tests
cd backend && pytest tests/ -v

# Frontend tests (if configured)
cd frontend && npm test
```

---

## Deployment to Railway

### Prerequisites

```bash
npm install -g @railway/cli
railway login
railway link  # Select project
```

### Deploy

```bash
# Push to staging branch (pré-produção)
git add .
git commit -m "feat(scope): description"
git push origin staging

# Railway auto-builds (Nixpacks, ~3-5 min)

# Monitor build
railway logs --service API-V2 --follow

# Once ready, create PR: staging → main for production
```

### Verify

```bash
# Test API health
curl https://api-v2-production.railway.app/api/v1/health

# Test frontend
open https://epi-monitor-frontend.railway.app

# View logs
railway logs --service API-V2 -n 50
```

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `psycopg2.OperationalError: FATAL: remaining connection slots are reserved` | Connection pool exhausted | Check for `next(get_db())` instead of context manager |
| `ModuleNotFoundError: No module named 'app'` | Python path issue | Run from project root: `python -m app` |
| `CORS error in browser console` | Frontend URL not in CORS_ORIGINS | Add frontend domain to Railway env vars |
| `AnnotationInterface not rendering` | Props missing or incorrect | Check `AnnotationInterface.jsx` contract in component docs |
| `HLS stream not playing` | Camera not reachable | Test RTSP: `ffprobe rtsp://host:port/stream` |
| `Redis connection refused` | Redis service down | Check Railway Redis plugin status |
| `R2 upload fails` | Invalid credentials | Verify `R2_KEY`, `R2_SECRET`, `R2_BUCKET` in Railway |

---

## Contact & Contributors

- **Lead:** Vitor Emanuel (Backend + DevOps)
- **Frontend:** [Your name] (React/TypeScript)
- **ML:** [Your name] (YOLOv8 training)
- **QA:** [Your name] (Testing)

---

**Last Updated:** 2026-04-09  
**Status:** Active Development (Phase 4+5)  
**Next Milestone:** GPU-accelerated inference on separate service
