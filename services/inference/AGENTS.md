<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-09 -->

# inference-service

YOLOv8 real-time object detection on video frames from Redis. Consumes frames from camera-gateway, publishes detections to Redis.

## Purpose

Single responsibility: frame inference → bounding box detection. Runs continuously, stateless, scalable horizontally.

## Architecture

```
Redis (psubscribe frame:*)
    ↓
frame_consumer.py   (receive frames from camera-gateway)
    ↓
inference_engine.py (YOLOv8 inference)
    ↓
Redis (publish det:{camera_id})
    ↓
ws-gateway         (WebSocket broadcast to clients)
```

## Package Structure

```
inference/
├── __init__.py
├── main.py              # Entry point: create_app() + spawn inference threads
├── app.py               # Flask app factory (health endpoint)
├── config.py            # Environment config
├── redis_client.py      # Redis connection
├── frame_consumer.py    # Subscribed to frame:*, buffer frames
├── inference_engine.py  # YOLOv8 model loading, inference
├── health_reporter.py   # Health metrics
```

## Key Dependencies

- `flask>=3.0.0` — Health endpoint
- `redis>=5.0.0` — Frame consumer, detection publisher
- `ultralytics>=8.0.0` — YOLOv8 (includes PyTorch)
- `opencv-python-headless>=4.9.0` — Image processing
- `numpy>=1.26.0` — Numerical operations

PyTorch (~1.5GB) is heavy — Dockerfile pre-downloads YOLOv8n model at build time.

## Redis Channels

### Subscribe
```
frame:*             # Wildcard pattern subscribe (psubscribe)
                    # Messages: {camera_id: "uuid", frame: <binary jpeg>}
```

### Publish
```
det:{camera_id}     # Detection results JSON
inference:health    # Health status JSON
```

## Detection Flow

### Receive Frame
```python
frame_consumer.py (thread):
  psubscribe("frame:*")
  On message:
    {
      "channel": "frame:uuid-123",
      "camera_id": "uuid-123",
      "frame": <binary jpeg data>,
      "timestamp": "2026-04-09T10:00:00Z"
    }
```

### Inference
```python
inference_engine.py (thread):
  model = YOLO("yolov8n.pt")
  results = model(frame, conf=DETECTION_CONFIDENCE_THRESHOLD)
  
  For each detection:
    {
      "class": "helmet",
      "confidence": 0.92,
      "bbox": {
        "x1": 100,
        "y1": 50,
        "x2": 200,
        "y2": 150
      }
    }
```

### Publish Detection
```python
det_payload = {
  "camera_id": "uuid-123",
  "timestamp": "2026-04-09T10:00:00.123Z",
  "frame_shape": [480, 640, 3],
  "detections": [
    {
      "class": "helmet",
      "confidence": 0.92,
      "bbox": {"x1": 100, "y1": 50, "x2": 200, "y2": 150}
    },
    {
      "class": "no_vest",
      "confidence": 0.78,
      "bbox": {"x1": 250, "y1": 100, "x2": 350, "y2": 300}
    }
  ]
}

redis.publish(f"det:{camera_id}", json.dumps(det_payload))
```

## Endpoints

### Health
```bash
GET /health

Response (200):
{
  "status": "healthy",
  "inference_id": "inference-1",
  "yolo_model": "yolov8n.pt",
  "total_frames_processed": 4523,
  "frames_per_second": 5.2,
  "average_inference_time_ms": 195,
  "active_cameras": 4,
  "gpu_available": true,
  "memory_usage_mb": 1024
}
```

## Environment Variables

```bash
# Redis
REDIS_URL=redis://host:6379/0

# Inference
INFERENCE_ID=inference-1                          # Unique per instance
YOLO_MODEL_PATH=yolov8n.pt                        # Model: n (nano) / s / m / l / x
DETECTION_CONFIDENCE_THRESHOLD=0.5                # Confidence 0.0-1.0
INFERENCE_HEALTH_TTL=60                           # Health key expiration (Redis)
INFERENCE_HEALTH_INTERVAL=20                      # Health report interval (seconds)
INFERENCE_BATCH_SIZE=1                            # Frames per batch (1 for real-time)
INFERENCE_DEVICE=cpu                              # cpu / cuda / mps

# Flask
FLASK_ENV=production
PORT=8002
```

## YOLO Model Selection

| Model | Size (MB) | Speed | Accuracy | RAM | Notes |
|-------|-----------|-------|----------|-----|-------|
| n (nano) | 11 | 400 FPS | 26.4 mAP | 256 MB | Default, lightweight |
| s (small) | 22 | 300 FPS | 27.8 mAP | 512 MB | Better accuracy |
| m (medium) | 50 | 200 FPS | 28.8 mAP | 1.2 GB | Slower |
| l (large) | 94 | 100 FPS | 31.2 mAP | 1.8 GB | For GPU |

Default: `yolov8n.pt` (nano, fastest, sufficient for EPI detection).

## EPI Classes

YOLO detects:
- `helmet` — Hard hat
- `no_helmet` — Missing hard hat
- `vest` — Safety vest
- `no_vest` — Missing vest
- `gloves` — Safety gloves
- `no_gloves` — Missing gloves
- `safety_glasses` — Protective eyewear
- `no_safety_glasses` — Missing eyewear

(Custom YOLOv8 model trained on EPI dataset, not COCO)

## Frame Buffer Strategy

frame_consumer.py maintains per-camera buffer:

```python
frame_buffer = {
  "uuid-123": {
    "latest": <numpy array>,
    "timestamp": "2026-04-09T10:00:00.123Z",
    "ready": True
  }
}
```

inference_engine.py (separate thread per GPU/CPU):
1. Poll frame_buffer every 200ms (5 FPS)
2. Run inference on latest frame
3. Publish detection immediately
4. No blocking — skip frames if inference slower than 5 FPS

## Performance Tuning

**CPU mode (default)**:
- ~195ms per inference (5 FPS)
- One inference thread per inference-service instance
- Can run 2-3 instances per CPU core

**GPU mode (if available)**:
- ~50ms per inference (20 FPS)
- Set `INFERENCE_DEVICE=cuda`
- Requires CUDA-enabled Railway GPU service (if available)

## Health Metrics

Health reporter tracks:
- Total frames processed (cumulative)
- Frames per second (rolling average)
- Average inference time (ms)
- Number of active cameras
- GPU availability and memory
- Last frame timestamp per camera

Publishes every `INFERENCE_HEALTH_INTERVAL` seconds to `inference:health`.

## Error Handling

frame_consumer.py:
- Malformed frame → skip, log error
- Redis connection loss → exponential backoff, auto-reconnect

inference_engine.py:
- Model load failure → retry on startup (3 attempts)
- OOM (out of memory) → reduce batch size, log warning
- YOLO inference timeout (>5s) → skip frame, log error

## Scaling

Each inference-service instance:
- Handles 2-4 cameras (depending on FPS target)
- ~1.5 GB RAM (includes PyTorch)
- 1 CPU core (or GPU if available)

**Deployment pattern**:
```bash
# inference-1: cameras 1-4
inference-1 → SERVICE_TYPE=inference INFERENCE_ID=inference-1 PORT=8002

# inference-2: cameras 5-8
inference-2 → SERVICE_TYPE=inference INFERENCE_ID=inference-2 PORT=8003

# inference-3: cameras 9-12
inference-3 → SERVICE_TYPE=inference INFERENCE_ID=inference-3 PORT=8004
```

All subscribe to `frame:*`, publish to `det:{camera_id}`.

## Testing

```bash
# Health
curl http://localhost:8002/health

# Watch detections (requires redis-cli)
redis-cli --raw subscribe 'det:*' | jq '.'

# Manual frame test (decode JPEG and publish)
python3 -c "
import redis
import base64
r = redis.from_url('redis://localhost:6379')
# Simulate frame from camera-gateway
frame_data = open('/tmp/test_frame.jpg', 'rb').read()
r.publish('frame:test-cam-1', frame_data)
"

# Check health
redis-cli get inference:health | jq '.'
```

## Service Dependencies

- **Redis** — Frame consumer, detection publisher (railway plugin)
- **camera-gateway** — Sends frames to Redis

Does not depend on auth-service or other services.

## Deployment

Railway automatically runs:
```
CMD ["python", "-m", "inference.main"]
```

Set `INFERENCE_ID`, `YOLO_MODEL_PATH`, and `PORT` in Railway Variables (unique per instance).

Model downloads at build time via Dockerfile RUN. If offline at build, downloads at first startup.
