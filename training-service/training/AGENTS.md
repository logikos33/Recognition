# training-service/training — AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Mission

Training Service orchestrates YOLOv8 model training on RunPod GPU infrastructure and publishes progress updates in real-time.

**Responsibilities**:
- Dispatch training jobs to RunPod API
- Poll job status with exponential backoff
- Publish progress updates to Redis for frontend
- Handle job cancellation
- Manage circuit breaker for API resilience

## Architecture

### Startup Sequence (main.py)

```
main()
  ├─ create JobManager() (holds RunPodClient + ProgressPublisher)
  ├─ Flask.run() [blocks main thread, serves /health + /api/training/* endpoints]
  └─ Flask routes dispatch to JobManager methods
```

**Key pattern**: Unlike gateway/inference, training service is primarily request-driven (HTTP) with background polling threads spawned per job.

## Modules

### main.py — Entrypoint

Minimal: create JobManager, run Flask, register graceful shutdown.

### app.py — Flask Factory

Flask app with Blueprint registration.

**Routes** (defined in routes or app directly):
- `POST /api/training/start` → JobManager.start_job()
- `POST /api/training/cancel/{job_id}` → JobManager.cancel_job()
- `GET /api/training/status/{job_id}` → JobManager.status()
- `GET /health` → health check

### job_manager.py — Job Orchestration

**Class**: `JobManager` (singleton)

**Methods**:
- `start_job(job_id, dataset_url) -> dict` — Async, spawns polling thread
- `cancel_job(job_id) -> bool` — Sends cancel to RunPod, publishes failed event
- `active_jobs() -> list[str]` — Returns list of active job IDs

**Start Flow**:
```python
def start_job(self, job_id: str, dataset_url: str) -> dict:
    self._pub.creating_pod(job_id)  # publishes status
    result = self._runpod.start_job(job_id, dataset_url)
    runpod_id = result.get("id", "")
    with self._lock:
        self._active[job_id] = {"runpod_id": runpod_id}
    
    # Spawn polling thread
    threading.Thread(
        target=self._poll, args=(job_id, runpod_id),
        daemon=True, name=f"poll-{job_id[:8]}"
    ).start()
    
    return {"job_id": job_id, "runpod_id": runpod_id, "status": "running"}
```

**Polling Flow** (`_poll` method):
```python
def _poll(self, job_id: str, runpod_id: str) -> None:
    while True:
        with self._lock:
            if job_id not in self._active:
                return  # job was cancelled
        
        try:
            s = self._runpod.get_status(runpod_id)
            state = s.get("status", "")
            
            if state == "COMPLETED":
                output = s.get("output", {})
                self._pub.completed(
                    job_id,
                    output.get("model_key", ""),
                    output.get("metrics", {})
                )
                with self._lock:
                    self._active.pop(job_id, None)
                return
            
            elif state == "FAILED":
                self._pub.failed(job_id, s.get("error", "failed"))
                with self._lock:
                    self._active.pop(job_id, None)
                return
            
            elif state == "IN_PROGRESS":
                output = s.get("output", {})
                self._pub.training(
                    job_id,
                    output.get("epoch", 0),
                    TRAINING_EPOCHS,
                    output.get("loss")
                )
        
        except Exception as exc:
            logger.error("poll_error: job=%s err=%s", job_id, exc)
        
        time.sleep(POLL_INTERVAL)  # default 30s
```

**Thread Safety**: Uses `self._lock` to protect `self._active` dict.

### runpod_client.py — RunPod API Client

**Class**: `RunPodClient`

Provides circuit breaker pattern with exponential backoff.

**Methods**:
- `start_job(job_id, dataset_url) -> dict` — Create training job, return RunPod job ID
- `get_status(runpod_id) -> dict` — Get job status (PENDING, IN_PROGRESS, COMPLETED, FAILED)
- `cancel_job(runpod_id) -> bool` — Send cancel request

**Circuit Breaker**:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.open_at = None
    
    def is_open(self):
        if self.open_at is None:
            return False
        if time.time() - self.open_at > self.timeout:
            self.open_at = None
            return False
        return True
    
    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.open_at = time.time()
    
    def record_success(self):
        self.failure_count = 0
        self.open_at = None
```

**Behavior**:
- 3 consecutive failures → circuit opens for 60 seconds
- All requests fail immediately while open (fast-fail)
- Automatic recovery after timeout

### progress_publisher.py — Real-Time Status

**Class**: `ProgressPublisher`

Publishes training progress to Redis channels for WebSocket delivery to frontend.

**Methods**:
- `creating_pod(job_id)` — Job created, waiting for pod
- `training(job_id, epoch, total_epochs, loss)` — In-progress update
- `completed(job_id, model_key, metrics)` — Job finished successfully
- `failed(job_id, error_message)` — Job failed

**Output Channels**: `training:{job_id}`

**Payloads**:

```json
// creating_pod
{"status": "creating", "job_id": "...", "timestamp": "..."}

// training
{"status": "training", "job_id": "...", "epoch": 5, "total_epochs": 100, "loss": 0.25, "timestamp": "..."}

// completed
{"status": "completed", "job_id": "...", "model_key": "s3://...", "metrics": {"mAP": 0.92, ...}, "timestamp": "..."}

// failed
{"status": "failed", "job_id": "...", "error": "OOM", "timestamp": "..."}
```

**Consumption**: `ws-gateway` subscribes to `training:*` and relays to frontend via `/training` namespace.

## Configuration (config.py)

```python
PORT = 5001
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")
RUNPOD_ENDPOINT = "https://api.runpod.io/graphql"
POLL_INTERVAL = 30  # seconds
TRAINING_EPOCHS = 100
```

## Redis Channels

| Channel | Type | TTL | Set By | Read By |
|---------|------|-----|--------|---------|
| `training:{job_id}` | pubsub | N/A | ProgressPublisher | ws-gateway (socket_bridge) |

## RunPod API Integration

**Assumptions**:
- RunPod API endpoint accessible at RUNPOD_ENDPOINT
- Job input: `{"job_id": "...", "dataset_url": "s3://..."}`
- Job output: `{"model_key": "s3://...", "metrics": {...}, "epoch": N, "loss": X}`
- Statuses: PENDING, IN_PROGRESS, COMPLETED, FAILED

**Error Handling**:
- Network failures → circuit breaker opens
- Timeout → logged, retry next poll interval
- JSON parsing errors → logged, continue polling

## Job Lifecycle

```
start_job()
  ├─ publish creating_pod event
  ├─ call RunPod API
  ├─ spawn polling thread
  └─ return immediately with job_id

_poll() [background thread]
  ├─ every POLL_INTERVAL seconds:
  │  ├─ get_status() from RunPod
  │  ├─ if COMPLETED: publish completed event, stop thread
  │  ├─ if FAILED: publish failed event, stop thread
  │  └─ if IN_PROGRESS: publish training event, continue
  └─ exit when job completes or is removed from active
```

## Logging

Key events:
- `poll_error: job=... err=...` (non-fatal, next poll retries)
- `circuit_breaker_open` (all requests fail fast for 60s)
- `circuit_breaker_closed` (recovery after timeout)

## Error Handling

| Error | Handling |
|-------|----------|
| RunPod API timeout | Circuit breaker tracks, fast-fails after 3 failures |
| JSON parsing in response | Logged, polling continues |
| Job not found in RunPod | Status assumed PENDING, retried next interval |
| Network connectivity lost | Exponential backoff in polling, circuit breaker kicks in |

## Integration Points

**Inbound**:
- HTTP POST to `/api/training/start` with dataset_url
- HTTP POST to `/api/training/cancel/{job_id}`

**Outbound**:
- RunPod API (GraphQL queries for job management)
- Redis channel `training:{job_id}` (progress updates for frontend)

## Testing Notes

```bash
# 1. Start training service
python -m training.main

# 2. Start a training job
curl -X POST http://localhost:5001/api/training/start \
  -H "Content-Type: application/json" \
  -d '{"dataset_url":"s3://bucket/dataset.zip"}'

# 3. Monitor progress (from Redis)
redis-cli SUBSCRIBE 'training:*'

# 4. Cancel job
curl -X POST http://localhost:5001/api/training/cancel/<job_id>

# 5. Check health
curl http://localhost:5001/health
```

## Known Limitations

- No persistence of job history (lost on restart)
- No retry of failed jobs (manual restart required)
- No support for multiple training pipelines in parallel (single JobManager)
- RunPod credentials in env var (not encrypted)
- No timeout on long polling (relies on RunPod to complete or fail)
- No metrics on training execution (just logging)
