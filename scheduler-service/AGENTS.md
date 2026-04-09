<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-09 -->

# scheduler-service

Celery Beat scheduler for maintenance tasks. Manages cleanup, health checks, and periodic operations.

## Purpose

Single responsibility: scheduled task orchestration. Runs on single Railway instance with Celery Beat + Worker in separate threads.

## Architecture

```
Flask app (health endpoint)
    ↓
Celery Beat (scheduler)
    ↓
Tasks (cleanup, health checks)
    ↓
Celery Worker (executes tasks)
    ↓
PostgreSQL, Redis, Alerts
```

## Package Structure

```
scheduler/
├── __init__.py
├── main.py          # Entry point: Flask + Celery in threads
├── app.py           # Flask app factory (health endpoint)
├── config.py        # Celery config, environment
├── celery_app.py    # Celery instance factory
├── tasks.py         # All scheduled tasks
```

## Key Dependencies

- `flask>=3.0.0` — Health endpoint
- `celery[redis]>=5.3.0` — Task scheduler + worker
- `redis>=5.0.0` — Task broker
- `psycopg2-binary>=2.9.0` — PostgreSQL direct access

## Scheduled Tasks

### 1. cleanup_old_frames (Daily @ 4:00 AM)

```python
@celery.task(name='scheduler.tasks.cleanup_old_frames')
def cleanup_old_frames():
    """Delete frames older than FRAMES_RETENTION_DAYS from R2."""
    
    retention_days = int(os.environ.get('FRAMES_RETENTION_DAYS', 7))
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    # List all frames in R2
    s3_client = boto3.client('s3', endpoint_url=R2_ENDPOINT)
    response = s3_client.list_objects_v2(
        Bucket=R2_BUCKET,
        Prefix='frames/'
    )
    
    deleted_count = 0
    for obj in response.get('Contents', []):
        if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
            s3_client.delete_object(Bucket=R2_BUCKET, Key=obj['Key'])
            deleted_count += 1
    
    logger.info(f"Cleanup: deleted {deleted_count} old frames")
    return {"deleted": deleted_count}
```

Schedule:
```
Cron: 0 4 * * *  (4:00 AM daily)
```

### 2. cleanup_old_alerts (Daily @ 3:00 AM)

```python
@celery.task(name='scheduler.tasks.cleanup_old_alerts')
def cleanup_old_alerts():
    """Delete alerts older than ALERTS_RETENTION_DAYS from PostgreSQL."""
    
    retention_days = int(os.environ.get('ALERTS_RETENTION_DAYS', 90))
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM alerts
                WHERE created_at < %s
                """,
                (cutoff_date,)
            )
            deleted_count = cur.rowcount
            conn.commit()
    
    logger.info(f"Cleanup: deleted {deleted_count} old alerts")
    return {"deleted": deleted_count}
```

Schedule:
```
Cron: 0 3 * * *  (3:00 AM daily)
```

### 3. check_cameras_health (Every 5 minutes)

```python
@celery.task(name='scheduler.tasks.check_cameras_health')
def check_cameras_health():
    """
    Monitor camera streams.
    - Check if Redis key exists for each active camera
    - Publish alert if stream missing for >5 minutes
    """
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get all active cameras
            cur.execute(
                "SELECT id, name FROM cameras WHERE is_active = true"
            )
            cameras = cur.fetchall()
    
    r = redis.from_url(os.environ['REDIS_URL'])
    alerts_published = 0
    
    for camera_id, camera_name in cameras:
        # Check if gateway published health in last 5 minutes
        health_key = f"camera:health:{camera_id}"
        last_heartbeat = r.get(health_key)
        
        if not last_heartbeat:
            # Stream missing — publish alert
            alert = {
                "type": "stream_missing",
                "camera_id": str(camera_id),
                "camera_name": camera_name,
                "timestamp": datetime.utcnow().isoformat()
            }
            r.publish("alert:stream", json.dumps(alert))
            alerts_published += 1
            logger.warning(f"Stream missing: {camera_name}")
    
    logger.info(f"Health check: {len(cameras)} cameras, {alerts_published} alerts")
    return {"cameras_checked": len(cameras), "alerts": alerts_published}
```

Schedule:
```
Cron: */5 * * * *  (every 5 minutes)
```

## Celery Configuration

```python
# scheduler/config.py
class CeleryConfig:
    broker_url = os.environ['REDIS_URL']
    result_backend = os.environ['REDIS_URL']
    
    beat_schedule = {
        'cleanup-old-alerts': {
            'task': 'scheduler.tasks.cleanup_old_alerts',
            'schedule': crontab(hour=3, minute=0),  # 3:00 AM daily
        },
        'cleanup-old-frames': {
            'task': 'scheduler.tasks.cleanup_old_frames',
            'schedule': crontab(hour=4, minute=0),  # 4:00 AM daily
        },
        'check-cameras-health': {
            'task': 'scheduler.tasks.check_cameras_health',
            'schedule': crontab(),  # Every minute (beat adjusts to */5)
        },
    }
    
    task_serializer = 'json'
    accept_content = ['json']
    result_serializer = 'json'
    timezone = 'UTC'
    enable_utc = True
```

## Endpoints

### GET /health

```bash
curl http://localhost:8006/health

Response (200):
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "celery_beat": "running",
  "celery_worker": "running",
  "scheduled_tasks": 3,
  "active_tasks": 0,
  "pending_tasks": 0
}

Response (503):
{
  "status": "unhealthy",
  "database": "error: connection timeout",
  "redis": "connected",
  "celery_beat": "running",
  "celery_worker": "running"
}
```

## Environment Variables

```bash
# Redis
REDIS_URL=redis://host:6379/0

# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# Retention policies
ALERTS_RETENTION_DAYS=90             # Delete alerts older than 90 days
FRAMES_RETENTION_DAYS=7              # Delete frames older than 7 days

# Flask
FLASK_ENV=production
SECRET_KEY=min-32-chars-random-secret
PORT=8006
```

## Threading Model

main.py runs Flask + Celery Beat + Celery Worker in parallel threads:

```python
# scheduler/main.py
import threading

app = create_app()
celery_app = celery_instance()

def run_celery_beat():
    celery_app.start(
        argv=['celery', '--app=scheduler.celery_app', 'beat', '--loglevel=info']
    )

def run_celery_worker():
    celery_app.worker_main(
        argv=['celery', '--app=scheduler.celery_app', 'worker', '--loglevel=info']
    )

if __name__ == '__main__':
    beat_thread = threading.Thread(target=run_celery_beat, daemon=True)
    worker_thread = threading.Thread(target=run_celery_worker, daemon=True)
    
    beat_thread.start()
    worker_thread.start()
    
    # Flask runs on main thread
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8006)))
```

## Task Monitoring

Monitor task execution via Celery Flower (optional):

```bash
# In separate service
celery -A scheduler.celery_app flower --port=5555
```

Or inspect via Redis:

```bash
# Celery stores task state in Redis
redis-cli
KEYS celery-task-meta-*  # Active task states
HGETALL celery-task-meta-{task_id}
```

## Scaling

scheduler-service:
- Single instance (not replicated)
- ~256 MB RAM
- Celery Beat: one global scheduler (no HA)
- Celery Worker: processes tasks sequentially

**Note**: Celery Beat is NOT HA (high availability). If scheduler crashes and restarts, tasks may be skipped or duplicated. For production HA, consider:
- Celery Beat with redis-py locking
- APScheduler with distributed lock
- Manual cron jobs on separate host

Current design acceptable for EPI Monitor (non-critical maintenance).

## Testing

```bash
# Health
curl http://localhost:8006/health

# Check Celery status
redis-cli KEYS "celery*"

# Manually trigger task (for testing)
# In Python:
from scheduler.celery_app import celery_app
from scheduler.tasks import cleanup_old_frames

result = cleanup_old_frames.delay()
print(result.get())

# Or via Celery CLI:
celery -A scheduler.celery_app call scheduler.tasks.cleanup_old_frames

# Watch task logs
celery -A scheduler.celery_app worker --loglevel=info
```

## Error Handling

- **Database connection lost**: Task fails, logged to Celery backend
- **R2 connection timeout**: Task retries (exponential backoff, max 3 times)
- **Redis connection lost**: Celery broker unavailable, tasks queued

All errors logged to stdout (Celery worker logs).

## Task Results

Results stored in Redis (with TTL):

```
celery-task-meta-{task_id}:
{
  "status": "SUCCESS",
  "result": {"deleted": 42},
  "date_done": "2026-04-09T10:00:00.123Z"
}
```

Results expire after 24 hours (configurable via `result_expires`).

## Service Dependencies

- **PostgreSQL** — alerts table access (railway plugin)
- **Redis** — Celery broker, task state (railway plugin)
- **R2** — frame cleanup (external, optional if not used)

Does not depend on auth-service, camera-gateway, inference-service, or ws-gateway.

## Deployment

Railway automatically runs:
```
CMD ["python", "-m", "scheduler.main"]
```

Set `DATABASE_URL`, `REDIS_URL`, and `ALERTS_RETENTION_DAYS` in Railway Variables.

**Important**: Do NOT scale this service to multiple instances. Celery Beat runs on a single leader. If you need HA scheduling, use external service like AWS EventBridge or managed APScheduler.
