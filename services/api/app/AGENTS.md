<!-- Parent: ../AGENTS.md -->

# backend/app — Flask Application Core

**Purpose**: Application Factory, extensions initialization, configuration, constants, and API blueprints.

## Key Components

### Application Factory (`__init__.py`)

**Entry point**: `create_app(config_name: str | None) -> Flask`

Pattern:
- Gunicorn calls: `gunicorn -w 2 -k eventlet "app:create_app()"`
- Initializes Flask with configuration
- Registers all extensions (JWT, SocketIO, CORS)
- Registers all blueprints from `api/v1/`
- Configures middleware (error handlers, security headers, logging)
- Starts Redis bridge (WebSocket pub/sub)
- Serves frontend React in production (fallback to index.html)
- Configures Swagger UI at `/api/v1/docs` (if flasgger installed)

**Database pool initialization**:
- Calls `DatabasePool.initialize()` with min/max connections from config
- Skipped in testing mode (mocked)

**WebSocket bridge**:
- Starts `start_redis_bridge(socketio)` in production
- Subscribes to Redis pub/sub channels
- Broadcasts to SocketIO clients in real-time

### Configuration (`config.py`)

**Pattern**: Inheritance hierarchy with factory function.

Classes:
- `Config` (base) — all environment variables, no defaults for production secrets
- `DevelopmentConfig` — DEBUG=True, permissive defaults
- `TestingConfig` — in-memory database, minimal pool
- `ProductionConfig` — strict validation (min 32-char JWT_SECRET_KEY)

**Factory**: `get_config(env_name: Optional[str]) -> Config`

**Key variables**:
- `DATABASE_URL` — PostgreSQL (Railway auto-injects)
- `REDIS_URL` — Redis (Railway auto-injects)
- `JWT_SECRET_KEY` — must be ≥32 chars in production
- `SECRET_KEY` — Flask secret
- `CORS_ORIGINS` — comma-separated list, never "*" in production
- `R2_*` — Cloudflare credentials
- `MAX_UPLOAD_SIZE_MB`, `ALLOWED_EXTENSIONS` — upload validation
- `BLUR_THRESHOLD`, `BRIGHTNESS_THRESHOLD` — frame quality filters
- `YOLO_*` — inference config (model path, confidence, skip frames)
- `HLS_*` — stream tuning (segment time, playlist size)

**Database URL fix**: Automatically converts `postgres://` to `postgresql://` for psycopg2.

### Extensions (`extensions.py`)

**Singletons created here, initialized in `create_app()`**:

```python
jwt = JWTManager()           # JWT token decode/verify
socketio = SocketIO()        # WebSocket + message queue (Redis)
```

No database extension — uses direct psycopg2 with connection pool.

### Constants (`constants.py`)

**All enums and string constants — never magic strings in code**:

**Enums**:
- `VideoStatus` — pending, uploading, processing, completed, failed
- `FrameStatus` — raw, queued, annotated, rejected
- `TrainingStatus` — queued, running, completed, failed, stopped
- `CameraStatus` — inactive, starting, active, error
- `UserRole` — admin, operator
- `EpiClass` — helmet, no_helmet, vest, no_vest, gloves, no_gloves, safety_glasses, no_safety_glasses
- `TrainingPreset` — fast, balanced, quality

**Prefixes**:
- `R2Prefix` — keys for Cloudflare R2 storage (raw-videos, frames, labels, datasets, models, evidence)
- `RedisChannel` — pub/sub channel templates (detection, training_progress, camera_control, etc.)

## API Blueprints (`api/v1/`)

**13 blueprints registered in order**:

1. **health** — `GET /api/v1/health`
   - System health check (database, Redis, R2)
   - No authentication required

2. **auth** — `/api/v1/auth/*`
   - `POST /api/v1/auth/register` — Create user account
   - `POST /api/v1/auth/login` — Get JWT token
   - `GET /api/v1/auth/me` — Current user (JWT required)
   - `POST /api/v1/auth/logout` — Invalidate token

3. **training** — `/api/v1/training/*`
   - `POST /api/v1/training/jobs` — Start training job
   - `GET /api/v1/training/jobs/{job_id}` — Job status
   - `GET /api/v1/training/models` — List trained models

4. **cameras** — `/api/v1/cameras/*`
   - `GET /api/v1/cameras` — List user's cameras
   - `POST /api/v1/cameras` — Create camera (RTSP auto-generated)
   - `GET /api/v1/cameras/{id}` — Get camera (password masked)
   - `PUT /api/v1/cameras/{id}` — Update camera
   - `DELETE /api/v1/cameras/{id}` — Delete camera
   - `POST /api/v1/cameras/{id}/test` — Test RTSP connectivity

5. **streams** — `/api/v1/streams/*`
   - `POST /api/v1/cameras/{id}/stream/start` — Start HLS + YOLO
   - `POST /api/v1/cameras/{id}/stream/stop` — Stop stream
   - `GET /api/v1/cameras/{id}/stream/status` — Stream status
   - `GET /api/v1/streams/status` — All streams status
   - `GET /streams/health` — Detailed health report

6. **videos** — `/api/v1/videos/*`
   - `POST /api/v1/videos/upload` — Get presigned URL for R2
   - `GET /api/v1/videos` — List videos
   - `GET /api/v1/videos/{id}` — Video metadata
   - `DELETE /api/v1/videos/{id}` — Delete video

7. **dashboard** — `/api/v1/dashboard/*`
   - `GET /api/v1/dashboard/kpis` — KPI dashboard
   - `GET /api/v1/dashboard/export` — Export to Excel

8. **storage** — `/api/v1/storage/*`
   - `GET /api/v1/storage/health` — R2 health check

9. **alerts** — `/api/v1/alerts/*`
   - `GET /api/v1/alerts` — List alerts
   - `POST /api/v1/alerts/{id}/acknowledge` — Mark as read

10. **rules** — `/api/v1/rules/*`
    - `GET /api/v1/rules` — List detection rules
    - `POST /api/v1/rules` — Create rule

11. **modules** — `/api/v1/modules/*`
    - `GET /api/v1/modules` — List installed modules
    - `POST /api/v1/modules/{name}/enable` — Enable module

12. **reports** — `/api/v1/reports/*`
    - `GET /api/v1/reports` — List reports
    - `POST /api/v1/reports/generate` — Generate report

13. **frames** — `/api/v1/frames/*`
    - `GET /api/v1/frames` — List frames
    - `GET /api/v1/frames/{id}` — Frame metadata
    - `POST /api/v1/frames/{id}/label` — Label frame (annotation)

## Core Layer (`core/`)

**Cross-cutting concerns**:

- **auth.py** — JWT token creation/verification, `@jwt_required()` decorator
- **exceptions.py** — `EpiMonitorError` hierarchy (DatabaseError, ValidationError, etc.)
- **responses.py** — `success_response()`, `error_response()` standardized JSON
- **middleware.py** — error handlers, security headers (X-Content-Type-Options, X-Frame-Options), request logging
- **validators.py** — `RTSPUrlValidator`, `VideoUploadValidator`, input sanitization
- **socket_bridge.py** — Redis pub/sub listener, broadcasts to SocketIO clients

## Directories

### `domain/` — Business Logic

Service classes (no Flask dependency):
- `AuthService` — user registration, password hashing (bcrypt)
- `CameraService` — camera CRUD, RTSP URL generation
- `VideoService` — video upload metadata, frame extraction
- `TrainingService` — training job submission, model management
- `InferenceService` — YOLOv8 inference pipeline
- `DatasetService` — dataset versions, frame collection

### `infrastructure/` — External Systems

**database/**
- `connection.py` — `DatabasePool` (psycopg2 ThreadedConnectionPool)
- `repositories/` — SQL queries isolated here (no SQL in domain/)

**storage/**
- `base.py` — `StorageStrategy` (ABC)
- `r2_storage.py` — R2 implementation (boto3)
- `local_storage.py` — Local disk (development)

**queue/**
- `celery_app.py` — Celery factory
- `tasks/` — Celery tasks (extraction, quality, versioning, training, inference)

## Common Patterns

### Adding a New Blueprint

1. Create directory: `api/v1/my_feature/`
2. Create `routes.py` with `Blueprint("my_feature", __name__, url_prefix="/api/v1/my_feature")`
3. Create `__init__.py` with empty file
4. Import and register in `__init__.py` `_register_blueprints()` function
5. Add tests in `tests/unit/` and `tests/integration/`

### Adding a New Configuration Variable

1. Add to `Config` class in `config.py` with `os.environ.get()`
2. Set default (if safe) or raise ValueError in `ProductionConfig.__init_subclass__()`
3. Document in CLAUDE.md Environment Variables section

### Adding a New Enum or Constant

1. Add to `constants.py`
2. Use in code via `from app.constants import MyEnum`
3. Never use magic strings or numbers elsewhere

## Swagger UI

**Endpoint**: `GET /api/v1/docs`

Configuration in `_configure_swagger()`:
- Automatically scanned from all blueprints (if flasgger installed)
- Docstrings on routes become documentation
- Bearer token authentication shown in UI
- Gracefully disabled if flasgger not in requirements

## Testing

**Fixtures in conftest.py**:
- `app` — Flask test app (config="testing")
- `client` — Flask test client
- `mock_storage` — In-memory R2 mock
- `mock_db_pool` — MagicMock database for unit tests

**Run tests**:
```bash
pytest                              # All tests
pytest tests/unit/                  # Unit tests only
pytest tests/integration/           # Integration tests only
pytest tests/ -v --cov=app/         # With coverage
```

**Minimum coverage**: 80% per module (enforced in CI/CD)

## Security

1. **CORS**: Never bare `CORS(app)` — always `CORS(app, origins=config.CORS_ORIGINS)`
2. **JWT**: All routes except `/health` and `/login` require `@jwt_required()`
3. **Input validation**: Use validators in `core/validators.py`
4. **Camera passwords**: Encrypted with Fernet in database, never returned in API
5. **Logging**: Never log passwords, tokens, connection strings (use structured logging)

## Deployment

**Railway**:
- Service name: `api`
- Start command: `gunicorn -w 2 -k eventlet --worker-connections 1000 --bind 0.0.0.0:$PORT "app:create_app()"`
- Health check: `GET /api/v1/health` (expects 200)
- Environment variables: `DATABASE_URL`, `REDIS_URL` (auto-injected by Railway plugins)
