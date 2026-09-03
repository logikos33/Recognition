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


class FrameSource(StrEnum):
    """Origem de um frame de treinamento (migration 094 — CHECK chk_training_frames_source)."""

    VIDEO = "video"    # Extraído de vídeo enviado
    UPLOAD = "upload"  # Upload manual em batch
    AUTO = "auto"      # Auto-captura de alertas de inferência
    NVR = "nvr"        # Extração de playback gravado (NVR/DVR)


class CurationStatus(StrEnum):
    """Status de curadoria de um frame de treino (migration 110 — CHECK
    chk_training_frames_curation_status).

    active   — no fluxo normal (padrão; visível na galeria e no anotador)
    duvida   — marcado para revisão humana antes de entrar no dataset
    excluida — descartado da curadoria (nunca some do banco — nunca apagar
               caixas; só sai da galeria por padrão)
    """

    ACTIVE = "active"
    DUVIDA = "duvida"
    EXCLUIDA = "excluida"


class DatasetRole(StrEnum):
    """Emprego permanente de um frame (migration 133 — CHECK
    chk_training_frames_dataset_role).

    "Um quadro só tem UM emprego para sempre — gabarito mede, proposta
    alimenta." Um gabarito que entra no treino faz o modelo decorar a prova,
    e toda medição posterior passa a mentir para cima sem acusar nada.

    pool    — alimenta treino (padrão de todo frame que já existe)
    holdout — gabarito: mede modelo e NUNCA entra em export de treino
              (trava em versioning_v2._snapshot_labeled_frames/
              _fetch_annotations, por ALLOWLIST `= 'pool'`)

    Ortogonal a CurationStatus: um gabarito é 'active' na curadoria — o que
    muda é o emprego, não a qualidade.
    """

    POOL = "pool"
    HOLDOUT = "holdout"


class HoldoutVerdict(StrEnum):
    """Resposta do gabarito para "nesta imagem, a ausência da classe X era
    real?" (migration 135 — CHECK chk_holdout_verdicts_verdict).

    sim     — a ausência era real (a pessoa estava mesmo sem o EPI)
    nao     — não era: ou o EPI estava lá, ou não havia pessoa nenhuma
    nao_sei — o avaliador olhou e não deu para decidir

    O `nao_sei` NÃO é estado de conveniência: forçar binário faz quem julga
    chutar quando a imagem não permite decidir, e gabarito com chute mede o
    chute, não o modelo. É ele que separa "o modelo errou" de "a imagem não
    dava para saber" na hora de ler o A/B.
    """

    SIM = "sim"
    NAO = "nao"
    NAO_SEI = "nao_sei"


class HoldoutVerdictReason(StrEnum):
    """Por que a resposta saiu assim (migration 135 — coluna `reason`).

    sem_pessoa — veio do atalho de um toque "não há pessoa", que responde
                 'nao' para TODAS as classes de uma vez. Semanticamente
                 correto (sem pessoa, nenhuma ausência é real) e é o negativo
                 que o A/B mais precisa: modelo que acusa "sem luvas" em
                 corredor vazio está produzindo falso positivo. Registrado à
                 parte porque "não, ele usava luva" e "não, não havia
                 ninguém" são fatos diferentes ao auditar a prova — um
                 gabarito de 138 corredores vazios não mede nada.

    Ausência de valor (NULL) = julgada classe a classe.
    """

    SEM_PESSOA = "sem_pessoa"


# Classes de ausência que o gabarito do A/B julga, por NOME.
#
# Por nome e não por id: as duas primeiras vêm do catálogo global
# (`module_classes`, class_id pequeno 0-based) e as três últimas são classes
# do tenant (`yolo_classes`, class_id namespaced +100000 — ver
# domain/services/class_namespace.py). Fixar o inteiro aqui prenderia a régua
# aos ids que o DEV tem hoje; o nome é o que o dono do produto reconhece e o
# que sobrevive a outro ambiente. `ModuleService.get_classes` já devolve as
# duas origens na MESMA lista — a resolução acontece lá, não aqui.
#
# ⚠️ ORDEM É CONTEÚDO. As duas primeiras são o FOCO: são as que têm gabarito
# ZERO no holdout do RVB e por isso deixaram o A/B das três variantes NÃO
# CONCLUSIVO. As outras três valem se sobrar atenção — e a tela diz isso na
# cara, em vez de apresentar cinco perguntas de peso igual.
GABARITO_CLASSES = (
    "Sem Luvas",
    "Sem mascara",
    "Sem Óculos",
    "Sem protetor de ouvido",
    "Uso incorreto de mascara",
)

GABARITO_CLASSES_FOCO = GABARITO_CLASSES[:2]


class DatasetVersionStatus(StrEnum):
    """Status de build de uma dataset_version (migration 096)."""

    BUILDING = "building"
    READY = "ready"
    ERROR = "error"


class ExportFormat(StrEnum):
    """Formato de export de dataset (migration 096 — dataset_versions.export_format)."""

    COCO = "coco"
    YOLO = "yolo"


class Framework(StrEnum):
    """Framework de treinamento/serving (migrations 097/098). License-safe: Apache/MIT."""

    RFDETR = "rfdetr"
    YOLOX = "yolox"
    ULTRALYTICS = "ultralytics"  # Legado — nunca no caminho de serving (AGPL)


class GpuProvider(StrEnum):
    """Provedor de GPU para treinamento (migration 097 — training_jobs.gpu_provider).

    Dobra como `compute_target` da abstração TrainingCompute (ADR-0039) — reusa
    esta mesma coluna/enum em vez de criar uma nova, mesma decisão do PR-4 de
    não duplicar o que já existe. EDGE (Jetson via edge-sync-agent) adicionado
    aqui é BLOQUEADO-HARDWARE — ver `app/infrastructure/gpu/training_compute.py`
    e a issue de validação de hardware correspondente.

    RUNPOD substitui VAST_AI como provedor de GPU de terceiro real (decisão
    do dono — `infrastructure/gpu/vast_client.py` foi deletado; a API
    console.vast.ai nunca entregou treino em produção). VAST_AI permanece no
    enum só por linhagem de dados legados (jobs antigos com
    `gpu_provider='vast_ai'` no banco) — nenhum dispatch novo usa esse valor.
    """

    RUNPOD = "runpod"
    VAST_AI = "vast_ai"
    COLAB = "colab"
    EDGE = "edge"
    LOCAL = "local"


# Guard por DESTINO (nunca por flag) — task "propagação no edge": a imagem
# SAI da Logikos pra nuvem de terceiro só nos providers OFFSITE; nos
# ONSITE (Jetson do site, ou hipoteticamente um processo local) ela nunca
# deixa o site, então o guard fail-closed de datas de
# `domain/services/propagation_pool.py` deixa de fazer sentido (mas o
# resto do guard de pool — tenant/câmera/r2_key — continua valendo sempre,
# ver `validate_pool_frames(..., enforce_date_guard=...)`). Um provider
# novo SEM classificação aqui não deve silenciosamente cair em nenhum dos
# dois lados — a checagem abaixo levanta na importação do módulo
# (fail-closed: quebra o boot em vez de deixar um provider desclassificado
# passar por um guard incerto).
OFFSITE_PROVIDERS: frozenset[GpuProvider] = frozenset({
    GpuProvider.RUNPOD, GpuProvider.VAST_AI, GpuProvider.COLAB,
})
ONSITE_PROVIDERS: frozenset[GpuProvider] = frozenset({
    GpuProvider.EDGE, GpuProvider.LOCAL,
})

_unclassified_gpu_providers = set(GpuProvider) - (OFFSITE_PROVIDERS | ONSITE_PROVIDERS)
if _unclassified_gpu_providers:
    raise RuntimeError(
        "GpuProvider sem classificação OFFSITE_PROVIDERS/ONSITE_PROVIDERS: "
        f"{sorted(p.value for p in _unclassified_gpu_providers)} — fail-closed, "
        "ver app/constants.py::OFFSITE_PROVIDERS/ONSITE_PROVIDERS."
    )


class EvalVerdict(StrEnum):
    """Veredito de avaliação campeão×desafiante (101 — CHECK chk_model_evaluations_verdict)."""

    PENDING = "pending"
    PROMOTE = "promote"
    REJECT = "reject"


class RecorderProtocol(StrEnum):
    """Protocolo de acesso a NVR/DVR (migration 099 — CHECK chk_recorders_protocol)."""

    ONVIF = "onvif"
    HIKVISION = "hikvision"
    DAHUA = "dahua"
    INTELBRAS = "intelbras"
    RTSP = "rtsp"


class RecorderStatus(StrEnum):
    """Status de conectividade de um recorder (migration 099 — CHECK chk_recorders_status)."""

    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class DeploymentStatus(StrEnum):
    """Status de um model_deployment (100 — CHECK chk_model_deployments_status)."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ROLLED_BACK = "rolled_back"


class R2Prefix:
    """Prefixos de chave no Cloudflare R2. Nunca strings literais no código."""

    RAW_VIDEOS = "raw-videos"
    FRAMES = "frames"
    LABELS = "labels"
    DATASETS = "datasets"
    MODELS = "models"
    EVIDENCE = "evidence"
    DEMO_VIDEOS = "demo-videos"  # Vídeos MP4 para modo demonstração (superadmin only)
    TRAINING_IMAGES = "training-images"  # Uploads e auto-captura de frames para treinamento
    DATASET_EXPORTS = "dataset-exports"  # Exports COCO/YOLO gerados por build_dataset_version_v2
    SNAPSHOTS = "snapshots"  # Miniaturas de triagem de câmera (Bloco A) — snapshot ONVIF/RTSP


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
