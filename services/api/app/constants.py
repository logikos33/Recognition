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


ROLE_PERMISSIONS: dict[str, list[str]] = {
    "view_cameras":          ["superadmin", "admin", "operator", "analyst", "trainer", "viewer"],
    "control_cameras":       ["superadmin", "admin", "operator"],
    "view_alerts":           ["superadmin", "admin", "operator", "analyst", "viewer"],
    "feedback_alerts":       ["superadmin", "admin", "operator", "analyst"],
    "annotate_frames":       ["superadmin", "admin", "operator", "trainer"],
    "create_training_job":   ["superadmin", "admin", "trainer"],
    "approve_model":         ["superadmin", "admin"],
    "view_reports":          ["superadmin", "admin", "operator", "analyst", "viewer"],
    "manage_users":          ["superadmin", "admin"],
    "configure_cameras":     ["superadmin", "admin"],
    "manage_tenant":         ["superadmin"],
    "view_admin_panel":      ["superadmin"],
    "approve_training":      ["superadmin"],
    "manage_workers":        ["superadmin"],
    "manage_plans":          ["superadmin"],
    "manage_announcements":  ["superadmin"],
    "view_audit_log":        ["superadmin"],
    "manage_tickets":        ["superadmin", "admin"],
}


# Registry canônico de módulos da plataforma e suas funcionalidades.
# Fonte única para o picker validado do painel admin (WS8 — Planos) e para
# validação de plans.modules_allowed / plans.module_features.
# Union dos module_codes reais: seeds 029 (basic/epi/counting/quality) +
# module_classes 009/041 (epi/fueling).
PLATFORM_MODULES: dict[str, dict] = {
    "epi": {
        "label": "EPI Monitor",
        "features": [
            {"key": "vms", "label": "Monitoramento ao vivo (VMS)"},
            {"key": "alerts", "label": "Alertas"},
            {"key": "training", "label": "Treinamento de modelos"},
            {"key": "reports", "label": "Relatórios"},
        ],
    },
    "fueling": {
        "label": "Controle de Abastecimento",
        "features": [
            {"key": "vms", "label": "Monitoramento ao vivo (VMS)"},
            {"key": "alerts", "label": "Alertas"},
            {"key": "training", "label": "Treinamento de modelos"},
            {"key": "reports", "label": "Relatórios"},
        ],
    },
    "counting": {
        "label": "Contagem",
        "features": [
            {"key": "counting_lines", "label": "Linhas de contagem"},
            {"key": "loading_sessions", "label": "Sessões de carregamento"},
            {"key": "reports", "label": "Relatórios"},
        ],
    },
    "quality": {
        "label": "Qualidade",
        "features": [
            {"key": "defects", "label": "Detecção de defeitos"},
            {"key": "reports", "label": "Relatórios"},
        ],
    },
    "basic": {
        "label": "Básico",
        "features": [
            {"key": "vms", "label": "Monitoramento ao vivo (VMS)"},
            {"key": "alerts", "label": "Alertas"},
        ],
    },
}


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
