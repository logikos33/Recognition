"""
Recognition — Admin: Demo Events Routes (superadmin only).

Seed/status/remoção de eventos mock de demonstração (tabela apartada demo_events).
Os eventos aparecem na Investigação do tenant alvo com marcador is_demo=true.
O tenant_id vem EXPLÍCITO do body/query: o superadmin semeia para o tenant do
cliente em demonstração, não para o seu próprio. NUNCA aceito de roles menores
(todas as rotas exigem @require_superadmin).

GET    /api/v1/admin/demo-events?tenant_id=      — status por módulo
POST   /api/v1/admin/demo-events/seed            — body {tenant_id, module_code, count?}
DELETE /api/v1/admin/demo-events?tenant_id=&module_code= — remoção (só demo_events)
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity

from app.core.auth import get_role
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.core.tenant import require_superadmin
from app.domain.services import demo_event_service

logger = logging.getLogger(__name__)

demo_events_bp = Blueprint("demo_events", __name__, url_prefix="/api/v1/admin/demo-events")


@demo_events_bp.route("", methods=["GET"])
@require_superadmin
def demo_events_status():  # type: ignore[no-untyped-def]
    """Status dos eventos demo de um tenant: contagem por módulo + total."""
    try:
        tenant_id = (request.args.get("tenant_id") or "").strip()
        if not tenant_id:
            return error("Parâmetro 'tenant_id' é obrigatório", 400)

        result = demo_event_service.status(tenant_id, user_role=get_role())
        return success(result)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("demo_events_status_error: %s", exc, exc_info=True)
        return error("Erro ao consultar eventos demo", 500)


@demo_events_bp.route("/seed", methods=["POST"])
@require_superadmin
def seed_demo_events():  # type: ignore[no-untyped-def]
    """Semeia N eventos demo para o tenant alvo (default 30, clamp 1..500)."""
    try:
        body = request.get_json(silent=True) or {}
        tenant_id = (str(body.get("tenant_id") or "")).strip()
        if not tenant_id:
            return error("Campo 'tenant_id' é obrigatório", 400)

        module_code = (str(body.get("module_code") or "epi")).strip()
        count = body.get("count")

        result = demo_event_service.seed(
            tenant_id=tenant_id,
            module_code=module_code,
            count=count,
            user_role=get_role(),
            user_id=get_jwt_identity() or None,
        )
        return success(result, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("demo_events_seed_error: %s", exc, exc_info=True)
        return error("Erro ao semear eventos demo", 500)


@demo_events_bp.route("", methods=["DELETE"])
@require_superadmin
def remove_demo_events():  # type: ignore[no-untyped-def]
    """Remove eventos demo do tenant (opcionalmente por módulo). Alertas reais intocados."""
    try:
        tenant_id = (request.args.get("tenant_id") or "").strip()
        if not tenant_id:
            return error("Parâmetro 'tenant_id' é obrigatório", 400)

        module_code = (request.args.get("module_code") or "").strip() or None

        result = demo_event_service.remove(
            tenant_id=tenant_id,
            user_role=get_role(),
            module_code=module_code,
        )
        return success(result)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("demo_events_remove_error: %s", exc, exc_info=True)
        return error("Erro ao remover eventos demo", 500)
