# camera-gateway/gateway — AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Mission

Camera Gateway captures frames from RTSP streams, transcodes them to HLS via FFmpeg, and publishes frames to Redis for real-time inference.

**Responsibilities**:
- Manage FFmpeg subprocesses (RTSP → HLS transcoding)
- Monitor stream health via Redis keys
- Capture and publish frames at configurable intervals
- Handle graceful shutdown with proper cleanup

## Architecture

### Startup Sequence (main.py)

```
main()
  ├─ verify Redis connectivity (ping)
  ├─ create StreamManager()
  ├─ create HealthReporter(mgr)
  ├─ create CommandListener(mgr)
  ├─ spawn 2 daemon threads:
  │  ├─ HealthReporter.run()  → publishes service:gateway:health
  │  └─ CommandListener.run() → listens on gateway:commands
  ├─ register SIGTERM/SIGINT handlers
  └─ Flask.run() [blocks main thread]
```

### Redis Connection Pattern

Two connection types:

1. **Regular (default)**: For set/get/publish operations
   ```python
   r = make_redis()  # socket_timeout=5, decode_responses=True
   r.get("key")
   r.publish("channel", json.dumps(data))
   ```

2. **Subscription (for_subscribe=True)**: For blocking listen
   ```python
   r = make_redis(for_subscribe=True)
   pubsub = r.pubsub()
   pubsub.subscribe("channel")
   for msg in pubsub.listen():  # blocks indefinitely
       ...
   ```

## Modules

### main.py — Entrypoint

Starts Flask + 2 daemon threads (HealthReporter, CommandListener). Graceful shutdown via SIGTERM/SIGINT.

**Key pattern**: Flask runs on main thread to keep process alive. Daemon threads run listeners.

### app.py — Flask Factory

Single route: `GET /health` returns `{"status": "ok"}`.

### stream_manager.py — Core Logic

**Class**: `StreamManager` (thread-safe singleton)

**Methods**:
- `start_stream(camera_id, rtsp_url, cmd_config)` — Idempotent. Starts FFmpeg + FramePublisher thread + monitor thread.
- `stop_stream(camera_id)` — Terminates FFmpeg process, stops threads, cleans Redis keys.
- `is_active(camera_id)` → bool
- `active_camera_ids()` → list[str]

**FFmpeg Command**:
```bash
ffmpeg -y
  -rtsp_transport tcp
  -i <rtsp_url>
  -c:v libx264 -preset ultrafast -tune zerolatency
  -f hls -hls_time <segment_time> -hls_list_size <list_size>
  -hls_flags delete_segments
  /tmp/hls/<camera_id>/stream.m3u8
```

**Lifecycle**:
1. Creates `/tmp/hls/<camera_id>/` directory
2. Spawns FFmpeg subprocess → outputs to `stream.m3u8`
3. Creates FramePublisher thread (reads RTSP, publishes frames)
4. Creates monitor thread (watches `epi:stream:{camera_id}:active` key, stops stream if key vanishes)

**Thread Safety**: Uses `self._lock` for `self._active` dict access.

### command_listener.py — Redis Command Channel

**Class**: `CommandListener`

Subscribes to `gateway:commands` channel. Implements exponential backoff reconnection (2s → 60s max).

**Commands**:
```json
{"action": "start_stream", "camera_id": "...", "rtsp_url": "...", "hls_segment_time": 1, "hls_list_size": 3}
{"action": "stop_stream", "camera_id": "..."}
{"action": "ping"}
```

**Dispatch Logic**:
- `start_stream` → calls `mgr.start_stream()`
- `stop_stream` → calls `mgr.stop_stream()`
- `ping` → logs receipt
- Unknown → logs warning

**Reconnection Pattern**:
```python
backoff = 2.0
while self._running:
    try:
        r = make_redis(for_subscribe=True)
        pubsub = r.pubsub()
        pubsub.subscribe(_CHANNEL)
        backoff = 2.0  # reset
        for msg in pubsub.listen():
            self._handle(msg)
    except Exception:
        time.sleep(backoff)
        backoff = min(backoff * 2, 60.0)
    finally:
        pubsub.close()
```

### frame_publisher.py — Frame Capture & Publish

**Class**: `FramePublisher`

One instance per active camera. Runs in daemon thread. Captures frames from RTSP via OpenCV, downsamples, and publishes as base64 JPEG.

**Methods**:
- `run()` — Main loop (called in thread)
- `stop()` — Sets `_running = False`

**Frame Publishing**:
- Captures from RTSP using `cv2.VideoCapture(rtsp_url)` with buffer size 1
- Skips every `N` frames (configurable via `FRAME_EVERY_N`)
- Encodes frame as JPEG with quality 85 (configurable)
- Base64 encodes JPEG bytes
- Publishes to `frame:{camera_id}` channel

**Payload Schema**:
```json
{
  "camera_id": "uuid",
  "frame_b64": "base64-encoded-jpeg",
  "timestamp": "2024-04-08T10:30:00+00:00"
}
```

**Reconnection**:
- Exponential backoff (2s → 60s max)
- Catches `ConnectionError` when RTSP won't open
- Skips frames on every read error (continues loop)

### health_reporter.py — Health Monitoring

**Class**: `HealthReporter`

Publishes `service:gateway:health` key with TTL 60s. Signals thread/process that service is alive.

**Key**: `service:gateway:health`
**Value**: JSON with fields (e.g., `{"status": "ok", "active_cameras": 3}`)
**TTL**: 60s (renewed every 30s)

## Configuration (config.py)

```python
PORT = 5001
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
HLS_SEGMENT_TIME = 1  # seconds per segment
HLS_LIST_SIZE = 3     # number of segments to keep in playlist
FRAME_EVERY_N = 5     # publish every 5th frame
FRAME_JPEG_QUALITY = 85
```

## Redis Keys

| Key | Type | TTL | Set By | Read By |
|-----|------|-----|--------|---------|
| `service:gateway:health` | string (JSON) | 60s | HealthReporter | orchestrator |
| `epi:stream:{camera_id}:active` | string | auto-renewed | start_stream | monitor_thread |
| `frame:{camera_id}` | pubsub channel | N/A | FramePublisher | InferenceService |

## Logging

All logs include timestamp, level, module, message.

**Key events**:
- `gateway_redis_ok` / `gateway_redis_unreachable`
- `gateway_starting`
- `start_stream_ok` / `start_stream_already_active`
- `ffmpeg_started` / `ffmpeg_start_failed`
- `frame_publisher_connected` / `frame_publisher_error`
- `frame_publisher_error: camera=... err=... retry_in=Xs`
- `gateway_shutdown_signal`
- `monitor_key_gone: camera=... stopping` (stream stops when key TTL expires)

## Thread Safety

- `StreamManager._active` dict protected by `self._lock`
- Redis operations are thread-safe (redis-py handles synchronization)
- FramePublisher runs in dedicated thread per camera (no shared state)
- CommandListener runs in dedicated thread (no shared state)
- HealthReporter runs in dedicated thread (only writes to Redis)

## Error Handling

| Error | Handling |
|-------|----------|
| Redis unreachable at startup | Exit with code 1 |
| FFmpeg fails to start | Log error, FramePublisher enters retry loop |
| RTSP connection fails | FramePublisher exponential backoff |
| Frame encoding fails | Skip frame, continue |
| Redis publish fails | Log warning, continue |

## Integration Points

**Inbound**:
- Redis channel `gateway:commands` — receives start/stop commands

**Outbound**:
- Redis channel `frame:{camera_id}` — publishes frames for inference
- Redis key `service:gateway:health` — signals liveness

**Files Written**:
- `/tmp/hls/{camera_id}/stream.m3u8` — HLS playlist
- `/tmp/hls/{camera_id}/stream-*.ts` — HLS video segments

## Testing Notes

To test locally:

```bash
# 1. Start gateway
python -m gateway.main

# 2. Send start command
redis-cli PUBLISH gateway:commands '{"action":"start_stream","camera_id":"cam-001","rtsp_url":"rtsp://example.com/stream"}'

# 3. Check health
redis-cli GET service:gateway:health

# 4. Monitor frames
redis-cli SUBSCRIBE frame:cam-001

# 5. Stop
redis-cli PUBLISH gateway:commands '{"action":"stop_stream","camera_id":"cam-001"}'
```

## Known Limitations

- HLS files are stored in `/tmp/` — ephemeral storage, lost on restart
- No authentication on RTSP URLs (assumes trusted network)
- Frame publishing is best-effort (no retry if Redis down)
- No metrics collection (just logs)
