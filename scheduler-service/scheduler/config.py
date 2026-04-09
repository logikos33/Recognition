import os

REDIS_URL             = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL          = os.environ.get("DATABASE_URL", "")
ALERTS_RETENTION_DAYS = int(os.environ.get("ALERTS_RETENTION_DAYS", "90"))
FRAMES_RETENTION_DAYS = int(os.environ.get("FRAMES_RETENTION_DAYS", "7"))
PORT                  = int(os.environ.get("PORT", "8006"))
