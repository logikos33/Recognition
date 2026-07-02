"""
Recognition — Constants and Enums.

Nenhuma magic string no código — todas centralizadas aqui.
"""
from enum import StrEnum


class VideoStatus(StrEnum):
    """Status do pipeline de vídeo."""

    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FrameStatus(StrEnum):
    """Status de um frame extraído."""

    RAW = "raw"
    QUEUED = "queued"
    ANNOTATED = "annotated"
    REJECTED = "rejected"


class TrainingStatus(StrEnum):
    """Status de um job de treinamento."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class CameraStatus(StrEnum):
    """Status de uma câmera IP."""

    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    ERROR = "error"


class UserRole(StrEnum):
    """
    Papéis de usuário.

    superadmin — acesso ao painel admin (tenant Logikos)
    admin      — gerencia o próprio tenant (câmeras, usuários, treinamentos)
    operator   — opera câmeras, visualiza alertas
    analyst    — visualiza dashboards e relatórios, dá feedback em alertas
    trainer    — acessa módulo de treinamento, anota frames, cria jobs
    viewer     — somente visualização (read-only)
    """

    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    TRAINER = "trainer"
    VIEWER = "viewer"


class EpiClass(StrEnum):
    """Classes de EPI para detecção YOLO."""

    HELMET = "helmet"
    NO_HELMET = "no_helmet"
    VEST = "vest"
    NO_VEST = "no_vest"
    GLOVES = "gloves"
    NO_GLOVES = "no_gloves"
    SAFETY_GLASSES = "safety_glasses"
    NO_SAFETY_GLASSES = "no_safety_glasses"


class TrainingPreset(StrEnum):
    """Presets de treinamento."""

    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


class R2Prefix:
    """Prefixos de chave no Cloudflare R2. Nunca strings literais no código."""

    RAW_VIDEOS = "raw-videos"
    FRAMES = "frames"
    LABELS = "labels"
    DATASETS = "datasets"
    MODELS = "models"
    EVIDENCE = "evidence"
    DEMO_VIDEOS = "demo-videos"  # Vídeos MP4 para modo demonstração (superadmin only)


# WS7: matriz legada DERIVADA do registry canônico (app/core/permissions.py).
# Shape byte-compatível com a constante literal anterior — contract test em
# tests/unit/core/test_permissions_registry.py garante paridade.
from app.core.permissions import legacy_role_permissions as _legacy_role_permissions

ROLE_PERMISSIONS: dict[str, list[str]] = _legacy_role_permissions()


# WS6: catálogo canônico de módulos da plataforma — fonte única consumida por
# GET /api/v1/admin/modules/catalog. Elimina listas hardcoded divergentes no
# frontend (AdminTenantsPage × AdminTenantDetailPage).
# status: 'active' (operacional) | 'beta' (em validação) | 'coming_soon' (placeholder)
MODULE_CATALOG: list[dict[str, str]] = [
    {
        "code": "epi",
        "label": "EPI Monitor",
        "description": "Detecção de equipamentos de proteção individual (capacete, colete, luvas, óculos) em tempo real.",
        "status": "active",
    },
    {
        "code": "basic",
        "label": "Básico",
        "description": "Funcionalidades essenciais da plataforma: câmeras, alertas e relatórios.",
        "status": "active",
    },
    {
        "code": "counting",
        "label": "Contagem",
        "description": "Contagem de objetos e pessoas por linha de passagem ou área monitorada.",
        "status": "beta",
    },
    {
        "code": "quality",
        "label": "Qualidade Industrial",
        "description": "Inspeção visual de qualidade em linhas de produção.",
        "status": "beta",
    },
    {
        "code": "analytics",
        "label": "Analytics",
        "description": "Dashboards avançados, séries históricas e exportação de indicadores.",
        "status": "active",
    },
    {
        "code": "fueling",
        "label": "Controle de Abastecimento",
        "description": "Monitoramento de abastecimento de veículos (caminhão, placa, bico de combustível).",
        "status": "coming_soon",
    },
]


class RedisChannel:
    """Canais Redis pub/sub. Templates com .format()."""

    DETECTION = "det:{camera_id}"
    TRAINING_PROGRESS = "training:{job_id}"
    CAMERA_CONTROL = "camera_control:{camera_id}"
    WORKER_HEALTH = "epi:worker:{worker_id}:health"
    WORKER_COMMANDS = "epi:commands:{worker_id}"
    STREAM_STATUS = "epi:stream:{camera_id}"
    WORKERS_SET = "epi:workers"
    DETECTIONS = "epi:detections"
