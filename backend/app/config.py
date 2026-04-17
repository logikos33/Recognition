"""
EPI Monitor V2 — Configuration Factory.

Pattern: heranca por ambiente com factory function.
Todas as variáveis sensíveis vêm de os.environ — NUNCA hardcoded.
"""
import os


class Config:
    """Base configuration — comum a todos os ambientes."""

    # Flask
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    DEBUG: bool = False
    TESTING: bool = False

    # JWT — JWT_SECRET_KEY DEVE ser igual em todos os serviços Railway
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
    JWT_EXPIRY_HOURS: int = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
    JWT_ALGORITHM: str = "HS256"

    # Database (Railway injeta DATABASE_URL automaticamente)
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    DB_POOL_MIN: int = int(os.environ.get("DB_POOL_MIN", "1"))
    DB_POOL_MAX: int = int(os.environ.get("DB_POOL_MAX", "10"))

    # Redis (Railway injeta REDIS_URL automaticamente)
    REDIS_URL: str = os.environ.get("REDIS_URL", "")

    # Cloudflare R2 (S3-compatível)
    R2_ENDPOINT: str = os.environ.get("R2_ENDPOINT", "")
    R2_BUCKET: str = os.environ.get("R2_BUCKET", "epi-monitor")
    R2_KEY: str = os.environ.get("R2_KEY", "")
    R2_SECRET: str = os.environ.get("R2_SECRET", "")

    # Ultralytics Hub (cloud training)
    ULTRALYTICS_HUB_API_KEY: str = os.environ.get("ULTRALYTICS_HUB_API_KEY", "")
    ULTRALYTICS_HUB_PROJECT_ID: str = os.environ.get("ULTRALYTICS_HUB_PROJECT_ID", "")

    # RunPod (GPU training — fallback)
    RUNPOD_API_KEY: str = os.environ.get("RUNPOD_API_KEY", "")
    RUNPOD_ENDPOINT_ID: str = os.environ.get("RUNPOD_ENDPOINT_ID", "")

    # CORS — NUNCA "*" em produção
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,"
            "https://frontend-production-bf96.up.railway.app",
        ).split(",")
        if o.strip()
    ]

    # Camera encryption
    CAMERA_SECRET_KEY: str = os.environ.get("CAMERA_SECRET_KEY", "")

    # Upload
    MAX_UPLOAD_SIZE_MB: int = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "2048"))
    ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"mp4", "avi", "mov"})

    # Frame extraction (FFmpeg scene detection)
    SCENE_DETECTION_THRESHOLD: float = float(
        os.environ.get("SCENE_DETECTION_THRESHOLD", "0.3")
    )

    # Quality filter thresholds
    BLUR_THRESHOLD: float = float(os.environ.get("BLUR_THRESHOLD", "100.0"))
    BRIGHTNESS_THRESHOLD: float = float(
        os.environ.get("BRIGHTNESS_THRESHOLD", "40.0")
    )

    # Celery
    CELERY_TASK_MAX_RETRIES: int = int(
        os.environ.get("CELERY_TASK_MAX_RETRIES", "3")
    )
    CELERY_TASK_RETRY_COUNTDOWN: int = int(
        os.environ.get("CELERY_TASK_RETRY_COUNTDOWN", "30")
    )

    # HLS streaming
    HLS_SEGMENT_TIME: int = int(os.environ.get("HLS_SEGMENT_TIME", "2"))
    HLS_LIST_SIZE: int = int(os.environ.get("HLS_LIST_SIZE", "3"))

    # YOLO inference
    YOLO_INFERENCE_EVERY_N_FRAMES: int = int(
        os.environ.get("YOLO_INFERENCE_EVERY_N_FRAMES", "5")
    )
    YOLO_MODEL_PATH: str = os.environ.get("YOLO_MODEL_PATH", "yolo26n.pt")
    DETECTION_CONFIDENCE: float = float(
        os.environ.get("DETECTION_CONFIDENCE", "0.5")
    )

    @classmethod
    def _fix_database_url(cls) -> None:
        """Railway usa postgres:// — psycopg2 precisa postgresql://."""
        if cls.DATABASE_URL.startswith("postgres://"):
            cls.DATABASE_URL = cls.DATABASE_URL.replace(
                "postgres://", "postgresql://", 1
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls._fix_database_url()


class DevelopmentConfig(Config):
    """Desenvolvimento local."""

    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-prod")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-change-in-prod")


class TestingConfig(Config):
    """Testes automatizados."""

    TESTING = True
    DEBUG = True
    SECRET_KEY = "testing-secret-key-not-for-production"  # noqa: S105
    JWT_SECRET_KEY = "testing-jwt-key-not-for-production"  # noqa: S105
    DATABASE_URL = os.environ.get(
        "DATABASE_TEST_URL",
        os.environ.get("DATABASE_URL", ""),
    )
    DB_POOL_MIN = 1
    DB_POOL_MAX = 2


class ProductionConfig(Config):
    """Produção Railway."""

    DEBUG = False

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.SECRET_KEY:
            raise ValueError("SECRET_KEY obrigatória em produção")
        if not cls.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY obrigatória em produção")
        if len(cls.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY deve ter mínimo 32 caracteres")


_configs: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str | None = None) -> Config:
    """Factory: retorna instância de Config para o ambiente."""
    name = env_name or os.environ.get("FLASK_ENV", "production")
    config_class = _configs.get(name, ProductionConfig)
    config_class._fix_database_url()
    return config_class()
