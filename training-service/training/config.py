import os

REDIS_URL               = os.environ.get("REDIS_URL", "redis://localhost:6379")
ULTRALYTICS_HUB_API_KEY = os.environ.get("ULTRALYTICS_HUB_API_KEY", "")
R2_ENDPOINT             = os.environ.get("R2_ENDPOINT", "")
R2_BUCKET               = os.environ.get("R2_BUCKET", "epi-monitor")
R2_KEY                  = os.environ.get("R2_KEY", "")
R2_SECRET               = os.environ.get("R2_SECRET", "")
TRAINING_EPOCHS         = int(os.environ.get("TRAINING_EPOCHS", "50"))
TRAINING_BATCH_SIZE     = int(os.environ.get("TRAINING_BATCH_SIZE", "16"))
TRAINING_IMG_SIZE       = int(os.environ.get("TRAINING_IMG_SIZE", "640"))
TRAINING_MODEL_ARCH     = os.environ.get("TRAINING_MODEL_ARCH", "yolo26n")
POLL_INTERVAL           = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
PORT                    = int(os.environ.get("PORT", "8004"))
