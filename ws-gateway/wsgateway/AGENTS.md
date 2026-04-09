# ws-gateway/wsgateway — AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Mission

WebSocket Gateway bridges Redis pub/sub channels to browser WebSockets in real-time. Provides live monitoring of camera feeds, detections, alerts, and training progress.

**Responsibilities**:
- Subscribe to detection, alert, and training Redis channels
- Relay pub/sub messages to browser clients via SocketIO rooms
- Manage SocketIO namespaces and event handlers
- Handle graceful client connection/disconnection

## Architecture

### Critical: eventlet.monkey_patch()

**MUST be called before any other import** (including Flask, redis-py):

```python
import eventlet
eventlet.monkey_patch()  # ← must be FIRST

import logging
import signal
import sys
from .app import app, socketio  # etc
```

Without this, sockets and threads are not properly patched for greenlet compatibility, causing deadlocks and hangs.

### Startup Sequence (main.py)

```
main()
  ├─ eventlet.monkey_patch() [MUST BE FIRST]
  ├─ create RedisBridge(socketio)
  ├─ _startup():
  │  ├─ check Redis connectivity (ping)
  │  ├─ bridge.start() [spawns subscription threads]
  │  └─ log "ws_gateway_ready"
  ├─ register SIGTERM/SIGINT handlers
  └─ socketio.run(app, ...) [blocks on main thread]

on SIGTERM/SIGINT:
  ├─ bridge.stop()
  └─ sys.exit(0)
```

**Key pattern**: RedisBridge starts background subscription threads. Flask-SocketIO runs on main thread via eventlet.

## Modules

### main.py — Entrypoint

Minimal, critical setup:
1. `eventlet.monkey_patch()` first
2. Import app/bridge/redis after
3. Create RedisBridge instance
4. Startup with Redis check (non-fatal if fails — bridge retries)
5. Run socketio.run()

### app.py — Flask-SocketIO Factory

```python
from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, 
    cors_allowed_origins=[...],
    message_queue=REDIS_URL
)

@socketio.on("connect", namespace="/monitor")
def on_monitor_connect():
    ...

@socketio.on("subscribe_camera", namespace="/monitor")
def on_subscribe_camera(data):
    ...
```

**Namespaces**:
- `/monitor` — camera feeds and detections
- `/training` — training job progress
- `/alerts` — system alerts

### bridge.py — Redis Subscription Loop

**Class**: `RedisBridge`

Manages background subscription threads via psubscribe (pattern matching). Routes messages to SocketIO rooms.

**Methods**:
- `start()` — Spawns subscription thread
- `stop()` — Signals thread to exit
- `run()` — Main loop (called in background thread)

**Subscription Pattern**:
```python
class RedisBridge:
    def __init__(self, socketio):
        self._socketio = socketio
        self._running = False
        self._patterns = ["det:*", "training:*", "alert:*"]
    
    def start(self):
        self._running = True
        threading.Thread(target=self.run, daemon=True, name="redis-bridge").start()
    
    def run(self):
        """Main loop with reconnection."""
        backoff = 2.0
        while self._running:
            pubsub = None
            try:
                r = make_redis(for_subscribe=True)
                pubsub = r.pubsub()
                for pattern in self._patterns:
                    pubsub.psubscribe(pattern)
                logger.info("bridge_subscribed: patterns=%s", self._patterns)
                backoff = 2.0
                
                for msg in pubsub.listen():
                    if not self._running:
                        return
                    if msg.get("type") != "pmessage":
                        continue
                    
                    channel = msg["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode()
                    
                    # Route based on channel prefix
                    if channel.startswith("det:"):
                        self._route_detection(channel, msg["data"])
                    elif channel.startswith("training:"):
                        self._route_training(channel, msg["data"])
                    elif channel.startswith("alert:"):
                        self._route_alert(channel, msg["data"])
            
            except Exception as exc:
                logger.error("bridge_error: err=%s reconnect_in=%.0fs", exc, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
            finally:
                if pubsub:
                    try:
                        pubsub.close()
                    except Exception:
                        pass
    
    def _route_detection(self, channel, data):
        camera_id = channel.split(":")[1]
        room = f"camera:{camera_id}"
        self._socketio.emit("detection", json.loads(data), room=room, namespace="/monitor")
    
    def _route_training(self, channel, data):
        job_id = channel.split(":")[1]
        room = f"job:{job_id}"
        self._socketio.emit("training_progress", json.loads(data), room=room, namespace="/training")
    
    def _route_alert(self, channel, data):
        tenant_id = channel.split(":")[1]
        room = f"tenant:{tenant_id}"
        self._socketio.emit("alert", json.loads(data), room=room, namespace="/alerts")
```

**Routing Logic**:
- `det:{camera_id}` → emit to room `camera:{camera_id}` (event: `detection`)
- `training:{job_id}` → emit to room `job:{job_id}` (event: `training_progress`)
- `alert:{tenant_id}` → emit to room `tenant:{tenant_id}` (event: `alert`)

## SocketIO Namespaces & Events

### /monitor Namespace (Camera Monitoring)

**Client Events** (browser → server):
- `connect` — client joins namespace
- `subscribe_camera` → `{"camera_id": "uuid"}` — join room `camera:{camera_id}`
- `unsubscribe_camera` → `{"camera_id": "uuid"}` — leave room

**Server Events** (server → browser):
- `detection` ← from `det:{camera_id}` Redis channel
  ```json
  {
    "camera_id": "uuid",
    "timestamp": "2024-04-08T10:30:00+00:00",
    "detections": [
      {"class": "helmet", "confidence": 0.95, "bbox": [100, 150, 50, 80]}
    ],
    "has_violation": false
  }
  ```

### /training Namespace (Job Progress)

**Client Events**:
- `connect` — client joins
- `subscribe_job` → `{"job_id": "uuid"}` — join room `job:{job_id}`
- `unsubscribe_job` → `{"job_id": "uuid"}` — leave room

**Server Events**:
- `training_progress` ← from `training:{job_id}` Redis channel
  ```json
  {
    "status": "training",  // or "creating", "completed", "failed"
    "job_id": "uuid",
    "epoch": 25,
    "total_epochs": 100,
    "loss": 0.25,
    "timestamp": "..."
  }
  ```

### /alerts Namespace (System Alerts)

**Client Events**:
- `connect` — client joins
- `subscribe_tenant` → `{"tenant_id": "uuid"}` — join room `tenant:{tenant_id}`

**Server Events**:
- `alert` ← from `alert:{tenant_id}` Redis channel
  ```json
  {
    "type": "camera_offline",
    "camera_id": "uuid",
    "camera_name": "Baia 1",
    "timestamp": "..."
  }
  ```

## Configuration (config.py)

```python
PORT = 5001
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
SOCKETIO_MESSAGE_QUEUE = REDIS_URL  # for multi-worker deployments
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
```

## Redis Keys & Channels

| Channel | Type | TTL | Published By | Relayed To |
|---------|------|-----|--------------|-----------|
| `det:{camera_id}` | pubsub | N/A | inference-service | ws-gateway → `/monitor` room `camera:{camera_id}` |
| `training:{job_id}` | pubsub | N/A | training-service | ws-gateway → `/training` room `job:{job_id}` |
| `alert:{tenant_id}` | pubsub | N/A | scheduler-service | ws-gateway → `/alerts` room `tenant:{tenant_id}` |

## Thread Safety

- `RedisBridge._running` is atomic boolean (safe for thread-safe read/write)
- SocketIO emit is thread-safe (Redis message_queue handles synchronization)
- No shared state between RedisBridge and SocketIO handlers (one reads Redis, other handles HTTP)

## Error Handling

| Error | Handling |
|-------|----------|
| Redis unreachable at startup | Log warning, continue (bridge retries in background) |
| Pubsub connection fails | Exponential backoff, log error, auto-reconnect |
| JSON parsing error | Log warning, skip message, continue loop |
| SocketIO emit fails | Log warning (message is lost, no retry) |

## Logging

Key events:
- `ws_gateway_redis_ok` / `ws_gateway_redis_unavailable`
- `bridge_subscribed: patterns=[...]`
- `bridge_error: err=... reconnect_in=Xs`
- `ws_gateway_ready: port=5001`

## Integration Points

**Inbound** (Redis pub/sub):
- Subscribes to `det:*` (from inference-service)
- Subscribes to `training:*` (from training-service)
- Subscribes to `alert:*` (from scheduler-service)

**Outbound** (WebSocket to browsers):
- Emits detection events to `/monitor` namespace, room `camera:{camera_id}`
- Emits training progress to `/training` namespace, room `job:{job_id}`
- Emits alerts to `/alerts` namespace, room `tenant:{tenant_id}`

## Frontend Integration (Expected)

```typescript
// Monitor detection for camera cam-001
import io from "socket.io-client";

const socket = io("http://localhost:5001", {
  namespace: "/monitor"
});

socket.emit("subscribe_camera", { camera_id: "cam-001" });

socket.on("detection", (data) => {
  console.log("Detection:", data);
  // Render bounding boxes on video
});

// Training progress
const trainingSocket = io("http://localhost:5001", {
  namespace: "/training"
});

trainingSocket.emit("subscribe_job", { job_id: "job-123" });

trainingSocket.on("training_progress", (data) => {
  console.log("Progress:", data.epoch, "/", data.total_epochs);
});
```

## Testing Notes

```bash
# 1. Start ws-gateway
python -m wsgateway.main

# 2. Simulate detection via Redis
redis-cli PUBLISH det:cam-001 '{"camera_id":"cam-001","timestamp":"...","detections":[],"has_violation":false}'

# 3. Connect browser WebSocket
# Open http://localhost:5001 with socket.io client

# 4. Subscribe to camera
# socket.emit("subscribe_camera", {camera_id: "cam-001"})

# 5. Listen for detection
# socket.on("detection", (data) => console.log(data))
```

## Known Limitations

- No client authentication (any WebSocket connection can join any room)
- No message rate limiting (potential DoS via flood)
- No delivery guarantee (messages not acked, lost if client disconnected)
- No message history (clients miss detections while offline)
- No per-client filtering (all subscribed clients see all messages in room)
