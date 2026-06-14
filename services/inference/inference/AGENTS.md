# inference-service/inference — AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Mission

Inference Service consumes frames from Redis, runs YOLOv8 object detection, and publishes detections for real-time monitoring and alerting.

**Responsibilities**:
- Load YOLOv8 model from disk or cache
- Subscribe to frame stream via Redis pubsub
- Run inference on received frames
- Publish detection results to Redis channels
- Report service health

## Architecture

### Startup Sequence (main.py)

```
main()
  ├─ verify Redis connectivity (ping)
  ├─ load InferenceEngine (YOLO model from disk or cache)
  ├─ set engine in Flask app context
  ├─ create HealthReporter(engine)
  ├─ create FrameConsumer(engine)
  ├─ spawn 2 daemon threads:
  │  ├─ HealthReporter.run()  → publishes service:inference:health
  │  └─ FrameConsumer.run()   → listens on frame:*
  ├─ register SIGTERM/SIGINT handlers
  └─ Flask.run() [blocks main thread, serves /health]
```

### Model Loading

YOLO loads via Ultralytics library with cache at `/tmp/epi_models/`:

```python
from ultralytics import YOLO
cache_dir = "/tmp/epi_models"
os.makedirs(cache_dir, exist_ok=True)
model = YOLO("yolov8n.pt")  # or custom path
```

**Thread Safety**: Uses `_model_lock` to ensure only one thread loads the model. Subsequent threads get cached instance.

**Loading Time**: ~30s (why `healthcheckTimeout=300` in Railway config).

## Modules

### main.py — Entrypoint

Starts Flask + 2 daemon threads. Graceful shutdown via SIGTERM/SIGINT.

**Key pattern**: Same as camera-gateway — Flask on main thread, listeners in daemon threads.

### app.py — Flask Factory

Single route: `GET /health`

Returns `{"status": "ok"}` if inference engine is ready, else `503`.

**Context Function**: `set_engine(engine)` stores engine in Flask `g` object for request context.

### frame_consumer.py — Redis Subscription Loop

**Class**: `FrameConsumer`

Subscribes to `frame:*` pattern via psubscribe (pattern matching). Implements exponential backoff reconnection.

**Subscription Pattern**:
```python
r = make_redis(for_subscribe=True)
pubsub = r.pubsub()
pubsub.psubscribe("frame:*")
for msg in pubsub.listen():
    if msg.get("type") == "pmessage":
        channel = msg["channel"]  # e.g., b"frame:cam-001"
        camera_id = channel.split(":")[1]
        data = json.loads(msg["data"])
        engine.process_frame(camera_id, data["frame_b64"], data["timestamp"])
```

**Input Channel**: `frame:{camera_id}`

**Input Payload**:
```json
{
  "camera_id": "uuid",
  "frame_b64": "base64-encoded-jpeg",
  "timestamp": "2024-04-08T10:30:00+00:00"
}
```

**Reconnection Logic**: Same exponential backoff as camera-gateway (2s → 60s).

**Error Handling**: 
- Frames that fail to decode → logged, skipped
- JSON parsing errors → logged, skipped
- Inference errors → logged, skipped

### inference_engine.py — YOLO Processing

**Class**: `InferenceEngine`

Processes frames and publishes detections.

**Methods**:
- `is_ready()` → bool (returns True if model loaded successfully)
- `process_frame(camera_id, frame_b64, timestamp)` → publishes detection
- `frames_processed` (property) → int (counter)

**Inference Pipeline**:
1. `_decode_frame(frame_b64)` — base64 → JPEG → OpenCV frame (or None on error)
2. `_run_yolo(frame)` — runs model, extracts detections
3. `_publish(camera_id, detections, timestamp)` — publishes to Redis

**YOLO Output Parsing**:
```python
results = model(frame, conf=DETECTION_CONFIDENCE, verbose=False)
detections = []
for r in results:
    for box in r.boxes:
        cls_name = r.names[int(box.cls)]
        conf = float(box.conf)
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        detections.append({
            "class": cls_name,
            "confidence": round(conf, 3),
            "bbox": [x1, y1, x2 - x1, y2 - y1]  # [x, y, w, h]
        })
```

**Detection Publishing**:
- Channel: `det:{camera_id}`
- Checks if any detection class starts with `no_` (violation flag)
- Publishes JSON with all detections + violation flag

**Output Payload**:
```json
{
  "camera_id": "uuid",
  "timestamp": "2024-04-08T10:30:00+00:00",
  "detections": [
    {
      "class": "helmet",
      "confidence": 0.95,
      "bbox": [100, 150, 50, 80]
    },
    {
      "class": "no_vest",
      "confidence": 0.87,
      "bbox": [200, 300, 60, 100]
    }
  ],
  "has_violation": true
}
```

### health_reporter.py — Health Monitoring

**Class**: `HealthReporter`

Publishes `service:inference:health` key with TTL 60s.

**Value**: JSON with `{"status": "ok", "frames_processed": N}`

**Renewal**: Every 30s (TTL 60s).

## Configuration (config.py)

```python
PORT = 5001
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
YOLO_MODEL_PATH = os.environ.get("YOLO_MODEL_PATH", "yolov8n.pt")
DETECTION_CONFIDENCE = float(os.environ.get("DETECTION_CONFIDENCE", 0.5))
```

## Redis Keys & Channels

| Key/Channel | Type | TTL | Set By | Read By |
|-------------|------|-----|--------|---------|
| `service:inference:health` | string (JSON) | 60s | HealthReporter | orchestrator |
| `frame:*` | pubsub pattern | N/A | camera-gateway (FramePublisher) | FrameConsumer |
| `det:{camera_id}` | pubsub channel | N/A | InferenceEngine | ws-gateway (socket_bridge) |

## Logging

Key events:
- `inference_redis_ok` / `inference_redis_unreachable`
- `inference_loading_model: <path>`
- `inference_model_ready: ready=True/False`
- `inference_starting: port=5001`
- `frame_consumer_subscribed: pattern=frame:*`
- `frame_consumer_msg_error: ...` (non-fatal, continues loop)
- `frame_consumer_error: err=... reconnect_in=Xs`
- `process_frame_error: camera=... err=...`
- `yolo_model_loading: <path>`
- `yolo_model_loaded: <path>`
- `inference_shutdown_signal`

## Thread Safety

- Model loading via `_model_lock` (one-time, then cached)
- Redis operations are thread-safe (redis-py)
- FrameConsumer runs in dedicated thread (no shared state)
- HealthReporter runs in dedicated thread (only writes to Redis)

## Error Handling

| Error | Handling |
|-------|----------|
| Redis unreachable at startup | Log warning, continue (health reports unavailable) |
| YOLO model not found/installed | Model = None, is_ready() returns False, /health returns 503 |
| Frame decode fails | Log error, skip frame, continue |
| YOLO inference fails | Log error, skip frame, continue |
| Redis publish fails | Log warning, continue |

## Integration Points

**Inbound**:
- Redis pattern `frame:*` — receives frames from camera-gateway

**Outbound**:
- Redis channels `det:{camera_id}` — publishes detections for socket_bridge
- Redis key `service:inference:health` — signals liveness

## Performance Characteristics

- **Inference latency**: ~100-200ms per frame (YOLOv8 nano on CPU)
- **Frame throughput**: ~5-10 FPS depending on frame skipping config
- **Memory**: ~1.5GB (YOLO model + OpenCV buffers)
- **CPU**: 1-2 cores (single-threaded inference)

## Testing Notes

```bash
# 1. Start inference service
python -m inference.main

# 2. Publish test frame
redis-cli PUBLISH frame:cam-001 '{"camera_id":"cam-001","frame_b64":"...","timestamp":"2024-04-08T10:30:00+00:00"}'

# 3. Monitor detections
redis-cli SUBSCRIBE det:cam-001

# 4. Check health
redis-cli GET service:inference:health
```

## Known Limitations

- Inference is **not** real-time (runs at frame publish rate, not camera FPS)
- No GPU support (CPU-only, slow on high frame rates)
- No caching of detections (recomputes every frame)
- Model must fit in memory (no quantization/pruning)
- No metrics/monitoring dashboards (logs only)
