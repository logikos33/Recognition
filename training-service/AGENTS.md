<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-09 -->

# training-service

Manages YOLOv8 training jobs on RunPod serverless. Dispatches training tasks, monitors progress, stores results in R2.

## Purpose

Single responsibility: training job orchestration. Runs on CPU-only Railway instance (GPU not available), dispatches to RunPod GPU for actual training.

## Architecture

```
Flask API
    ↓
POST /api/training/start
    ↓
job_manager.py      (create job, dispatch to RunPod)
    ↓
runpod_client.py    (async call, get job ID)
    ↓
progress_publisher.py (poll RunPod status, publish to Redis)
    ↓
Redis (publish training:{job_id})
    ↓
ws-gateway         (WebSocket broadcast progress)
```

## Package Structure

```
training/
├── __init__.py
├── main.py              # Entry point: create_app() + run
├── app.py               # Flask app factory
├── config.py            # Environment config
├── redis_client.py      # Redis connection
├── job_manager.py       # Training job CRUD
├── runpod_client.py     # RunPod API client (circuit breaker, polling)
├── progress_publisher.py # Poll status, publish progress to Redis
```

## Key Dependencies

- `flask>=3.0.0` — Web framework
- `gunicorn>=21.0.0` — Production server
- `redis>=5.0.0` — Progress publishing, job coordination
- `boto3>=1.34.0` — R2 upload (trained model storage)
- `requests>=2.31.0` — RunPod API calls

## Endpoints

### Start Training Job

```bash
POST /api/training/start
Authorization: Bearer <token>
Content-Type: application/json

{
  "dataset_id": "uuid-456",
  "epochs": 50,
  "batch_size": 16,
  "learning_rate": 0.001,
  "name": "EPI Detection Run 1"
}

Response (202):
{
  "status": "success",
  "data": {
    "job_id": "run-123",
    "status": "queued",
    "dataset_id": "uuid-456",
    "epochs": 50,
    "created_at": "2026-04-09T10:00:00Z"
  }
}
```

### Get Job Status

```bash
GET /api/training/jobs/{job_id}
Authorization: Bearer <token>

Response (200):
{
  "status": "success",
  "data": {
    "job_id": "run-123",
    "status": "running",          # queued | running | completed | failed
    "progress": {
      "epoch": 15,
      "total_epochs": 50,
      "loss": 0.234,
      "accuracy": 0.88,
      "eta_seconds": 3600
    },
    "created_at": "2026-04-09T10:00:00Z",
    "started_at": "2026-04-09T10:05:00Z",
    "completed_at": null,
    "model_url": null
  }
}
```

### List Jobs

```bash
GET /api/training/jobs?limit=10&offset=0
Authorization: Bearer <token>

Response (200):
{
  "status": "success",
  "data": [
    {
      "job_id": "run-123",
      "status": "completed",
      "epochs": 50,
      "created_at": "2026-04-09T10:00:00Z",
      "completed_at": "2026-04-10T02:00:00Z",
      "model_url": "https://r2.../models/run-123/best.pt"
    }
  ],
  "total": 42
}
```

### Health

```bash
GET /health

Response (200):
{
  "status": "healthy",
  "redis": "connected",
  "runpod_status": "available",
  "active_jobs": 2,
  "jobs": {
    "queued": 1,
    "running": 1,
    "completed": 18,
    "failed": 2
  }
}
```

## RunPod Integration

### Circuit Breaker Pattern

```python
runpod_client.py:
  - Async call: POST https://api.runpod.io/v1/{endpoint_id}/run
  - Get job_id, queue immediately
  - If RunPod offline: 503 Service Unavailable
  - Retry policy: exponential backoff (max 3 attempts)
  - Timeout: 30 seconds
```

### Polling Status

progress_publisher.py (background thread):

```python
while True:
  for job_id in redis.keys("job:*"):
    if job['status'] in ['queued', 'running']:
      runpod_status = runpod_client.get_status(runpod_job_id)
      
      if runpod_status['status'] == 'COMPLETED':
        # Download model from RunPod → upload to R2
        model_url = runpod_status['output']['model_url']
        r2.upload(model_url, f"models/{job_id}/best.pt")
        
        # Publish completion
        redis.publish(f"training:{job_id}", {
          "status": "completed",
          "model_url": f"https://r2.../models/{job_id}/best.pt"
        })
      
      else if runpod_status['status'] == 'FAILED':
        redis.publish(f"training:{job_id}", {
          "status": "failed",
          "error": runpod_status['error']
        })
      
      sleep(30)  # Poll every 30 seconds
```

## Environment Variables

```bash
# Redis
REDIS_URL=redis://host:6379/0

# RunPod
RUNPOD_API_KEY=rpa_...                          # From RunPod dashboard
RUNPOD_ENDPOINT_ID=...                          # Serverless endpoint ID
RUNPOD_POLLING_INTERVAL=30                      # seconds
RUNPOD_TIMEOUT=30                               # seconds

# R2 (Cloudflare)
R2_ENDPOINT=https://{account_id}.r2.cloudflarestorage.com
R2_BUCKET=epi-monitor
R2_KEY=<access_key>
R2_SECRET=<secret_key>

# Training defaults
TRAINING_EPOCHS=50
TRAINING_BATCH_SIZE=16
TRAINING_LEARNING_RATE=0.001
TRAINING_IMG_SIZE=640

# Flask
FLASK_ENV=production
SECRET_KEY=min-32-chars-random-secret
PORT=8004
```

## Job Lifecycle

```
1. POST /api/training/start
   ↓
2. job_manager.create_job()
   - Create job record in Redis
   - Status: "queued"
   ↓
3. runpod_client.dispatch()
   - POST to RunPod endpoint
   - Get runpod_job_id
   - Store in job record
   ↓
4. progress_publisher polling thread
   - Every 30s: GET RunPod status
   - Update job record
   - Publish to Redis training:{job_id}
   ↓
5. ws-gateway broadcasts to clients
   ↓
6. RunPod completes training
   - progress_publisher downloads model
   - Uploads to R2
   - Updates job: status="completed", model_url="..."
   ↓
7. GET /api/training/jobs/{job_id} returns model_url
```

## Storage Structure (R2)

```
models/
├── run-123/
│   ├── best.pt              # Trained model
│   ├── metrics.json         # Training metrics
│   ├── confusion_matrix.png # Validation results
│   └── metadata.json        # Dataset info, hyperparameters
├── run-124/
│   └── ...
```

## Error Handling

- **RunPod offline**: Return 503, client retries
- **Training failed**: Job status="failed", error message published to Redis
- **R2 upload timeout**: Retry upload (exponential backoff)
- **Malformed request**: Return 400, validation error

## Progress Events

Real-time events published to Redis `training:{job_id}`:

```json
{
  "job_id": "run-123",
  "status": "running",
  "epoch": 15,
  "total_epochs": 50,
  "loss": 0.234,
  "val_loss": 0.198,
  "accuracy": 0.88,
  "val_accuracy": 0.91,
  "learning_rate": 0.001,
  "eta_seconds": 3600,
  "timestamp": "2026-04-09T10:15:00Z"
}
```

ws-gateway emits to `/training` namespace, clients subscribe to `job:{job_id}`.

## Scaling

training-service:
- ~1 instance (CPU only, no GPU required)
- ~256 MB RAM
- Manages unlimited jobs (limited by RunPod quota)

RunPod serverless:
- GPU instance (H100, A100, etc.)
- On-demand per job
- Training time: ~8-12 hours per dataset (estimated)

## Testing

```bash
# Health
curl http://localhost:8004/health

# Start training (requires valid dataset_id)
TOKEN=$(...)  # Your JWT token
curl -X POST http://localhost:8004/api/training/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "uuid-456",
    "epochs": 5,
    "name": "Quick Test"
  }'

# Get job status
curl http://localhost:8004/api/training/jobs/run-123 \
  -H "Authorization: Bearer $TOKEN"

# Watch progress
redis-cli subscribe 'training:*'
```

## Service Dependencies

- **Redis** — Job state, progress publishing (railway plugin)
- **auth-service** — JWT validation
- **RunPod** — GPU training (external)
- **R2** — Model storage (external, Cloudflare)

Does not depend on camera-gateway, inference-service, or ws-gateway.

## Deployment

Railway automatically runs:
```
CMD ["python", "-m", "training.main"]
```

Set `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID`, and `R2_*` in Railway Variables.

**Note**: This service is CPU-only. GPU training happens on RunPod, not Railway.
