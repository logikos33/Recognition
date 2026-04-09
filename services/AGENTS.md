<!-- Parent: ../CLAUDE.md -->
<!-- Generated: 2026-04-09 -->

# Services/Shared — EPI Monitor V2 Shared Utilities

**Purpose**: Shared utilities used by both API and Worker services. Provides database connection management, Redis event bus (pub/sub), and constants.

**Tech Stack**: psycopg2-binary, redis-py

**Critical Rule**: ALWAYS use `get_db_connection()` context manager. Never create raw connections.

---

## Directory Structure

```
services/
├── __init__.py
└── shared/
    ├── __init__.py
    ├── database.py               # PostgreSQL connection management
    │   ├── get_database_url()    # Returns correct URL (postgres → postgresql)
    │   ├── get_db_connection()   # Context manager (CRITICAL PATTERN)
    │   └── test_connection()     # Health check
    ├── events.py                 # Redis event bus (pub/sub)
    │   ├── get_redis_client()    # Redis connection factory
    │   ├── is_redis_available()  # Health check
    │   ├── EventPublisher        # Worker publishes detections/status
    │   └── EventConsumer         # API subscribes to events
    └── constants.py              # Shared enums (if any)
```

---

## Core Modules

### 1. database.py — PostgreSQL Connection Pool

**Purpose**: Thread-safe connection management via context manager.

```python
from services.shared.database import get_db_connection

# ✅ ALWAYS do this — connection closes automatically
with get_db_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()

# ❌ NEVER do this — causes pool exhaustion (V1 crash #1)
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("SELECT * FROM users")
# Oops, forgot to close!
```

**Key Functions**:

| Function | Returns | Notes |
|----------|---------|-------|
| `get_database_url()` | str | Converts `postgres://` → `postgresql://` (Railway compatibility) |
| `get_db_connection()` | context manager | Yields psycopg2 connection, auto-closes, auto-commits |
| `test_connection()` | bool | Health check: returns True if DB accessible |

**Implementation Details**:

```python
@contextmanager
def get_db_connection():
    """Yields connection, commits on success, rolls back on error, always closes."""
    conn = None
    try:
        conn = psycopg2.connect(
            get_database_url(),
            connect_timeout=15,
            cursor_factory=psycopg2.extras.RealDictCursor  # Row access by column name
        )
        yield conn
        conn.commit()  # Commit on success
    except Exception:
        if conn:
            conn.rollback()  # Rollback on error
        raise
    finally:
        if conn and not conn.closed:
            conn.close()  # Always close
```

**Why RealDictCursor?**
- `row['id']` instead of `row[0]` — more readable
- Works with repositories mapping to domain models

---

### 2. events.py — Redis Event Bus (Pub/Sub)

**Purpose**: Decouple API and Worker via Redis channels. Worker publishes, API subscribes.

#### EventPublisher (used by Worker)

```python
from services.shared.events import EventPublisher

pub = EventPublisher()

# Publish detection
pub.publish_detection(
    camera_id='cam-123',
    detections=[
        {'class_name': 'produto', 'confidence': 0.87, 'bbox': [100, 150, 250, 300]}
    ],
    timestamp=time.time()
)
# → publishes to epi:detections channel

# Update stream status
pub.set_stream_status('cam-123', 'active')
# → sets Redis key epi:stream:cam-123 (120s TTL)
# → publishes to epi:stream_status channel

# Report worker health
pub.update_health(
    worker_id='worker-1',
    active_streams=2,
    stream_ids=['cam-123', 'cam-456']
)
# → updates epi:workers set
# → sets epi:worker:worker-1:alive (60s TTL)
# → sets epi:worker:worker-1:health (90s TTL)
```

**Channels**:
- `epi:detections` — Detection events from worker
- `epi:stream_status` — Stream status updates
- `epi:workers` — Set of active worker IDs
- `epi:worker:{id}:alive` — Worker heartbeat (60s TTL)
- `epi:worker:{id}:health` — Worker health JSON (90s TTL)
- `epi:stream:{id}` — Stream status JSON (120s TTL)
- `epi:commands:{worker_id}` — Commands from API to worker

#### EventConsumer (used by API)

```python
from services.shared.events import EventConsumer

consumer = EventConsumer()

# Find least-loaded worker (picks one with <4 streams)
best_worker = consumer.get_best_worker()
# Returns: 'worker-1' or None if no workers available

# Send command to worker
consumer.send_command('worker-1', {
    'action': 'start_stream',
    'camera_id': 'cam-123',
    'rtsp_url': 'rtsp://192.168.1.100:554/live/ch0'
})
# → publishes to epi:commands:worker-1

# Get stream status
status = consumer.get_stream_status('cam-123')
# Returns: {'status': 'active', 'camera_id': 'cam-123'}
# or: {'status': 'stopped'} if not found

# Get all workers health
workers = consumer.get_all_workers_health()
# Returns: [
#   {'worker_id': 'worker-1', 'active_streams': 2, 'stream_ids': [...], 'is_alive': True},
#   {'worker_id': 'worker-2', 'active_streams': 1, 'stream_ids': [...], 'is_alive': True}
# ]

# Subscribe to events (background thread)
pubsub = consumer.subscribe_all()  # Returns redis.pubsub() on dedicated connection
for message in pubsub.listen():
    if message['type'] == 'pmessage':
        channel = message['channel']
        data = json.loads(message['data'])
        # Handle event
```

**Key Methods**:

| Method | Returns | Notes |
|--------|---------|-------|
| `get_redis_client()` | redis.Redis | New connection with socket_timeout=5 |
| `is_redis_available()` | bool | Health check |
| `EventPublisher.publish_detection()` | none | Publishes to epi:detections |
| `EventPublisher.set_stream_status()` | none | Sets key + publishes |
| `EventPublisher.update_health()` | none | Updates worker health |
| `EventConsumer.send_command()` | none | Publishes to epi:commands:{worker_id} |
| `EventConsumer.get_best_worker()` | str or None | Least-loaded worker |
| `EventConsumer.get_stream_status()` | dict | Stream status from Redis |
| `EventConsumer.get_all_workers_health()` | list[dict] | All workers health |
| `EventConsumer.subscribe_all()` | redis.PubSub | Dedicated connection (no socket_timeout) |
| `EventConsumer.set_camera_worker()` | none | Cache camera → worker mapping (1h TTL) |
| `EventConsumer.get_camera_worker()` | str or None | Get cached worker for camera |

#### Redis Connection Details

```python
# Normal client (socket_timeout=5, good for quick operations)
def get_redis_client():
    import redis
    url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    return redis.from_url(url, decode_responses=True, socket_timeout=5)

# Pub/Sub client (socket_timeout=None, for blocking listen())
# This is used internally in EventConsumer.subscribe_all()
r = redis.from_url(
    url,
    decode_responses=True,
    socket_timeout=None,           # CRITICAL: None for blocking listen()
    socket_keepalive=True,
    health_check_interval=25       # Detect idle disconnects
)
```

**Important**: subscribe_all() creates its own connection with `socket_timeout=None`. The normal client has `socket_timeout=5` which would timeout during blocking listen().

---

## For AI Agents

### When adding a new shared utility:

1. **Database queries** → add repository method in `backend/app/infrastructure/database/repositories/`
   - Use `get_db_connection()` pattern
   - Return domain model, not raw row

2. **Redis communication** → extend `EventPublisher` or `EventConsumer`
   - Worker publishes detections → `EventPublisher.publish_detection()`
   - API consumes detections → `EventConsumer.subscribe_all()`
   - New channels: add method to appropriate class

3. **Shared constants** → add to `services/shared/constants.py` (if none exists)
   - Enums, Redis channel names, timeouts

### Database Usage Pattern

```python
# In any API endpoint or Worker code
from services.shared.database import get_db_connection

def get_user(user_id: str):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, full_name FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        if row:
            return User(id=row['id'], email=row['email'], name=row['full_name'])
        return None
```

### Redis Event Usage Pattern

#### Worker publishes:
```python
from services.shared.events import EventPublisher

pub = EventPublisher()
pub.publish_detection('cam-123', detections, timestamp)
pub.set_stream_status('cam-123', 'active')
pub.update_health('worker-1', 2, ['cam-123', 'cam-456'])
```

#### API subscribes:
```python
from services.shared.events import EventConsumer

consumer = EventConsumer()

# Get best worker for new camera
worker_id = consumer.get_best_worker()
if worker_id:
    consumer.send_command(worker_id, {
        'action': 'start_stream',
        'camera_id': camera_id,
        'rtsp_url': camera.rtsp_url
    })

# Background thread listening
pubsub = consumer.subscribe_all()
for msg in pubsub.listen():
    if msg['type'] == 'pmessage':
        channel = msg['channel']
        data = json.loads(msg['data'])
        if channel.startswith('epi:detections'):
            # Handle detection
            pass
```

### Common Pitfalls

- ❌ `psycopg2.connect()` directly → use `get_db_connection()`
- ❌ Creating multiple Redis clients everywhere → use `get_redis_client()`
- ❌ `socket_timeout=5` on pubsub connection → causes TimeoutError during listen()
- ❌ Publishing raw objects → always `json.dumps()` first
- ❌ Not checking `is_redis_available()` before operations → health check first
- ❌ Forgetting to call `.close()` on pubsub → will leak connections

### Testing

```python
# tests/unit/test_database.py
def test_get_db_connection_commits_on_success():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
    # Connection is closed and committed
    assert conn.closed

def test_get_db_connection_rolls_back_on_error():
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("INVALID SQL")
    except Exception:
        pass  # Expected
    # Connection is closed and rolled back
    assert conn.closed

# tests/unit/test_events.py
def test_publisher_publishes_detection(mock_redis):
    pub = EventPublisher()
    pub._r = mock_redis
    pub.publish_detection('cam-123', [{'class': 'test'}], 123.45)
    mock_redis.publish.assert_called_once()
```

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Redis
REDIS_URL=redis://user:pass@host:port/db
```

**Railway**: Set via dashboard, automatically injected into services.

---

## References

- **psycopg2 docs**: https://www.psycopg.org
- **redis-py docs**: https://redis-py.readthedocs.io
- **PostgreSQL URL format**: https://www.postgresql.org/docs/current/libpq-connect-using-params.html
