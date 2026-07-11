"""
Inference Service — configuração via variáveis de ambiente.

task-055a: YOLO_MODEL_PATH agora aponta para modelo ONNX (Apache 2.0).
  Default atualizado para yolox_s.onnx — setar em env de produção:
  YOLO_MODEL_PATH=/models/yolox_s.onnx
"""
import os

REDIS_URL               = os.environ.get("REDIS_URL", "redis://localhost:6379")
INFERENCE_ID            = os.environ.get("INFERENCE_ID", "inference-1")
YOLO_MODEL_PATH         = os.environ.get("YOLO_MODEL_PATH", "models/yolox_s.onnx")
DETECTION_CONFIDENCE    = float(os.environ.get("DETECTION_CONFIDENCE_THRESHOLD", "0.5"))
HEALTH_TTL              = int(os.environ.get("INFERENCE_HEALTH_TTL", "60"))
HEALTH_INTERVAL         = int(os.environ.get("INFERENCE_HEALTH_INTERVAL", "20"))
PORT                    = int(os.environ.get("PORT", "8002"))
# Classes que geram alerta de violação.
# EPI: "no_helmet,no_vest,no_gloves". Teste COCO pré-treinado: "person".
VIOLATION_CLASSES       = os.environ.get("VIOLATION_CLASSES", "no_helmet,no_vest,no_gloves")
