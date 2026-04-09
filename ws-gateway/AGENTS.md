<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-09 -->

# ws-gateway

WebSocket gateway bridging Redis pub/sub to browser clients. Broadcasts detections, training progress, and alerts in real-time.

## Purpose

Single responsibility: Redis pub/sub → WebSocket event streaming to connected clients. Zero business logic — pure message relay.

## Architecture

```
Redis (psubscribe det:*, training:*, alert:*)
    ↓
bridge.py           (message listener threads)
    ↓
Flask-SocketIO      (emit to connected namespaces)
    ↓
Browser (socket.io-client)
```

## Package Structure

```
wsgateway/
├── __init__.py
├── main.py          # Entry point: create_app() + socketio.run()
├── app.py           # Flask + SocketIO factory
├── config.py        # Environment config
├── redis_client.py  # Redis connection
├── bridge.py        # Redis pub/sub → SocketIO relay
```

## Key Dependencies

- `flask>=3.0.0` — Web framework
- `flask-socketio>=5.3.0` — WebSocket server
- `eventlet>=0.35.0` — Async I/O (required for SocketIO)
- `gunicorn>=21.0.0` — Production WSGI (NOT used; see below)
- `redis>=5.0.0` — Pub/sub consumer
- `PyJWT>=2.8.0` — Token validation

**Important**: This service uses `socketio.run()` (development) or `eventlet` + `gunicorn -k eventlet`, NOT standard gunicorn worker. See Deployment section.

## SocketIO Namespaces

### `/monitor` — Detection Events

Emitted to all connected clients on namespace `/monitor`:

```python
@socketio.on("connect", namespace="/monitor")
def on_monitor_connect():
    # Client connected
    return True

@socketio.on("disconnect", namespace="/monitor")
def on_monitor_disconnect():
    # Client disconnected
    pass

# Incoming events (from client)
@socketio.on("subscribe_camera", namespace="/monitor")
def on_subscribe_camera(data):
    camera_id = data.get("camera_id")
    # Client explicitly joins room for camera_id
    join_room(f"camera:{camera_id}", namespace="/monitor")
    emit("subscribed", {"camera_id": camera_id})

@socketio.on("unsubscribe_camera", namespace="/monitor")
def on_unsubscribe_camera(data):
    camera_id = data.get("camera_id")
    leave_room(f"camera:{camera_id}", namespace="/monitor")
    emit("unsubscribed", {"camera_id": camera_id})
```

**Broadcast events** (from Redis bridge.py):

```python
# Detection event (from Redis det:{camera_id})
socketio.emit("detection", {
  "camera_id": "uuid-123",
  "timestamp": "2026-04-09T10:00:00.123Z",
  "detections": [
    {"class": "helmet", "confidence": 0.92, "bbox": {...}},
    {"class": "no_vest", "confidence": 0.78, "bbox": {...}}
  ]
}, room=f"camera:{camera_id}", namespace="/monitor")

# Alert event (from Redis alert:{type})
socketio.emit("alert", {
  "type": "stream_failure",
  "camera_id": "uuid-123",
  "message": "Stream disconnected",
  "timestamp": "2026-04-09T10:00:00Z"
}, namespace="/monitor")
```

### `/training` — Training Progress

Emitted to all connected clients on namespace `/training`:

```python
@socketio.on("connect", namespace="/training")
def on_training_connect():
    return True

# Incoming events
@socketio.on("subscribe_job", namespace="/training")
def on_subscribe_job(data):
    job_id = data.get("job_id")
    join_room(f"job:{job_id}", namespace="/training")
    emit("subscribed", {"job_id": job_id})

# Broadcast events (from Redis training:{job_id})
socketio.emit("progress", {
  "job_id": "run-123",
  "epoch": 5,
  "total_epochs": 50,
  "loss": 0.234,
  "accuracy": 0.88,
  "eta_seconds": 1200
}, room=f"job:{job_id}", namespace="/training")
```

## Redis Channels

### Subscribe (psubscribe pattern)

```
det:*           # From inference-service (detections)
alert:*         # From services (alerts/errors)
training:*      # From training-service (progress)
```

## Client Integration (Browser)

```typescript
import { io } from "socket.io-client"

const monitor = io("http://localhost:8003/monitor", {
  extraHeaders: {
    Authorization: `Bearer ${token}`
  }
})

// Subscribe to camera
monitor.emit("subscribe_camera", { camera_id: "uuid-123" })

// Listen for detections
monitor.on("detection", (data) => {
  console.log("Detections:", data.detections)
  // Draw bounding boxes on canvas
  renderDetections(data)
})

// Listen for alerts
monitor.on("alert", (data) => {
  console.log("Alert:", data.message)
  // Show toast notification
})

// Disconnect
monitor.disconnect()
```

## Environment Variables

```bash
# Redis
REDIS_URL=redis://host:6379/0

# JWT validation
JWT_SECRET_KEY=min-32-chars-random-secret    # Must match auth-service
JWT_ALGORITHM=HS256

# CORS
CORS_ORIGINS=http://localhost:5173,https://app.example.com

# Flask
FLASK_ENV=production
SECRET_KEY=min-32-chars-random-secret
PORT=8003
```

## Endpoints

### GET /health

```bash
curl http://localhost:8003/health

Response (200):
{
  "status": "healthy",
  "websocket": "ready",
  "redis": "connected",
  "connected_clients": 5,
  "namespaces": {
    "/monitor": {"rooms": 3, "clients": 4},
    "/training": {"rooms": 1, "clients": 1}
  }
}
```

## Authentication

On SocketIO `connect`, client MUST send JWT token:

```typescript
const socket = io(url, {
  extraHeaders: {
    Authorization: `Bearer ${token}`
  }
})
```

bridge.py validates token before accepting messages. Invalid tokens → `disconnect`.

## Message Flow Example

1. **camera-gateway** extracts frame from camera 123
2. **inference-service** runs YOLOv8 inference
3. Publishes detection to Redis: `det:uuid-123` → `{"detections": [...]}`
4. **ws-gateway** bridge.py listens on `det:*`
5. Redis message triggers: `on_det_message(channel, data)`
6. SocketIO emits to room `camera:uuid-123`:
   ```python
   socketio.emit("detection", data, room=f"camera:{camera_id}", namespace="/monitor")
   ```
7. Browser clients subscribed to `camera:uuid-123` receive event
8. Canvas renders bounding boxes

## Scaling

Each ws-gateway instance:
- ~50 MB RAM (no ML/FFmpeg)
- Handles ~500 concurrent WebSocket connections
- Uses eventlet for async I/O

**Deployment pattern** (sticky sessions not required):

```bash
# ws-gateway-1
ws-gateway-1 → SERVICE_TYPE=ws FLASK_ENV=production PORT=8003

# ws-gateway-2 (load balanced)
ws-gateway-2 → SERVICE_TYPE=ws FLASK_ENV=production PORT=8003

# Redis message_queue ensures broadcast reaches all instances
socketio = SocketIO(app, message_queue=REDIS_URL)
```

All instances share Redis message queue — SocketIO ensures every client gets the message.

## Testing

```bash
# Health
curl http://localhost:8003/health

# WebSocket test (using wscat)
npm install -g wscat
wscat -c "ws://localhost:8003/monitor" --header "Authorization: Bearer YOUR_TOKEN"

# Inside wscat:
{"emit": ["subscribe_camera", {"camera_id": "test-cam-1"}]}
{"emit": ["detection", {"camera_id": "test-cam-1", "detections": [...]}]}
```

## Common Issues

**"Authorization: Bearer token header not received"**
- Client MUST include token in `extraHeaders`, not as query param
- SocketIO doesn't use default Authorization header

**"Clients not receiving messages"**
- Check Redis connection: `redis-cli ping`
- Verify room name: `room=f"camera:{camera_id}"`
- Check namespace: clients must connect to correct namespace (`/monitor` vs `/training`)

**"Latency high"**
- ws-gateway is stateless — no local buffering
- Latency = frame extraction time + inference time + network time
- If >3s, check inference-service performance

## Deployment

Railway automatically runs:
```
CMD ["python", "-m", "wsgateway.main"]
```

**Important**: `main.py` uses `socketio.run()` with eventlet, NOT gunicorn. If you override, use:

```bash
gunicorn -w 1 -k eventlet --worker-connections 1000 \
  --bind 0.0.0.0:$PORT \
  wsgateway.app:app
```

(Single worker `-w 1` — eventlet handles concurrency)
