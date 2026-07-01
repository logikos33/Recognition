"""
Recognition — Counting Sessions API.

Sessões de contagem com anti-duplicata via DeepSORT track_ids.

Routes:
  POST   /api/counting/sessions              — iniciar sessão
  GET    /api/counting/sessions              — listar sessões ativas do tenant
  DELETE /api/counting/sessions/<id>         — encerrar sessão
  GET    /api/counting/sessions/<id>/stats   — contagens em tempo real

LPR (task-050):
  PATCH  /api/counting/sessions/<id>/plate   — registrar/corrigir placa (OCR ou manual)
  GET    /api/counting/sessions/plates       — sessões com placa (plate_text IS NOT NULL)
"""
import logging
from uuid import UUID

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.domain.services.lpr_service import parse_plate
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.counting_repository import CountingRepository
from app.domain.services.counting_service import CountingService

logger = logging.getLogger(__name__)
counting_bp = Blueprint("counting", __name__)


def _get_service() -> CountingService:
    pool = DatabasePool.get_instance()
    return CountingService(CountingRepository(pool))


def _get_repo() -> CountingRepository:
    pool = DatabasePool.get_instance()
    return CountingRepository(pool)


@counting_bp.route("/api/counting/sessions", methods=["POST"])
@jwt_required()
def start_session():  # type: ignore[no-untyped-def]
    """Inicia nova sessão de contagem para uma câmera."""
    body = request.get_json(silent=True) or {}
    camera_id = body.get("camera_id")
    module_code = body.get("module_code", "epi")

    if not camera_id:
        return error("camera_id é obrigatório", 400)

    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        session = svc.start_session(
            tenant_id=UUID(str(tenant_id)),
            camera_id=UUID(camera_id),
            module_code=module_code,
        )
        return success({"session": session}), 201
    except EpiMonitorError as exc:
        return error(str(exc), exc.status_code if hasattr(exc, "status_code") else 400)
    except Exception as exc:
        logger.error("start_session_error: %s", exc)
        return error("Erro ao iniciar sessão", 500)


@counting_bp.route("/api/counting/sessions", methods=["GET"])
@jwt_required()
def list_sessions():  # type: ignore[no-untyped-def]
    """Lista sessões ativas do tenant."""
    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        sessions = svc.list_active(UUID(str(tenant_id)))
        return success({"sessions": sessions})
    except Exception as exc:
        logger.error("list_sessions_error: %s", exc)
        return error("Erro ao listar sessões", 500)


@counting_bp.route("/api/counting/sessions/<session_id>", methods=["DELETE"])
@jwt_required()
def stop_session(session_id: str):  # type: ignore[no-untyped-def]
    """Encerra sessão e retorna totais finais."""
    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        session = svc.stop_session(
            session_id=UUID(session_id),
            tenant_id=UUID(str(tenant_id)),
        )
        return success({"session": session})
    except EpiMonitorError as exc:
        return error(str(exc), exc.status_code if hasattr(exc, "status_code") else 400)
    except Exception as exc:
        logger.error("stop_session_error: %s", exc)
        return error("Erro ao encerrar sessão", 500)


@counting_bp.route("/api/counting/sessions/<session_id>/stats", methods=["GET"])
@jwt_required()
def session_stats(session_id: str):  # type: ignore[no-untyped-def]
    """Retorna contagens ao vivo por classe."""
    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        stats = svc.get_live_stats(
            session_id=UUID(session_id),
            tenant_id=UUID(str(tenant_id)),
        )
        return success(stats)
    except EpiMonitorError as exc:
        return error(str(exc), exc.status_code if hasattr(exc, "status_code") else 400)
    except Exception as exc:
        logger.error("session_stats_error: %s", exc)
        return error("Erro ao buscar estatísticas", 500)


# ---------------------------------------------------------------------------
# LPR — task-050
# ---------------------------------------------------------------------------

@counting_bp.route("/api/counting/sessions/<session_id>/plate", methods=["PATCH"])
@jwt_required()
def update_plate(session_id: str):  # type: ignore[no-untyped-def]
    """
    Registra ou corrige a placa associada a uma sessão de carga/descarga.

    Body (JSON):
      plate_text        string  — texto da placa (ex.: "ABC1D23")
      plate_confidence  float   — confiança do OCR; omitir para correção manual
      plate_review      bool    — forçar flag de revisão (raro; normalmente calculado)

    Se plate_confidence < 0.80 → plate_review=True automaticamente.
    Se plate_confidence ausente → plate_manual=True (correção humana).
    Valida formato da placa (Mercosul ou antiga); rejeita texto inválido.
    Isolamento: só atualiza se session.tenant_id == JWT tenant_id.
    """
    body = request.get_json(silent=True) or {}
    plate_text_raw = (body.get("plate_text") or "").strip()
    plate_confidence = body.get("plate_confidence")
    force_review = bool(body.get("plate_review", False))

    if not plate_text_raw:
        return error("plate_text é obrigatório", 400)

    # Valida formato
    parsed = parse_plate(plate_text_raw)
    if not parsed:
        return error(
            f"Formato de placa inválido: '{plate_text_raw}'. "
            "Use Mercosul (ABC1D23) ou antiga (ABC1234).",
            422,
        )

    plate_text = parsed["normalized"]
    is_manual = plate_confidence is None

    # Decide flag de revisão
    if is_manual:
        plate_review = False  # Correção humana — confiança implícita = 1.0
    elif isinstance(plate_confidence, (int, float)):
        plate_confidence = float(plate_confidence)
        plate_review = force_review or plate_confidence < 0.80
    else:
        return error("plate_confidence deve ser um número entre 0.0 e 1.0", 400)

    try:
        tenant_id = get_tenant_id()
        repo = _get_repo()
        updated = repo.update_plate(
            session_id=UUID(session_id),
            tenant_id=UUID(str(tenant_id)),
            plate_text=plate_text,
            plate_confidence=plate_confidence if not is_manual else None,
            plate_review=plate_review,
            plate_manual=is_manual,
        )
        if not updated:
            return error("Sessão não encontrada", 404)
        return success({
            "session_id": session_id,
            "plate_text": plate_text,
            "plate_confidence": plate_confidence,
            "plate_review": plate_review,
            "plate_manual": is_manual,
            "plate_format": parsed["format"],
        })
    except ValueError:
        return error("session_id inválido", 400)
    except Exception as exc:
        logger.error("update_plate_error: %s", exc)
        return error("Erro ao atualizar placa", 500)


@counting_bp.route("/api/counting/sessions/plates", methods=["GET"])
@jwt_required()
def list_sessions_with_plates():  # type: ignore[no-untyped-def]
    """
    Lista sessões que têm placa associada (plate_text IS NOT NULL).

    Query params:
      review_only=true  — filtra apenas as marcadas para revisão humana
    """
    try:
        tenant_id = get_tenant_id()
        only_review = request.args.get("review_only", "").lower() in ("1", "true", "yes")
        repo = _get_repo()
        sessions = repo.list_sessions_with_plate(
            UUID(str(tenant_id)),
            only_review=only_review,
        )
        return success({"sessions": sessions})
    except Exception as exc:
        logger.error("list_sessions_plates_error: %s", exc)
        return error("Erro ao listar sessões com placa", 500)
