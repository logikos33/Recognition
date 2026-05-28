import os


class PreAnnotationConfig:
    DATABASE_URL: str = os.environ.get("PREANNOT_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    REDIS_URL: str = os.environ.get("PREANNOT_REDIS_URL", os.environ.get("REDIS_URL", ""))

    R2_ENDPOINT: str = os.environ.get("PREANNOT_R2_ENDPOINT", os.environ.get("R2_ENDPOINT", ""))
    R2_BUCKET: str = os.environ.get("PREANNOT_R2_BUCKET", os.environ.get("R2_BUCKET", "epi-monitor"))
    R2_KEY: str = os.environ.get("PREANNOT_R2_KEY", os.environ.get("R2_KEY", ""))
    R2_SECRET: str = os.environ.get("PREANNOT_R2_SECRET", os.environ.get("R2_SECRET", ""))

    # Caminhos dos modelos
    DINO_CONFIG: str = os.environ.get("PREANNOT_DINO_CONFIG", "GroundingDINO_SwinT_OGC.py")
    DINO_CHECKPOINT: str = os.environ.get("PREANNOT_DINO_CHECKPOINT", "groundingdino_swint_ogc.pth")
    SAM_CHECKPOINT: str = os.environ.get("PREANNOT_SAM_CHECKPOINT", "sam_vit_b_01ec64.pth")

    # AI_NOTE: Thresholds baixos para maximizar recall — humano corrige falsos positivos
    DINO_BOX_THRESHOLD: float = float(os.environ.get("PREANNOT_DINO_BOX_THRESHOLD", "0.20"))
    DINO_TEXT_THRESHOLD: float = float(os.environ.get("PREANNOT_DINO_TEXT_THRESHOLD", "0.15"))


config = PreAnnotationConfig()
