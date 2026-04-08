# Edge Agent Architecture — EPI Monitor V2

## The Problem: NAT Traversal for IP Cameras

IP cameras at client sites (factories, warehouses, loading bays) are connected to
the client's internal network. They are behind NAT routers and firewalls, which means
the cloud API running on Railway has no direct way to reach them.

The naive solution — opening inbound ports and setting up port forwarding — is
impractical in enterprise environments: it requires network admin approval, introduces
security risks, and breaks every time the camera or router is replaced.

## The Solution: Edge Agent (Outbound-Only)

The Edge Agent is a lightweight process that runs **inside the client's network**,
alongside the cameras. It initiates all connections outbound over HTTPS/WSS on port 443.
No inbound ports. No firewall rules. No NAT configuration.

The agent connects to cameras via RTSP on the local network (LAN speeds, no latency),
performs optional local inference, and pushes results to the cloud via a persistent
WebSocket connection and direct uploads to Cloudflare R2.

```
Cliente Network                    Cloud (Railway)
+-------------------+              +-------------------+
| IP Camera (RTSP)  |              | API-V2 (Flask)    |
|     |             |              |        |          |
| Edge Agent        |--WSS:443---> | WebSocket Server  |
|  - Camera Manager |              |        |          |
|  - YOLO (optional)|              | Redis pub/sub     |
|  - Cloud Connector|              |        |          |
|  - R2 Uploader    |--HTTPS:443-> | Cloudflare R2     |
+-------------------+              +-------------------+
```

All traffic exits the client network on port 443 (standard HTTPS/WSS). No special
firewall rules required. Works through corporate proxies.

---

## Three Operation Modes

### Relay Mode

The agent captures RTSP frames, transcodes them to HLS segments via FFmpeg, and
pushes the `.ts` segment files to Cloudflare R2 using presigned URLs. The cloud
frontend plays back the HLS stream directly from R2.

- **Best for**: Sites where the cloud needs live video preview
- **Bandwidth**: High (full video stream uploaded)
- **CPU on edge**: Medium (FFmpeg transcoding)
- **Cloud inference**: Detection runs on Worker service in the cloud

### Edge Mode

The agent runs YOLOv8 inference locally on each frame at 5 FPS. Only detection
events and small evidence JPEG frames (~10KB each) are sent to the cloud via WebSocket.
No raw video is uploaded.

- **Best for**: Sites with limited upload bandwidth (common in industrial settings)
- **Bandwidth**: Very low (~5KB/s per camera for detection events only)
- **CPU on edge**: High (YOLO inference)
- **Latency**: Lowest — detection happens on LAN, no upload round-trip

### Hybrid Mode (Recommended for Production)

Edge inference for real-time detection events + Relay for HLS preview. The agent
runs YOLO locally and simultaneously pushes HLS segments to R2 so operators can
watch the live feed in the dashboard while receiving instant detection alerts.

- **Best for**: Full-featured production deployments
- **Bandwidth**: Medium (HLS for preview, tiny events for detections)
- **CPU on edge**: High (both FFmpeg and YOLO)

---

## Component Architecture

### `camera_manager.py`

Manages RTSP connections for all configured cameras. Each camera runs in its own
thread with automatic reconnect on failure (2s delay between attempts). Supports
direct RTSP URLs or auto-generated URLs from manufacturer + IP + credentials.

Supports ONVIF discovery for automatic camera detection on the local network.

### `cloud_connector.py`

Maintains a single persistent WebSocket connection to the cloud API. Features:

- **Heartbeat**: Sends ping every 30 seconds to keep connection alive through NAT
- **Exponential backoff**: Reconnect delay starts at 2s, doubles up to 60s max
- **Outbound queue**: `asyncio.Queue(maxsize=1000)` buffers messages when offline,
  drops oldest when full (detection events are ephemeral — stale data is worthless)
- **Authentication**: `X-Agent-ID` and `X-API-Key` headers on every connection

### `inference_engine.py`

Optional YOLOv8 inference running locally. Loads model at startup. If `ultralytics`
is not installed, inference is silently disabled (Relay mode still works). Returns
structured detection dicts with class name, confidence, and bounding box coordinates.

### `config.py`

Loads configuration from two sources in priority order:
1. Environment variables (`API_URL`, `API_KEY`, `WORKER_ID`, `INFERENCE_MODE`)
2. `config.yaml` file mounted as a volume in Docker

This allows Docker deployments to use env vars for secrets and YAML for camera lists.

---

## Installation

### Docker (Recommended)

```bash
# 1. Copy and edit configuration
cp config.yaml.example config.yaml
# Edit config.yaml: set your camera IPs, credentials, etc.

# 2. Create .env with secrets (never commit this)
echo "API_URL=wss://api-v2-production-131a.up.railway.app" > .env
echo "API_KEY=your-api-key-here" >> .env
echo "WORKER_ID=edge-site-1" >> .env

# 3. Build and run
docker compose up -d

# 4. Check logs
docker compose logs -f edge-agent
```

### Native Python

```bash
# Python 3.11+ required
pip install -r requirements.txt

# Install FFmpeg (Ubuntu/Debian)
apt-get install ffmpeg

# Set environment variables
export API_URL=wss://api-v2-production-131a.up.railway.app
export API_KEY=your-api-key-here
export WORKER_ID=edge-site-1

# Run
python src/main.py
```

---

## Security Considerations

1. **No inbound ports**: The agent never listens on any port. All connections are
   outbound only. Zero attack surface from the internet.

2. **API Key authentication**: Every WebSocket connection sends `X-API-Key` header.
   Keys are scoped per agent and can be revoked from the cloud dashboard.

3. **TLS only**: All cloud communication uses TLS 1.2+ (WSS and HTTPS). Camera
   credentials never leave the agent process — only detection metadata is sent to cloud.

4. **Camera passwords**: Stored only in `config.yaml` (mounted as read-only volume).
   Never logged, never sent to cloud.

5. **Evidence frames**: JPEG thumbnails sent as evidence are small crops of detected
   objects, not full frames, minimizing data exposure.

6. **Principle of least privilege**: The Docker container runs as a non-root user.
   Only the `config.yaml` and `models/` directories are mounted from the host.

---

## Scaling

One Edge Agent instance handles 3-5 cameras in Edge/Hybrid mode (limited by YOLO
inference throughput). For sites with more cameras:

- Run multiple agents with different `WORKER_ID` values
- Split camera assignments across agent instances in `config.yaml`
- Each agent maintains its own independent WebSocket connection to the cloud
