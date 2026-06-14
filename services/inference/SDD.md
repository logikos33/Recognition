# SDD — Software Design Document
# services/inference — Motor de Inferência YOLO

**Versão:** 1.0
**Data:** 2026-05-28
**Status:** Ativo (backend Ultralytics) / Planejado (backend DeepStream, Fase 5)
**Serviço Railway:** `inference-service`

---

## Visão Geral

O `services/inference` é responsável pela inferência YOLO em tempo real sobre frames de câmeras IP. Consome frames publicados no Redis, processa com YOLOv8 + DeepSORT anti-duplicate, e publica detecções para consumo pelo `socket_bridge` da API (que repassa ao frontend via WebSocket).

**Dois backends suportados:**
- **Ultralytics** (`INFERENCE_ENGINE=ultralytics`): Python puro, suporta CPU e GPU. Padrão em dev, CI, e modo cloud.
- **DeepStream** (`INFERENCE_ENGINE=deepstream`): Pipeline GStreamer + TensorRT INT8. Exclusivo para edge com GPU NVIDIA. Fase 5.

O canal Redis de saída (`det:{camera_id}`) é idêntico em ambos os backends — o `socket_bridge` não precisa ser alterado independentemente do backend usado.

---

## Componentes

### 1. Entry Point (`inference/main.py`)

```python
# Seleciona backend com base em INFERENCE_ENGINE
engine_type = os.environ.get("INFERENCE_ENGINE", "ultralytics")

if engine_type == "ultralytics":
    from .inference_engine import InferenceEngine
    engine = InferenceEngine()
elif engine_type == "deepstream":
    from .backends.deepstream.pipeline import DeepStreamPipeline
    engine = DeepStreamPipeline()
else:
    raise ValueError(f"Unknown INFERENCE_ENGINE: {engine_type}")

# Inicia frame_consumer em loop
frame_consumer.start(engine)
```

Também inicia:
- `model_watcher.py` em thread para reload automático de modelos
- `app.py` (Flask `/health`) em thread separada

### 2. Frame Consumer (`inference/frame_consumer.py`)

Assina Redis com `for_subscribe=True` (socket_timeout=None, bloqueante):

```python
r = make_redis(for_subscribe=True)
pubsub = r.pubsub()
pubsub.psubscribe("frame:*")      # frame:{camera_id}

for message in pubsub.listen():
    if message["type"] != "pmessage":
        continue
    camera_id = message["channel"].split(":", 1)[1]
    payload = json.loads(message["data"])
    frame_b64 = payload["frame_b64"]
    timestamp = payload["timestamp"]
    engine.process_frame(camera_id, frame_b64, timestamp)
```

**Controle de FPS:** se o consumer receber frames mais rápido que o `FRAME_RATE_TARGET` (padrão 5 FPS), descarta frames intermediários com base em timestamp.

### 3. Inference Engine — Backend Ultralytics (`inference/inference_engine.py`)

```
InferenceEngine
  ├── __init__()
  │   ├── _r = make_redis()             # conexão para PUBLISH
  │   └── _model = _load_model(path)   # carrega YOLOv8 com cache
  │
  └── process_frame(camera_id, frame_b64, timestamp)
        ├── base64.b64decode(frame_b64) → bytes
        ├── cv2.imdecode → numpy array
        ├── model.predict(frame, conf=threshold, verbose=False)
        ├── _parse_results(results) → list[Detection]
        ├── tracker = _get_tracker(camera_id)  → DeepSORT por câmera
        ├── tracker.update_tracks(detections, frame)
        ├── _build_payload(camera_id, tracks, timestamp)
        └── r.publish(f"det:{camera_id}", json.dumps(payload))
```

**Cache de modelos** (`_model_cache: dict[str, YOLO]`):
- Thread-safe via `_model_lock`
- Cache em memória por `model_path`
- Invalidado por `model_watcher` ao detectar novo arquivo

**Cache de trackers** (`_deepsort_trackers: dict[str, DeepSort]`):
- Thread-safe via `_deepsort_lock`
- Um tracker por `camera_id` — evita contaminação cross-câmera
- `max_age=30`, `n_init=3`

### 4. Model Watcher (`inference/model_watcher.py`)

Monitora `YOLO_MODELS_DIR` (padrão `/models`) em thread com `watchdog` ou polling:

```
Loop a cada 10s:
  → lista arquivos .pt e .engine em YOLO_MODELS_DIR
  → compara SHA256 com estado anterior
  → se novo arquivo detectado: invalida _model_cache[path]
  → próximo frame usa o modelo atualizado (lazy load)
```

No modo Edge, o `edge-sync-agent` coloca novos modelos neste diretório após download da cloud.

### 5. Redis Client (`inference/redis_client.py`)

```python
make_redis(for_subscribe=False) → redis.Redis

# Para PUBLISH (timeout curto):
r = make_redis()               # socket_timeout=5

# Para SUBSCRIBE (bloqueante):
r = make_redis(for_subscribe=True)   # socket_timeout=None, keepalive=True
```

### 6. Health Reporter (`inference/health_reporter.py`)

Métricas expostas em `GET /health`:

```json
{
  "status": "ok",
  "engine": "ultralytics",
  "frames_processed": 45231,
  "detections_published": 1823,
  "models_loaded": ["yolov8n.pt", "yolov8s-rvb-v3.pt"],
  "cameras_active": 8,
  "uptime_s": 86400,
  "fps_actual": 4.8
}
```

---

## Interfaces

### Entrada (Redis Subscribe)

**Canal:** `frame:{camera_id}`

```json
{
  "frame_b64": "<JPEG base64>",
  "camera_id": "uuid-da-camera",
  "timestamp": "2026-05-28T14:32:00.123Z",
  "model_path": "yolov8n.pt"
}
```

### Saída (Redis Publish)

**Canal:** `det:{camera_id}`

```json
{
  "camera_id": "uuid-da-camera",
  "timestamp": "2026-05-28T14:32:00.456Z",
  "detections": [
    {
      "class": "no_helmet",
      "confidence": 0.87,
      "bbox": [120, 45, 340, 280],
      "track_id": 42
    }
  ],
  "has_violation": true,
  "model_path": "yolov8n.pt",
  "inference_ms": 23.4
}
```

**Consumidor:** `socket_bridge` na API assina `det:*` e faz broadcast via SocketIO.

---

## Fluxo de Dados

### Backend Ultralytics (atual)

```
frame:{camera_id} (Redis)
  │
  ▼
frame_consumer.py  →  InferenceEngine.process_frame()
                              │
                    cv2.imdecode (JPEG → numpy)
                              │
                    YOLOv8.predict() → bounding boxes + classes + confidence
                              │
                    DeepSORT.update_tracks() → track_ids únicos
                              │
                    build_payload() → {detections[], has_violation}
                              │
                    r.publish(f"det:{camera_id}", payload)
                              │
                              ▼
                        det:{camera_id} (Redis)
                              │
                              ▼
                    socket_bridge (api-v3) → SocketIO → Frontend
```

### Backend DeepStream (Fase 5)

```
RTSP (DVR) → MediaMTX → nvurisrcbin
                              │
                       nvstreammux (batch 4 streams)
                              │
                       nvinfer (TensorRT INT8 engine)
                              │
                       nvtracker (DeepSORT acelerado GPU)
                              │
                       nvdsosd (overlay metadata)
                              │
                       custom appsink → Python callback
                              │
                    r.publish(f"det:{camera_id}", payload)
                              │
                        det:{camera_id} (Redis local)
                              │
                    edge-sync-agent → batch POST → api-v3 (cloud)
```

---

## Dependências

| Dependência | Backend | Uso |
|------------|---------|-----|
| `ultralytics` | Ultralytics | YOLOv8 inference |
| `opencv-python-headless` | Ultralytics | Decode de frames JPEG |
| `deep_sort_realtime` | Ultralytics | Anti-duplicate tracking |
| `numpy` | Ambos | Operações em arrays de imagem |
| `redis` | Ambos | pub/sub para frames e detecções |
| `torch` | Ultralytics | Backend de inferência PyTorch |
| `DeepStream SDK 6.x` | DeepStream | Pipeline GStreamer + TensorRT |
| `Flask` | Ambos | Endpoint /health |

**Variáveis de ambiente:**
```
REDIS_URL                          # obrigatório
INFERENCE_ENGINE=ultralytics       # obrigatório (default: ultralytics)
YOLO_MODEL_PATH=yolov8n.pt        # modelo padrão
YOLO_MODELS_DIR=/models           # diretório de modelos
DETECTION_CONFIDENCE_THRESHOLD=0.5
FRAME_RATE_TARGET=5
```

---

## Decisões Relevantes

| ADR | Impacto |
|-----|---------|
| ADR-0001 | DeepStream no edge (Fase 5); Ultralytics no dev/cloud |
| ADR-0003 | Redis pub/sub: `frame:{camera_id}` entrada, `det:{camera_id}` saída |
| ADR-0015 | DeepSORT por câmera para `track_id` únicos anti-duplicate |
| ADR-0002 | Modelos treinados via Roboflow workspace; formato `.pt` para Ultralytics, `.engine` para TensorRT |

---

## Considerações de Performance

**Ultralytics (dev/cloud):**
- GPU: ~23ms por frame (RTX série 30+)
- CPU: ~400ms por frame (inviável para > 2 câmeras a 5 FPS)
- Cache de modelo evita reload a cada frame (crítico para latência)

**DeepStream (edge, Fase 5):**
- TensorRT INT8: ~5ms por frame por stream
- nvstreammux suporta batch de até 30 streams simultâneos
- RTX 5060 Ti: capacidade estimada de 28 câmeras a 5 FPS com margem

**Memória:**
- `yolov8n.pt`: ~6MB em memória
- `yolov8s.pt`: ~22MB em memória
- Um DeepSORT tracker por câmera: ~2MB/câmera

---

## Graceful Shutdown

Ao receber SIGTERM:
1. `frame_consumer` para de aceitar novos frames (fecha pubsub)
2. Aguarda frame em processamento completar (timeout 5s)
3. Publica métricas finais no health reporter
4. Fecha conexão Redis
5. Encerra processo

Isso garante que o último frame processado seja publicado antes do container parar.
