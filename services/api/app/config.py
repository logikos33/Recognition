"""
Recognition — Configuration Factory.

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

    # RunPod (GPU training real — substitui Vast.ai, decisão do dono).
    # infrastructure/gpu/runpod_client.py e runpod_runner.py leem
    # RUNPOD_API_KEY direto de os.environ (mesmo padrão que vast_client.py
    # usava) — os atributos aqui documentam a env var pro operador, mas não
    # são o ponto de leitura em runtime. RUNPOD_ENDPOINT_ID é RESERVA — não
    # usado ainda; existe pra uma futura modalidade serverless (endpoints
    # RunPod, diferente de pods sob demanda), fora do escopo desta task.
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

    # Worker on-premise authentication secret
    WORKER_SECRET: str = os.environ.get("WORKER_SECRET", "")

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
    """Produção Railway (e staging — ver `_configs` abaixo)."""

    DEBUG = False

    def __init__(self) -> None:
        # __init_subclass__ só dispara para subclasses de ProductionConfig — como
        # antes nada herdava dela, essa validação nunca rodava (achado P1 da
        # auditoria de segurança). __init__ roda toda vez que get_config()
        # instancia a classe, inclusive agora que DevelopmentConfig herda daqui
        # (DevelopmentConfig sobrescreve __init__ para pular esta validação —
        # ver comentário lá).
        super().__init__()
        self._validate_production_secrets()

    def _validate_production_secrets(self) -> None:
        """Extraído do __init__ para DevelopmentConfig poder pular só isto,
        sem duplicar a chamada a super().__init__()."""
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY obrigatória em produção")
        if not self.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY obrigatória em produção")
        if len(self.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY deve ter mínimo 32 caracteres")


class DevelopmentConfig(ProductionConfig):
    """Desenvolvimento local.

    Herda de ProductionConfig (não de Config) de propósito: alta fidelidade
    com produção — os ~50 campos da base (pool de conexões, CORS, thresholds,
    Celery, HLS, etc.) são idênticos por herança, sem duplicação. As únicas
    divergências intencionais Dev×Prod são as 4 abaixo; qualquer outra
    diferença de comportamento seria bug, não feature.
    """

    # Divergência 1/4: DEBUG ligado — reload automático e tracebacks no
    # browser ajudam localmente e nunca devem chegar em produção.
    DEBUG = True

    # Divergência 2/4: SECRET_KEY tem default fraco para não exigir .env
    # local. Nunca vaza para produção porque produção usa ProductionConfig,
    # cujo __init__ (acima, via _validate_production_secrets) rejeitaria
    # esse valor por ser previsível.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-prod")

    # Divergência 3/4: mesma lógica de default fraco para JWT_SECRET_KEY.
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-change-in-prod")

    # Divergência 4/4: pula a validação de secrets de produção. Herdar
    # ProductionConfig.__init__ sem sobrescrever faria o boot local falhar
    # com ValueError, já que as divergências 2 e 3 acima são justamente
    # secrets fracos/previsíveis. Chama Config.__init__ diretamente (em vez
    # de super().__init__(), que executaria ProductionConfig.__init__ e a
    # validação que queremos pular) — hoje um no-op, mas mantém a base no
    # caminho de inicialização caso ela ganhe um __init__ próprio no futuro.
    def __init__(self) -> None:
        Config.__init__(self)


_configs: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    # No modelo deste projeto, `staging` É produção (CLAUDE.md: "staging =
    # PRODUÇÃO, auto-deploy Railway"). Explícito no mapa: documenta a
    # realidade do projeto e permite que seletor desconhecido seja ERRO
    # (get_config abaixo) em vez de virar produção em silêncio.
    "staging": ProductionConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str | None = None) -> Config:
    """Factory: retorna instância de Config para o ambiente.

    FLASK_ENV desconhecido é erro de configuração, não fallback: um typo
    ("prodution") virando ProductionConfig em silêncio é exatamente o tipo
    de acidente que o mapa explícito acima existe para impedir.
    """
    name = env_name or os.environ.get("FLASK_ENV", "production")
    try:
        config_class = _configs[name]
    except KeyError:
        valid = ", ".join(sorted(_configs))
        raise ValueError(
            f"FLASK_ENV desconhecido: {name!r} — válidos: {valid}"
        ) from None
    config_class._fix_database_url()
    return config_class()
