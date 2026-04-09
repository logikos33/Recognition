# database/ — Database Connection Pool & Repositories

<!-- Parent: ../AGENTS.md -->

**Domain**: All database access for EPI Monitor V2. Provides connection pooling, transaction management, and SQL query isolation.

---

## Quick Facts

- **Connection Pool**: `DatabasePool` singleton wrapping `psycopg2.pool.ThreadedConnectionPool`
- **Cursor Factory**: `RealDictCursor` (dict-like row access, not tuples)
- **Initialization**: Called once in `app/__init__.py` via `DatabasePool.initialize(db_url)`
- **Usage**: Always `with pool.get_connection() as conn:` context manager
- **Isolation**: NO SQL outside repositories — absolute rule (enforced via code review)
- **Transaction**: Auto-commit on success, auto-rollback on error

---

## Files

### connection.py — DatabasePool

**Class**: `DatabasePool` (Singleton)

**Key Methods**:
- `DatabasePool.initialize(database_url, min_conn=1, max_conn=10) -> DatabasePool`
  - Called once during app startup
  - Returns singleton instance
  - Raises `DatabaseError` if pool creation fails

- `get_instance() -> Optional[DatabasePool]`
  - Returns current singleton or None if not initialized

- `get_connection() -> contextmanager[psycopg2.connection]`
  - Returns context manager that yields a connection
  - Auto-commits on success
  - Auto-rollbacks on exception
  - Always returns connection to pool in finally block

- `close_all() -> None`
  - Closes all pooled connections
  - Called during Flask app shutdown

**Key Details**:
- Uses `psycopg2.pool.ThreadedConnectionPool` for thread-safe connection reuse
- Pool is NOT thread-local — connections are returned to shared pool
- `RealDictCursor` hardcoded as cursor factory (no tuples!)
- `DATABASE_URL` auto-corrected: `postgres://` → `postgresql://` (Railway compatibility)

**Error Handling**:
- `psycopg2.Error` wrapped as `DatabaseError` with message
- Connection is rollback'd and returned to pool even on error
- All errors logged with structured logging

---

### base.py — BaseRepository

**Class**: `BaseRepository` (Abstract)

All repositories extend this. Injects `DatabasePool` via `__init__`.

**Methods** (all handle transaction/error automatically):

- `_execute(query: str, params: tuple) -> list[dict]`
  - SELECT queries
  - Returns list of dict rows (empty list if no rows)
  - Uses `RealDictCursor`

- `_execute_one(query: str, params: tuple) -> Optional[dict]`
  - SELECT queries returning single row
  - Returns dict or None

- `_execute_mutation(query: str, params: tuple) -> Optional[dict]`
  - INSERT/UPDATE/DELETE with RETURNING clause
  - Returns dict of returned row or None
  - Commits transaction within `get_connection()`

- `_execute_mutation_no_return(query: str, params: tuple) -> int`
  - INSERT/UPDATE/DELETE without RETURNING
  - Returns rowcount (>0 if succeeded)

- `_execute_many(query: str, params_list: list[tuple]) -> int`
  - Bulk INSERT/UPDATE/DELETE via `executemany()`
  - Returns total rowcount
  - Single transaction for all rows

---

### repositories/ — Concrete Repositories

Each entity has a repository. All extend `BaseRepository`.

**Repositories** (11 total):
- `UserRepository` — users table (auth, roles)
- `CameraRepository` — ip_cameras table (RTSP streaming)
- `VideoRepository` — videos table (upload + extraction)
- `FrameRepository` — dataset_frames table (quality filter + training)
- `AnnotationRepository` — annotations table (bounding boxes)
- `DatasetRepository` — datasets table (dataset versioning)
- `TrainingRepository` — training_runs table (YOLO training)
- `AlertRepository` — alerts table (rule violations + evidence)
- `ModuleRepository` — modules table (multi-tenant)

**Pattern** (all repositories follow):
```python
class XyzRepository(BaseRepository):
    def create(self, **kwargs) -> dict:
        return self._execute_mutation(
            "INSERT INTO xyz (...) VALUES (...) RETURNING *",
            (param1, param2, ...)
        )
    
    def get_by_id(self, xyz_id: UUID) -> Optional[dict]:
        return self._execute_one(
            "SELECT * FROM xyz WHERE id = %s",
            (str(xyz_id),)
        )
    
    def list_by_user(self, user_id: UUID) -> list[dict]:
        return self._execute(
            "SELECT * FROM xyz WHERE user_id = %s",
            (str(user_id),)
        )
```

**Key Rules**:
- All IDs converted to string: `str(uuid_object)` (PostgreSQL accepts string UUIDs)
- All params passed as tuple, never f-string or % formatting
- SELECT without WHERE should have ORDER BY
- Password fields (camera credentials) only returned in methods that explicitly need them

---

### migrations/ — Schema Management

**Structure**:
- `001_initial_schema.sql` through `011_active_learning.sql`
- Each migration is idempotent (safe to run multiple times)
- Tracked in PostgreSQL `schema_migrations` table

**Migrations Applied**:
1. Initial users, datasets, videos, frames, annotations
2. IP cameras (RTSP streaming)
3. Training runs (YOLO training)
4. Camera alerts + alert rules (rule engine)
5. Multi-tenant support
6. Alert rules + templates
7. Camera model variants (Hikvision, Intelbras, Generic)
8. Tenant modules (multi-module per tenant)
9. Module classification (per-module EPI classes)
10. Module code generation
11. Active learning (recommendation engine)

**Migration Runner** (run_migrations.py):
- Called on Railway app startup (before HTTP server starts)
- Checks `schema_migrations` before applying each SQL file
- Idempotent: skips if version already exists
- Exits with code 1 on failure (Railway deployment fails)

**Usage**:
```bash
# Local (after database is set up):
python -m backend.app.infrastructure.database.migrations.run_migrations

# Railway: automatic via nixpacks.toml (runs before gunicorn start)
```

---

## Usage Patterns

### In a Service (domain/)

```python
from app.infrastructure.database.repositories.video_repository import VideoRepository

class VideoService:
    def __init__(self, db_pool: DatabasePool):
        self._repo = VideoRepository(db_pool)
    
    def get_video(self, video_id: UUID) -> Video:
        row = self._repo.get_by_id(video_id)
        if not row:
            raise VideoNotFound()
        return Video(**row)
```

### In a Route (api/v1/)

```python
from flask import request, jsonify
from app.infrastructure.database.connection import DatabasePool
from app.domain.services.video_service import VideoService

@app.route('/api/v1/videos/<video_id>')
def get_video(video_id: str):
    pool = DatabasePool.get_instance()
    service = VideoService(pool)
    video = service.get_video(UUID(video_id))
    return jsonify(video.to_dict())
```

### In a Celery Task (queue/tasks/)

```python
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.frame_repository import FrameRepository

@celery.task
def extract_frames(video_key: str, video_id: str):
    pool = DatabasePool.get_instance()
    if not pool:
        raise RuntimeError("DatabasePool not initialized")
    
    repo = FrameRepository(pool)
    repo.create(video_id=video_id, ...)
```

---

## Common Errors & Fixes

**Error: "column 'X' does not exist"**
- Cause: Schema hasn't been migrated
- Fix: Run `run_migrations.py`, verify migrations/\*.sql applied

**Error: "too many connections"**
- Cause: Connections not being returned to pool
- Fix: Check for missing `with get_connection()` — connections must use context manager

**Error: "psycopg2.pool.PoolError: connection pool is closed"**
- Cause: `DatabasePool.close_all()` called, but code still tries to access
- Fix: Only call `close_all()` during app shutdown; don't use pool after

**Error: "tuple object is not subscriptable"**
- Cause: Using `row[0]` instead of `row['column_name']`
- Fix: Pool is configured with `RealDictCursor`, so use dict access

---

## When to Add a New Repository

1. New entity (table) is created in a migration
2. Service needs CRUD for that entity
3. Create `repositories/xyz_repository.py` extending `BaseRepository`
4. Add methods for all queries (not just CRUD — include common filters)
5. Add unit tests in `tests/unit/infrastructure/database/`
6. Update `repositories/__init__.py` with export

---

## Database URL Format

**Local**:
```bash
postgresql://postgres:password@localhost:5432/epi_monitor
```

**Railway Plugin**:
```bash
# Auto-injected by Railway as DATABASE_URL env var
postgresql://user:pass@pg-xxxxx.railway.app:5432/railway
```

**Correction** (automatic in `connection.py`):
- Railway sometimes sends `postgres://` (old format)
- Automatically corrected to `postgresql://` (psycopg2 requirement)

---

## Testing Database Layer

**Unit Tests** (mock DatabasePool):
```python
def test_user_create():
    mock_pool = Mock(spec=DatabasePool)
    repo = UserRepository(mock_pool)
    # Mock _execute_mutation response
    repo._execute_mutation = Mock(return_value={'id': 'uuid', 'email': 'test@example.com'})
    result = repo.create(email='test@example.com', ...)
    assert result['email'] == 'test@example.com'
```

**Integration Tests** (real PostgreSQL):
```python
# Uses test database (TEST_DATABASE_URL env var)
@pytest.fixture
def db_pool():
    pool = DatabasePool.initialize(os.environ['TEST_DATABASE_URL'])
    yield pool
    pool.close_all()

def test_user_create_integration(db_pool):
    repo = UserRepository(db_pool)
    result = repo.create(email='test@example.com', ...)
    assert result['email'] == 'test@example.com'
    # Cleanup
    repo.delete_by_email('test@example.com')
```

---

## Related Documentation

- Parent: `/backend/app/infrastructure/AGENTS.md` — infrastructure overview
- Sibling: `/backend/app/infrastructure/queue/AGENTS.md` — async task processing
- Sibling: `/backend/app/infrastructure/storage/AGENTS.md` — file storage (R2/local)
- Guides: `/CLAUDE.md` — database patterns and absolute rules
