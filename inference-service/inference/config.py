"""
Inference Service — configuração via variáveis de ambiente.
"""
import os

REDIS_URL               = os.environ.get("REDIS_URL", "redis://localhost:6379")
INFERENCE_ID            = os.environ.get("INFERENCE_ID", "inference-1")
YOLO_MODEL_PATH         = os.environ.get("YOLO_MODEL_PATH", "yolov8n.pt")
DETECTION_CONFIDENCE    = float(os.environ.get("DETECTION_CONFIDENCE_THRESHOLD", "0.5"))
HEALTH_TTL              = int(os.environ.get("INFERENCE_HEALTH_TTL", "60"))
HEALTH_INTERVAL         = int(os.environ.get("INFERENCE_HEALTH_INTERVAL", "20"))
PORT                    = int(os.environ.get("PORT", "8002"))
