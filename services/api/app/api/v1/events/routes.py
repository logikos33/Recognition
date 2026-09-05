"""
Events endpoints — busca investigativa, timeline e resumo agregado (task-049 + WS3).

Endpoints:
  GET /api/v1/events/search    JWT obrigatório; busca combinada de alertas por tenant
  GET /api/v1/events/timeline  JWT obrigatório; contagem de eventos por bucket de tempo
  GET /api/v1/events/summary   JWT obrigatório; agregado por classe e por câmera no período
  GET /api/v1/events/profile   JWT obrigatório; volume por hora de CAPTURA × polaridade

Filtros comuns:
  camera_id[]     UUID (repetível para múltiplas câmeras)
  class_name[]    string (repetível: "no_helmet", "plate", etc.)
  module_code     string ("epi", "fueling", ...)
  from            ISO datetime (ex.: "2025-01-15T14:00:00")
  to              ISO datetime
  min_confidence  float [0, 1]

Segurança:
  - SEMPRE filtra por tenant_id (extraído do JWT — nunca de input externo)
  - Valores de filtro passados como parâmetros SQL (%s), NUNCA interpolados em f-string
"""
import logging
from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__, url_prefix="/api/v1")

_ALLOWED_BUCKETS = frozenset({"hour", "day", "week"})
_MAX_ITEMS = 200
_MAX_SUMMARY_DAYS = 92  # protege o banco contra janelas gigantes no agregado JSONB


def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _get_repo() -> AlertRepository:
    return AlertRepository(_pool())


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _time_column() -> str:
    """Coluna de tempo pedida na query — 'captured' vira `alerts.timestamp`.

    Default 'created' (= `created_at`) preserva byte a byte o comportamento de
    quem já chama a timeline. Só o eixo de CAPTURA responde "em que horário a
    fábrica gera violação"; `created_at` responde "a que horas o servidor
    gravou" (ver `AlertRepository.capture_profile`).
    """
    return "timestamp" if request.args.get("time_field") == "captured" else "created_at"


def _safe_list(key: str) -> list[str]:
    """Extrai lista de query params (suporta key[] e key repetido)."""
    values = request.args.getlist(f"{key}[]") or request.args.getlist(key)
    return [v.strip() for v in values if v.strip()][:50]


def _serialize_event(row: dict, storage) -> dict:
    ev = {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]) if row.get("tenant_id") else None,
        "camera_id": str(row["camera_id"]) if row.get("camera_id") else None,
        "camera_name": row.get("camera_name"),
        "module_code": row.get("module_code"),
        "confidence": row.get("confidence"),
        "violations": row.get("violations") or [],
        "evidence_key": row.get("evidence_key"),
        "acknowledged": row.get("acknowledged", False),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "frame_url": None,
        "is_demo": bool(row.get("is_demo", False)),
    }
    if ev["evidence_key"]:
        try:
            ev["frame_url"] = storage.generate_presigned_download_url(
                ev["evidence_key"], ttl=3600
            )
        except Exception:
            pass
    return ev


# ---------------------------------------------------------------------------
# GET /api/v1/events/search
# ---------------------------------------------------------------------------
@events_bp.route("/events/search", methods=["GET"])
@jwt_required()
def search_events():
    try:
        tenant_id = get_tenant_id()
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(_MAX_ITEMS, max(1, int(request.args.get("per_page", 20))))
        offset = (page - 1) * per_page

        camera_ids = _safe_list("camera_id") or None
        class_names = _safe_list("class_name") or None
        module_code = (request.args.get("module_code") or "").strip() or None
        from_ts = _parse_iso(request.args.get("from"))
        to_ts = _parse_iso(request.args.get("to"))
        min_conf = _parse_float(request.args.get("min_confidence"))
        include_demo = request.args.get("include_demo", "true").strip().lower() != "false"

        result = _get_repo().search_events(
            tenant_id=tenant_id,
            limit=per_page,
            offset=offset,
            camera_ids=camera_ids,
            class_names=class_names,
            module_code=module_code,
            from_ts=from_ts,
            to_ts=to_ts,
            min_confidence=min_conf,
            include_demo=include_demo,
        )

        storage = get_storage()
        events = [_serialize_event(dict(r), storage) for r in result["items"]]
        total = result["total"]

        return success(
            {
                "events": events,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": max(1, (total + per_page - 1) // per_page),
            }
        )
    except Exception as exc:
        logger.error("search_events_error: %s", exc, exc_info=True)
        return error("Erro na busca de eventos", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/events/timeline
# ---------------------------------------------------------------------------
@events_bp.route("/events/timeline", methods=["GET"])
@jwt_required()
def events_timeline():
    try:
        tenant_id = get_tenant_id()
        bucket = request.args.get("bucket", "hour").strip().lower()
        if bucket not in _ALLOWED_BUCKETS:
            bucket = "hour"

        from_ts = _parse_iso(request.args.get("from"))
        to_ts = _parse_iso(request.args.get("to"))

        if not from_ts or not to_ts:
            return error("Parâmetros 'from' e 'to' são obrigatórios", 400)

        camera_ids = _safe_list("camera_id") or None
        class_names = _safe_list("class_name") or None
        module_code = (request.args.get("module_code") or "").strip() or None
        include_demo = request.args.get("include_demo", "true").strip().lower() != "false"

        rows = _get_repo().timeline_by_bucket(
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            bucket=bucket,
            camera_ids=camera_ids,
            class_names=class_names,
            module_code=module_code,
            include_demo=include_demo,
            time_column=_time_column(),
        )

        timeline = [
            {
                "bucket": r["bucket"].isoformat() if r.get("bucket") else None,
                "count": r["count"],
            }
            for r in rows
        ]

        return success({"timeline": timeline, "bucket": bucket})
    except Exception as exc:
        logger.error("events_timeline_error: %s", exc, exc_info=True)
        return error("Erro na timeline de eventos", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/events/summary
# ---------------------------------------------------------------------------
@events_bp.route("/events/summary", methods=["GET"])
@jwt_required()
def events_summary():
    """Agregado leve do período: total, distribuição por classe e top câmeras.

    tenant_id SEMPRE do JWT (nunca de input); from/to obrigatórios;
    janela limitada a _MAX_SUMMARY_DAYS dias.
    """
    try:
        tenant_id = get_tenant_id()

        from_ts = _parse_iso(request.args.get("from"))
        to_ts = _parse_iso(request.args.get("to"))
        if not from_ts or not to_ts:
            return error("Parâmetros 'from' e 'to' são obrigatórios", 400)
        if to_ts < from_ts:
            return error("'to' deve ser posterior a 'from'", 400)
        if (to_ts - from_ts).days > _MAX_SUMMARY_DAYS:
            return error(f"Período máximo de {_MAX_SUMMARY_DAYS} dias", 400)

        camera_ids = _safe_list("camera_id") or None
        class_names = _safe_list("class_name") or None
        module_code = (request.args.get("module_code") or "").strip() or None

        repo = _get_repo()
        total = repo.count_in_window(
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            module_code=module_code,
            camera_ids=camera_ids,
        )
        by_class = repo.violations_by_class(
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            module_code=module_code,
            camera_ids=camera_ids,
            class_names=class_names,
        )
        by_camera = repo.top_cameras_by_alerts(
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            module_code=module_code,
            limit=10,
        )

        return success(
            {
                "total": total,
                "by_class": [
                    {"class": r["class"], "count": r["count"]} for r in by_class
                ],
                "by_camera": [
                    {
                        "camera_id": str(r["camera_id"]) if r.get("camera_id") else None,
                        "camera_name": r.get("camera_name"),
                        "count": r["count"],
                    }
                    for r in by_camera
                ],
            }
        )
    except Exception as exc:
        logger.error("events_summary_error: %s", exc, exc_info=True)
        return error("Erro no resumo de eventos", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/events/profile
# ---------------------------------------------------------------------------
@events_bp.route("/events/profile", methods=["GET"])
@jwt_required()
def events_profile():
    """Perfil do período pelo HORÁRIO DE CAPTURA: volume × polaridade + tratativa.

    Um pedido só para as três perguntas que o painel faz sobre o mesmo conjunto
    de eventos — em que HORA DO DIA a fábrica gera violação, em que DIAS, e
    o que aquele total soma (violação × conformidade × não classificada).

    As linhas saem em bucket de hora UTC, como `/events/timeline`; a dobra em
    hora-do-dia e em dia é do cliente, que é quem sabe o fuso de quem lê. Ver
    `AlertRepository.capture_profile` para por que o eixo é `timestamp` e não
    `created_at`.
    """
    try:
        tenant_id = get_tenant_id()

        from_ts = _parse_iso(request.args.get("from"))
        to_ts = _parse_iso(request.args.get("to"))
        if not from_ts or not to_ts:
            return error("Parâmetros 'from' e 'to' são obrigatórios", 400)
        if to_ts < from_ts:
            return error("'to' deve ser posterior a 'from'", 400)
        if (to_ts - from_ts).days > _MAX_SUMMARY_DAYS:
            return error(f"Período máximo de {_MAX_SUMMARY_DAYS} dias", 400)

        module_code = (request.args.get("module_code") or "").strip() or None

        repo = _get_repo()
        rows = repo.capture_profile(
            tenant_id=tenant_id, from_ts=from_ts, to_ts=to_ts, module_code=module_code
        )
        situacao = repo.review_situation(
            tenant_id=tenant_id, from_ts=from_ts, to_ts=to_ts, module_code=module_code
        )

        def _iso(value):  # type: ignore[no-untyped-def]
            return value.isoformat() if value is not None else None

        return success(
            {
                "rows": [
                    {
                        "bucket": _iso(r.get("bucket")),
                        "kind": r["kind"],
                        "count": r["count"],
                    }
                    for r in rows
                ],
                "situacao": {
                    "total": situacao.get("total", 0),
                    "nao_reconhecidos": situacao.get("nao_reconhecidos", 0),
                    "procedentes": situacao.get("procedentes", 0),
                    "improcedentes": situacao.get("improcedentes", 0),
                    "cameras": situacao.get("cameras", 0),
                    "primeira_captura": _iso(situacao.get("primeira_captura")),
                    "ultima_captura": _iso(situacao.get("ultima_captura")),
                    "confianca_media": (
                        float(situacao["confianca_media"])
                        if situacao.get("confianca_media") is not None
                        else None
                    ),
                },
            }
        )
    except Exception as exc:
        logger.error("events_profile_error: %s", exc, exc_info=True)
        return error("Erro no perfil de eventos", 500)
