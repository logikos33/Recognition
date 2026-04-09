"""WS Gateway — configuração via variáveis de ambiente."""
import os

REDIS_URL      = os.environ.get("REDIS_URL", "redis://localhost:6379")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
CORS_ORIGINS   = os.environ.get("CORS_ORIGINS", "*").split(",")
PORT           = int(os.environ.get("PORT", "8003"))
