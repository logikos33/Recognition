# queue/ — Celery Task Queue

<!-- Parent: ../AGENTS.md -->

**Domain**: Asynchronous task processing for long-running operations (frame extraction, YOLO training, HLS streaming). Runs on separate Worker service (can be separate Railway service or same container with `SERVICE_TYPE=worker`).

---

## Quick Facts

- **Broker & Backend**: Redis (same instance)
- **Task Serialization**: JSON
- **Execution Model**: Long-running tasks (5 min to 2 hours)
- **Queues**: 5 separate queues by priority/type
- **Task Routes**: Defined in `celery_app.py` (auto-routes tasks to correct queue)
- **Reliability**: `acks_late=True` (ACK only after task completes)
- **Concurrency**: Flask API (2 workers) + Celery (2-4 workers concurrency)
- **Entry Point**: `celery -A app.infrastructure.queue.celery_app:celery worker`

---

## Files

### celery_app.py — Celery Factory

**Function**: `make_celery(app=None) -> Celery`

- Creates Celery instance connected to Redis
- Takes optional Flask app for context integration
- Returns configured `celery` singleton

**Configuration**:
```python
celery = Celery("epi_monitor", broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(
    task_serializer="json",           # All tasks JSON
    result_serializer="json",         # Results JSON
    accept_content=["json"],          # Only accept JSON
    task_track_started=True,          # Track task start/completion
    task_acks_late=True,              # ACK after task completes (reliable)
    worker_prefetch_multiplier=1,     # Don't prefetch (low RAM workers)
    worker_max_tasks_per_child=100,   # Restart worker every 100 tasks (memory leak prevention)
    timezone="UTC",
    enable_utc=True,
    task_routes={...}                 # Route tasks to specific queues
)
```

**Task Routes** (auto-routing):
```
extraction.* → extraction queue
quality.* → extraction queue (grouped for efficiency)
versioning.* → versioning queue
training.* → training queue
inference.* → inference queue
```

**Flask Integration**:
If Flask app provided, wraps all tasks with `app.app_context()` so they can access Flask context (config, logger, g object).

**Standalone Usage**:
```python
# In worker process (no Flask app)
from app.infrastructure.queue.celery_app import celery

@celery.task
def my_task():
    pass
```

---

### tasks/ — Celery Tasks

Five task modules, each with domain-specific tasks.

#### extraction.py — Frame Extraction

**Queue**: `extraction` (high priority, short-lived)

**Main Task**: `extract_frames(video_key, video_id, user_id, scene_threshold=0.3)`

- Downloads video from R2/local storage to `/tmp/`
- Runs FFmpeg with scene detection: `-vf "select='gt(scene,0.3)',setpts=N/FRAMERATE/TB'"`
- Extracts JPEGs to `/tmp/frames_{video_id}/`
- Uploads each frame to R2 (key: `frames/{user_id}/{video_id}/frame_{0000}.jpg`)
- Creates database records via `FrameRepository`
- Dispatches `quality_filter` task for each frame
- Updates video status to `'extracted'`
- Cleans up `/tmp/` directory

**Error Handling**:
- Max retries: 3 (exponential backoff 30 * (retries + 1) seconds)
- Failures logged with video_id, user_id, error message
- Database records created only for successfully extracted frames

#### quality.py — Frame Quality Filtering

**Queue**: `extraction` (same queue as extraction, runs after)

**Tasks**:
- `quality_filter(frame_id, frame_key)` — Score frame for blurriness, brightness, contrast
  - Returns scores for use in training dataset selection
  - Flagged frames (low quality) marked with status `'rejected'`

#### versioning.py — Dataset Versioning

**Queue**: `versioning` (medium priority, can be slower)

**Main Task**: `build_dataset_version(dataset_id, version_string)`

- Collects all approved frames from dataset
- Splits into train/val/test (80/10/10)
- Downloads frames from R2 to `/tmp/dataset_v{X}.{Y}.{Z}/`
- Generates `dataset.yaml` (YOLOv8 format)
- Organizes into YOLOv8 directory structure:
  ```
  dataset_v1.0.0/
  ├── images/
  │   ├── train/
  │   └── val/
  └── labels/
      ├── train/
      └── val/
  ```
- Uploads entire version to R2 (`datasets/v{X}.{Y}.{Z}/`)
- Saves metadata JSON with frame count, class distribution

#### training.py — YOLO Model Training

**Queue**: `training` (low priority, very long-lived)

**Main Task**: `dispatch_training(dataset_id, version, epochs=50, device='gpu')`

- (Currently stub) Will dispatch to external Vast.ai GPU or Runpod
- Trains YOLOv8 on provided dataset version
- Saves trained model to R2 (`models/{run_id}/best.pt`)
- Tracks metrics (mAP, precision, recall) per epoch

#### inference.py — YOLO Real-time Detection + HLS Streaming

**Queue**: `inference` (critical, continuous)

**Main Tasks**:

1. **`start_hls_stream(camera_id, rtsp_url)`** — FFmpeg HLS transcoding
   - Spawns FFmpeg subprocess:
     ```bash
     ffmpeg -i {rtsp_url} \
       -f hls \
       -hls_time 1 \
       -hls_list_size 3 \
       -hls_flags delete_segments \
       -preset ultrafast \
       {output_dir}/stream.m3u8
     ```
   - HLS files stored in `streams/{camera_id}/`
   - Segments auto-deleted after 3 (keeps 3 seconds buffer)
   - Health monitoring: checks process alive every 30s

2. **`inference_loop(camera_id, rtsp_url, model_path='yolov8n.pt', fps=5)`** — Continuous YOLO detection
   - Opens RTSP stream via OpenCV
   - Runs YOLO inference every 200ms (5 FPS default)
   - Publishes detections via Redis pub/sub: `epi:det:{camera_id}`
   - Payload:
     ```json
     {
       "camera_id": "uuid",
       "timestamp": "2026-04-08T15:30:45.123Z",
       "detections": [
         {"class": "helmet", "confidence": 0.95, "bbox": [x, y, w, h]},
         ...
       ]
     }
     ```
   - Flask-SocketIO listener receives pub/sub and emits to WebSocket clients
   - Graceful shutdown: Checks Redis key `epi:stream:{camera_id}:active`
   - Falls back: If ultralytics not installed, returns `{"status": "skipped"}` instead of crashing

**CRITICAL**: `inference_loop` is FALLBACK when camera-gateway/inference-service not available. Long-term, move to dedicated service. Currently kept in main Celery for rapid iteration.

---

## Key Design Patterns

### Task Naming Convention
```
app.infrastructure.queue.tasks.{module}.{function}
# Auto-routes to queue via task_routes config
```

### Error Handling in Tasks
```python
@celery.task(bind=True, max_retries=3)
def my_task(self, param1, param2):
    try:
        # work
        return {"status": "success", "data": ...}
    except SomeError as exc:
        logger.error("task_failed", task_name=self.name, error=str(exc))
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
```

### Database Access in Tasks
```python
from app.infrastructure.database.connection import DatabasePool

@celery.task
def my_task(video_id):
    pool = DatabasePool.get_instance()
    if not pool:
        raise RuntimeError("DatabasePool not initialized")
    
    repo = VideoRepository(pool)
    video = repo.get_by_id(video_id)
```

### Redis Pub/Sub for Long-running Operations
```python
import redis

r = redis.from_url(os.environ['REDIS_URL'], decode_responses=True)

# Publish detection (inference_loop)
r.publish(f"epi:det:{camera_id}", json.dumps(detection_payload))

# Subscribe (Flask route)
pubsub = r.pubsub()
pubsub.subscribe(f"epi:det:{camera_id}")
# Emit to WebSocket when message arrives
```

---

## Queue Priorities & Scale

| Queue | Priority | Use Case | Workers | Max Runtime |
|-------|----------|----------|---------|------------|
| `inference` | Critical | YOLO 24/7 | 2-4 | N/A (continuous) |
| `extraction` | High | Extract frames + quality score | 2 | 5 min |
| `versioning` | Medium | Build dataset versions | 1 | 10 min |
| `training` | Low | YOLO training (dispatched to Vast.ai) | 1 | 2-4 hours |

---

## Deployment (Railway)

**Separate Worker Service** (optional, recommended for scale):
```bash
# service: worker
celery -A app.infrastructure.queue.celery_app:celery worker \
  --loglevel=info \
  --concurrency=4 \
  --max-tasks-per-child=100
```

**Environment Variables** (inherited from API service):
- `REDIS_URL` — Redis broker/backend
- `DATABASE_URL` — PostgreSQL connection
- `SERVICE_TYPE=worker` — Identifies this as worker (optional, for logging)

**Health Check**:
- Celery worker reports to Redis every heartbeat (~2s)
- Railway can monitor Redis keys for dead workers (via Redis plugin)

---

## Monitoring & Debugging

### View Active Tasks
```bash
celery -A app.infrastructure.queue.celery_app:celery inspect active

# Output:
# {
#   'celery@worker1': [
#     {'id': 'task-uuid', 'name': 'tasks.inference.inference_loop', 'args': [...], ...}
#   ]
# }
```

### View Queue Lengths
```bash
celery -A app.infrastructure.queue.celery_app:celery inspect reserved
celery -A app.infrastructure.queue.celery_app:celery inspect active_queues
```

### Monitor from Python
```python
from celery.result import AsyncResult

task_result = AsyncResult('task-uuid', app=celery)
print(task_result.status)  # PENDING, STARTED, SUCCESS, RETRY, FAILURE
print(task_result.result)  # Result dict or exception
```

### Logs
- Local: Standard Python logging (capture in journalctl or app.log)
- Railway: Use `railway logs --service worker` to stream worker logs

---

## Common Issues & Fixes

**Issue: "DatabasePool not initialized in worker"**
- Cause: Worker started before API app called `DatabasePool.initialize()`
- Fix: Ensure database setup happens before Celery tasks run (in `railway_start.py`)

**Issue: "redis.exceptions.ConnectionError"**
- Cause: REDIS_URL not set or Redis not running
- Fix: Set `REDIS_URL` env var, verify Redis is online

**Issue: "TypeError: Object of type UUID is not JSON serializable"**
- Cause: Task args contain UUID objects, but Celery uses JSON serialization
- Fix: Convert UUIDs to strings: `task.delay(str(uuid_obj), ...)`

**Issue: "Task hangs for 5+ minutes then times out"**
- Cause: Infinite loop or blocking operation in task
- Fix: Add heartbeats, timeouts, or break long operations into subtasks

---

## Testing Tasks

**Unit Test** (mock dependencies):
```python
@patch('app.infrastructure.queue.tasks.extraction.get_storage')
@patch('app.infrastructure.queue.tasks.extraction.get_frame_repo')
def test_extract_frames_success(mock_repo, mock_storage):
    mock_repo.return_value.create.return_value = {'id': 'frame-uuid'}
    result = extract_frames.apply_async(video_key='test.mp4', ...).get()
    assert result['status'] == 'success'
```

**Integration Test** (real Redis + DB):
```python
@pytest.mark.slow
def test_extract_frames_integration(db_pool, redis_client):
    # Setup: create video record
    # Call task via Celery
    # Poll task status
    # Verify frames in DB
```

---

## Related Documentation

- Parent: `/backend/app/infrastructure/AGENTS.md` — infrastructure overview
- Sibling: `/backend/app/infrastructure/database/AGENTS.md` — database repositories
- Sibling: `/backend/app/infrastructure/storage/AGENTS.md` — file storage
- Guides: `/CLAUDE.md` — task patterns and Celery configuration
- Tutorial: `/docs/celery-guide.md` (if exists)
