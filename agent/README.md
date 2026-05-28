# EPI Monitor Edge Agent

Local agent that connects to IP cameras on the client's network and streams
detection data to the EPI Monitor cloud (Railway) via outbound HTTPS/WSS on
port 443. No port forwarding or firewall rules required.

## What it does

- Connects to RTSP cameras on the local network
- Runs optional YOLOv8 inference locally (Edge/Hybrid modes)
- Sends detection events to the cloud via persistent WebSocket
- Auto-reconnects on disconnect with exponential backoff

## Quick Start — Docker (Recommended)

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your camera IPs and credentials

# Create .env with your secrets
echo "API_URL=wss://api-v2-production-131a.up.railway.app" > .env
echo "API_KEY=your-api-key-here" >> .env
echo "WORKER_ID=edge-site-1" >> .env

docker compose up -d
docker compose logs -f edge-agent
```

## Quick Start — Native Python

```bash
pip install -r requirements.txt
export API_URL=wss://api-v2-production-131a.up.railway.app
export API_KEY=your-api-key-here
export WORKER_ID=edge-site-1
python src/main.py
```

## Required Environment Variables

| Variable | Description |
|---|---|
| `API_URL` | WebSocket URL of the cloud API |
| `API_KEY` | Agent authentication key |
| `WORKER_ID` | Unique identifier for this agent instance |

## Optional Environment Variables

| Variable | Default | Description |
|---|---|---|
| `INFERENCE_MODE` | `edge` | `relay`, `edge`, or `hybrid` |
| `YOLO_MODEL` | `yolov8n.pt` | Path to YOLO model file |

## Camera Configuration (config.yaml)

```yaml
cameras:
  - id: cam-001
    name: "Baia 1"
    rtsp_url: "rtsp://admin:password@192.168.1.100:554/stream1"
```

See `config.yaml.example` for all options including auto-generated RTSP URLs
by manufacturer (intelbras, hikvision, generic).
