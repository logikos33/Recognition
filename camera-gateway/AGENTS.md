<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-09 -->

# camera-gateway

RTSP camera streaming to HLS via FFmpeg. Receives stream commands, manages FFmpeg processes, publishes frames to Redis.

## Purpose

Single responsibility: RTSP → HLS transcoding + frame extraction. Stateless per camera — can scale horizontally (one gateway per 3-4 cameras).

## Architecture

```
Redis (listen gateway:commands)
    ↓
command_listener.py  (subscribe to commands)
    ↓
stream_manager.py    (start/stop FFmpeg processes)
    ↓
frame_publisher.py   (extract frames, publish to Redis)
    ↓
Redis (publish frame:{camera_id})
    ↓
inference-service   (consumes frames)
```

## Package Structure

```
gateway/
├── __init__.py
├── main.py              # Entry point: create_app() + run
├── app.py               # Flask app factory
├── config.py            # Environment config
├── redis_client.py      # Redis connection
├── command_listener.py  # Subscribe to gateway:commands, dispatch
├── stream_manager.py    # FFmpeg process management
├── frame_publisher.py   # Frame extraction, Redis publish
├── health_reporter.py   # Health check endpoint
```

## Key Dependencies

- `flask>=3.0.0` — Web framework (health endpoint only)
- `redis>=5.0.0` — Command listener, frame publisher
- `opencv-python-headless>=4.9.0` — Frame extraction
- `numpy>=1.26.0` — Numerical operations

FFmpeg is installed in Dockerfile (system package).

## Redis Channels

### Subscribe
```
gateway:commands    # JSON: {"camera_id": "uuid", "action": "start|stop", ...}
```

### Publish
```
frame:{camera_id}   # JPEG frame binary data
gateway:health      # Health status JSON
```

## Command Flow

### Start Stream
```json
{
  "type": "command",
  "action": "start",
  "camera_id": "uuid-123",
  "rtsp_url": "rtsp://192.168.1.100:554/stream1",
  "output_path": "/tmp/streams/uuid-123"
}
```

stream_manager.py spawns FFmpeg:
```bash
ffmpeg -rtsp_transport tcp \
  -i "rtsp://192.168.1.100:554/stream1" \
  -c:v libx264 -preset ultrafast \
  -b:v 512k -s 640x360 \
  -hls_time 2 -hls_list_size 3 \
  "/tmp/streams/uuid-123/stream.m3u8"
```

frame_publisher.py:
1. Polls stream.m3u8 for new .ts segments
2. Extracts frame every N frames (FRAME_EVERY_N=5)
3. JPEG encode at quality 80
4. Publish to Redis `frame:{camera_id}` (binary data)

### Stop Stream
```json
{
  "type": "command",
  "action": "stop",
  "camera_id": "uuid-123"
}
```

stream_manager.py kills FFmpeg process, cleans /tmp/streams/{camera_id}.

## Endpoints

### Health
```bash
GET /health

Response (200):
{
  "status": "healthy",
  "gateway_id": "gateway-1",
  "uptime_seconds": 3600,
  "active_streams": 2,
  "streams": {
    "uuid-123": {"status": "running", "rtsp_url": "rtsp://...", "uptime_seconds": 1800},
    "uuid-456": {"status": "running", "rtsp_url": "rtsp://...", "uptime_seconds": 600}
  }
}
```

## Environment Variables

```bash
# Redis
REDIS_URL=redis://host:6379/0

# Gateway
GATEWAY_ID=gateway-1              # Unique per instance
FRAME_EVERY_N=5                   # Extract frame every N frames
FRAME_JPEG_QUALITY=80             # JPEG quality 0-100
HLS_SEGMENT_TIME=2                # Segment duration (seconds)
HLS_LIST_SIZE=3                   # Playlist size (3 segments = 6s latency)
GATEWAY_HEALTH_TTL=60             # Health key expiration (Redis)
GATEWAY_HEALTH_INTERVAL=20        # Health report interval (seconds)

# Flask
FLASK_ENV=production
PORT=8001
```

## Process Management

stream_manager.py tracks FFmpeg processes:

```python
processes = {
  "uuid-123": {
    "process": <Popen>,
    "pid": 12345,
    "output_path": "/tmp/streams/uuid-123",
    "started_at": "2026-04-09T10:00:00Z",
    "status": "running"
  }
}
```

**Auto-restart logic** (planned):
- Monitor process exit code
- If exit, retry up to 3 times (exponential backoff)
- Publish alert to Redis `alert:stream_failure`

## FFmpeg Config

Optimized for low-latency HLS:

```bash
-rtsp_transport tcp       # Reliable RTSP (not UDP)
-preset ultrafast         # CPU: fastest encoding
-b:v 512k                 # Bitrate: 512 Kbps
-s 640x360                # Resolution: 640x360
-hls_time 2               # Segment: 2 seconds
-hls_list_size 3          # Playlist: 3 segments = ~6s latency
```

Adjustable via environment variables:
- `FFMPEG_PRESET=ultrafast|superfast|veryfast|fast|medium`
- `FFMPEG_BITRATE=512k|1024k|2048k`
- `FFMPEG_RESOLUTION=640x360|1280x720|1920x1080`

## Health Check

Runs on separate thread every `GATEWAY_HEALTH_INTERVAL` seconds:

1. Check Redis connectivity (PING)
2. Count active FFmpeg processes
3. Report uptime, frame rate, disk usage
4. Publish to Redis `gateway:health` with TTL

## Scaling

Each gateway instance:
- Handles 3-4 simultaneous streams
- ~256 MB RAM (no ML models)
- ~1 CPU core per stream

**Deployment pattern**:
```bash
# gateway-1: streams for cameras 1-4
gateway-1 → SERVICE_TYPE=gateway GATEWAY_ID=gateway-1 PORT=8001

# gateway-2: streams for cameras 5-8
gateway-2 → SERVICE_TYPE=gateway GATEWAY_ID=gateway-2 PORT=8002

# gateway-3: streams for cameras 9-12
gateway-3 → SERVICE_TYPE=gateway GATEWAY_ID=gateway-3 PORT=8003
```

Each publishes to same Redis, inference-service psubscribes `frame:*`.

## Testing

```bash
# Health
curl http://localhost:8001/health

# Manual command (Redis)
redis-cli publish gateway:commands '{
  "type": "command",
  "action": "start",
  "camera_id": "test-cam-1",
  "rtsp_url": "rtsp://192.168.1.100:554/stream1",
  "output_path": "/tmp/streams/test-cam-1"
}'

# Watch frames
redis-cli --raw subscribe 'frame:test-cam-1' | \
  while read -r frame; do
    echo "$frame" | base64 -d > /tmp/frame.jpg
    echo "Frame saved: /tmp/frame.jpg"
  done
```

## Service Dependencies

- **Redis** — Command listener, frame publisher (railway plugin)
- **FFmpeg** — System dependency (installed in Dockerfile)

No dependencies on auth-service or other microservices.

## Deployment

Railway automatically runs:
```
CMD ["python", "-m", "gateway.main"]
```

Set `PORT` and `GATEWAY_ID` in Railway Variables (unique per instance).
