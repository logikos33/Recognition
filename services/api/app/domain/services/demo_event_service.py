"""
Recognition — Demo Event Service.

Seed/status/remoção de eventos mock de demonstração (tabela apartada demo_events).
ISOLAMENTO CRÍTICO: todas as operações exigem role superadmin — clientes nunca
semeiam nem removem eventos demo. O tenant alvo vem EXPLÍCITO (o superadmin
semeia para o tenant do cliente em demonstração, não para o seu próprio).

Precedente: demo_video_service.py (mock admin superadmin-only).
"""
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.demo_event_repository import DemoEventRepository
from app.infrastructure.database.repositories.module_repository import ModuleRepository

logger = logging.getLogger(__name__)

_ALLOWED_MODULES = frozenset({"epi", "fueling"})
_DEFAULT_COUNT = 30
_MAX_COUNT = 500
_SPREAD_DAYS = 7

# Fallback estático quando module_classes não tem registros para o módulo
_FALLBACK_CLASSES: dict[str, list[str]] = {
    "epi": [
        "no_helmet", "no_vest", "no_gloves", "no_glasses",
        "helmet", "vest", "gloves", "glasses",
    ],
    "fueling": ["truck", "plate", "fuel_nozzle"],
}

# Pool de nomes de câmera pt-BR para tenants sem câmeras reais
_CAMERA_LABELS = [
    "Portaria (demo)",
    "Pátio (demo)",
    "Almoxarifado (demo)",
    "Doca 2 (demo)",
]

_rng = secrets.SystemRandom()


def _get_repo() -> DemoEventRepository:
    pool = DatabasePool.get_instance()
    return DemoEventRepository(pool)


def _get_module_repo() -> ModuleRepository:
    pool = DatabasePool.get_instance()
    return ModuleRepository(pool)


def _require_superadmin_role(user_role: str) -> None:
    """Defesa em profundidade: além do decorator da rota, o service revalida o role."""
    if user_role != "superadmin":
        raise AuthorizationError("Eventos demo restritos a superadmin")


def _validate_tenant(tenant_id: str) -> str:
    """Valida formato UUID e existência do tenant. Retorna o UUID normalizado."""
    try:
        normalized = str(uuid.UUID(str(tenant_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("tenant_id inválido — informe um UUID") from exc

    if not _get_repo().tenant_exists(normalized):
        raise NotFoundError("Tenant")
    return normalized


def _validate_module(module_code: str) -> str:
    code = (module_code or "").strip().lower()
    if code not in _ALLOWED_MODULES:
        raise ValidationError(
            f"module_code inválido: '{module_code}'. Use um de: {sorted(_ALLOWED_MODULES)}"
        )
    return code


def _class_names_for_module(module_code: str) -> list[str]:
    """Classes do módulo via module_classes; fallback estático se vazio."""
    try:
        rows = _get_module_repo().get_classes(module_code)
        names = [r["class_name"] for r in rows if r.get("class_name")]
        if names:
            return names
    except Exception as exc:
        logger.warning("demo_events_classes_fallback: module=%s err=%s", module_code, exc)
    return _FALLBACK_CLASSES.get(module_code, _FALLBACK_CLASSES["epi"])


def seed(
    tenant_id: str,
    module_code: str,
    count: Optional[int],
    user_role: str,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Semeia eventos demo realistas para o tenant alvo (superadmin only).

    - violations JSONB [{class, confidence}] com 1–2 itens
    - confidence aleatória 0.60–0.98
    - created_at espalhado uniformemente em NOW()-7d..NOW()
    - camera_id = câmera real do tenant se existir, senão NULL + camera_label pt-BR
    - evidence_key NULL (UI mostra placeholder 'sem frame' — não fabricar URL falsa)
    """
    _require_superadmin_role(user_role)
    tenant = _validate_tenant(tenant_id)
    module = _validate_module(module_code)

    try:
        n = int(count) if count is not None else _DEFAULT_COUNT
    except (ValueError, TypeError) as exc:
        raise ValidationError("count deve ser um número inteiro") from exc
    n = max(1, min(_MAX_COUNT, n))

    class_names = _class_names_for_module(module)
    repo = _get_repo()
    camera = repo.first_camera_of_tenant(tenant)
    camera_id = str(camera["id"]) if camera else None

    batch_id = str(uuid.uuid4())
    now = datetime.now()
    spread_seconds = _SPREAD_DAYS * 24 * 3600

    rows: list[dict[str, Any]] = []
    for _ in range(n):
        num_violations = _rng.randint(1, min(2, len(class_names)))
        chosen = _rng.sample(class_names, num_violations)
        violations = [
            {"class": cls, "confidence": round(_rng.uniform(0.60, 0.98), 2)}
            for cls in chosen
        ]
        confidence = max(v["confidence"] for v in violations)
        created_at = now - timedelta(seconds=_rng.uniform(0, spread_seconds))
        rows.append(
            {
                "camera_id": camera_id,
                "camera_label": (
                    camera["name"] if camera else _rng.choice(_CAMERA_LABELS)
                ),
                "module_code": module,
                "violations": json.dumps(violations),
                "confidence": confidence,
                "batch_id": batch_id,
                "created_by": user_id,
                "created_at": created_at,
            }
        )

    created = repo.create_batch(tenant, rows)
    logger.info(
        "demo_events_seeded: tenant=%s module=%s created=%d batch=%s by=%s",
        tenant, module, created, batch_id, user_id,
    )
    return {"created": created, "batch_id": batch_id}


def status(tenant_id: str, user_role: str) -> dict[str, Any]:
    """Contagem de eventos demo por módulo do tenant (superadmin only)."""
    _require_superadmin_role(user_role)
    tenant = _validate_tenant(tenant_id)
    counts = _get_repo().counts_by_module(tenant)
    serialized = [
        {
            "module_code": c["module_code"],
            "count": c["count"],
            "last_seeded_at": (
                c["last_seeded_at"].isoformat() if c.get("last_seeded_at") else None
            ),
        }
        for c in counts
    ]
    total = sum(c["count"] for c in serialized)
    return {"counts": serialized, "total": total}


def remove(
    tenant_id: str,
    user_role: str,
    module_code: Optional[str] = None,
) -> dict[str, Any]:
    """Remove eventos demo do tenant, opcionalmente por módulo (superadmin only).

    DELETE físico APENAS em demo_events — alertas reais jamais são tocados.
    """
    _require_superadmin_role(user_role)
    tenant = _validate_tenant(tenant_id)
    module = _validate_module(module_code) if module_code else None
    deleted = _get_repo().delete_by_tenant(tenant, module)
    logger.info(
        "demo_events_removed: tenant=%s module=%s deleted=%d", tenant, module, deleted
    )
    return {"deleted": deleted}
