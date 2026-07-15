"""
Recognition — Pre-Annotation Backend Factory.

Resolve o backend pluglável a partir da feature flag do tenant
(tenants.feature_flags, mesmo padrão do módulo fueling —
FUELING_MOCK_FLAG em api/v1/fueling/routes.py). Nasce OFF (ver ADR-0031,
adendo 2026-07-12): nenhum tenant tem DINO+SAM ligado por default.

Nota (task-098, ADR-0047): `pre_annotation_backend: "zero_shot"` é um valor
INTENCIONALMENTE não resolvível por esta factory — `get_pre_annotation_backend`
retorna None pra ele, e é o comportamento correto, não uma lacuna. O backend
`PreAnnotationBackend` daqui é um proxy HTTP síncrono por-frame (chamado pelo
botão "pré-anotar" do AnnotationInterface, resposta imediata). O zero-shot
roda no EDGE (Jetson, onboarding) e só é alcançável via polling
(config_poller.py/command_poller.py, ciclos de 1-5 min em
services/edge-sync-agent) — não cabe no contrato síncrono
`predict_and_store(frame_id, module_code) -> int`. A implementação real vive
em `services/edge-sync-agent/app/zero_shot_pre_annotation.py`
(`is_zero_shot_enabled`), um lote sob demanda rodado pelo operador de
onboarding, não uma chamada disparada por esta factory. Ver o PR da task-098
para a análise completa.
"""
import logging
import os
from uuid import UUID

from app.domain.services.pre_annotation.base import PreAnnotationBackend

logger = logging.getLogger(__name__)

PRE_ANNOTATION_ENABLED_FLAG = "pre_annotation_enabled"
PRE_ANNOTATION_BACKEND_FLAG = "pre_annotation_backend"
_DEFAULT_BACKEND_NAME = "dino_sam"

_BACKENDS: dict[str, type[PreAnnotationBackend]] = {}


def _register_backends() -> None:
    """Import lazy — evita custo de import (requests) quando a flag nunca liga."""
    if _BACKENDS:
        return
    from app.domain.services.pre_annotation.dino_sam_backend import (  # noqa: PLC0415
        DinoSamHttpBackend,
    )
    _BACKENDS[_DEFAULT_BACKEND_NAME] = DinoSamHttpBackend


def _get_feature_flags(tenant_id: str) -> dict:
    """Resolve o próprio pool (fail-soft) — mesmo padrão de
    resolve_vast_api_key/resolve_r2_credentials: caller não precisa ter um
    pool em mãos, só um tenant_id."""
    try:
        from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
        from app.infrastructure.database.repositories.tenant_settings_repository import (  # noqa: PLC0415,E501
            TenantSettingsRepository,
        )
        pool = DatabasePool.get_instance()
        if pool is None:
            return {}
        return TenantSettingsRepository(pool).get_feature_flags(UUID(str(tenant_id)))
    except Exception as exc:
        logger.warning("pre_annotation_flags_read_failed: tenant=%s err=%s", tenant_id, exc)
        return {}


def _enabled_for_tenant(tenant_id: str) -> bool:
    flags = _get_feature_flags(tenant_id)
    if PRE_ANNOTATION_ENABLED_FLAG in flags:
        return bool(flags[PRE_ANNOTATION_ENABLED_FLAG])
    return os.environ.get("PRE_ANNOTATION_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _backend_name_for_tenant(tenant_id: str) -> str:
    flags = _get_feature_flags(tenant_id)
    name = flags.get(PRE_ANNOTATION_BACKEND_FLAG)
    if isinstance(name, str) and name:
        return name
    return os.environ.get("PRE_ANNOTATION_BACKEND", _DEFAULT_BACKEND_NAME)


def get_pre_annotation_backend(tenant_id: str) -> "PreAnnotationBackend | None":
    """Resolve o backend do tenant, ou None se a flag estiver desligada
    (default) ou o backend configurado não existir."""
    if not _enabled_for_tenant(tenant_id):
        return None
    _register_backends()
    name = _backend_name_for_tenant(tenant_id)
    backend_cls = _BACKENDS.get(name)
    if backend_cls is None:
        logger.warning("pre_annotation_backend_unknown: tenant=%s name=%s", tenant_id, name)
        return None
    return backend_cls()
