"""
CORE config_validation.py — validação de faixa das envs numéricas críticas no boot.

Contexto (mutirão 2.6): a família de bugs "config numérica fora de faixa" já
matou a coleta 3 vezes — zero frame, zero erro no log. Ex.: `HLS_LIST_SIZE=0`
derruba o playlist HLS silenciosamente; `HLS_PLAYBACK_TOKEN_TTL<=0` expira o
token antes do browser terminar o handshake; `EDGE_OFFLINE_THRESHOLD_SECONDS`
absurdamente alto nunca detecta um site morto. Regra: fora do domínio → falha
ALTA no boot (nunca degradação silenciosa depois).

DECISÃO (mutirão 2.6): NÃO migrar a base para pydantic-settings — 157
ocorrências de `os.environ` espalhadas e tasks Celery que leem env em import
time tornam isso um big-bang capaz de quebrar o deploy. Este módulo valida
SÓ o crítico: os ~15 envs numéricos no caminho de streaming/coleta e
health/readiness que já causaram (ou têm perfil idêntico ao que já causou)
zero-frame-zero-erro.

Cada env continua sendo lido onde sempre foi (`app/config.py`,
`app/core/playback_token.py`, `app/api/v1/cameras/local_stream_manager.py`,
`app/core/edge_offline.py`, `app/domain/services/liveness_service.py`,
`app/infrastructure/queue/tasks/*.py`) — este módulo é uma checagem
REDUNDANTE e INDEPENDENTE, chamada uma vez no boot. Não substitui os
`os.environ.get(...)` existentes (mudar os 157 pontos de leitura está fora de
escopo — ver decisão acima); apenas impede o processo de subir com um valor
que, no runtime, se manifestaria como coleta zerada sem nenhum erro.

Usa pydantic (`Field(ge=, le=)`) porque já é dependência direta do projeto
(`requirements/base.in`, seção "# Validation") — só que nunca tinha sido
usada em `app/`.

Chamado por `app/__init__.py::create_app()`. Pulado quando `config.TESTING`
(a suíte usa `create_app("testing")` em centenas de testes, com env
arbitrário/ausente — não é o alvo desta validação).
"""
import logging
import os

from pydantic import BaseModel, Field, ValidationError, model_validator

logger = logging.getLogger(__name__)


class _CriticalConfigRanges(BaseModel):
    """Domínio válido das envs numéricas críticas. Ver docstring do módulo."""

    # HLS streaming — fora da faixa, o FFmpeg/hls.js trava sem erro no log.
    HLS_SEGMENT_TIME: int = Field(ge=1, le=10)
    HLS_LIST_SIZE: int = Field(ge=1, le=20)
    HLS_INACTIVITY_TIMEOUT: int = Field(ge=5, le=600)
    # Sinal de "tem espectador" (epi:stream:*:active), lido por /edge/live-view/
    # wanted. Separado do HLS_INACTIVITY_TIMEOUT acima, que é o ócio do FFmpeg
    # local — ver comentário em stream_handlers._HLS_INACTIVITY_TTL.
    HLS_VIEWER_TTL: int = Field(ge=30, le=600)
    HLS_STALL_TIMEOUT: int = Field(ge=3, le=300)
    HLS_PLAYBACK_TOKEN_TTL: int = Field(ge=60, le=86400)

    # Health/readiness do edge — limiar errado nunca detecta câmera/site morto
    # (ou, no outro extremo, gera falso-positivo constante).
    EDGE_OFFLINE_THRESHOLD_SECONDS: int = Field(ge=10, le=3600)
    LIVENESS_GAP_THRESHOLD_MINUTES: int = Field(ge=1, le=120)

    # Cadência de inferência — 0 é módulo-por-zero / trava silenciosa do worker.
    YOLO_INFERENCE_EVERY_N_FRAMES: int = Field(ge=1, le=100)
    QUALITY_INFERENCE_FPS: int = Field(ge=1, le=30)

    # Thresholds de decisão — fora de [0,1] é sempre-verdadeiro ou nunca-verdadeiro
    # (ex.: DETECTION_CONFIDENCE_THRESHOLD=1.0 zera toda detecção sem erro nenhum).
    DETECTION_CONFIDENCE_THRESHOLD: float = Field(ge=0.0, le=1.0)
    VERIFICATION_THRESHOLD: float = Field(ge=0.0, le=1.0)
    DRIFT_SCORE_ALERT_THRESHOLD: float = Field(ge=0.0, le=1.0)

    AUTO_CAPTURE_DEDUP_TTL_SECONDS: int = Field(ge=1, le=3600)

    # Pool de conexões do Postgres — 0 é "sem conexão nenhuma", derruba tudo.
    DB_POOL_MIN: int = Field(ge=1, le=50)
    DB_POOL_MAX: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def _pool_min_le_max(self) -> "_CriticalConfigRanges":
        if self.DB_POOL_MIN > self.DB_POOL_MAX:
            raise ValueError(
                f"DB_POOL_MIN ({self.DB_POOL_MIN}) não pode ser maior que "
                f"DB_POOL_MAX ({self.DB_POOL_MAX})"
            )
        return self


# Defaults IDÊNTICOS aos já usados em cada ponto de leitura real (ver docstring
# do módulo) — ausência da env não deve mudar comportamento, só a presença de
# um valor fora de faixa.
_ENV_DEFAULTS: dict[str, str] = {
    "HLS_SEGMENT_TIME": "2",
    "HLS_LIST_SIZE": "3",
    "HLS_INACTIVITY_TIMEOUT": "30",
    "HLS_VIEWER_TTL": "90",
    "HLS_STALL_TIMEOUT": "12",
    "HLS_PLAYBACK_TOKEN_TTL": "3600",
    "EDGE_OFFLINE_THRESHOLD_SECONDS": "120",
    "LIVENESS_GAP_THRESHOLD_MINUTES": "5",
    "YOLO_INFERENCE_EVERY_N_FRAMES": "5",
    "QUALITY_INFERENCE_FPS": "5",
    "DETECTION_CONFIDENCE_THRESHOLD": "0.5",
    "VERIFICATION_THRESHOLD": "0.85",
    "DRIFT_SCORE_ALERT_THRESHOLD": "0.3",
    "AUTO_CAPTURE_DEDUP_TTL_SECONDS": "30",
    "DB_POOL_MIN": "1",
    "DB_POOL_MAX": "10",
}


def validate_critical_config(testing: bool = False) -> None:
    """Valida a faixa das envs numéricas críticas listadas acima.

    Agrega TODAS as violações numa mensagem só — se três envs estão erradas,
    as três aparecem de uma vez (não uma por deploy/restart, que foi como o
    incidente se repetiu 3x). Mata o boot com `SystemExit(78)` se houver
    qualquer violação.

    `testing=True` (config.TESTING) pula a validação inteira.
    """
    if testing:
        return

    raw: dict[str, str] = {
        name: os.environ.get(name, default)
        for name, default in _ENV_DEFAULTS.items()
    }

    try:
        _CriticalConfigRanges(**raw)
    except ValidationError as exc:
        violations = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            field = str(err["loc"][0]) if err["loc"] else None
            value = raw.get(field, "?") if field else "?"
            label = loc or "config"
            violations.append(f"{label}={value!r}: {err['msg']}")

        message = (
            "Boot abortado: config numérica fora do domínio esperado "
            "(família zero-frame-zero-erro, mutirão 2.6). Corrija TODAS as "
            "envs abaixo e reinicie:\n  " + "\n  ".join(violations)
        )
        logger.critical(message)
        raise SystemExit(78)
