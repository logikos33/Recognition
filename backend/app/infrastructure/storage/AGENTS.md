# storage/ — Object Storage (R2/Local)

<!-- Parent: ../AGENTS.md -->

**Domain**: File storage abstraction (Strategy pattern) with two implementations:
1. **R2Storage** — Cloudflare R2 (S3-compatible, production)
2. **LocalStorage** — Filesystem (development/fallback)

Handles: training videos, extracted frames, annotated labels, trained models, evidence snapshots.

---

## Quick Facts

- **Pattern**: Strategy (ABC `StorageStrategy` + implementations)
- **Primary**: Cloudflare R2 (S3-compatible via boto3)
- **Fallback**: Local filesystem (development)
- **Key Prefixes**: Defined in `app/constants.py` (R2Prefix enum)
- **Initialization**: `get_storage() -> StorageStrategy` returns configured instance
- **URL Format**: Presigned URLs (15 min for upload, 1 hour for download)
- **No Path Traversal**: LocalStorage validates paths to prevent `../` attacks

---

## Files

### base.py — StorageStrategy (Abstract)

**ABC with 8 abstract methods:**

```python
class StorageStrategy(ABC):
    @abstractmethod
    def generate_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", ttl: int = 900
    ) -> str:
        """Presigned URL for client-side upload PUT request."""
        ...

    @abstractmethod
    def generate_presigned_download_url(self, key: str, ttl: int = 3600) -> str:
        """Presigned URL for client-side download GET request."""
        ...

    @abstractmethod
    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        """Upload bytes from server (e.g., evidence frame)."""
        ...

    @abstractmethod
    def download_bytes(self, key: str) -> bytes:
        """Download bytes to server."""
        ...

    @abstractmethod
    def upload_file(self, key: str, local_path: str) -> None:
        """Upload file from server filesystem."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete object from storage."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if object exists."""
        ...

    @abstractmethod
    def list_keys(self, prefix: str) -> list[str]:
        """List keys with given prefix."""
        ...
```

**Benefits**:
- Swap R2 ↔ LocalStorage without changing service/repository code
- Easy to add S3/GCS/MinIO implementations later
- Dependency Inversion Principle: high-level code depends on interface, not concrete class

---

### r2_storage.py — R2Storage (Cloudflare)

**Class**: `R2Storage(StorageStrategy)`

**Init**:
```python
R2Storage(
    endpoint="https://{account_id}.r2.cloudflarestorage.com",
    bucket="epi-monitor",
    access_key=os.environ["R2_KEY"],
    secret_key=os.environ["R2_SECRET"]
)
```

**Implementation Details**:
- Uses `boto3` with S3 client configured for R2
- `region_name="auto"` (R2 specific, auto-routes requests)
- Endpoint URL required (unlike AWS S3)

**Methods**:

1. **`generate_presigned_upload_url(key, content_type, ttl=900) -> str`**
   - Returns URL for `PUT {key}` with signed headers
   - TTL: 15 minutes default (file upload window)
   - Backend generates URL, client uploads directly without backend proxy

2. **`generate_presigned_download_url(key, ttl=3600) -> str`**
   - Returns URL for `GET {key}` with signed headers
   - TTL: 1 hour default
   - Useful for privacy (URL expires after 1 hour)

3. **`upload_bytes(key, data: bytes, content_type) -> None`**
   - Uploads bytes directly from server
   - Used for: evidence frames (saved during inference), dataset exports
   - Raises `StorageError` on failure

4. **`download_bytes(key) -> bytes`**
   - Downloads bytes to server memory
   - Used for: dataset frame processing, model loading
   - Raises `StorageError` if key not found

5. **`upload_file(key, local_path) -> None`**
   - Uploads file from server filesystem
   - Used for: trained models, dataset exports
   - Raises `StorageError` if file not found

6. **`delete(key) -> None`**
   - Deletes object from R2
   - Used for: cleanup after versioning
   - Silent if key doesn't exist (idempotent)

7. **`exists(key) -> bool`**
   - Returns True if object exists
   - Used for: validation before download

8. **`list_keys(prefix) -> list[str]`**
   - Lists all keys with given prefix
   - Used for: dataset discovery, model inventory
   - Returns empty list if no matches

**Error Handling**:
- All `botocore.exceptions.ClientError` wrapped as `StorageError`
- Errors include: key not found, permissions, network, etc.
- Caller should catch `StorageError` and handle appropriately

---

### local_storage.py — LocalStorage (Filesystem)

**Class**: `LocalStorage(StorageStrategy)`

**Init**:
```python
LocalStorage(base_dir="storage")
# All files stored under ./storage/ (or provided base_dir)
```

**Key Details**:
- Resolves all paths with `os.path.realpath()` to prevent `../` traversal attacks
- `_full_path()` validates that resolved path is within `base_dir`
- Raises `StorageError` if path traversal detected

**Methods** (simplified vs R2):

1. **`generate_presigned_upload_url(key, ...) -> str`**
   - Returns: `/api/storage/upload/{key}`
   - Frontend makes POST to this endpoint, backend handles file storage
   - TTL parameter ignored (local always available)

2. **`generate_presigned_download_url(key, ...) -> str`**
   - Returns: `/api/storage/download/{key}`
   - Frontend makes GET to this endpoint, backend serves file
   - TTL parameter ignored

3. **`upload_bytes(key, data, content_type) -> None`**
   - Writes bytes to `{base_dir}/{key}`
   - Creates directories as needed
   - Raises `StorageError` on permission/disk errors

4. **`download_bytes(key) -> bytes`**
   - Reads bytes from `{base_dir}/{key}`
   - Raises `StorageError` if file not found or unreadable

5. **`upload_file(key, local_path) -> None`**
   - Copies file from `local_path` to `{base_dir}/{key}`
   - Raises `StorageError` if source not found

6. **`delete(key) -> None`**
   - Removes file at `{base_dir}/{key}`
   - Silent if file doesn't exist (idempotent)

7. **`exists(key) -> bool`**
   - Returns True if file exists and is readable

8. **`list_keys(prefix) -> list[str]`**
   - Uses `glob.glob()` to find files matching pattern
   - Returns relative paths from base_dir

**Path Traversal Protection**:
```python
def _full_path(self, key: str) -> str:
    full = os.path.realpath(os.path.join(self._base_dir, key))
    if not full.startswith(self._base_dir + os.sep) and full != self._base_dir:
        raise StorageError("Path traversal detected")
    return full
```

---

### __init__.py — Factory

**Function**: `get_storage() -> StorageStrategy`

Returns configured storage instance based on environment:
```python
def get_storage() -> StorageStrategy:
    if USE_R2:
        return R2Storage(
            endpoint=os.environ["R2_ENDPOINT"],
            bucket=os.environ["R2_BUCKET"],
            access_key=os.environ["R2_KEY"],
            secret_key=os.environ["R2_SECRET"]
        )
    else:
        return LocalStorage(base_dir="storage")
```

**Caching** (optional):
May cache instance as module-level singleton to avoid recreating boto3 client repeatedly.

---

## Key Prefixes (R2Prefix constants)

All storage keys use standardized prefixes defined in `app/constants.py`:

```python
class R2Prefix:
    RAW_VIDEOS = "raw-videos"              # {dataset_id}/{video_id}.mp4
    FRAMES = "frames"                      # {dataset_id}/{frame_id}.jpg
    FRAMES_REJECTED = "frames/rejected"    # {dataset_id}/{frame_id}.jpg (low quality)
    LABELS = "labels"                      # {dataset_id}/{frame_id}.txt (YOLO format)
    DATASETS = "datasets"                  # v{X}.{Y}.{Z}/train|val|test/images|labels/
    MODELS = "models"                      # {run_id}/best.pt
    EVIDENCE = "evidence"                  # {camera_id}/{timestamp_iso}.jpg (alert)
```

**Usage Pattern**:
```python
from app.constants import R2Prefix

key = f"{R2Prefix.FRAMES}/{dataset_id}/{frame_id}.jpg"
storage.upload_bytes(key, jpeg_bytes, "image/jpeg")
```

---

## Usage Patterns

### In a Service Layer

```python
from app.infrastructure.storage import get_storage

class VideoService:
    def upload_training_video(self, user_id: UUID, filename: str) -> str:
        storage = get_storage()
        key = f"{R2Prefix.RAW_VIDEOS}/{user_id}/{filename}"
        url = storage.generate_presigned_upload_url(key, "video/mp4")
        return url  # Frontend uploads directly to this URL
```

### In a Celery Task

```python
from app.infrastructure.storage import get_storage

@celery.task
def extract_frames(video_key: str, video_id: str):
    storage = get_storage()
    
    # Download video
    video_bytes = storage.download_bytes(video_key)
    
    # Extract frame (via FFmpeg, etc.)
    frame_bytes = ...
    
    # Upload frame
    frame_key = f"{R2Prefix.FRAMES}/{video_id}/frame_0000.jpg"
    storage.upload_bytes(frame_key, frame_bytes, "image/jpeg")
```

### In an API Route (evidence saving)

```python
@app.route('/api/v1/alerts/<alert_id>/evidence')
def get_evidence(alert_id: str):
    alert = repo.get_by_id(alert_id)
    
    storage = get_storage()
    evidence_key = f"{R2Prefix.EVIDENCE}/{alert['camera_id']}/{alert['timestamp']}.jpg"
    
    # For R2: return presigned download URL
    url = storage.generate_presigned_download_url(evidence_key)
    return jsonify({"evidence_url": url})
```

---

## Environment Variables

### R2 Configuration
```bash
# Enable R2 (if all 4 vars present)
R2_ENDPOINT=https://{account_id}.r2.cloudflarestorage.com
R2_BUCKET=epi-monitor
R2_KEY=your-access-key
R2_SECRET=your-secret-key

# Falls back to LocalStorage if any missing
```

### Local Configuration
```bash
# Optional: override base directory
STORAGE_BASE_DIR=/var/lib/epi-monitor/storage

# Falls back to "storage/" in working directory if not set
```

---

## Error Handling

All storage operations raise `StorageError` on failure:

```python
from app.core.exceptions import StorageError

try:
    url = storage.generate_presigned_upload_url(key)
except StorageError as exc:
    logger.error("presigned_url_failed", key=key, error=str(exc))
    return error_response(f"Failed to generate upload URL: {exc}", 500)
```

**Don't catch exceptions in tasks** — let them propagate so Celery retries with exponential backoff.

---

## Testing

### Unit Tests (mock storage)

```python
@patch('app.infrastructure.storage.get_storage')
def test_video_service_upload(mock_storage):
    mock_storage.return_value.generate_presigned_upload_url.return_value = "https://..."
    
    service = VideoService()
    url = service.upload_training_video(user_id, "test.mp4")
    
    assert url.startswith("https://")
    mock_storage.return_value.generate_presigned_upload_url.assert_called_once()
```

### Integration Tests (real R2 or LocalStorage)

```python
@pytest.fixture
def storage():
    # Use LocalStorage for tests (temporary directory)
    return LocalStorage(base_dir=tmp_dir)

def test_upload_download(storage):
    key = "test/file.txt"
    data = b"hello world"
    
    storage.upload_bytes(key, data, "text/plain")
    retrieved = storage.download_bytes(key)
    
    assert retrieved == data
```

---

## Migration from LocalStorage to R2

1. **No code changes needed** — interface is identical
2. Set R2 environment variables
3. `get_storage()` automatically returns R2Storage
4. Existing local files are NOT migrated (start fresh or migrate manually)

**Manual migration**:
```python
local = LocalStorage()
r2 = R2Storage(...)

for key in local.list_keys(""):
    data = local.download_bytes(key)
    r2.upload_bytes(key, data, "application/octet-stream")
```

---

## Performance Considerations

### R2
- **Upload speed**: 5-50 MB/s (R2 → CloudFlare edge)
- **Download speed**: 5-50 MB/s (CloudFlare edge → client)
- **Cost**: $0.015/GB stored, $0.015/GB downloaded (cheap!)
- **Latency**: ~50-200ms (varies by region)

### LocalStorage
- **Upload speed**: Limited by disk I/O (100+ MB/s on SSD)
- **Download speed**: Limited by disk I/O
- **Cost**: $0 (uses server disk)
- **Latency**: <5ms (local filesystem)

**Recommendation**:
- Dev: LocalStorage (faster iterations, no credentials)
- Prod: R2 (scalable, cheap, managed)

---

## Related Documentation

- Parent: `/backend/app/infrastructure/AGENTS.md` — infrastructure overview
- Sibling: `/backend/app/infrastructure/database/AGENTS.md` — data persistence
- Sibling: `/backend/app/infrastructure/queue/AGENTS.md` — async tasks using storage
- Constants: `/backend/app/constants.py` — R2Prefix enum
- Guides: `/CLAUDE.md` — storage patterns and Cloudflare R2 config
