<!-- Parent: ../CLAUDE.md -->
<!-- Generated: 2026-04-09 -->

# Worker — EPI Monitor V2 Stream & Detection Service

**Purpose**: Standalone Redis-based worker service. Listens for API commands via Redis pub/sub, manages FFmpeg HLS streams, runs YOLO detection (or simulation), publishes detections back to API via Redis events.

**Entry Point**: `python worker/worker_server.py` → connects to Redis, subscribes to `epi:commands:{WORKER_ID}` channel

**Tech Stack**: Python 3.11, Redis (pub/sub), FFmpeg (optional), YOLOv8 (optional), threading

**Scaling**: 1 instance per 3-4 cameras (~1.5 GB RAM per instance on Railway)

---

## Directory Structure

```
worker/
├── __init__.py                   # Empty init file
└── worker_server.py              # Main worker service
    ├── WorkerManager class       # Orchestrates streams, detections, health
    ├── start_stream()            # Starts FFmpeg + YOLO
    ├── stop_stream()             # Stops both
    ├── handle_command()          # Dispatch Redis commands
    ├── _health_loop()            # Periodic health reporting
    ├── run()                      # Main loop (Redis listen)
    └── shutdown()                # Graceful shutdown
```

**Design**: Single-threaded main loop listening to Redis, spawns background threads for streams and health checks.

---

## How It Works

### 1. Startup
```python
worker = WorkerManager()           # Load FFmpeg/YOLO processors
worker.redis.sadd('epi:workers', WORKER_ID)  # Register self
threading.Thread(target=worker._health_loop, daemon=True).start()
worker.run()                       # Enter main loop
```

### 2. Redis Command Subscription
```python
# Subscribes to: epi:commands:{WORKER_ID}
# Example command from API:
{
  "action": "start_stream",
  "camera_id": "cam-123",
  "rtsp_url": "rtsp://192.168.1.100:554/live/ch0",
  "config": { "fps": 5, "resolution": "640x360" }
}
```

### 3. Stream Management
```python
def start_stream(self, camera_id: str, rtsp_url: str, config: dict = None):
    # 1. Update status → starting
    self.pub.set_stream_status(camera_id, 'starting')
    
    # 2. Start FFmpeg (if available)
    if self.stream_mgr:
        self.stream_mgr.start_stream(camera_id, rtsp_url)
    
    # 3. Start YOLO detection (if available)
    if self.yolo:
        self.yolo.start_processing(camera_id, rtsp_url, fps=5)
    else:
        # Fallback: simulation mode (random detections)
        threading.Thread(target=self._simulate, args=(camera_id,), daemon=True).start()
    
    # 4. Update status → active
    self.pub.set_stream_status(camera_id, 'active')
```

### 4. Detection Publishing
```python
def _on_detection(self, camera_id, detections, timestamp=None):
    # Called by YOLOProcessor when detection found
    self.pub.publish_detection(camera_id, detections, timestamp or time.time())
    
# Example detection published to Redis channel epi:detections:
{
  "type": "detection",
  "camera_id": "cam-123",
  "detections": [
    {
      "class_name": "produto",
      "confidence": 0.87,
      "bbox": [100, 150, 250, 300]
    },
    {
      "class_name": "caminhao",
      "confidence": 0.95,
      "bbox": [50, 50, 500, 500]
    }
  ],
  "timestamp": 1712693400.123
}
```

### 5. Health Reporting
```python
def _health_loop(self):
    while self.running:
        self.pub.update_health(WORKER_ID, len(self.active), list(self.active.keys()))
        time.sleep(20)

# Redis keys set:
# - epi:workers (set) — list of active worker IDs
# - epi:worker:{WORKER_ID}:alive (key, 60s TTL)
# - epi:worker:{WORKER_ID}:health (JSON, 90s TTL)
```

### 6. Graceful Shutdown
```python
def shutdown(self):
    self.running = False
    # Stop all streams
    for cam in list(self.active.keys()):
        self.stop_stream(cam)
    # Deregister self
    self.redis.srem('epi:workers', WORKER_ID)

# Signal handlers
signal.signal(signal.SIGTERM, lambda s, f: (mgr.shutdown(), sys.exit(0)))
signal.signal(signal.SIGINT,  lambda s, f: (mgr.shutdown(), sys.exit(0)))
```

---

## Key Methods Reference

| Method | Input | Output | Notes |
|--------|-------|--------|-------|
| `start_stream()` | camera_id, rtsp_url, config | Updates Redis status | Spawns FFmpeg + YOLO threads |
| `stop_stream()` | camera_id | Removes from active dict | Calls FFmpeg/YOLO stop |
| `handle_command()` | cmd (dict from Redis) | Dispatches to start/stop/ping | Main command dispatcher |
| `_health()` | none | Updates Redis health keys | Called every 20s |
| `_make_pubsub()` | none | Returns redis.pubsub() | socket_timeout=None (blocks on listen) |
| `run()` | none | Infinite loop | Listens to Redis, calls handle_command |
| `shutdown()` | none | Gracefully exits | Signal handler + cleanup |

---

## Architecture Patterns

### 1. Redis Communication
```python
# Worker receives commands via Redis pub/sub (not HTTP)
# Pattern: API publishes to epi:commands:{WORKER_ID}
# Worker subscribes and processes

# API side (example):
from services.shared.events import EventConsumer
consumer = EventConsumer()
consumer.send_command('worker-1', {
    'action': 'start_stream',
    'camera_id': 'cam-123',
    'rtsp_url': 'rtsp://...'
})

# Worker side:
worker.handle_command({
    'action': 'start_stream',
    'camera_id': 'cam-123',
    'rtsp_url': 'rtsp://...'
})
```

**Benefit**: No HTTP between services, decoupled, scales across workers.

### 2. Processors Pattern
```python
class WorkerManager:
    def _load_processors(self):
        # FFmpeg processor (optional, graceful fallback)
        try:
            from api.utils.stream_manager import StreamManager
            self.stream_mgr = StreamManager()
        except ImportError:
            self.stream_mgr = None
        
        # YOLO processor (optional, falls back to simulation)
        try:
            from api.utils.yolo_processor import YOLOProcessor
            self.yolo = YOLOProcessor(model_path=YOLO_MODEL)
        except ImportError:
            self.yolo = None
```

**Benefit**: Graceful degradation — system runs in simulation mode even without FFmpeg/YOLO.

### 3. Threading for Blocking Operations
```python
# Redis listen() blocks, so wrap in daemon thread
pubsub = self._make_pubsub()
for msg in pubsub.listen():
    # This blocks until message arrives
    self.handle_command(json.loads(msg['data']))

# Health reporting in separate thread
threading.Thread(target=self._health_loop, daemon=True).start()

# Simulated detections in separate thread
threading.Thread(
    target=self._simulate,
    args=(camera_id,),
    daemon=True
).start()
```

**Critical**: `socket_timeout=None` on Redis connection (blocks indefinitely on listen).

### 4. Active Stream Tracking
```python
self.active: dict = {}

def start_stream(self, camera_id: str, ...):
    if camera_id in self.active:
        return  # Already running
    self.active[camera_id] = {
        'rtsp_url': rtsp_url,
        'started': time.time()
    }

def stop_stream(self, camera_id: str):
    if camera_id not in self.active:
        return
    del self.active[camera_id]

def shutdown(self):
    for cam in list(self.active.keys()):
        self.stop_stream(cam)
```

---

## For AI Agents

### When modifying the worker:

1. **Command dispatch logic** in `handle_command()`
   - Add new actions: `start_stream`, `stop_stream`, `ping`
   - Parse JSON from Redis message
   - Call corresponding method

2. **Stream lifecycle**
   - `start_stream()` → FFmpeg + YOLO
   - `stop_stream()` → graceful cleanup
   - Track in `self.active` dict

3. **Detection callbacks**
   - YOLOProcessor calls `self._on_detection(camera_id, detections)`
   - Publish via `self.pub.publish_detection()`

4. **Health reporting**
   - `_health_loop()` runs every 20s
   - Updates Redis keys for API to discover workers

### Adding a new processor:

```python
def _load_processors(self):
    # Existing code...
    
    # New processor (graceful fallback)
    try:
        from api.utils.new_processor import NewProcessor
        self.new_proc = NewProcessor()
        logger.info("✅ NewProcessor carregado")
    except ImportError as e:
        logger.warning(f"NewProcessor indisponível: {e}")
        self.new_proc = None

def start_stream(self, camera_id: str, ...):
    # ... existing code ...
    
    if self.new_proc:
        self.new_proc.process(camera_id, rtsp_url)
```

### Debugging:

```bash
# Check worker is registered
redis-cli SMEMBERS epi:workers

# Check health
redis-cli GET epi:worker:worker-1:health

# Check active streams
redis-cli GET epi:stream:cam-123

# Check detections (tail-like)
redis-cli SUBSCRIBE epi:detections
```

### Common pitfalls:

- ❌ Blocking operation in main thread → offload to threading.Thread
- ❌ `socket_timeout=5` on pubsub connection → causes TimeoutError after idle
- ❌ Hardcoding stream config → pass via command dict
- ❌ No graceful shutdown signal handlers → cleanup never runs
- ❌ Publishing to wrong Redis channel → use `self.pub` (correct channels)
- ❌ Not updating `self.active` dict → health reporting incorrect

### Testing simulation mode:

```bash
# Start worker without YOLO
export YOLO_MODEL_PATH=/nonexistent
python worker/worker_server.py

# Send command
redis-cli PUBLISH epi:commands:worker-1 '{"action": "start_stream", "camera_id": "test", "rtsp_url": "rtsp://test"}'

# Watch simulated detections
redis-cli SUBSCRIBE epi:detections

# You should see random detections every 3s
```

---

## Deployment (Railway)

### Service Configuration

```bash
# Service type: worker
# Start command:
python worker/worker_server.py

# Environment variables:
SERVICE_TYPE=worker
WORKER_ID=worker-1
YOLO_MODEL_PATH=storage/models/active/model.pt
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
```

### Scaling Multiple Workers

```bash
# Railway can run multiple worker instances
# service: worker-1
# WORKER_ID=worker-1

# service: worker-2
# WORKER_ID=worker-2

# API distributes cameras to least-loaded worker
from services.shared.events import EventConsumer
consumer = EventConsumer()
best_worker = consumer.get_best_worker()  # Picks worker with <4 streams
```

### Logs

```bash
# Check worker is running
railway logs --service worker

# Should see:
# EPI Monitor V2 Worker -- worker-1
# ✅ StreamManager carregado
# ✅ YOLOProcessor carregado
# ✅ Escutando: epi:commands:worker-1
```

---

## References

- **Redis pub/sub docs**: https://redis.io/docs/interact/pubsub/
- **Python threading**: https://docs.python.org/3/library/threading.html
- **Signal handling**: https://docs.python.org/3/library/signal.html
