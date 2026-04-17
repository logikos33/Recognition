"""
EPI Monitor V2 — Admin Routes (superadmin only).

Endpoints:
  GET  /api/v1/admin/dashboard           — resumo global (todos os tenants)
  GET  /api/v1/admin/tenants             — listar todos os tenants
  POST /api/v1/admin/tenants             — criar tenant + schema + admin user
  PATCH /api/v1/admin/tenants/<id>       — atualizar plan, modules_enabled, active
  GET  /api/v1/admin/tenants/<id>/overview — dados do tenant (câmeras, alertas, jobs)
  GET  /api/v1/admin/workers/status      — status dos workers por tenant

Todos protegidos por @require_superadmin.
"""
import json
import logging
import uuid

from flask import Blueprint, request

from app.core.auth import hash_password
from app.core.responses import error, success
from app.core.tenant import (
    get_schema_whitelist,
    invalidate_schema_cache,
    require_superadmin,
    set_search_path,
    validate_schema,
)
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")


def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


# ---------------------------------------------------------------------------
# GET /api/v1/admin/dashboard
# ---------------------------------------------------------------------------
@admin_bp.route("/dashboard", methods=["GET"])
@require_superadmin
def get_dashboard():  # type: ignore[no-untyped-def]
    """
    Retorna resumo global da plataforma.

    Consulta public.tenants e public.users para métricas básicas.
    Câmeras e alertas online requerem queries por schema — retornados como 0
    nesta versão (fase 1). Fase 2: agregar via worker health Redis.
    """
    try:
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                # Contar tenants
                cur.execute("SELECT COUNT(*) FROM tenants")
                tenants_total = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM tenants WHERE is_active = true")
                tenants_active = cur.fetchone()[0]

                # Contar usuários
                cur.execute("SELECT COUNT(*) FROM users")
                users_total = cur.fetchone()[0]

                # Listar tenants com count de usuários
                cur.execute("""
                    SELECT
                        t.id, t.slug, t.name, t.plan, t.schema_name,
                        t.is_active, t.modules_enabled,
                        COUNT(u.id) AS user_count
                    FROM tenants t
                    LEFT JOIN users u ON u.tenant_id = t.id
                    GROUP BY t.id
                    ORDER BY t.created_at DESC
                """)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                tenants = []
                for row in rows:
                    r = dict(zip(cols, row))
                    r["id"] = str(r["id"])
                    # modules_enabled pode vir como str ou list do psycopg2
                    if isinstance(r.get("modules_enabled"), str):
                        try:
                            r["modules_enabled"] = json.loads(r["modules_enabled"])
                        except Exception:
                            r["modules_enabled"] = []
                    tenants.append(r)

        return success({
            "tenants_total": tenants_total,
            "tenants_active": tenants_active,
            "users_total": users_total,
            "cameras_online": 0,   # fase 2: agregar via Redis worker health
            "alerts_24h": 0,       # fase 2: agregar por schema
            "tenants": tenants,
        })

    except Exception as exc:
        logger.error("admin_dashboard_error: %s", exc, exc_info=True)
        return error("Erro ao carregar dashboard", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/tenants
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants", methods=["GET"])
@require_superadmin
def list_tenants():  # type: ignore[no-untyped-def]
    """Lista todos os tenants com count de usuários."""
    try:
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        t.id, t.slug, t.name, t.plan, t.schema_name,
                        t.is_active, t.modules_enabled, t.created_at,
                        COUNT(u.id) AS user_count
                    FROM tenants t
                    LEFT JOIN users u ON u.tenant_id = t.id
                    GROUP BY t.id
                    ORDER BY t.created_at DESC
                """)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                tenants = []
                for row in rows:
                    r = dict(zip(cols, row))
                    r["id"] = str(r["id"])
                    if isinstance(r.get("modules_enabled"), str):
                        try:
                            r["modules_enabled"] = json.loads(r["modules_enabled"])
                        except Exception:
                            r["modules_enabled"] = []
                    if r.get("created_at"):
                        r["created_at"] = r["created_at"].isoformat()
                    tenants.append(r)

        return success({"tenants": tenants})

    except Exception as exc:
        logger.error("list_tenants_error: %s", exc, exc_info=True)
        return error("Erro ao listar tenants", 500)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/tenants
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants", methods=["POST"])
@require_superadmin
def create_tenant():  # type: ignore[no-untyped-def]
    """
    Cria novo tenant + schema PostgreSQL + usuário admin inicial.

    Body: {name, slug, plan, modules_enabled}
    Executa: SELECT public.create_tenant_schema(slug)
    """
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        slug = (data.get("slug") or "").strip().lower()
        plan = data.get("plan", "standard")
        modules_enabled = data.get("modules_enabled", ["epi", "counting", "basic"])

        if not name or not slug:
            return error("name e slug são obrigatórios", 400)

        # slug só pode ter letras, números e hifens
        if not slug.replace("-", "").isalnum():
            return error("slug inválido: use apenas letras, números e hifens", 400)

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                # Verificar se slug já existe
                cur.execute("SELECT id FROM tenants WHERE slug = %s", (slug,))
                if cur.fetchone():
                    return error(f"Slug '{slug}' já existe", 409)

                # Criar tenant
                tenant_id = str(uuid.uuid4())
                modules_json = json.dumps(modules_enabled)
                cur.execute("""
                    INSERT INTO tenants (id, slug, name, plan, schema_name, modules_enabled, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, true)
                    RETURNING id, slug, name, plan, schema_name, is_active
                """, (tenant_id, slug, name, plan, slug, modules_json))
                tenant = dict(zip([d[0] for d in cur.description], cur.fetchone()))
                tenant["id"] = str(tenant["id"])

                # Criar schema PostgreSQL (usa a função criada na migration 024)
                cur.execute("SELECT public.create_tenant_schema(%s)", (slug,))

                # Criar usuário admin inicial
                admin_email = f"admin@{slug}.epimonitor.local"
                temp_password = f"EpiMonitor@{slug[:4].upper()}2024!"
                password_hash = hash_password(temp_password)
                cur.execute("""
                    INSERT INTO users (email, password_hash, name, role, tenant_id, is_active)
                    VALUES (%s, %s, %s, 'admin', %s, true)
                    ON CONFLICT (email) DO NOTHING
                """, (admin_email, password_hash, f"Admin {name}", tenant_id))

            conn.commit()

        # Invalidar cache de schemas
        invalidate_schema_cache()

        logger.info("tenant_created: slug=%s schema=%s", slug, slug)
        return success({
            "tenant": tenant,
            "admin_email": admin_email,
            "temp_password": temp_password,
            "message": "Tenant criado. Altere a senha do admin no primeiro acesso.",
        }, status=201)

    except Exception as exc:
        logger.error("create_tenant_error: %s", exc, exc_info=True)
        return error("Erro ao criar tenant", 500)


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/tenants/<id>
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>", methods=["PATCH"])
@require_superadmin
def update_tenant(tenant_id: str):  # type: ignore[no-untyped-def]
    """Atualiza plan, modules_enabled ou is_active de um tenant."""
    try:
        data = request.get_json() or {}
        allowed_fields = {"plan", "modules_enabled", "active"}
        updates = {k: v for k, v in data.items() if k in allowed_fields}

        if not updates:
            return error("Nenhum campo válido para atualizar", 400)

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                if "plan" in updates:
                    cur.execute(
                        "UPDATE tenants SET plan = %s WHERE id = %s",
                        (updates["plan"], tenant_id),
                    )
                if "modules_enabled" in updates:
                    cur.execute(
                        "UPDATE tenants SET modules_enabled = %s::jsonb WHERE id = %s",
                        (json.dumps(updates["modules_enabled"]), tenant_id),
                    )
                if "active" in updates:
                    cur.execute(
                        "UPDATE tenants SET is_active = %s WHERE id = %s",
                        (bool(updates["active"]), tenant_id),
                    )
            conn.commit()

        return success({"updated": True})

    except Exception as exc:
        logger.error("update_tenant_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar tenant", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/tenants/<id>/overview
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/overview", methods=["GET"])
@require_superadmin
def tenant_overview(tenant_id: str):  # type: ignore[no-untyped-def]
    """
    Retorna visão operacional do tenant: câmeras, alertas recentes, jobs.

    Usa SET search_path para o schema do tenant (read-only).
    schema_name é validado contra whitelist antes de usar.
    """
    try:
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                # Buscar tenant e schema
                cur.execute(
                    "SELECT id, name, slug, plan, schema_name FROM tenants WHERE id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
                if not row:
                    return error("Tenant não encontrado", 404)

                tenant = dict(zip([d[0] for d in cur.description], row))
                tenant["id"] = str(tenant["id"])
                schema_name = tenant.get("schema_name", "public")

            # Validar schema contra whitelist antes de usar em SET search_path
            if not validate_schema(schema_name):
                return error(f"Schema inválido: {schema_name}", 400)

            with pool.get_connection() as conn2:
                with conn2.cursor() as cur2:
                    set_search_path(conn2, schema_name)

                    # Câmeras
                    cameras = []
                    try:
                        cur2.execute("SELECT id, name, status, active_module FROM cameras LIMIT 50")
                        rows = cur2.fetchall()
                        cols = [d[0] for d in cur2.description]
                        cameras = [dict(zip(cols, r)) for r in rows]
                        for c in cameras:
                            c["id"] = str(c["id"])
                    except Exception:
                        pass  # Tabela pode não existir no schema

                    # Alertas últimas 24h
                    recent_alerts = []
                    try:
                        cur2.execute("""
                            SELECT id, violation_type, confidence, created_at
                            FROM alerts
                            WHERE created_at >= NOW() - INTERVAL '24 hours'
                            ORDER BY created_at DESC LIMIT 20
                        """)
                        rows = cur2.fetchall()
                        cols = [d[0] for d in cur2.description]
                        recent_alerts = [dict(zip(cols, r)) for r in rows]
                        for a in recent_alerts:
                            a["id"] = str(a["id"])
                            if a.get("created_at"):
                                a["created_at"] = a["created_at"].isoformat()
                    except Exception:
                        pass

                    # Training jobs
                    training_jobs = []
                    try:
                        cur2.execute("""
                            SELECT id, name, status, module, created_at
                            FROM training_jobs
                            ORDER BY created_at DESC LIMIT 10
                        """)
                        rows = cur2.fetchall()
                        cols = [d[0] for d in cur2.description]
                        training_jobs = [dict(zip(cols, r)) for r in rows]
                        for j in training_jobs:
                            j["id"] = str(j["id"])
                            if j.get("created_at"):
                                j["created_at"] = j["created_at"].isoformat()
                    except Exception:
                        pass

        return success({
            "tenant": tenant,
            "cameras": cameras,
            "recent_alerts": recent_alerts,
            "training_jobs": training_jobs,
        })

    except Exception as exc:
        logger.error("tenant_overview_error: %s", exc, exc_info=True)
        return error("Erro ao carregar overview do tenant", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/workers/status
# ---------------------------------------------------------------------------
@admin_bp.route("/workers/status", methods=["GET"])
@require_superadmin
def workers_status():  # type: ignore[no-untyped-def]
    """
    Retorna status de todos os workers por tenant_schema.

    Lê Redis: worker:heartbeat:{schema} (TTL 90s).
    Se chave ausente → worker "railway" (fallback automático).
    """
    try:
        from app.infrastructure.queue.worker_registry import get_all_workers_status
        workers = get_all_workers_status()
        return success({"workers": workers})
    except ImportError:
        # worker_registry ainda não existe — retornar placeholder
        whitelist = get_schema_whitelist()
        workers = {schema: "railway" for schema in whitelist if schema != "public"}
        return success({"workers": workers})
    except Exception as exc:
        logger.error("workers_status_error: %s", exc, exc_info=True)
        return error("Erro ao buscar status dos workers", 500)
