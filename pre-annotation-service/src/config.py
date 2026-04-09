"""Configuração do Pre-Annotation Service."""
from pydantic_settings import BaseSettings


class PreAnnotationConfig(BaseSettings):
    DATABASE_URL: str = ""
    REDIS_URL: str = ""

    R2_ENDPOINT: str = ""
    R2_BUCKET: str = "epi-monitor"
    R2_KEY: str = ""
    R2_SECRET: str = ""

    # Caminhos dos modelos
    DINO_CONFIG: str = "GroundingDINO_SwinT_OGC.py"
    DINO_CHECKPOINT: str = "groundingdino_swint_ogc.pth"
    SAM_CHECKPOINT: str = "sam_vit_b_01ec64.pth"

    # Thresholds de detecção
    DINO_BOX_THRESHOLD: float = 0.35
    DINO_TEXT_THRESHOLD: float = 0.25

    model_config = {"env_prefix": "PREANNOT_"}


config = PreAnnotationConfig()
