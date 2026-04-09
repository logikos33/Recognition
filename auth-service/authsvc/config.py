import os

DATABASE_URL                    = os.environ.get("DATABASE_URL", "")
REDIS_URL                       = os.environ.get("REDIS_URL", "redis://localhost:6379")
JWT_SECRET_KEY                  = os.environ.get("JWT_SECRET_KEY", "")
JWT_ALGORITHM                   = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS   = int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
PORT                            = int(os.environ.get("PORT", "8005"))
