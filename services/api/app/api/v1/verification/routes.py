"""
Recognition — Verification Queue API.

Routes:
  GET  /api/verification/queue          — alertas sem veredito (verdict IS NULL) para revisão
  GET  /api/verification/queue/count    — contagem (badge na nav)
  POST /api/verification/<id>/review    — operador aprova ou rejeita
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.core.tenant import require_permission
from app.domain.services.verification_service import VerificationService

logger = logging.getLogger(__name__)
verification_bp = Blueprint("verification", __name__)

_svc = VerificationService()


@verification_bp.route("/api/verification/queue", methods=["GET"])
@jwt_required()
def get_queue():  # type: ignore[no-untyped-def]
    """Lista alertas aguardando revisão humana do tenant autenticado (C-01).

    `total` vem de `get_queue_count` — o MESMO WHERE do `items` (verdict
    nulo + exclusão de conformidade + dedup de rajada), escopado pelo mesmo
    `camera_id`. É embutido aqui (não uma segunda chamada da tela a
    `/queue/count`) de propósito: um único request garante que lista e total
    são a MESMA leitura do banco — duas chamadas separadas no poll de 15s
    podiam divergir por uma escrita no meio (outro operador revisando). A
    tela usa `total`, não `count` (`count` é só `len(items)`, capado no
    `limit` — não é "quantos faltam", é "quantos vieram nesta página").

    `user_id` vai junto SÓ para o rodízio de trilha (`_trilha`): a fila é a
    mesma para todo mundo, cada operador só começa por um ponto diferente —
    é o que impede três pessoas de abrirem o MESMO alerta na segunda. Não
    filtra nada, e `total` (que não recebe `user_id`) continua sendo o
    trabalho do TENANT, não "o meu pedaço".
    """
    camera_id = request.args.get("camera_id")
    limit = min(int(request.args.get("limit", 50)), 100)
    try:
        tenant_id = str(get_tenant_id())
        items = _svc.get_human_queue(
            tenant_id=tenant_id, limit=limit, camera_id=camera_id,
            user_id=str(get_current_user_id()),
        )
        total = _svc.get_queue_count(tenant_id=tenant_id, camera_id=camera_id)
        return success({"items": items, "count": len(items), "total": total})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_queue_error: %s", exc)
        return error("Erro ao buscar fila", 500)


@verification_bp.route("/api/verification/queue/count", methods=["GET"])
@jwt_required()
def queue_count():  # type: ignore[no-untyped-def]
    """Contagem rápida para badge na navegação, escopada ao tenant (C-01).

    `camera_id` opcional, mesma semântica de `/queue` — alinhado de propósito
    (achado do cético: contagem e lista podiam divergir por não aceitarem os
    mesmos filtros).
    """
    camera_id = request.args.get("camera_id")
    try:
        tenant_id = str(get_tenant_id())
        count = _svc.get_queue_count(tenant_id=tenant_id, camera_id=camera_id)
        return success({"count": count})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("queue_count_error: %s", exc)
        return error("Erro", 500)


@verification_bp.route("/api/verification/<alert_id>/review", methods=["POST"])
@jwt_required()
@require_permission("verification:write")
def review_alert(alert_id: str):  # type: ignore[no-untyped-def]
    """Operador aprova ou rejeita alerta do próprio tenant (C-01).

    Alerta pertencente a outro tenant não é encontrado — 404, nunca 200
    (isolamento cross-tenant, achado #14 do API_CONTRACT_MAP.md).

    Alerta que OUTRA pessoa já julgou → **409**, nunca 200: `human_review`
    levanta `ConflictError` (EpiMonitorError → o handler do middleware devolve
    409 com a mensagem "Fulana já avaliou este alerta há 2 minutos"). Antes
    disso o segundo veredito sobrescrevia o primeiro em silêncio, com 200 nas
    duas pontas. O `raise` do `except EpiMonitorError` abaixo é o que deixa
    esse 409 passar — não transforme em `except Exception`.
    """
    body = request.get_json(silent=True) or {}
    verdict = body.get("verdict")
    if verdict not in ("approve", "reject"):
        return error("verdict deve ser 'approve' ou 'reject'", 400)

    try:
        user_id = str(get_current_user_id())
        tenant_id = str(get_tenant_id())
        affected = _svc.human_review(
            alert_id=alert_id, verdict=verdict, user_id=user_id,
            tenant_id=tenant_id, reason=body.get("reason"),
        )
        if not affected:
            # "já revisado" deixou de ser causa: re-revisão é permitida e o
            # veredito vale para qualquer alerta do tenant (ver human_review).
            return error("Alerta não encontrado", 404)
        return success({"alert_id": alert_id, "verdict": verdict})
    except EpiMonitorError:
        raise
    except ValueError as exc:
        return error(str(exc), 400)
    except Exception as exc:
        logger.error("review_alert_error: alert=%s err=%s", alert_id, exc)
        return error("Erro ao revisar alerta", 500)
