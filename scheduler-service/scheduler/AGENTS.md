# scheduler-service/scheduler — AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Mission

Scheduler Service runs Celery Beat to execute periodic background tasks: cleanup old alerts, cleanup old frames, and monitor camera health.

**Responsibilities**:
- Execute scheduled Celery tasks on fixed cron schedule
- Clean up expired alerts (unacknowledged, older than retention)
- Clean up pending frames (older than retention)
- Monitor camera connectivity via Redis keys
- Publish camera offline alerts

## Architecture

### Startup Sequence (main.py)

```
main()
  ├─ create Celery Beat scheduler in subprocess
  ├─ start Celery worker in subprocess (in parallel with Beat)
  ├─ Flask.run() [blocks main thread, serves /health]
  └─ on SIGTERM/SIGINT: stop both subprocesses
```

**Key pattern**: Beat + Worker run in dedicated subprocess threads so Flask can serve `/health` on main thread.

## Modules

### main.py — Entrypoint

Uses threading to spawn Celery Beat + Worker subprocesses.

```python
def subprocess_worker():
    os.system("celery -A scheduler.celery_app:celery worker --loglevel=info")

def subprocess_beat():
    os.system("celery -A scheduler.celery_app:celery beat --loglevel=info")

threading.Thread(target=subprocess_worker, daemon=True).start()
threading.Thread(target=subprocess_beat, daemon=True).start()
app.run(...)
```

### app.py — Flask Factory

Single route: `GET /health` returns `{"status": "ok"}`.

### celery_app.py — Celery Factory

```python
celery = Celery(
    "scheduler",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL
)
celery.conf.beat_schedule = {
    "cleanup-alerts": {
        "task": "scheduler.tasks.cleanup_old_alerts",
        "schedule": crontab(hour=3, minute=0)  # 03:00 UTC daily
    },
    "cleanup-frames": {
        "task": "scheduler.tasks.cleanup_old_frames",
        "schedule": crontab(hour=4, minute=0)  # 04:00 UTC daily
    },
    "check-cameras": {
        "task": "scheduler.tasks.check_cameras_health",
        "schedule": crontab(minute="*/5")  # Every 5 minutes
    }
}
```

### tasks.py — Scheduled Tasks

**Task 1: cleanup_old_alerts**

```python
@celery.task(name="scheduler.tasks.cleanup_old_alerts")
def cleanup_old_alerts() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=ALERTS_RETENTION_DAYS)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM alerts WHERE acknowledged = false AND created_at < %s",
                (cutoff,)
            )
            deleted = cur.rowcount
    return {"deleted": deleted}
```

**Behavior**: Removes unacknowledged alerts older than configured days (default 30).

**Logging**: `cleanup_alerts: deleted=<N>`

---

**Task 2: cleanup_old_frames**

```python
@celery.task(name="scheduler.tasks.cleanup_old_frames")
def cleanup_old_frames() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=FRAMES_RETENTION_DAYS)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM training_frames WHERE status = 'pending' AND created_at < %s",
                (cutoff,)
            )
            deleted = cur.rowcount
    return {"deleted": deleted}
```

**Behavior**: Removes pending training frames older than configured days (default 7).

**Logging**: `cleanup_frames: deleted=<N>`

---

**Task 3: check_cameras_health** (Most Complex)

```python
@celery.task(name="scheduler.tasks.check_cameras_health")
def check_cameras_health() -> dict:
    r = _r()
    offline = []
    
    with _db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get all active cameras
            cur.execute(
                "SELECT id::text, name, tenant_id::text FROM cameras WHERE status = 'active'"
            )
            cameras = cur.fetchall() or []
            
            for cam in cameras:
                cam_id = cam["id"]
                # Check if last detection is recent
                raw = r.get(f"camera:last_detection:{cam_id}")
                if not raw:
                    offline.append(cam_id)
                    continue
                
                try:
                    last_dt = datetime.fromisoformat(raw)
                    if datetime.now(timezone.utc) - last_dt > timedelta(minutes=5):
                        offline.append(cam_id)
                except ValueError:
                    offline.append(cam_id)
            
            # Update camera status to 'error' if offline
            if offline:
                cur.execute(
                    "UPDATE cameras SET status = 'error' WHERE id = ANY(%s::uuid[])",
                    (offline,)
                )
                # Publish alerts
                for cam in cameras:
                    if cam["id"] in offline:
                        r.publish(f"alert:{cam.get('tenant_id', '')}", json.dumps({
                            "type": "camera_offline",
                            "camera_id": cam["id"],
                            "camera_name": cam["name"],
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }))
    
    return {"offline": len(offline)}
```

**Logic**:
1. Query all cameras with status='active'
2. For each camera, check Redis key `camera:last_detection:{cam_id}`
3. If missing or timestamp > 5 minutes old → mark as offline
4. Update camera status to 'error' in database
5. Publish `alert:{tenant_id}` with camera_offline event

**Logging**: `camera_health: offline=<N>`

## Configuration (config.py)

```python
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://...")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
ALERTS_RETENTION_DAYS = int(os.environ.get("ALERTS_RETENTION_DAYS", 30))
FRAMES_RETENTION_DAYS = int(os.environ.get("FRAMES_RETENTION_DAYS", 7))
```

## PostgreSQL Schema (Required)

```sql
-- alerts table (for cleanup_old_alerts)
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    type VARCHAR(50) NOT NULL,
    message TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- training_frames table (for cleanup_old_frames)
CREATE TABLE training_frames (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- cameras table (for check_cameras_health)
CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Redis Keys

| Key | Type | TTL | Set By | Read By |
|-----|------|-----|--------|---------|
| `camera:last_detection:{cam_id}` | string (ISO timestamp) | N/A | inference-service | scheduler (check_cameras_health) |
| `alert:{tenant_id}` | pubsub channel | N/A | scheduler (check_cameras_health) | ws-gateway |

## Schedule

| Task | Schedule | Frequency | Purpose |
|------|----------|-----------|---------|
| cleanup_old_alerts | 03:00 UTC | Daily | Remove unacknowledged alerts older than 30 days |
| cleanup_old_frames | 04:00 UTC | Daily | Remove pending frames older than 7 days |
| check_cameras_health | Every 5 min | Every 5 minutes | Mark offline cameras, publish alerts |

## Logging

Key events:
- `cleanup_alerts: deleted=<N>`
- `cleanup_frames: deleted=<N>`
- `camera_health: offline=<N>`
- `cleanup_alerts_error: ...`
- `cleanup_frames_error: ...`
- `camera_health_error: ...`

## Integration Points

**Inbound**:
- Reads `camera:last_detection:{cam_id}` from Redis (set by inference-service)
- Reads cameras, alerts, frames from PostgreSQL

**Outbound**:
- Updates camera status in PostgreSQL
- Publishes alerts to `alert:{tenant_id}` Redis channel (consumed by ws-gateway → frontend)

## Error Handling

| Error | Handling |
|-------|----------|
| DB connection fails | Task returns `{"error": "..."}`, logs error, next run retries |
| Redis unavailable | Task fails, Celery retries (configurable) |
| Invalid timestamp in Redis | Camera marked as offline, alert published |

## Testing Notes

```bash
# Run Celery Beat in foreground (for testing)
celery -A scheduler.celery_app:celery beat --loglevel=info

# Or run Celery Worker in separate terminal
celery -A scheduler.celery_app:celery worker --loglevel=info

# Manually trigger a task
celery -A scheduler.celery_app:celery call scheduler.tasks.check_cameras_health

# Monitor tasks
celery -A scheduler.celery_app:celery events
```

## Known Limitations

- No task result persistence (tasks return dict but not stored)
- No alerting if tasks fail (silent retry)
- No metrics on task execution time
- Camera offline detection requires manual timestamp updates (depends on inference-service setting key)
- No backpressure handling (cleanup tasks don't limit batch size)
