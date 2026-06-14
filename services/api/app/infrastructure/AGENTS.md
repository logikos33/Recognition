# backend/app/infrastructure/AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Overview

The `infrastructure/` directory contains implementations of domain abstractions: database access (repositories), async task processing (Celery), and file storage (R2/local).

**Key Principle**: All SQL is isolated here. No SQL outside `database/repositories/`. Services depend on abstractions, not implementations.

---

## Directory Structure

```
infrastructure/
├── database/
│   ├── connection.py           # ThreadedConnectionPool singleton
│   ├── migrations/
│   │   └── run_migrations.py   # Migration runner (001_, 002_, ...)
│   └── repositories/           # SQL isolated here
│       ├── base.py             # Abstract base with common SQL methods
│       ├── user_repository.py
│       ├── camera_repository.py
│       ├── video_repository.py
│       ├── frame_repository.py
│       ├── annotation_repository.py
│       ├── dataset_repository.py
│       ├── training_repository.py
│       ├── alert_repository.py
│       └── module_repository.py
├── queue/
│   ├── celery_app.py           # Celery factory + config
│   └── tasks/
│       ├── extraction.py       # extract_frames
│       ├── quality.py          # quality_filter
│       ├── versioning.py       # build_dataset_version
│       ├── training.py         # dispatch_training
│       └── inference.py        # inference_loop, start_hls_stream
└── storage/
    ├── base.py                 # StorageStrategy (abstract)
    ├── r2_storage.py           # R2 implementation (boto3)
    └── local_storage.py        # Local filesystem (dev/testing)
```

---

## Database Layer

### connection.py — Connection Pool (Singleton)

**Purpose**: Centralized PostgreSQL connection management with `ThreadedConnectionPool`.

**Key Rule**: Use context manager `with pool.get_connection()` — NEVER create connections outside this layer.

```python
# database/connection.py
import psycopg2.pool
from app.core.exceptions import DatabaseError

class DatabasePool:
    """Singleton ThreadedConnectionPool for psycopg2."""
    _instance: Optional["DatabasePool"] = None

    @staticmethod
    def initialize(database_url: str) -> "DatabasePool":
        """Create singleton instance."""
        if DatabasePool._instance is None:
            DatabasePool._instance = DatabasePool(database_url)
        return DatabasePool._instance

    @staticmethod
    def get_instance() -> Optional["DatabasePool"]:
        """Get existing instance."""
        return DatabasePool._instance

    def __init__(self, database_url: str, min_conn: int = 1, max_conn: int = 10):
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=min_conn,
            maxconn=max_conn,
            dsn=database_url,
            cursor_factory=psycopg2.extras.RealDictCursor,  # ← Returns dicts, not tuples
        )

    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Context manager for connection."""
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)
```

**Usage**:

```python
# CORRECT — always use context manager
with database_pool.get_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()

# WRONG — never do this
conn = database_pool.get_connection()  # Conn stays open = leak
user = conn.execute("SELECT ...")
```

**Initialization** (in `app/__init__.py`):

```python
def create_app(config_name: str = "development") -> Flask:
    app = Flask(__name__)
    
    # Initialize database pool
    database_url = os.environ.get("DATABASE_URL")
    DatabasePool.initialize(database_url)
    
    return app
```

---

### repositories/base.py — Abstract Base Repository

All repositories inherit from `BaseRepository` which provides common SQL execution methods.

```python
# infrastructure/database/repositories/base.py
from abc import ABC
from app.infrastructure.database.connection import DatabasePool

class BaseRepository(ABC):
    """Abstract base for all repositories."""

    def __init__(self, db_pool: DatabasePool) -> None:
        self._db = db_pool

    def _execute(
        self, query: str, params: tuple = ()
    ) -> list[dict[str, Any]]:
        """Execute SELECT, return list of dicts."""
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def _execute_one(
        self, query: str, params: tuple = ()
    ) -> Optional[dict[str, Any]]:
        """Execute SELECT, return one dict or None."""
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _execute_mutation(
        self, query: str, params: tuple = ()
    ) -> Optional[dict[str, Any]]:
        """Execute INSERT/UPDATE/DELETE with RETURNING, commit, return dict."""
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
```

### repositories/{entity}_repository.py — Concrete Repositories

Each entity has one repository with CRUD operations and custom queries.

**Example: UserRepository**

```python
# infrastructure/database/repositories/user_repository.py
from uuid import UUID
from app.infrastructure.database.repositories.base import BaseRepository

class UserRepository(BaseRepository):
    """User data access."""

    def create(
        self, email: str, password_hash: str, name: str
    ) -> dict[str, Any]:
        """Create user."""
        query = """
            INSERT INTO users (id, email, password_hash, name, role, is_active, created_at, updated_at)
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                NOW(),
                NOW()
            )
            RETURNING *
        """
        user_id = uuid.uuid4()
        return self._execute_mutation(
            query,
            (user_id, email, password_hash, name, UserRole.USER.value, True),
        )

    def get_by_id(self, user_id: UUID) -> Optional[dict[str, Any]]:
        """Get user by ID."""
        query = "SELECT * FROM users WHERE id = %s"
        return self._execute_one(query, (user_id,))

    def get_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Get user by email."""
        query = "SELECT * FROM users WHERE email = %s"
        return self._execute_one(query, (email,))

    def exists_by_email(self, email: str) -> bool:
        """Check if email exists."""
        result = self.get_by_email(email)
        return result is not None

    def update(self, user_id: UUID, **kwargs) -> dict[str, Any]:
        """Update user fields."""
        allowed_fields = {"name", "is_active", "password_hash"}
        fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not fields:
            return self.get_by_id(user_id)
        
        set_clause = ", ".join(f"{k} = %s" for k in fields.keys())
        values = list(fields.values()) + [user_id]
        
        query = f"""
            UPDATE users
            SET {set_clause}, updated_at = NOW()
            WHERE id = %s
            RETURNING *
        """
        return self._execute_mutation(query, tuple(values))

    def delete(self, user_id: UUID) -> None:
        """Delete user."""
        query = "DELETE FROM users WHERE id = %s"
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (user_id,))
            conn.commit()
```

**Example: CameraRepository (with Encryption)**

```python
# infrastructure/database/repositories/camera_repository.py
from cryptography.fernet import Fernet
import os

class CameraRepository(BaseRepository):
    """Camera data access (passwords encrypted)."""

    def __init__(self, db_pool: DatabasePool) -> None:
        super().__init__(db_pool)
        cipher_key = os.environ.get("CAMERA_SECRET_KEY").encode()
        self._cipher = Fernet(cipher_key)

    def create(
        self,
        user_id: UUID,
        name: str,
        ip: str,
        port: int,
        username: str,
        password: str,
        rtsp_url: str,
        channel: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create camera with encrypted password."""
        password_encrypted = self._cipher.encrypt(password.encode()).decode()
        
        query = """
            INSERT INTO cameras (id, user_id, name, ip, port, username, password_encrypted, rtsp_url, channel, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING *
        """
        camera_id = uuid.uuid4()
        result = self._execute_mutation(
            query,
            (camera_id, user_id, name, ip, port, username, password_encrypted, rtsp_url, channel, True),
        )
        # Mask password in response
        if result:
            result.pop("password_encrypted", None)
        return result

    def get_by_id(self, camera_id: UUID) -> Optional[dict[str, Any]]:
        """Get camera (password masked)."""
        query = """
            SELECT id, user_id, name, ip, port, username, rtsp_url, channel, is_active, created_at, updated_at
            FROM cameras
            WHERE id = %s
        """
        return self._execute_one(query, (camera_id,))

    def get_by_id_with_password(self, camera_id: UUID) -> Optional[dict[str, Any]]:
        """Get camera WITH decrypted password (internal only)."""
        query = "SELECT * FROM cameras WHERE id = %s"
        result = self._execute_one(query, (camera_id,))
        
        if result and result.get("password_encrypted"):
            encrypted = result.pop("password_encrypted")
            result["password"] = self._cipher.decrypt(encrypted.encode()).decode()
        
        return result
```

### SQL Rules for Repositories

1. **Use parameterized queries** — Always `%s` placeholders, never f-strings
2. **Use RealDictCursor** — Returns dicts, not tuples
3. **Include `updated_at`** — Every UPDATE should set `updated_at = NOW()`
4. **Return dicts from mutations** — Use `RETURNING *`
5. **One query per method** — No complex SQL spanning multiple statements
6. **Error wrapping** — Catch `psycopg2.Error` and raise `DatabaseError`

---

## Queue Layer (Celery)

### celery_app.py — Celery Factory and Configuration

```python
# infrastructure/queue/celery_app.py
from celery import Celery
import os

def make_celery() -> Celery:
    """Create Celery instance with Redis broker."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    
    celery = Celery("epi_monitor", broker=redis_url, backend=redis_url)
    
    celery.conf.update(
        # Serialization
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # Reliability
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        # Task routing to queues
        task_routes={
            "app.infrastructure.queue.tasks.extraction.*": {"queue": "extraction"},
            "app.infrastructure.queue.tasks.quality.*": {"queue": "extraction"},
            "app.infrastructure.queue.tasks.versioning.*": {"queue": "versioning"},
            "app.infrastructure.queue.tasks.training.*": {"queue": "training"},
            "app.infrastructure.queue.tasks.inference.*": {"queue": "inference"},
        },
    )
    
    return celery

celery = make_celery()
```

**Initialization** (in `app/__init__.py`):

```python
from app.infrastructure.queue.celery_app import make_celery

def create_app():
    app = Flask(__name__)
    app.celery = make_celery()
    return app
```

### tasks/*.py — Async Tasks

Each task module represents a queue domain.

**Example: extraction.py**

```python
# infrastructure/queue/tasks/extraction.py
from app.infrastructure.queue.celery_app import celery
from app.infrastructure.database.connection import DatabasePool
import logging

logger = logging.getLogger(__name__)

@celery.task(bind=True, max_retries=3, queue="extraction")
def extract_frames(self, video_key: str, video_id: str, dataset_id: str):
    """Extract frames from video using FFmpeg."""
    try:
        logger.info("extraction_started", video_id=video_id)
        
        # Get video from R2
        storage = get_storage()
        video_bytes = storage.download_bytes(video_key)
        
        # Extract frames
        frames = extract_with_ffmpeg(video_bytes)
        
        # Save frames to R2
        for i, frame_data in enumerate(frames):
            key = f"frames/{dataset_id}/frame_{i}.jpg"
            storage.upload_bytes(key, frame_data, "image/jpeg")
        
        # Update video status
        with DatabasePool.get_instance().get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE videos SET status = %s, frame_count = %s WHERE id = %s",
                ("extracted", len(frames), video_id),
            )
            conn.commit()
        
        logger.info("extraction_complete", video_id=video_id, frame_count=len(frames))
        return {"status": "success", "frame_count": len(frames)}
        
    except Exception as exc:
        logger.error("extraction_failed", video_id=video_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
```

**Task Rules**:

1. **Bind=True** — Access retry context
2. **Max Retries** — Set appropriate limit
3. **Queue** — Route to correct queue
4. **Logging** — Structured logs at start, end, error
5. **Error Handling** — Catch, log, retry with backoff
6. **Status Updates** — Write results back to database

---

## Storage Layer

### base.py — StorageStrategy (Abstract)

```python
# infrastructure/storage/base.py
from abc import ABC, abstractmethod

class StorageStrategy(ABC):
    """Interface for object storage (R2, S3, local)."""

    @abstractmethod
    def generate_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", ttl: int = 900
    ) -> str:
        """Generate URL for client-side direct upload."""
        ...

    @abstractmethod
    def generate_presigned_download_url(self, key: str, ttl: int = 3600) -> str:
        """Generate URL for client-side direct download."""
        ...

    @abstractmethod
    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        """Server-side upload."""
        ...

    @abstractmethod
    def download_bytes(self, key: str) -> bytes:
        """Server-side download."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete object."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if object exists."""
        ...
```

### r2_storage.py — R2 Implementation (Production)

```python
# infrastructure/storage/r2_storage.py
import boto3
import os
from app.infrastructure.storage.base import StorageStrategy
from app.core.exceptions import StorageError

class R2Storage(StorageStrategy):
    """Cloudflare R2 storage (S3-compatible)."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("R2_ENDPOINT"),
            aws_access_key_id=os.environ.get("R2_KEY"),
            aws_secret_access_key=os.environ.get("R2_SECRET"),
            region_name="auto",
        )
        self._bucket = os.environ.get("R2_BUCKET", "epi-monitor")

    def generate_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", ttl: int = 900
    ) -> str:
        """Generate presigned upload URL."""
        try:
            url = self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=ttl,
            )
            return url
        except Exception as exc:
            raise StorageError(f"Presigned URL generation failed: {str(exc)}")

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        """Upload bytes to R2."""
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except Exception as exc:
            raise StorageError(f"Upload failed: {str(exc)}")

    def download_bytes(self, key: str) -> bytes:
        """Download bytes from R2."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise StorageError(f"Download failed: {str(exc)}")
```

### local_storage.py — Local Storage (Development)

```python
# infrastructure/storage/local_storage.py
import os
from pathlib import Path
from app.infrastructure.storage.base import StorageStrategy
from app.core.exceptions import StorageError

class LocalStorage(StorageStrategy):
    """Local filesystem storage (dev/testing)."""

    def __init__(self, base_path: str = "/tmp/epi-storage") -> None:
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _get_path(self, key: str) -> Path:
        """Safe path resolution (prevent path traversal)."""
        full_path = (self._base_path / key).resolve()
        if not str(full_path).startswith(str(self._base_path)):
            raise StorageError("Path traversal detected")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        return full_path

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        """Write bytes to file."""
        try:
            path = self._get_path(key)
            path.write_bytes(data)
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"Upload failed: {str(exc)}")

    def download_bytes(self, key: str) -> bytes:
        """Read bytes from file."""
        try:
            path = self._get_path(key)
            if not path.exists():
                raise StorageError(f"File not found: {key}")
            return path.read_bytes()
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"Download failed: {str(exc)}")

    def generate_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", ttl: int = 900
    ) -> str:
        """Return local file path (no actual presigned URL)."""
        return f"/storage/upload/{key}"

    def generate_presigned_download_url(self, key: str, ttl: int = 3600) -> str:
        """Return local file path."""
        return f"/storage/download/{key}"
```

---

## Dependency Injection Pattern

Services receive infrastructure implementations via constructor:

```python
# In api/v1/{domain}/routes.py
from app.infrastructure.storage.r2_storage import R2Storage

def _get_service() -> VideoService:
    """Factory: inject dependencies."""
    pool = DatabasePool.get_instance()
    storage = R2Storage()
    celery = celery_app
    
    return VideoService(
        video_repo=VideoRepository(pool),
        storage=storage,
        celery=celery,
    )

@bp.route("/videos", methods=["POST"])
@jwt_required
def upload_video():
    service = _get_service()
    presigned_url, video_id = service.upload_video(...)
    return success({"presigned_url": presigned_url, "video_id": str(video_id)})
```

---

## Migration Runner

```python
# infrastructure/database/migrations/run_migrations.py
import os
from pathlib import Path
import psycopg2

def run_migrations(database_url: str) -> None:
    """Run all numbered SQL migrations (001_, 002_, ...)."""
    migrations_dir = Path(__file__).parent
    migrations = sorted(migrations_dir.glob("*.sql"))
    
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            for migration_file in migrations:
                sql = migration_file.read_text()
                cur.execute(sql)
            conn.commit()
```

**Call in startup**:

```python
# app/__init__.py
def create_app():
    # ... setup ...
    from app.infrastructure.database.migrations.run_migrations import run_migrations
    run_migrations(os.environ.get("DATABASE_URL"))
    return app
```

---

## Related Documentation

- **Database**: `database/` — repositories with SQL
- **Queue**: `queue/` — async tasks
- **Storage**: `storage/` — file operations
- **Domain Services**: `../domain/services/` — use these repositories
