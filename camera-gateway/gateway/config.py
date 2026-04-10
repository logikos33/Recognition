"""
Camera Gateway — configuração via variáveis de ambiente.
"""
import os

REDIS_URL          = os.environ.get("REDIS_URL", "redis://localhost:6379")
GATEWAY_ID         = os.environ.get("GATEWAY_ID", "gateway-1")
FRAME_EVERY_N      = int(os.environ.get("FRAME_EVERY_N", "5"))
FRAME_JPEG_QUALITY = int(os.environ.get("FRAME_JPEG_QUALITY", "80"))
HLS_SEGMENT_TIME   = int(os.environ.get("HLS_SEGMENT_TIME", "2"))
HLS_LIST_SIZE      = int(os.environ.get("HLS_LIST_SIZE", "3"))
HEALTH_TTL         = int(os.environ.get("GATEWAY_HEALTH_TTL", "60"))
HEALTH_INTERVAL    = int(os.environ.get("GATEWAY_HEALTH_INTERVAL", "20"))
PORT               = int(os.environ.get("PORT", "8080"))
