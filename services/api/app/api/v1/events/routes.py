"""
Events endpoints — busca investigativa e timeline (task-049).

Endpoints:
  GET /api/v1/events/search    JWT obrigatório; busca combinada de alertas por tenant
  GET /api/v1/events/timeline  JWT obrigatório; contagem de eventos por bucket de tempo

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
  - A parte dinâmica do f-string é apenas a ESTRUTURA (número de %s), não os valores
"""
import logging
from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__, url_prefix="/api/v1")

_ALLOWED_BUCKETS = frozenset({"hour", "day", "week"})
_MAX_ITEMS = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _parse_iso(value: str | None) -> datetime | None:
    """Tenta parsear ISO datetime; retorna None se inválido."""
    if not value:
        return None
    try:
        # Suporta "2025-01-15T14:00:00" e "2025-01-15T14:00:00Z"
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _parse_float(value: str | None) -> float | None:
    """Tenta parsear float; retorna None se inválido."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_list(key: str) -> list[str]:
    """Extrai lista de query params (suporta key[] e key repetido)."""
    values = request.args.getlist(f"{key}[]") or request.args.getlist(key)
    # Ignora strings vazias; limita a 50 itens para evitar abusos
    return [v.strip() for v in values if v.strip()][:50]


def _build_where(tenant_id: str) -> tuple[str, list]:
    """
    Constrói cláusula WHERE parametrizada para filtragem de alertas.

    SEGURANÇA: todos os valores do usuário passam por params (%s).
    Apenas a estrutura (contagem de placeholders) é dinâmica na f-string.
    """
    conditions: list[str] = ["tenant_id = %s"]
    params: list = [tenant_id]

    # camera_id[] — IN clause parametrizada
    camera_ids = _safe_list("camera_id")
    if camera_ids:
        placeholders = ",".join(["%s"] * len(camera_ids))
        conditions.append(f"camera_id IN ({placeholders})")
        params.extend(camera_ids)

    # class_name[] — busca em violations JSONB via ILIKE parametrizado
    class_names = _safe_list("class_name")
    if class_names:
        name_conds = " OR ".join(["violations::text ILIKE %s"] * len(class_names))
        conditions.append(f"({name_conds})")
        params.extend([f"%{cn}%" for cn in class_names])

    # module_code
    module_code = (request.args.get("module_code") or "").strip()
    if module_code:
        conditions.append("module_code = %s")
        params.append(module_code)

    # from / to
    from_dt = _parse_iso(request.args.get("from"))
    to_dt = _parse_iso(request.args.get("to"))
    if from_dt:
        conditions.append("created_at >= %s")
        params.append(from_dt)
    if to_dt:
        conditions.append("created_at <= %s")
        params.append(to_dt)

    # min_confidence
    min_conf = _parse_float(request.args.get("min_confidence"))
    if min_conf is not None:
        conditions.append("confidence >= %s")
        params.append(min_conf)

    return " AND ".join(conditions), params


def _serialize_event(row: dict, storage) -> dict:
    """Serializa um row de alerta para JSON, adicionando URL assinada do frame."""
    ev = {
        "id": str(row["id"]),
        "camera_id": str(row["camera_id"]) if row.get("camera_id") else None,
        "module_code": row.get("module_code"),
        "confidence": row.get("confidence"),
        "violations": row.get("violations") or [],
        "evidence_key": row.get("evidence_key"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "frame_url": None,
    }
    if ev["evidence_key"]:
        try:
            ev["frame_url"] = storage.generate_presigned_download_url(
                ev["evidence_key"], ttl=3600
            )
        except Exception:
            pass  # Sem URL de frame — não falha a busca
    return ev


# ---------------------------------------------------------------------------
# GET /api/v1/events/search
# ---------------------------------------------------------------------------
@events_bp.route("/events/search", methods=["GET"])
@jwt_required()
def search_events():
    """
    Busca investigativa de eventos por tenant.
    Parâmetros via querystring; tenant_id sempre extraído do JWT.
    """
    try:
        tenant_id = get_tenant_id()
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(_MAX_ITEMS, max(1, int(request.args.get("per_page", 20))))
        offset = (page - 1) * per_page

        where, params = _build_where(tenant_id)
        count_sql = f"SELECT COUNT(*) AS count FROM alerts WHERE {where}"  # noqa: S608
        items_sql = (
            f"SELECT id, camera_id, module_code, violations, confidence, "  # noqa: S608
            f"evidence_key, created_at "
            f"FROM alerts WHERE {where} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s"
        )

        pool = _pool()
        storage = get_storage()

        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(count_sql, tuple(params))
            total_row = cur.fetchone()
            total = total_row["count"] if total_row else 0

            cur.execute(items_sql, tuple(params) + (per_page, offset))
            rows = cur.fetchall()

        events = [_serialize_event(dict(r), storage) for r in rows]

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
    """
    Contagem de eventos por bucket de tempo.
    Parâmetros: os mesmos filtros de search + bucket (hour|day|week, padrão: hour).
    Retorna [{bucket: "2025-01-15T14:00:00", count: N}, ...].
    """
    try:
        tenant_id = get_tenant_id()
        bucket = request.args.get("bucket", "hour").strip().lower()
        if bucket not in _ALLOWED_BUCKETS:
            bucket = "hour"

        where, params = _build_where(tenant_id)
        timeline_sql = (
            f"SELECT DATE_TRUNC(%s, created_at) AS bucket, COUNT(*) AS count "  # noqa: S608
            f"FROM alerts WHERE {where} "
            f"GROUP BY DATE_TRUNC(%s, created_at) "
            f"ORDER BY bucket ASC "
            f"LIMIT 200"
        )
        # bucket é validado contra allowlist — não vem diretamente do user input
        timeline_params = (bucket,) + tuple(params) + (bucket,)

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(timeline_sql, timeline_params)
            rows = cur.fetchall()

        buckets = [
            {
                "bucket": r["bucket"].isoformat() if r.get("bucket") else None,
                "count": r["count"],
            }
            for r in rows
        ]

        return success({"buckets": buckets, "bucket_size": bucket})
    except Exception as exc:
        logger.error("events_timeline_error: %s", exc, exc_info=True)
        return error("Erro na timeline de eventos", 500)
