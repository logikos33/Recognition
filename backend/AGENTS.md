<!-- Parent: ../CLAUDE.md -->
<!-- Generated: 2026-04-09 -->

# Backend — EPI Monitor V2 API Service

**Purpose**: Flask 3.0 REST API for EPI monitoring system. Domain-Driven Design with psycopg2 (no ORM). Handles authentication, camera management, stream control, training pipelines, dashboard KPIs, and WebSocket bridge to frontend via Redis.

**Entry Point**: `gunicorn -w 2 ... 'app:create_app()'` → runs on PORT (default 5001)

**Tech Stack**: Python 3.11, Flask 3.0, Flask-SocketIO, Flask-JWT-Extended, psycopg2-binary, Redis, Swagger/Flasgger

---

## Directory Structure

```
backend/
├── app/
│   ├── __init__.py               # Application factory: create_app(config_name)
│   ├── config.py                 # Configuration by environment (dev/test/prod)
│   ├── extensions.py             # Flask extensions: jwt, socketio
│   ├── constants.py              # Enums: VideoStatus, EpiClass, R2Prefix, RedisChannels
│   ├── api/v1/                   # API routes (blueprints by domain)
│   │   ├── auth/                 # Register, login, me
│   │   ├── cameras/              # Camera CRUD, RTSP builder
│   │   ├── videos/               # Video upload, processing
│   │   ├── frames/               # Frame extraction, quality filtering
│   │   ├── training/             # Training jobs, model versioning
│   │   ├── datasets/             # Dataset CRUD, export to YOLO format
│   │   ├── storage/              # R2 health check
│   │   ├── health/               # System health, liveness
│   │   ├── dashboard/            # KPIs, Excel export
│   │   ├── alerts/               # Alert rules and triggers
│   │   ├── rules/                # Rules engine for session logic
│   │   ├── modules/              # Installed detection modules
│   │   ├── reports/              # Report generation
│   │   └── streams/              # Stream status, HLS manifests (public)
│   ├── core/                     # Shared utilities (auth, responses, middleware)
│   │   ├── auth.py               # JWT decode/encode, @jwt_required wrapper
│   │   ├── responses.py          # success(), error() response builders
│   │   ├── exceptions.py         # Custom exception hierarchy
│   │   ├── validators.py         # RTSPUrlValidator, input validation
│   │   ├── middleware.py         # Error handlers, security headers, logging
│   │   └── socket_bridge.py      # Redis pub/sub → SocketIO bridge (det:*, training:*)
│   ├── domain/                   # Business logic (pure, no Flask/DB dependencies)
│   │   ├── models/               # Dataclasses: User, Camera, Video, Frame, Detection
│   │   └── services/             # Use cases: VideoService, FrameService, etc.
│   └── infrastructure/           # Low-level implementations
│       ├── database/
│       │   ├── connection.py     # DatabasePool (ThreadedConnectionPool singleton)
│       │   ├── repositories/     # One per entity: UserRepository, CameraRepository, etc.
│       │   └── migrations/       # SQL migrations (numbered, CREATE IF NOT EXISTS only)
│       ├── storage/              # R2/S3 storage
│       │   ├── base.py           # StorageStrategy (abstract)
│       │   └── r2_storage.py     # R2Storage (boto3)
│       └── queue/                # Celery (if used) or Redis pub/sub
│           ├── celery_app.py     # Celery factory
│           └── tasks/            # Task definitions (extraction, training, etc.)
├── migrations/                   # SQL files: 001_users.sql, 002_cameras.sql, ...
├── scripts/                      # Utility scripts
│   └── seed_admin.py             # Create default admin user
├── tests/                        # pytest unit/integration tests
│   ├── conftest.py               # Fixtures
│   ├── unit/                     # Unit tests (mocked dependencies)
│   └── integration/              # Integration tests (real DB/Redis)
├── storage/                      # Local temp storage (training_videos/, frames/, models/)
├── Dockerfile                    # Multi-stage: compile + runtime
├── nixpacks.toml                 # Railway build config (Python 3.11, FFmpeg)
├── railway.toml                  # Railway deploy config
└── railway_start.py              # Startup script (DB URL fix, migrations)
```

---

## Key Files Reference

| File | Purpose | Pattern |
|------|---------|---------|
| `app/__init__.py` | Application factory | `create_app(config_name='production')` returns configured Flask app |
| `app/config.py` | Configuration by environment | Load from env vars, defaults for dev |
| `app/extensions.py` | Extension initialization | `jwt = JWTManager()`, `socketio = SocketIO()` |
| `app/constants.py` | Enums and constants | `VideoStatus`, `EpiClass`, `R2Prefix`, `RedisChannels` |
| `app/core/auth.py` | JWT handling | `encode_token(user_id)`, `decode_token(token)`, `@jwt_required` |
| `app/core/responses.py` | Response builders | `success(data, status=200)`, `error(msg, status=400)` |
| `app/core/socket_bridge.py` | Redis → SocketIO | `start_redis_bridge(socketio)` (background thread) |
| `app/core/middleware.py` | Global handlers | `register_error_handlers(app)`, security headers |
| `infrastructure/database/connection.py` | Database pool | `DatabasePool.initialize()`, thread-safe singleton |
| `infrastructure/database/repositories/` | Data access | One class per entity, all SQL here |
| `migrations/` | Schema evolution | CREATE IF NOT EXISTS, numbered, SQL only |

---

## Architecture Patterns

### 1. Application Factory
```python
# app/__init__.py
def create_app(config_name: str = None) -> Flask:
    app = Flask(__name__)
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Extensions
    jwt.init_app(app)
    socketio.init_app(app, message_queue=config.REDIS_URL)
    
    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(cameras_bp)
    # ...
    
    return app
```

**Benefit**: Testable, configurable, multiple instances.

### 2. Repository Pattern
```python
# infrastructure/database/repositories/camera_repository.py
class CameraRepository:
    @staticmethod
    def create(user_id: str, name: str, ...) -> Camera:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO cameras (id, user_id, name, ...)
                VALUES (%s, %s, %s, ...)
                RETURNING *
            """, (uuid.uuid4(), user_id, name, ...))
            row = cur.fetchone()
            return Camera(**row)
```

**Benefit**: All SQL isolated, testable with mocks, zero SQL in routes.

### 3. Service Layer
```python
# domain/services/camera_service.py
class CameraService:
    def __init__(self, repo: CameraRepository, consumer: EventConsumer):
        self.repo = repo
        self.consumer = consumer
    
    def start_stream(self, user_id: str, camera_id: str):
        camera = self.repo.get_by_id(user_id, camera_id)
        worker_id = self.consumer.get_best_worker()
        self.consumer.send_command(worker_id, {
            'action': 'start_stream',
            'camera_id': str(camera_id),
            'rtsp_url': camera.rtsp_url
        })
```

**Benefit**: Business logic independent of Flask/DB/Redis, easy to test.

### 4. WebSocket Bridge (Observer Pattern)
```python
# Worker publishes: epi:detections → Redis
# Bridge listens: Redis pub/sub → emits via SocketIO → Browser
# Handles: det:*, training:* channels (pattern subscription)

# app/core/socket_bridge.py — start_redis_bridge(socketio)
# Background thread subscribes to epi:detections
# Emits 'detection' event to /monitor namespace
```

**Benefit**: Decouples worker from frontend, scales across multiple API instances.

### 5. Database Connection Management
```python
# ALWAYS use context manager — NEVER raw connections
with get_db_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT ...", (param,))
    rows = cur.fetchall()
# Connection closes automatically, transaction commits

# WRONG (causes pool exhaustion)
conn = psycopg2.connect(...)
cur = conn.cursor()
cur.execute(...)
# Oops, forgot to close!
```

**Critical**: This pattern prevents 90% of V1 crashes.

---

## For AI Agents

### When modifying or adding endpoints:

1. **Create the route** in `app/api/v1/{domain}/routes.py`
   - Validate input with validators from `core/validators.py`
   - Get user from JWT: `current_user = get_jwt_identity()`
   - Call service layer, never repository directly

2. **Add service method** in `domain/services/{entity}_service.py`
   - Inject repository and external clients (EventConsumer, StorageClient)
   - Implement business logic, return domain model

3. **Add repository method** in `infrastructure/database/repositories/{entity}_repository.py`
   - Write SQL query with psycopg2 (parameterized, never f-string)
   - Use `with get_db_connection() as conn:` pattern
   - Map DB row to domain model

4. **Add migration** if schema changes
   - File: `migrations/NNN_{feature}.sql`
   - Use CREATE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS
   - Never DROP or RENAME in production

5. **Test all three layers**
   - Unit test: mock repository, test service logic
   - Integration test: real DB/Redis, test full flow
   - Smoke test: curl endpoint, check response

### Dependencies flow (Dependency Inversion)

```
route → service → repository → SQL
  ↑        ↑          ↑
  └─ inject config  ─┘
  └─ inject external client (Redis, S3)
```

Routes never know about SQL or infrastructure details.

### Common pitfalls to avoid:

- ❌ `import psycopg2` in a route → SQL leaks to presentation layer
- ❌ `conn = psycopg2.connect(...)` without context manager → pool exhaustion
- ❌ `f"SELECT * FROM users WHERE id = {user_id}"` → SQL injection
- ❌ Service returns raw database row dict → should return domain model
- ❌ Hardcoded status strings → use `constants.VideoStatus` enum
- ❌ `socketio.emit()` in worker → publish to Redis instead, let bridge emit

### Testing strategy:

```python
# tests/unit/test_camera_service.py
def test_start_stream_sends_command(mock_repo, mock_consumer):
    service = CameraService(mock_repo, mock_consumer)
    service.start_stream("user123", "cam456")
    mock_consumer.send_command.assert_called_once()

# tests/integration/test_cameras_endpoint.py
def test_create_camera_201(client, auth_token):
    response = client.post(
        '/api/v1/cameras',
        headers={'Authorization': f'Bearer {auth_token}'},
        json={'name': 'Test', 'ip': '192.168.1.1', ...}
    )
    assert response.status_code == 201
```

### Health checks:

- `GET /api/v1/health` — returns system status (200 if all OK, 503 if DB/Redis down)
- Check: PostgreSQL connection, Redis connection, R2 bucket access

### Logging:

All endpoints and workers log via `logging.getLogger(__name__)`
Format: `%(asctime)s [%(name)s] %(levelname)s %(message)s`
Never use `print()` — structured logging only.

---

## Deployment (Railway)

### Environment variables:

```bash
# Required
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
JWT_SECRET_KEY=min-32-random-chars
SECRET_KEY=min-32-random-chars

# Optional (defaults in config.py)
FLASK_ENV=production
CORS_ORIGINS=https://frontend.railway.app
YOLO_MODEL_PATH=storage/models/active/model.pt
```

### Service startup:

```bash
gunicorn -w 2 -k eventlet --worker-connections 1000 \
  --timeout 120 --bind 0.0.0.0:$PORT \
  --access-logfile - --error-logfile - \
  "app:create_app()"
```

**Important**: `eventlet` worker class for SocketIO async mode.

### Migrations run automatically:

`railway_start.py` runs all migrations at startup (idempotent via `IF NOT EXISTS`).

---

## References

- **Swagger UI**: `/api/v1/docs` (if flasgger installed)
- **Health endpoint**: `/api/v1/health`
- **WebSocket namespace**: `/monitor` (for detections), `/training` (for progress)
- **Error codes**: Defined in `core/exceptions.py` with HTTP status mapping
