# AGENT.md — services/inference

**Serviço:** Inference Service — Motor de inferência YOLO em tempo real
**Responsabilidade:** Consumir frames de câmeras, rodar YOLO, publicar detecções no Redis
**Railway service:** `inference-service` (cloud-only mode)

---

## Propósito

Executa inferência YOLO frame-a-frame sobre streams de câmeras. Consome frames do Redis (`frame:{camera_id}`), processa com YOLOv8 + DeepSORT e publica detecções em `det:{camera_id}`. O `socket_bridge` na API assina `det:*` e repassa via WebSocket para o frontend — sem mudanças necessárias nessa ponte.

No modo Edge (Fase 5), este serviço é substituído por pipelines DeepStream com TensorRT INT8 rodando no mini PC do cliente.

---

## Stack

| Componente | Dev / Cloud | Edge (Fase 5) |
|-----------|-------------|---------------|
| Runtime | Python 3.11 | GStreamer + DeepStream 6.x |
| Modelo | Ultralytics YOLOv8 | TensorRT INT8 (engine compilado) |
| Tracking | DeepSORT (`deep_sort_realtime`) | nvtracker plugin |
| Mensageria | Redis pub/sub | Redis local |
| Backend seleção | `INFERENCE_ENGINE=ultralytics` | `INFERENCE_ENGINE=deepstream` |

---

## Variável de Controle: `INFERENCE_ENGINE`

```
INFERENCE_ENGINE=ultralytics   # padrão — dev, cloud, CI
INFERENCE_ENGINE=deepstream    # edge com GPU NVIDIA (Fase 5)
```

O `main.py` instancia o backend correto com base nessa variável. Ambos os backends publicam no mesmo canal Redis com o mesmo schema de evento.

---

## Estrutura de Diretórios

```
services/inference/
├── inference/
│   ├── __init__.py
│   ├── app.py               # Flask app para /health endpoint
│   ├── config.py            # Lê variáveis de ambiente
│   ├── main.py              # Entry point: seleciona backend, inicia loop
│   ├── frame_consumer.py    # Assina frame:{camera_id} no Redis
│   ├── inference_engine.py  # Backend Ultralytics YOLOv8 + DeepSORT
│   ├── model_watcher.py     # Detecta novos modelos e recarrega sem downtime
│   ├── redis_client.py      # make_redis() factory (publish / subscribe)
│   └── health_reporter.py   # Métricas: frames/s, detecções, modelos ativos
├── Dockerfile
├── railway.toml
├── requirements.txt
├── AGENT.md                 # Este arquivo
└── SDD.md
```

---

## Fluxo de Dados

```
Redis SUBSCRIBE frame:{camera_id}
  → frame_consumer.py recebe mensagem (JPEG base64 + metadata)
  → inference_engine.py:
      1. Decodifica frame base64 → numpy array (cv2)
      2. _load_model(model_path) → YOLOv8 com cache em /tmp/epi_models/
      3. model.predict(frame, conf=threshold) → lista de bounding boxes
      4. _get_tracker(camera_id) → instância DeepSORT por câmera
      5. deepsort.update_tracks(detections) → track_ids únicos
      6. Monta payload de evento
  → redis PUBLISH det:{camera_id} <payload JSON>
```

---

## Schema de Evento Publicado

Canal Redis: `det:{camera_id}`

```json
{
  "camera_id": "uuid-da-camera",
  "timestamp": "2026-05-28T14:32:00.123Z",
  "detections": [
    {
      "class": "no_helmet",
      "confidence": 0.87,
      "bbox": [x1, y1, x2, y2],
      "track_id": 42
    }
  ],
  "has_violation": true
}
```

**Campos:**
- `class`: nome da classe YOLO (ex.: `helmet`, `no_helmet`, `vest`, `no_vest`)
- `confidence`: float 0.0–1.0
- `bbox`: coordenadas absolutas em pixels `[x1, y1, x2, y2]`
- `track_id`: ID único do DeepSORT para o objeto (anti-duplicate counting)
- `has_violation`: true se qualquer detecção é classe de violação (no_helmet, no_vest, etc.)

---

## DeepSORT: Anti-Duplicate

Um tracker DeepSORT por `camera_id` (isolados por dicionário thread-safe `_deepsort_trackers`). Parâmetros padrão:
- `max_age=30`: frames sem detecção antes de remover track
- `n_init=3`: frames necessários para confirmar novo track

Se `deep_sort_realtime` não estiver instalado (CI light), tracking é desabilitado graciosamente (log warning, `track_id=None`).

---

## Gerenciamento de Modelos

`model_watcher.py` monitora o diretório `YOLO_MODELS_DIR` (padrão: `/models`). Quando detecta novo arquivo `.pt`, invalida o cache `_model_cache` e o próximo frame usa o modelo atualizado.

No modo Edge (Fase 4+), o `edge-sync-agent` faz download do modelo e coloca no diretório monitorado.

**Variáveis de ambiente do modelo:**
```
YOLO_MODEL_PATH=yolov8n.pt          # modelo padrão se não especificado por câmera
YOLO_MODELS_DIR=/models             # diretório com todos os modelos
DETECTION_CONFIDENCE_THRESHOLD=0.5  # threshold padrão (sobrescrito por câmera)
```

---

## Fase 3 — DeepStream Pipeline (Planejado)

Quando `INFERENCE_ENGINE=deepstream`:

```
GStreamer pipeline:
  nvurisrcbin (RTSP) → nvstreammux → nvinfer (TensorRT) → nvtracker → nvdsosd
                                                               ↓
                                                    custom sink → Redis PUBLISH det:{camera_id}
```

**Requisitos de hardware:**
- NVIDIA GPU com suporte CUDA 12+
- DeepStream 6.x instalado (Ubuntu 22.04)
- Modelo exportado para TensorRT INT8: `yolov8n.engine`

**Referência:** ADR-0001 (DeepStream vs Ultralytics), `deepstream/` no monorepo

---

## Redis Client

`make_redis(for_subscribe=False)` retorna conexão configurada:
- `for_subscribe=True`: `socket_timeout=None` (bloqueante para psubscribe/listen)
- `for_subscribe=False`: `socket_timeout=5` (para PUBLISH/SET)

---

## Health Endpoint

```
GET /health
→ {"status": "ok", "frames_processed": 1234, "models_loaded": ["yolov8n.pt"], "uptime_s": 3600}
```

---

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---------|--------|-----------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `INFERENCE_ENGINE` | `ultralytics` | Backend: `ultralytics` ou `deepstream` |
| `YOLO_MODEL_PATH` | `yolov8n.pt` | Modelo padrão |
| `YOLO_MODELS_DIR` | `/models` | Diretório de modelos |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5` | Threshold de confiança |
| `FRAME_RATE_TARGET` | `5` | FPS alvo para consumo |

---

## Comandos de Desenvolvimento

```bash
cd services/inference
export REDIS_URL=redis://localhost:6379 INFERENCE_ENGINE=ultralytics
python -m inference.main

# Lint
python -m ruff check .

# Teste
python -m pytest tests/ -v
```

---

## Restrições

- Zero `print()` — usar `logging.getLogger(__name__)`
- Graceful shutdown: ao receber SIGTERM, aguardar frame atual completar antes de encerrar
- Thread safety: `_model_lock` e `_deepsort_lock` protegem caches compartilhados
- `track_id` nunca reutilizado dentro de uma mesma sessão de câmera ativa
