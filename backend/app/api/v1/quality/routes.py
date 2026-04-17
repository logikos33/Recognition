"""
Módulo de Qualidade Industrial — Blueprint de rotas.

Prefixo: /api/v1/quality
Padrão de resposta: success() / error() de app.core.responses
Padrão DB: DatabasePool.get_connection() com RealDictCursor
Tenant: get_tenant_schema() + SET search_path TO {schema}, public
"""
import json
import logging
import os
from datetime import UTC, datetime
from uuid import uuid4

from flask import Blueprint, request
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.api.v1.quality.classes import DEFECT_CATEGORIES, QUALITY_CLASSES, VALID_CLASS_IDS
from app.core.quality_video_security import (
    RateLimitError,
    SecurityError,
    generate_quality_view_url,
    verify_andon_access,
)
from app.core.responses import error, success

logger = logging.getLogger(__name__)

# Blueprint com prefixo /api/v1/quality
quality_bp = Blueprint("quality", __name__, url_prefix="/api/v1/quality")


# ============================================================
# Helpers internos
# ============================================================

def _get_pool():
    """Retorna DatabasePool instance ou levanta RuntimeError."""
    from app.infrastructure.database.connection import DatabasePool
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado")
    return pool


def _require_jwt():
    """Verifica JWT e retorna (user_id_str, tenant_schema, modules_list)."""
    verify_jwt_in_request()
    claims = get_jwt()
    user_id = get_jwt_identity()
    tenant_schema = claims.get("tenant_schema", "public")
    modules = claims.get("modules", [])
    return user_id, tenant_schema, modules


def _set_search_path(cur, tenant_schema: str) -> None:
    """SET search_path para o tenant — chamado no início de cada handler."""
    cur.execute("SET search_path TO %s, public", (tenant_schema,))


def _require_quality_module(modules: list) -> bool:
    """Retorna True se 'quality' está nos módulos do tenant."""
    return "quality" in modules


def _current_shift() -> str:
    """Retorna turno atual com base na hora UTC (configurable)."""
    hour = datetime.now(UTC).hour
    if 6 <= hour < 14:
        return "morning"
    elif 14 <= hour < 22:
        return "afternoon"
    return "night"


def _publish_redis(channel: str, payload: dict) -> None:
    """Publica mensagem no Redis. Best-effort — nunca falha o endpoint."""
    try:
        import redis as _redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = _redis.from_url(redis_url, decode_responses=True, socket_timeout=3)
        r.publish(channel, json.dumps(payload))
    except Exception as exc:
        logger.warning("quality_redis_publish_error: channel=%s err=%s", channel, exc)


def _check_retrain_threshold(cur, tenant_schema: str, camera_id: str) -> None:
    """
    Verifica se o threshold de sugestões de retreino foi atingido (padrão: 5).
    Se sim, publica no Redis para notificar o frontend.
    """
    threshold = int(os.environ.get("QUALITY_RETRAIN_THRESHOLD", "5"))
    cur.execute(
        "SELECT COUNT(*) AS total FROM quality_retrain_suggestions WHERE status = 'pending'"
    )
    row = cur.fetchone()
    if row and row["total"] >= threshold:
        _publish_redis(
            f"quality:retrain_threshold:{tenant_schema}",
            {"camera_id": camera_id, "pending_count": row["total"]},
        )


# ============================================================
# CLASSES E CATEGORIAS
# ============================================================

@quality_bp.route("/classes", methods=["GET"])
def get_classes():
    """GET /api/v1/quality/classes — lista classes YOLO do módulo qualidade."""
    try:
        _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)
    return success(QUALITY_CLASSES)


@quality_bp.route("/defect-categories", methods=["GET"])
def get_defect_categories():
    """GET /api/v1/quality/defect-categories — lista categorias de defeito."""
    try:
        _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)
    return success(DEFECT_CATEGORIES)


# ============================================================
# CÂMERAS DO MÓDULO QUALIDADE
# ============================================================

@quality_bp.route("/cameras", methods=["GET"])
def list_quality_cameras():
    """GET /api/v1/quality/cameras — câmeras com active_module='quality' do tenant."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                SELECT
                    c.id, c.name, c.location, c.status, c.active_module,
                    c.model_quality_id, c.created_at,
                    qcc.is_setup_mode, qcc.product_type, qcc.production_order,
                    qcc.ok_confidence_threshold, qcc.nok_confidence_threshold,
                    qcc.inspection_cooldown_ms,
                    (SELECT created_at FROM quality_inspections
                     WHERE camera_id = c.id ORDER BY created_at DESC LIMIT 1) AS last_inspection_at,
                    (SELECT result FROM quality_inspections
                     WHERE camera_id = c.id ORDER BY created_at DESC LIMIT 1) AS last_result
                FROM cameras c
                LEFT JOIN quality_camera_config qcc ON qcc.camera_id = c.id
                WHERE c.active_module = 'quality'
                ORDER BY c.name
            """)
            cameras = [dict(r) for r in cur.fetchall()]
            # Converter UUIDs para string
            for cam in cameras:
                cam["id"] = str(cam["id"])
                if cam.get("model_quality_id"):
                    cam["model_quality_id"] = str(cam["model_quality_id"])
        return success(cameras)
    except Exception as exc:
        logger.error("quality_cameras_list_error: %s", exc)
        return error("Erro ao listar câmeras de qualidade", 500)


@quality_bp.route("/cameras/available", methods=["GET"])
def list_available_cameras():
    """GET /api/v1/quality/cameras/available — câmeras sem módulo quality."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                SELECT id, name, location, status, active_module
                FROM cameras
                WHERE active_module != 'quality'
                ORDER BY name
            """)
            cameras = [dict(r) for r in cur.fetchall()]
            for cam in cameras:
                cam["id"] = str(cam["id"])
        return success(cameras)
    except Exception as exc:
        logger.error("quality_cameras_available_error: %s", exc)
        return error("Erro ao listar câmeras disponíveis", 500)


@quality_bp.route("/cameras/<camera_id>/assign", methods=["POST"])
def assign_camera(camera_id: str):
    """POST /api/v1/quality/cameras/<id>/assign — atribui câmera ao módulo qualidade."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    if not _require_quality_module(modules):
        return error("Módulo qualidade não habilitado para este tenant", 403)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            # Atualizar active_module
            cur.execute(
                "UPDATE cameras SET active_module = 'quality', updated_at = NOW() "
                "WHERE id = %s RETURNING id",
                (camera_id,)
            )
            if cur.fetchone() is None:
                return error("Câmera não encontrada", 404)
            # Criar configuração padrão
            cur.execute("""
                INSERT INTO quality_camera_config (camera_id)
                VALUES (%s)
                ON CONFLICT (camera_id) DO NOTHING
            """, (camera_id,))
        return success({"camera_id": camera_id, "active_module": "quality"})
    except Exception as exc:
        logger.error("quality_camera_assign_error: %s", exc)
        return error("Erro ao atribuir câmera", 500)


@quality_bp.route("/cameras/<camera_id>/unassign", methods=["DELETE"])
def unassign_camera(camera_id: str):
    """DELETE /api/v1/quality/cameras/<id>/unassign — remove câmera do módulo qualidade."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute(
                "UPDATE cameras SET active_module = 'basic', updated_at = NOW() "
                "WHERE id = %s RETURNING id",
                (camera_id,)
            )
            if cur.fetchone() is None:
                return error("Câmera não encontrada", 404)
        return success({"camera_id": camera_id, "active_module": "basic"})
    except Exception as exc:
        logger.error("quality_camera_unassign_error: %s", exc)
        return error("Erro ao remover câmera do módulo", 500)


@quality_bp.route("/cameras/<camera_id>/config", methods=["PATCH"])
def update_camera_config(camera_id: str):
    """PATCH /api/v1/quality/cameras/<id>/config — atualiza config da câmera."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    body = request.get_json(silent=True) or {}
    allowed = {
        "product_type", "production_order", "ok_confidence_threshold",
        "nok_confidence_threshold", "inspection_cooldown_ms", "is_setup_mode",
    }
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return error("Nenhum campo válido para atualizar", 400)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            # Upsert — garante que config exista
            cur.execute("""
                INSERT INTO quality_camera_config (camera_id)
                VALUES (%s)
                ON CONFLICT (camera_id) DO NOTHING
            """, (camera_id,))
            # Construir UPDATE dinâmico com apenas campos enviados
            set_clauses = ", ".join(f"{k} = %s" for k in updates)
            values = list(updates.values()) + [camera_id]
            cur.execute(
                f"UPDATE quality_camera_config SET {set_clauses}, updated_at = NOW() "
                f"WHERE camera_id = %s RETURNING *",
                values,
            )
            row = cur.fetchone()
            if row is None:
                return error("Configuração não encontrada", 404)
            config = dict(row)
            config["camera_id"] = str(config["camera_id"])
        return success(config)
    except Exception as exc:
        logger.error("quality_camera_config_error: %s", exc)
        return error("Erro ao atualizar configuração", 500)


@quality_bp.route("/cameras/<camera_id>/toggle-setup-mode", methods=["POST"])
def toggle_setup_mode(camera_id: str):
    """POST /api/v1/quality/cameras/<id>/toggle-setup-mode — alterna modo setup."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                UPDATE quality_camera_config
                SET is_setup_mode = NOT is_setup_mode, updated_at = NOW()
                WHERE camera_id = %s
                RETURNING is_setup_mode
            """, (camera_id,))
            row = cur.fetchone()
            if row is None:
                return error("Configuração não encontrada", 404)
            new_state = row["is_setup_mode"]

        # Publicar no Redis para o worker de inferência
        _publish_redis(f"quality:setup_mode:{camera_id}", {"is_setup_mode": new_state})
        return success({"camera_id": camera_id, "is_setup_mode": new_state})
    except Exception as exc:
        logger.error("quality_toggle_setup_error: %s", exc)
        return error("Erro ao alternar modo setup", 500)


# ============================================================
# INSPEÇÕES
# ============================================================

@quality_bp.route("/inspections", methods=["GET"])
def list_inspections():
    """GET /api/v1/quality/inspections — lista paginada com filtros."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    # Filtros da query string
    camera_id = request.args.get("camera_id")
    result = request.args.get("result")
    defect_category = request.args.get("defect_category")
    feedback_status = request.args.get("feedback_status")
    shift = request.args.get("shift")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    production_order = request.args.get("production_order")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    offset = (page - 1) * per_page

    # Construir WHERE dinâmico
    conditions = []
    params: list = []

    if camera_id:
        conditions.append("camera_id = %s")
        params.append(camera_id)
    if result:
        conditions.append("result = %s")
        params.append(result)
    if defect_category:
        conditions.append("defect_category = %s")
        params.append(defect_category)
    if feedback_status:
        conditions.append("feedback_status = %s")
        params.append(feedback_status)
    if shift:
        conditions.append("shift = %s")
        params.append(shift)
    if date_from:
        conditions.append("created_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= %s")
        params.append(date_to)
    if production_order:
        conditions.append("production_order = %s")
        params.append(production_order)

    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)

            # Total para paginação
            cur.execute(f"SELECT COUNT(*) AS total FROM quality_inspections {where_sql}", params)
            total = cur.fetchone()["total"]

            # Items da página
            cur.execute(
                f"""
                SELECT qi.*, c.name AS camera_name
                FROM quality_inspections qi
                LEFT JOIN cameras c ON c.id = qi.camera_id
                {where_sql}
                ORDER BY qi.created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [per_page, offset],
            )
            items = []
            for row in cur.fetchall():
                item = dict(row)
                item["id"] = str(item["id"])
                if item.get("camera_id"):
                    item["camera_id"] = str(item["camera_id"])
                items.append(item)

        return success({
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        })
    except Exception as exc:
        logger.error("quality_inspections_list_error: %s", exc)
        return error("Erro ao listar inspeções", 500)


@quality_bp.route("/inspections/summary", methods=["GET"])
def get_inspections_summary():
    """GET /api/v1/quality/inspections/summary — métricas agregadas."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    camera_id = request.args.get("camera_id")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    shift = request.args.get("shift")
    production_order = request.args.get("production_order")

    conditions = []
    params: list = []
    if camera_id:
        conditions.append("camera_id = %s")
        params.append(camera_id)
    if date_from:
        conditions.append("created_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= %s")
        params.append(date_to)
    if shift:
        conditions.append("shift = %s")
        params.append(shift)
    if production_order:
        conditions.append("production_order = %s")
        params.append(production_order)

    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)

            # Métricas gerais
            cur.execute(f"""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE result = 'ok')  AS ok_count,
                    COUNT(*) FILTER (WHERE result = 'nok') AS nok_count,
                    COUNT(*) FILTER (WHERE feedback_status = 'pending') AS pending_feedback,
                    COUNT(*) FILTER (WHERE feedback_status = 'confirmed') AS confirmed,
                    COUNT(*) FILTER (WHERE feedback_status = 'rejected') AS rejected,
                    COUNT(*) FILTER (WHERE feedback_status = 'retrain_requested')
                        AS retrain_requested,
                    COUNT(*) FILTER (WHERE is_cep_alert = true) AS cep_alerts_count
                FROM quality_inspections {where_sql}
            """, params)
            metrics = dict(cur.fetchone())

            total = metrics["total"] or 1  # evitar divisão por zero
            metrics["ok_rate"] = round((metrics["ok_count"] or 0) / total * 100, 2)
            metrics["nok_rate"] = round((metrics["nok_count"] or 0) / total * 100, 2)

            # Distribuição de defeitos (pareto)
            cur.execute(f"""
                SELECT defect_category, COUNT(*) AS count
                FROM quality_inspections
                {where_sql}
                  {"AND" if where_sql else "WHERE"} defect_category IS NOT NULL
                GROUP BY defect_category
                ORDER BY count DESC
            """, params)
            rows = cur.fetchall()
            metrics["defect_distribution"] = {r["defect_category"]: r["count"] for r in rows}

        return success(metrics)
    except Exception as exc:
        logger.error("quality_inspections_summary_error: %s", exc)
        return error("Erro ao calcular summary", 500)


@quality_bp.route("/inspections/<inspection_id>", methods=["GET"])
def get_inspection(inspection_id: str):
    """GET /api/v1/quality/inspections/<id> — detalhe da inspeção."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                SELECT qi.*, c.name AS camera_name, c.location AS camera_location
                FROM quality_inspections qi
                LEFT JOIN cameras c ON c.id = qi.camera_id
                WHERE qi.id = %s
            """, (inspection_id,))
            row = cur.fetchone()
            if row is None:
                return error("Inspeção não encontrada", 404)
            item = dict(row)
            item["id"] = str(item["id"])
            if item.get("camera_id"):
                item["camera_id"] = str(item["camera_id"])
        return success(item)
    except Exception as exc:
        logger.error("quality_inspection_detail_error: %s", exc)
        return error("Erro ao buscar inspeção", 500)


@quality_bp.route("/inspections/<inspection_id>/clip-url", methods=["GET"])
def get_clip_url(inspection_id: str):
    """GET /api/v1/quality/inspections/<id>/clip-url — presigned URL do clip."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute(
                "SELECT clip_r2_key, clip_status FROM quality_inspections WHERE id = %s",
                (inspection_id,)
            )
            row = cur.fetchone()
            if row is None:
                return error("Inspeção não encontrada", 404)
            if row["clip_status"] != "available":
                return error(f"Clip não disponível (status: {row['clip_status']})", 404)
            if not row["clip_r2_key"]:
                return error("Clip ainda não gerado", 404)

        result = generate_quality_view_url(
            r2_key=row["clip_r2_key"],
            tenant_schema=tenant_schema,
            user_id=user_id,
            resource_type="clip",
            resource_id=inspection_id,
            ip_address=request.remote_addr,
        )
        return success(result)

    except SecurityError as exc:
        return error(str(exc), 403)
    except RateLimitError as exc:
        return error(str(exc), 429)
    except Exception as exc:
        logger.error("quality_clip_url_error: %s", exc)
        return error("Erro ao gerar URL do clip", 500)


@quality_bp.route("/inspections/<inspection_id>/evidence-url", methods=["GET"])
def get_evidence_url(inspection_id: str):
    """GET /api/v1/quality/inspections/<id>/evidence-url — presigned URL da foto."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute(
                "SELECT evidence_r2_key FROM quality_inspections WHERE id = %s",
                (inspection_id,)
            )
            row = cur.fetchone()
            if row is None:
                return error("Inspeção não encontrada", 404)
            if not row["evidence_r2_key"]:
                return error("Evidência não disponível", 404)

        result = generate_quality_view_url(
            r2_key=row["evidence_r2_key"],
            tenant_schema=tenant_schema,
            user_id=user_id,
            resource_type="evidence",
            resource_id=inspection_id,
            ip_address=request.remote_addr,
        )
        return success(result)

    except SecurityError as exc:
        return error(str(exc), 403)
    except RateLimitError as exc:
        return error(str(exc), 429)
    except Exception as exc:
        logger.error("quality_evidence_url_error: %s", exc)
        return error("Erro ao gerar URL da evidência", 500)


@quality_bp.route("/inspections/<inspection_id>/feedback", methods=["PATCH"])
def submit_feedback(inspection_id: str):
    """PATCH /api/v1/quality/inspections/<id>/feedback — registra feedback do operador."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    body = request.get_json(silent=True) or {}
    status = body.get("status")
    notes = body.get("notes", "")

    valid_statuses = {"confirmed", "rejected", "retrain_requested", "false_negative"}
    if status not in valid_statuses:
        return error(f"Status inválido. Use: {', '.join(valid_statuses)}", 400)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)

            cur.execute("""
                UPDATE quality_inspections
                SET feedback_status = %s,
                    feedback_by = %s,
                    feedback_at = NOW(),
                    feedback_notes = %s
                WHERE id = %s
                RETURNING id, camera_id, clip_r2_key, feedback_status
            """, (status, user_id, notes, inspection_id))

            row = cur.fetchone()
            if row is None:
                return error("Inspeção não encontrada", 404)

            camera_id = str(row["camera_id"]) if row["camera_id"] else None

            # Se operador solicitou retreino ou reportou falso negativo → criar sugestão
            if status in ("retrain_requested", "false_negative"):
                cur.execute("""
                    INSERT INTO quality_retrain_suggestions
                        (inspection_id, camera_id, clip_r2_key)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (inspection_id, camera_id, row["clip_r2_key"]))

                # Verificar threshold de sugestões
                if camera_id:
                    _check_retrain_threshold(cur, tenant_schema, camera_id)

        return success({"inspection_id": inspection_id, "feedback_status": status})
    except Exception as exc:
        logger.error("quality_feedback_error: %s", exc)
        return error("Erro ao registrar feedback", 500)


# ============================================================
# MONITOR ANDON — sem autenticação JWT, apenas IP interno
# ============================================================

@quality_bp.route("/andon/<camera_id>", methods=["GET"])
def get_andon_data(camera_id: str):
    """GET /api/v1/quality/andon/<camera_id> — dados para monitor de operação.
    Acesso sem JWT — validação por IP interno apenas.
    """
    if not verify_andon_access(request.remote_addr):
        return error("Acesso negado: apenas rede interna", 403)

    # Para andon, buscar o tenant_schema via camera_id na tabela pública
    # Estratégia: tentar cada tenant schema até encontrar a câmera
    try:
        import psycopg2
        import psycopg2.extras
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            return error("Banco não configurado", 500)

        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Buscar todos os tenant schemas
        cur.execute("SELECT schema_name FROM public.tenants WHERE schema_name IS NOT NULL")
        schemas = [r["schema_name"] for r in cur.fetchall()]

        camera_data = None
        found_schema = None

        for schema in schemas:
            try:
                cur.execute(f"SET search_path TO {schema}, public")
                cur.execute(
                    "SELECT id, name, location, status, active_module "
                    "FROM cameras WHERE id = %s",
                    (camera_id,)
                )
                row = cur.fetchone()
                if row:
                    camera_data = dict(row)
                    found_schema = schema
                    break
            except Exception:
                continue

        if camera_data is None:
            conn.close()
            return error("Câmera não encontrada", 404)

        cur.execute(f"SET search_path TO {found_schema}, public")

        # Config da câmera
        cur.execute("SELECT * FROM quality_camera_config WHERE camera_id = %s", (camera_id,))
        config_row = cur.fetchone()
        config = dict(config_row) if config_row else {}

        # Últimas 10 inspeções do turno
        cur.execute("""
            SELECT result, defect_category, confidence, created_at, is_cep_alert
            FROM quality_inspections
            WHERE camera_id = %s AND shift = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (camera_id, _current_shift()))
        recent = [dict(r) for r in cur.fetchall()]

        # Métricas do turno atual
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE result = 'ok') AS ok_count,
                COUNT(*) FILTER (WHERE result = 'nok') AS nok_count,
                COUNT(*) FILTER (WHERE feedback_status = 'pending') AS pending_feedback
            FROM quality_inspections
            WHERE camera_id = %s AND shift = %s
              AND DATE(created_at) = CURRENT_DATE
        """, (camera_id, _current_shift()))
        shift_stats = dict(cur.fetchone())

        # Status CEP
        cur.execute("""
            SELECT ucl, mean_nok_rate
            FROM quality_cep_baseline
            WHERE camera_id = %s
            ORDER BY baseline_date DESC LIMIT 1
        """, (camera_id,))
        cep_row = cur.fetchone()

        nok_total = shift_stats.get("total") or 1
        current_nok_rate = (shift_stats.get("nok_count") or 0) / nok_total

        cep_status = "in_control"
        if cep_row:
            if cep_row["ucl"] and current_nok_rate > cep_row["ucl"]:
                cep_status = "out_of_control"
            elif cep_row["mean_nok_rate"] and current_nok_rate > cep_row["mean_nok_rate"]:
                cep_status = "warning"

        conn.close()

        return success({
            "camera": {
                "id": str(camera_data["id"]),
                "name": camera_data["name"],
                "location": camera_data.get("location"),
                "status": camera_data["status"],
            },
            "config": {
                "product_type": config.get("product_type"),
                "production_order": config.get("production_order"),
                "is_setup_mode": config.get("is_setup_mode", False),
            },
            "shift": _current_shift(),
            "shift_stats": shift_stats,
            "last_inspections": recent,
            "cep_status": cep_status,
        })
    except Exception as exc:
        logger.error("quality_andon_error: camera=%s err=%s", camera_id, exc)
        return error("Erro ao buscar dados do Andon", 500)


# ============================================================
# ANOTAÇÃO DE FRAMES
# ============================================================

@quality_bp.route("/inspections/<inspection_id>/prepare-annotation", methods=["POST"])
def prepare_annotation(inspection_id: str):
    """POST /api/v1/quality/inspections/<id>/prepare-annotation — enfileira extração de frames."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        from app.infrastructure.queue.tasks.quality_annotation import prepare_quality_frames
        prepare_quality_frames.delay(inspection_id, tenant_schema)
        return success({"status": "preparing", "message": "Frames serão extraídos em instantes"})
    except Exception as exc:
        logger.error("quality_prepare_annotation_error: %s", exc)
        return error("Erro ao enfileirar extração de frames", 500)


@quality_bp.route("/inspections/<inspection_id>/annotation-frames", methods=["GET"])
def list_annotation_frames(inspection_id: str):
    """GET /api/v1/quality/inspections/<id>/annotation-frames — lista frames."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                SELECT id, inspection_id, r2_key, frame_number, timestamp_in_clip,
                       annotations, annotation_status, annotated_at
                FROM quality_annotation_frames
                WHERE inspection_id = %s
                ORDER BY frame_number
            """, (inspection_id,))
            frames = []
            for row in cur.fetchall():
                f = dict(row)
                f["id"] = str(f["id"])
                f["inspection_id"] = str(f["inspection_id"])
                frames.append(f)

        total = len(frames)
        annotated = sum(1 for f in frames if f["annotation_status"] == "annotated")
        skipped = sum(1 for f in frames if f["annotation_status"] == "skipped")

        return success({
            "frames": frames,
            "total": total,
            "annotated": annotated,
            "skipped": skipped,
            "pending": total - annotated - skipped,
        })
    except Exception as exc:
        logger.error("quality_annotation_frames_error: %s", exc)
        return error("Erro ao listar frames", 500)


@quality_bp.route("/annotation-frames/<frame_id>/url", methods=["GET"])
def get_frame_url(frame_id: str):
    """GET /api/v1/quality/annotation-frames/<id>/url — presigned URL do frame."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("SELECT r2_key FROM quality_annotation_frames WHERE id = %s", (frame_id,))
            row = cur.fetchone()
            if row is None:
                return error("Frame não encontrado", 404)

        result = generate_quality_view_url(
            r2_key=row["r2_key"],
            tenant_schema=tenant_schema,
            user_id=user_id,
            resource_type="frame",
            resource_id=frame_id,
            ip_address=request.remote_addr,
        )
        return success(result)

    except SecurityError as exc:
        return error(str(exc), 403)
    except RateLimitError as exc:
        return error(str(exc), 429)
    except Exception as exc:
        logger.error("quality_frame_url_error: %s", exc)
        return error("Erro ao gerar URL do frame", 500)


@quality_bp.route("/annotation-frames/<frame_id>/annotations", methods=["PUT"])
def save_annotations(frame_id: str):
    """PUT /api/v1/quality/annotation-frames/<id>/annotations — salva anotações do frame."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    body = request.get_json(silent=True) or {}
    annotations = body.get("annotations", [])
    ann_status = body.get("status", "annotated")

    if ann_status not in ("annotated", "skipped"):
        return error("Status inválido. Use: annotated | skipped", 400)

    # Validar cada anotação
    for ann in annotations:
        if ann.get("class_id") not in VALID_CLASS_IDS:
            return error(f"class_id inválido: {ann.get('class_id')}", 400)
        for coord in ("cx", "cy", "w", "h"):
            val = ann.get(coord)
            if val is None or not (0.0 <= float(val) <= 1.0):
                return error(f"Coordenada {coord} fora do intervalo [0.0, 1.0]", 400)
        # Área mínima do bbox
        if float(ann.get("w", 0)) * float(ann.get("h", 0)) < 0.001:
            return error("Bounding box com área mínima insuficiente (w*h < 0.001)", 400)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                UPDATE quality_annotation_frames
                SET annotations = %s::jsonb,
                    annotation_status = %s,
                    annotated_by = %s,
                    annotated_at = NOW()
                WHERE id = %s
                RETURNING id, annotation_status
            """, (json.dumps(annotations), ann_status, user_id, frame_id))
            row = cur.fetchone()
            if row is None:
                return error("Frame não encontrado", 404)
        return success({"frame_id": frame_id, "annotation_status": ann_status})
    except Exception as exc:
        logger.error("quality_save_annotations_error: %s", exc)
        return error("Erro ao salvar anotações", 500)


@quality_bp.route("/inspections/<inspection_id>/annotation-progress", methods=["GET"])
def get_annotation_progress(inspection_id: str):
    """GET /api/v1/quality/inspections/<id>/annotation-progress — progresso de anotação."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE annotation_status = 'annotated') AS annotated,
                    COUNT(*) FILTER (WHERE annotation_status = 'skipped') AS skipped,
                    COUNT(*) FILTER (WHERE annotation_status = 'pending') AS pending
                FROM quality_annotation_frames
                WHERE inspection_id = %s
            """, (inspection_id,))
            row = dict(cur.fetchone())
            total = row["total"] or 1
            row["pct_complete"] = round(row["annotated"] / total * 100, 1)
            row["can_create_job"] = row["annotated"] >= 10
        return success(row)
    except Exception as exc:
        logger.error("quality_annotation_progress_error: %s", exc)
        return error("Erro ao calcular progresso", 500)


@quality_bp.route("/inspections/<inspection_id>/create-training-job", methods=["POST"])
def create_job_from_inspection(inspection_id: str):
    """POST /api/v1/quality/inspections/<id>/create-training-job — job de retreino."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    body = request.get_json(silent=True) or {}
    name = body.get("name", f"Retreino {inspection_id[:8]}")

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)

            # Verificar mínimo de 10 frames anotados
            cur.execute("""
                SELECT COUNT(*) AS annotated
                FROM quality_annotation_frames
                WHERE inspection_id = %s AND annotation_status = 'annotated'
            """, (inspection_id,))
            count = cur.fetchone()["annotated"]
            if count < 10:
                return error(f"Mínimo 10 frames anotados necessários. Atual: {count}", 400)

            job_id = str(uuid4())
            cur.execute("""
                INSERT INTO quality_training_jobs
                    (id, name, status, source_type)
                VALUES (%s, %s, 'queued', 'annotation')
                RETURNING id, status
            """, (job_id, name))

        from app.infrastructure.queue.tasks.quality_training import run_quality_training
        run_quality_training.delay(job_id, tenant_schema, inspection_id)

        return success({"job_id": job_id, "status": "queued"}), 201
    except Exception as exc:
        logger.error("quality_create_job_from_inspection_error: %s", exc)
        return error("Erro ao criar job de retreino", 500)


# ============================================================
# TREINAMENTO
# ============================================================

@quality_bp.route("/training/jobs", methods=["POST"])
def create_training_job():
    """POST /api/v1/quality/training/jobs — cria job de treinamento por vídeo."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    body = request.get_json(silent=True) or {}
    name = body.get("name")
    source_video_r2_key = body.get("source_video_r2_key")
    prompt_description = body.get("prompt_description", "")

    if not name:
        return error("Campo 'name' obrigatório", 400)
    if not source_video_r2_key:
        return error("Campo 'source_video_r2_key' obrigatório", 400)

    try:
        pool = _get_pool()
        job_id = str(uuid4())
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                INSERT INTO quality_training_jobs
                    (id, name, status, source_type, source_video_r2_key, prompt_description)
                VALUES (%s, %s, 'queued', 'video', %s, %s)
                RETURNING id, status
            """, (job_id, name, source_video_r2_key, prompt_description))

        from app.infrastructure.queue.tasks.quality_training import run_quality_training
        run_quality_training.delay(job_id, tenant_schema)

        return success({"job_id": job_id, "status": "queued"}), 201
    except Exception as exc:
        logger.error("quality_training_job_create_error: %s", exc)
        return error("Erro ao criar job de treinamento", 500)


@quality_bp.route("/training/jobs", methods=["GET"])
def list_training_jobs():
    """GET /api/v1/quality/training/jobs — lista jobs do tenant."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                SELECT id, name, status, source_type, frames_extracted, frames_annotated,
                       metrics, error_message, active, created_at, updated_at
                FROM quality_training_jobs
                ORDER BY created_at DESC
            """)
            jobs = []
            for row in cur.fetchall():
                j = dict(row)
                j["id"] = str(j["id"])
                jobs.append(j)
        return success(jobs)
    except Exception as exc:
        logger.error("quality_training_jobs_list_error: %s", exc)
        return error("Erro ao listar jobs", 500)


@quality_bp.route("/training/jobs/<job_id>", methods=["GET"])
def get_training_job(job_id: str):
    """GET /api/v1/quality/training/jobs/<id> — detalhe do job."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("SELECT * FROM quality_training_jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
            if row is None:
                return error("Job não encontrado", 404)
            j = dict(row)
            j["id"] = str(j["id"])
        return success(j)
    except Exception as exc:
        logger.error("quality_training_job_detail_error: %s", exc)
        return error("Erro ao buscar job", 500)


@quality_bp.route("/training/jobs/<job_id>/progress", methods=["GET"])
def get_training_progress(job_id: str):
    """GET /api/v1/quality/training/jobs/<id>/progress.

    Retorna progresso via Redis — sem bater no banco.
    """
    try:
        _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        import redis as _redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = _redis.from_url(redis_url, decode_responses=True, socket_timeout=3)
        raw = r.get(f"quality:training_progress:{job_id}")
        if raw is None:
            return success({"stage": "unknown", "pct": 0})
        return success(json.loads(raw))
    except Exception as exc:
        logger.error("quality_training_progress_error: %s", exc)
        return error("Erro ao buscar progresso", 500)


@quality_bp.route("/training/models/<model_id>/activate", methods=["POST"])
def activate_model(model_id: str):
    """POST /api/v1/quality/training/models/<id>/activate — ativa modelo para câmeras."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    body = request.get_json(silent=True) or {}
    camera_ids = body.get("camera_ids", [])
    if not camera_ids:
        return error("camera_ids obrigatório e não pode ser vazio", 400)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)

            # Verificar que job existe
            cur.execute("SELECT id FROM quality_training_jobs WHERE id = %s", (model_id,))
            if cur.fetchone() is None:
                return error("Modelo não encontrado", 404)

            # Atualizar câmeras
            for cam_id in camera_ids:
                cur.execute(
                    "UPDATE cameras SET model_quality_id = %s, updated_at = NOW() WHERE id = %s",
                    (model_id, cam_id)
                )
                # Publicar para worker recarregar modelo
                _publish_redis(f"quality:model_changed:{cam_id}", {"model_id": model_id})

            # Marcar job como ativo (desativar os demais)
            cur.execute("UPDATE quality_training_jobs SET active = false")
            cur.execute("UPDATE quality_training_jobs SET active = true WHERE id = %s", (model_id,))

        return success({"model_id": model_id, "cameras_updated": len(camera_ids)})
    except Exception as exc:
        logger.error("quality_activate_model_error: %s", exc)
        return error("Erro ao ativar modelo", 500)


@quality_bp.route("/reference-snapshots/<camera_id>", methods=["GET"])
def get_reference_snapshots(camera_id: str):
    """GET /api/v1/quality/reference-snapshots/<camera_id> — snapshots de referência."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("""
                SELECT id, camera_id, production_order, r2_key, captured_at
                FROM quality_reference_snapshots
                WHERE camera_id = %s
                ORDER BY captured_at DESC
                LIMIT 10
            """, (camera_id,))
            snapshots = [dict(r) for r in cur.fetchall()]
            for s in snapshots:
                s["id"] = str(s["id"])
                s["camera_id"] = str(s["camera_id"])

        return success(snapshots)
    except Exception as exc:
        logger.error("quality_reference_snapshots_error: %s", exc)
        return error("Erro ao buscar snapshots", 500)


# ============================================================
# CEP — Controle Estatístico de Processo
# ============================================================

@quality_bp.route("/cep/<camera_id>", methods=["GET"])
def get_cep_data(camera_id: str):
    """GET /api/v1/quality/cep/<camera_id> — dados do gráfico de controle."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    product_type = request.args.get("product_type")

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)

            # Baseline mais recente
            conditions = ["camera_id = %s"]
            params: list = [camera_id]
            if product_type:
                conditions.append("product_type = %s")
                params.append(product_type)

            cur.execute(f"""
                SELECT mean_nok_rate, stddev_nok_rate, ucl, lcl, calculated_at
                FROM quality_cep_baseline
                WHERE {" AND ".join(conditions)}
                ORDER BY baseline_date DESC
                LIMIT 1
            """, params)
            baseline = dict(cur.fetchone()) if cur.rowcount else {}

            # Taxas das últimas 24 horas (agrupado por hora)
            cur.execute("""
                SELECT
                    date_trunc('hour', created_at) AS hour,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE result = 'nok') AS nok_count
                FROM quality_inspections
                WHERE camera_id = %s
                  AND created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY date_trunc('hour', created_at)
                ORDER BY hour
            """, (camera_id,))
            rates = []
            for row in cur.fetchall():
                total = row["total"] or 1
                rate = row["nok_count"] / total
                rates.append({
                    "timestamp": row["hour"].isoformat(),
                    "rate": round(rate, 4),
                    "is_above_ucl": baseline.get("ucl") and rate > baseline["ucl"],
                })

            # Determinar status atual
            current_rate = rates[-1]["rate"] if rates else 0
            ucl = baseline.get("ucl", 0) or 0
            mean = baseline.get("mean_nok_rate", 0) or 0

            if ucl > 0 and current_rate > ucl:
                cep_status = "out_of_control"
            elif mean > 0 and current_rate > mean:
                cep_status = "warning"
            else:
                cep_status = "in_control"

        return success({
            "camera_id": camera_id,
            "baseline": baseline,
            "recent_rates": rates,
            "current_status": cep_status,
        })
    except Exception as exc:
        logger.error("quality_cep_data_error: %s", exc)
        return error("Erro ao buscar dados CEP", 500)


# ============================================================
# RELATÓRIO DE TURNO
# ============================================================

@quality_bp.route("/reports/shift", methods=["GET"])
def get_shift_report():
    """GET /api/v1/quality/reports/shift — relatório JSON do turno."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    camera_id = request.args.get("camera_id")
    shift_date = request.args.get("shift_date", datetime.now(UTC).strftime("%Y-%m-%d"))
    shift = request.args.get("shift", _current_shift())

    if not camera_id:
        return error("Parâmetro camera_id obrigatório", 400)

    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)

            # Câmera
            cur.execute("SELECT id, name, location FROM cameras WHERE id = %s", (camera_id,))
            camera_row = cur.fetchone()
            if camera_row is None:
                return error("Câmera não encontrada", 404)

            # Métricas do turno
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE result = 'ok') AS ok,
                    COUNT(*) FILTER (WHERE result = 'nok') AS nok,
                    COUNT(*) FILTER (WHERE is_cep_alert = true) AS cep_alerts,
                    AVG(confidence) AS avg_confidence
                FROM quality_inspections
                WHERE camera_id = %s
                  AND shift = %s
                  AND DATE(created_at) = %s::date
            """, (camera_id, shift, shift_date))
            metrics = dict(cur.fetchone())
            total = metrics["total"] or 1
            metrics["ok_rate"] = round((metrics["ok"] or 0) / total * 100, 2)

            # Pareto de defeitos
            cur.execute("""
                SELECT defect_category, COUNT(*) AS count
                FROM quality_inspections
                WHERE camera_id = %s AND shift = %s AND DATE(created_at) = %s::date
                  AND defect_category IS NOT NULL
                GROUP BY defect_category
                ORDER BY count DESC
            """, (camera_id, shift, shift_date))
            pareto = [dict(r) for r in cur.fetchall()]

        return success({
            "camera": {
                "id": str(camera_row["id"]),
                "name": camera_row["name"],
                "location": camera_row.get("location"),
            },
            "shift": shift,
            "shift_date": shift_date,
            "summary": metrics,
            "defect_pareto": pareto,
        })
    except Exception as exc:
        logger.error("quality_shift_report_error: %s", exc)
        return error("Erro ao gerar relatório de turno", 500)


@quality_bp.route("/reports/shift/pdf", methods=["GET"])
def get_shift_report_pdf():
    """GET /api/v1/quality/reports/shift/pdf — PDF do relatório de turno (streaming response)."""
    try:
        user_id, tenant_schema, modules = _require_jwt()
    except Exception:
        return error("Token inválido ou ausente", 401)

    camera_id = request.args.get("camera_id")
    shift_date = request.args.get("shift_date", datetime.now(UTC).strftime("%Y-%m-%d"))
    shift = request.args.get("shift", _current_shift())

    if not camera_id:
        return error("Parâmetro camera_id obrigatório", 400)

    try:
        # Buscar dados do relatório (reutiliza lógica acima)
        import io

        from flask import make_response
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            return error("Geração de PDF não disponível (reportlab não instalado)", 501)

        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            _set_search_path(cur, tenant_schema)
            cur.execute("SELECT name, location FROM cameras WHERE id = %s", (camera_id,))
            camera_row = cur.fetchone()
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE result = 'ok') AS ok,
                       COUNT(*) FILTER (WHERE result = 'nok') AS nok
                FROM quality_inspections
                WHERE camera_id = %s AND shift = %s AND DATE(created_at) = %s::date
            """, (camera_id, shift, shift_date))
            metrics = dict(cur.fetchone())

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(f"Relatório de Turno — {shift_date}", styles["Title"]))
        camera_label = camera_row['name'] if camera_row else camera_id
        story.append(Paragraph(f"Câmera: {camera_label}", styles["Normal"]))
        story.append(Spacer(1, 12))

        ok_rate = round(
            (metrics.get('ok', 0) or 0) / max(metrics.get('total', 1), 1) * 100, 2
        )
        data = [
            ["Métrica", "Valor"],
            ["Total inspeções", str(metrics.get("total", 0))],
            ["Aprovados (OK)", str(metrics.get("ok", 0))],
            ["Rejeitados (NOK)", str(metrics.get("nok", 0))],
            ["Taxa OK", f"{ok_rate}%"],
        ]
        t = Table(data)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t)
        doc.build(story)
        buf.seek(0)

        response = make_response(buf.read())
        response.headers["Content-Type"] = "application/pdf"
        # inline — nunca attachment (sem download direto)
        response.headers["Content-Disposition"] = f"inline; filename=turno_{shift_date}_{shift}.pdf"
        return response

    except Exception as exc:
        logger.error("quality_shift_pdf_error: %s", exc)
        return error("Erro ao gerar PDF do relatório", 500)
