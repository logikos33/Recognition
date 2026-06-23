"""
Recognition — Admin Routes (superadmin only).

Todos os endpoints protegidos por @require_superadmin exceto /workers/heartbeat
que usa X-Worker-Secret header.

Grupos de endpoints:
  Dashboard     GET  /api/v1/admin/dashboard
  Tenants       GET|POST /tenants, GET|PATCH /tenants/<id>
                POST /tenants/<id>/suspend|reactivate
                GET  /tenants/<id>/plan-history, GET /tenants/<id>/overview
  Users         GET|POST /users, GET|PATCH /users/<id>
                POST /users/<id>/deactivate|reactivate|force-password-reset
                GET|DELETE /users/<id>/sessions
                GET  /permissions/matrix
  Approvals     GET|POST /training-approvals, GET /training-approvals/<id>
                POST /training-approvals/<id>/approve|reject
  Workers       GET /workers, GET /workers/<schema>
                POST /workers/<schema>/restart
                GET  /workers/<schema>/metrics
                POST /workers/heartbeat  (X-Worker-Secret, sem JWT)
  Plans         GET|POST /plans, PATCH /plans/<id>
                GET  /plans/<id>/tenants
  Flags         GET|PATCH /feature-flags
                GET|PATCH /feature-flags/tenant/<id>
  Tickets       GET /tickets, GET|PATCH /tickets/<id>
                POST /tickets/<id>/reply
                GET  /tickets/stats
  Audit         GET /audit-log, GET /audit-log/export (CSV)
  Announcements GET|POST|PATCH|DELETE /announcements
  Health        GET /health/platform, GET /health/metrics

Endpoints cliente (não-admin):
  GET  /api/v1/announcements          (JWT de qualquer role)
  POST /api/v1/announcements/<id>/read
"""
import csv
import io
import json
import logging
import os
import uuid
from datetime import datetime

import redis as _redis
from flask import Blueprint, Response, current_app, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_role, hash_password
from app.core.responses import error, success
from app.core.tenant import (
    invalidate_schema_cache,
    log_audit,
    require_superadmin,
    set_search_path,
    validate_schema,
)
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")
client_bp = Blueprint("client_announcements", __name__, url_prefix="/api/v1")

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _get_redis():
    return _redis.from_url(_REDIS_URL, decode_responses=True)


def _row_to_dict(cur, row):
    """Converte linha de cursor em dict usando description."""
    return _clean_row(dict(row))


def _rows_to_list(cur, rows):
    return [_clean_row(dict(r)) for r in rows]


def _serialize(obj):
    """Serializa UUIDs e datetimes para JSON."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "hex"):
        return str(obj)
    return obj


def _clean_row(row: dict) -> dict:
    """Converte UUIDs e datetimes para strings em um dict."""
    result = {}
    for k, v in row.items():
        if v is None:
            result[k] = None
        elif hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif hasattr(v, "hex") and not isinstance(v, (int, float, bool)):
            result[k] = str(v)
        else:
            result[k] = v
    return result


def _get_actor():
    """Retorna (actor_id, actor_role) do JWT atual."""
    try:
        actor_id = get_current_user_id()
        actor_role = get_role()
        return actor_id, actor_role
    except Exception:
        return None, "superadmin"


def _get_ip():
    return request.remote_addr


def _get_ua():
    return request.headers.get("User-Agent", "")[:500]


def _page_params():
    """Extrai page e per_page da querystring."""
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    offset = (page - 1) * per_page
    return page, per_page, offset


# ---------------------------------------------------------------------------
# GET /api/v1/admin/dashboard
# ---------------------------------------------------------------------------
@admin_bp.route("/dashboard", methods=["GET"])
@require_superadmin
def get_dashboard():
    try:
        pool = _pool()
        with pool.get_connection() as conn:  # noqa: SIM117
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM tenants WHERE is_active = true")
                tenants_active = cur.fetchone()["count"]

                cur.execute("SELECT COUNT(*) FROM users")
                users_total = cur.fetchone()["count"]

                cur.execute(
                    "SELECT COUNT(*) FROM training_approvals WHERE status = 'pending'"
                )
                approvals_pending = cur.fetchone()["count"]

                cur.execute(
                    "SELECT COUNT(*) FROM support_tickets WHERE status = 'open'"
                    if False else
                    "SELECT 0"
                )

                # Audit log: últimos 10 eventos críticos
                cur.execute("""
                    SELECT al.id, al.action, al.target_type, al.actor_role,
                           al.created_at, u.email AS actor_email,
                           t.name AS tenant_name
                    FROM public.audit_log al
                    LEFT JOIN public.users u ON u.id = al.actor_id
                    LEFT JOIN public.tenants t ON t.id = al.tenant_id
                    WHERE al.action IN ('suspended','worker_restart','training_rejected','deactivated')
                    ORDER BY al.created_at DESC LIMIT 10
                """)  # noqa: E501
                critical_rows = cur.fetchall()
                critical_events = [_clean_row(dict(r)) for r in critical_rows]

                # Workers status
                from app.infrastructure.queue.worker_registry import get_all_workers_status
                workers_list = get_all_workers_status()
                workers_summary = {"online": 0, "fallback": 0, "offline": 0}
                for w in workers_list:
                    s = w.get("status", "offline")
                    if s == "onpremise":
                        workers_summary["online"] += 1
                    elif s == "railway":
                        workers_summary["fallback"] += 1
                    else:
                        workers_summary["offline"] += 1

                cur.execute("""
                    SELECT t.name, COUNT(u.id) AS user_count
                    FROM tenants t
                    LEFT JOIN users u ON u.tenant_id = t.id
                    WHERE t.is_active = true
                    GROUP BY t.id, t.name
                    ORDER BY user_count DESC LIMIT 5
                """)
                top_rows = cur.fetchall()
                top_tenants = [{"tenant_name": r["name"], "user_count": r["user_count"]} for r in top_rows]  # noqa: E501

        return success({
            "tenants_active": tenants_active,
            "users_total": users_total,
            "cameras_online": 0,
            "alerts_24h": 0,
            "training_approvals_pending": approvals_pending,
            "tickets_open": 0,
            "mrr_estimated": 0,
            "workers": workers_summary,
            "recent_critical_events": critical_events,
            "top_tenants_users": top_tenants,
        })
    except Exception as exc:
        logger.error("admin_dashboard_error: %s", exc, exc_info=True)
        return error("Erro ao carregar dashboard", 500)


# ---------------------------------------------------------------------------
# Tenants — list
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants", methods=["GET"])
@require_superadmin
def list_tenants():
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT
                        t.id, t.slug, t.name, t.plan, t.schema_name,
                        t.is_active, t.modules_enabled, t.created_at,
                        t.suspended_at,
                        COUNT(u.id) AS user_count
                    FROM tenants t
                    LEFT JOIN users u ON u.tenant_id = t.id
                    GROUP BY t.id
                    ORDER BY t.created_at DESC
                """)
            rows = cur.fetchall()
            tenants = []
            for row in rows:
                r = _clean_row(dict(row))
                if isinstance(r.get("modules_enabled"), str):
                    try:
                        r["modules_enabled"] = json.loads(r["modules_enabled"])
                    except Exception:
                        r["modules_enabled"] = []
                tenants.append(r)

        return success({"tenants": tenants})
    except Exception as exc:
        logger.error("list_tenants_error: %s", exc, exc_info=True)
        return error("Erro ao listar tenants", 500)


# ---------------------------------------------------------------------------
# Tenants — create
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants", methods=["POST"])
@require_superadmin
def create_tenant():
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        slug = (data.get("slug") or "").strip().lower()
        plan = data.get("plan", "standard")
        modules_enabled = data.get("modules_enabled", ["epi", "counting", "basic"])

        if not name or not slug:
            return error("name e slug são obrigatórios", 400)
        if not slug.replace("-", "").isalnum():
            return error("slug inválido: use apenas letras, números e hifens", 400)

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM tenants WHERE slug = %s", (slug,))
                if cur.fetchone():
                    return error(f"Slug '{slug}' já existe", 409)

                tenant_id = str(uuid.uuid4())
                modules_json = json.dumps(modules_enabled)
                cur.execute("""
                    INSERT INTO tenants
                      (id, slug, name, plan, schema_name, modules_enabled, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, true)
                    RETURNING id, slug, name, plan, schema_name, is_active
                """, (tenant_id, slug, name, plan, slug, modules_json))
                tenant = _clean_row(dict(cur.fetchone()))

                cur.execute("SELECT public.create_tenant_schema(%s)", (slug,))

                admin_email = f"admin@{slug}.epimonitor.local"
                temp_password = f"EpiMonitor@{slug[:4].upper()}2024!"
                password_hash = hash_password(temp_password)
                cur.execute("""
                    INSERT INTO users (email, password_hash, name, role, tenant_id, is_active)
                    VALUES (%s, %s, %s, 'admin', %s, true)
                    ON CONFLICT (email) DO NOTHING
                """, (admin_email, password_hash, f"Admin {name}", tenant_id))

            conn.commit()

        invalidate_schema_cache()
        actor_id, actor_role = _get_actor()
        log_audit(actor_id, actor_role, tenant_id, "tenant", tenant_id,
                  "created", new_value={"slug": slug, "plan": plan},
                  ip_address=_get_ip(), user_agent=_get_ua())

        return success({
            "tenant": tenant,
            "admin_email": admin_email,
            "temp_password": temp_password,
        }, status=201)
    except Exception as exc:
        logger.error("create_tenant_error: %s", exc, exc_info=True)
        return error("Erro ao criar tenant", 500)


# ---------------------------------------------------------------------------
# Tenants — get detail
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>", methods=["GET"])
@require_superadmin
def get_tenant(tenant_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT t.*, COUNT(u.id) AS user_count
                    FROM tenants t
                    LEFT JOIN users u ON u.tenant_id = t.id
                    WHERE t.id = %s
                    GROUP BY t.id
                """, (tenant_id,))
            row = cur.fetchone()
            if not row:
                return error("Tenant não encontrado", 404)
            tenant = _clean_row(dict(row))
            if isinstance(tenant.get("modules_enabled"), str):
                try:
                    tenant["modules_enabled"] = json.loads(tenant["modules_enabled"])
                except Exception:
                    tenant["modules_enabled"] = []

            # Usuários do tenant
            cur.execute("""
                    SELECT id, email, name, role, is_active, created_at,
                           last_login_at, login_count
                    FROM users WHERE tenant_id = %s ORDER BY created_at
                """, (tenant_id,))
            users_rows = cur.fetchall()
            tenant["users"] = [_clean_row(dict(r)) for r in users_rows]

            # Aprovações de treinamento pendentes
            cur.execute("""
                    SELECT id, module, job_name, status, created_at
                    FROM public.training_approvals
                    WHERE tenant_id = %s AND status = 'pending'
                    ORDER BY created_at DESC LIMIT 5
                """, (tenant_id,))
            ap_rows = cur.fetchall()
            tenant["pending_approvals"] = [
                _clean_row(dict(r)) for r in ap_rows
            ]

        # Worker status
        schema = tenant.get("schema_name")
        if schema:
            from app.infrastructure.queue.worker_registry import (
                get_worker_metrics,
                get_worker_status,
            )
            tenant["worker_status"] = get_worker_status(schema)
            tenant["worker_metrics"] = get_worker_metrics(schema)

        return success({"tenant": tenant})
    except Exception as exc:
        logger.error("get_tenant_error: %s", exc, exc_info=True)
        return error("Erro ao buscar tenant", 500)


# ---------------------------------------------------------------------------
# Tenants — update
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>", methods=["PATCH"])
@require_superadmin
def update_tenant(tenant_id: str):
    try:
        data = request.get_json() or {}
        allowed_fields = {"plan", "modules_enabled", "active",
                          "requires_training_approval", "internal_notes",
                          "mrr_per_camera", "contract_cameras", "max_cameras",
                          "video_retention_days"}
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        if not updates:
            return error("Nenhum campo válido para atualizar", 400)

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                # Ler estado anterior para audit
                cur.execute(
                    "SELECT plan, modules_enabled, is_active FROM tenants WHERE id = %s",
                    (tenant_id,),
                )
                old_row = cur.fetchone()
                if not old_row:
                    return error("Tenant não encontrado", 404)
                old_plan = old_row["plan"]

                if "plan" in updates:
                    cur.execute(
                        "UPDATE tenants SET plan = %s WHERE id = %s",
                        (updates["plan"], tenant_id),
                    )
                    if updates["plan"] != old_plan:
                        actor_id, _ = _get_actor()
                        cur.execute("""
                            INSERT INTO public.tenant_plan_history
                              (tenant_id, old_plan, new_plan, changed_by, notes)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (tenant_id, old_plan, updates["plan"],
                              str(actor_id) if actor_id else None,
                              data.get("plan_change_notes")))

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
                for field in ("requires_training_approval", "internal_notes",
                              "mrr_per_camera", "contract_cameras",
                              "max_cameras", "video_retention_days"):
                    if field in updates:
                        val = updates[field]
                        if field == "mrr_per_camera":
                            cur.execute(
                                f"UPDATE tenants SET {field} = %s::jsonb WHERE id = %s",  # noqa: S608
                                (json.dumps(val), tenant_id),
                            )
                        else:
                            cur.execute(
                                f"UPDATE tenants SET {field} = %s WHERE id = %s",  # noqa: S608
                                (val, tenant_id),
                            )
            conn.commit()

        actor_id, actor_role = _get_actor()
        log_audit(actor_id, actor_role, tenant_id, "tenant", tenant_id,
                  "updated", new_value=updates,
                  ip_address=_get_ip(), user_agent=_get_ua())

        return success({"updated": True})
    except Exception as exc:
        logger.error("update_tenant_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar tenant", 500)


# ---------------------------------------------------------------------------
# Tenants — suspend
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/suspend", methods=["POST"])
@require_superadmin
def suspend_tenant(tenant_id: str):
    try:
        data = request.get_json() or {}
        reason = data.get("reason", "")

        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM tenants WHERE id = %s AND is_active = true",
                    (tenant_id,),
                )
                if not cur.fetchone():
                    return error("Tenant não encontrado ou já suspenso", 404)

                cur.execute("""
                    UPDATE tenants
                    SET is_active = false, suspended_at = NOW(), suspended_by = %s
                    WHERE id = %s
                """, (str(actor_id) if actor_id else None, tenant_id))

                # Revogar sessões ativas do tenant
                cur.execute("""
                    UPDATE public.active_sessions
                    SET revoked_at = NOW(), revoked_by = %s
                    WHERE tenant_id = %s AND revoked_at IS NULL AND expires_at > NOW()
                """, (str(actor_id) if actor_id else None, tenant_id))
            conn.commit()

        log_audit(actor_id, actor_role, tenant_id, "tenant", tenant_id,
                  "suspended", new_value={"reason": reason},
                  ip_address=_get_ip(), user_agent=_get_ua())
        return success({"suspended": True})
    except Exception as exc:
        logger.error("suspend_tenant_error: %s", exc, exc_info=True)
        return error("Erro ao suspender tenant", 500)


# ---------------------------------------------------------------------------
# Tenants — reactivate
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/reactivate", methods=["POST"])
@require_superadmin
def reactivate_tenant(tenant_id: str):
    try:
        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE tenants
                    SET is_active = true, suspended_at = NULL, suspended_by = NULL
                    WHERE id = %s
                """, (tenant_id,))
            conn.commit()

        log_audit(actor_id, actor_role, tenant_id, "tenant", tenant_id,
                  "reactivated", ip_address=_get_ip(), user_agent=_get_ua())
        return success({"reactivated": True})
    except Exception as exc:
        logger.error("reactivate_tenant_error: %s", exc, exc_info=True)
        return error("Erro ao reativar tenant", 500)


# ---------------------------------------------------------------------------
# Tenants — overview (read-only no schema do tenant)
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/overview", methods=["GET"])
@require_superadmin
def tenant_overview(tenant_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, slug, plan, schema_name FROM tenants WHERE id = %s",
                (tenant_id,),
            )
            row = cur.fetchone()
            if not row:
                return error("Tenant não encontrado", 404)
            tenant = _clean_row(dict(row))
            schema_name = tenant.get("schema_name", "public")

        if not validate_schema(schema_name):
            return error(f"Schema inválido: {schema_name}", 400)

        cameras, recent_alerts, training_jobs = [], [], []
        with pool.get_connection() as conn2, conn2.cursor() as cur2:
            set_search_path(conn2, schema_name)
            try:
                cur2.execute(
                    "SELECT id, name, status, active_module FROM cameras LIMIT 50"
                )
                cameras = [_clean_row(dict(r)) for r in cur2.fetchall()]
            except Exception:  # noqa: S110
                pass
            try:
                cur2.execute("""
                        SELECT id, violation_type, confidence, created_at
                        FROM alerts
                        WHERE created_at >= NOW() - INTERVAL '24 hours'
                        ORDER BY created_at DESC LIMIT 20
                    """)
                recent_alerts = [_clean_row(dict(r)) for r in cur2.fetchall()]
            except Exception:  # noqa: S110
                pass
            try:
                cur2.execute("""
                        SELECT id, name, status, module, created_at
                        FROM training_jobs ORDER BY created_at DESC LIMIT 10
                    """)
                training_jobs = [_clean_row(dict(r)) for r in cur2.fetchall()]
            except Exception:  # noqa: S110
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
# Tenants — plan history
# ---------------------------------------------------------------------------
@admin_bp.route("/tenants/<tenant_id>/plan-history", methods=["GET"])
@require_superadmin
def tenant_plan_history(tenant_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT tph.*, u.email AS changed_by_email
                    FROM public.tenant_plan_history tph
                    LEFT JOIN public.users u ON u.id = tph.changed_by
                    WHERE tph.tenant_id = %s
                    ORDER BY tph.created_at DESC
                """, (tenant_id,))
            rows = cur.fetchall()
            history = [_clean_row(dict(r)) for r in rows]
        return success({"history": history})
    except Exception as exc:
        logger.error("plan_history_error: %s", exc, exc_info=True)
        return error("Erro ao buscar histórico de planos", 500)


# ---------------------------------------------------------------------------
# Users — list
# ---------------------------------------------------------------------------
@admin_bp.route("/users", methods=["GET"])
@require_superadmin
def list_users():
    try:
        _, per_page, offset = _page_params()
        tenant_filter = request.args.get("tenant_id")
        role_filter = request.args.get("role")
        active_filter = request.args.get("active")
        search = request.args.get("search", "").strip()

        conditions = ["1=1"]
        params: list = []
        if tenant_filter:
            conditions.append("u.tenant_id = %s")
            params.append(tenant_filter)
        if role_filter:
            conditions.append("u.role = %s")
            params.append(role_filter)
        if active_filter is not None:
            conditions.append("u.is_active = %s")
            params.append(active_filter.lower() == "true")
        if search:
            conditions.append("(u.email ILIKE %s OR u.name ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = " AND ".join(conditions)

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM users u WHERE {where}", tuple(params)  # noqa: S608
            )
            total = cur.fetchone()["count"]

            cur.execute(f"""
                    SELECT u.id, u.email, u.name, u.role, u.tenant_id,
                           u.is_active, u.created_at, u.last_login_at,
                           u.login_count, u.force_password_reset,
                           t.name AS tenant_name
                    FROM users u
                    LEFT JOIN tenants t ON t.id = u.tenant_id
                    WHERE {where}
                    ORDER BY u.created_at DESC
                    LIMIT %s OFFSET %s
                """, tuple(params) + (per_page, offset))  # noqa: S608
            rows = cur.fetchall()
            users = [_clean_row(dict(r)) for r in rows]

        return success({"items": users, "total": total})
    except Exception as exc:
        logger.error("list_users_error: %s", exc, exc_info=True)
        return error("Erro ao listar usuários", 500)


# ---------------------------------------------------------------------------
# Users — get detail
# ---------------------------------------------------------------------------
@admin_bp.route("/users/<user_id>", methods=["GET"])
@require_superadmin
def get_user(user_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT u.*, t.name AS tenant_name
                    FROM users u
                    LEFT JOIN tenants t ON t.id = u.tenant_id
                    WHERE u.id = %s
                """, (user_id,))
            row = cur.fetchone()
            if not row:
                return error("Usuário não encontrado", 404)
            user = _clean_row(dict(row))
            user.pop("password_hash", None)

            # Últimas 10 ações no audit_log
            cur.execute("""
                    SELECT action, target_type, target_id, created_at, ip_address
                    FROM public.audit_log
                    WHERE actor_id = %s
                    ORDER BY created_at DESC LIMIT 10
                """, (user_id,))
            al_rows = cur.fetchall()
            user["recent_actions"] = [
                _clean_row(dict(r)) for r in al_rows
            ]

        return success({"user": user})
    except Exception as exc:
        logger.error("get_user_error: %s", exc, exc_info=True)
        return error("Erro ao buscar usuário", 500)


# ---------------------------------------------------------------------------
# Users — create
# ---------------------------------------------------------------------------
@admin_bp.route("/users", methods=["POST"])
@require_superadmin
def create_user():
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        role = data.get("role", "operator")
        tenant_id = data.get("tenant_id")
        access_expires_at = data.get("access_expires_at")

        if not email or not tenant_id:
            return error("email e tenant_id são obrigatórios", 400)

        valid_roles = ["superadmin", "admin", "operator", "analyst", "trainer", "viewer"]
        if role not in valid_roles:
            return error(f"Role inválido: {role}", 400)

        # Enforcement de assentos (tenants.max_seats — migration 051)
        from app.core.exceptions import ConflictError
        from app.domain.services.seat_service import check_seat_available
        from app.infrastructure.database.repositories.tenant_policy_repository import (
            TenantPolicyRepository,
        )
        try:
            check_seat_available(TenantPolicyRepository(_pool()), tenant_id)
        except ConflictError as seat_exc:
            return error(seat_exc.message, 409)

        import secrets
        temp_password = secrets.token_urlsafe(12)
        password_hash = hash_password(temp_password)
        user_id = str(uuid.uuid4())

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    return error("Email já cadastrado", 409)

                cur.execute("""
                    INSERT INTO users
                      (id, email, password_hash, name, role, tenant_id,
                       is_active, force_password_reset, access_expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, true, true, %s)
                    RETURNING id, email, role, tenant_id, is_active, created_at
                """, (user_id, email, password_hash, email.split("@")[0],
                      role, tenant_id, access_expires_at))
                user = _clean_row(dict(cur.fetchone()))
            conn.commit()

        # Token de primeiro acesso no Redis — TTL 48h
        try:
            r = _get_redis()
            first_access_token = str(uuid.uuid4())
            r.setex(f"first_access:{first_access_token}", 172800, user_id)
            r.close()
        except Exception:
            first_access_token = None

        actor_id, actor_role = _get_actor()
        log_audit(actor_id, actor_role, tenant_id, "user", user_id,
                  "created", new_value={"email": email, "role": role},
                  ip_address=_get_ip(), user_agent=_get_ua())

        return success({
            "user": user,
            "temp_password": temp_password,
            "first_access_token": first_access_token,
        }, status=201)
    except Exception as exc:
        logger.error("create_user_error: %s", exc, exc_info=True)
        return error("Erro ao criar usuário", 500)


# ---------------------------------------------------------------------------
# Users — update
# ---------------------------------------------------------------------------
@admin_bp.route("/users/<user_id>", methods=["PATCH"])
@require_superadmin
def update_user(user_id: str):
    try:
        data = request.get_json() or {}
        allowed = {"role", "access_expires_at"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return error("Nenhum campo válido para atualizar", 400)

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT role, tenant_id FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if not row:
                    return error("Usuário não encontrado", 404)
                old_role, tenant_id = row["role"], row["tenant_id"]

                if "role" in updates:
                    cur.execute(
                        "UPDATE users SET role = %s WHERE id = %s",
                        (updates["role"], user_id),
                    )
                if "access_expires_at" in updates:
                    cur.execute(
                        "UPDATE users SET access_expires_at = %s WHERE id = %s",
                        (updates["access_expires_at"], user_id),
                    )
            conn.commit()

        actor_id, actor_role = _get_actor()
        log_audit(actor_id, actor_role, str(tenant_id) if tenant_id else None,
                  "user", user_id, "updated",
                  old_value={"role": old_role}, new_value=updates,
                  ip_address=_get_ip(), user_agent=_get_ua())

        return success({"updated": True})
    except Exception as exc:
        logger.error("update_user_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar usuário", 500)


# ---------------------------------------------------------------------------
# Users — deactivate
# ---------------------------------------------------------------------------
@admin_bp.route("/users/<user_id>/deactivate", methods=["POST"])
@require_superadmin
def deactivate_user(user_id: str):
    try:
        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tenant_id FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if not row:
                    return error("Usuário não encontrado", 404)
                tenant_id = row["tenant_id"]

                cur.execute("""
                    UPDATE users
                    SET is_active = false, deactivated_at = NOW(), deactivated_by = %s
                    WHERE id = %s
                """, (str(actor_id) if actor_id else None, user_id))

                cur.execute("""
                    UPDATE public.active_sessions
                    SET revoked_at = NOW(), revoked_by = %s
                    WHERE user_id = %s AND revoked_at IS NULL
                """, (str(actor_id) if actor_id else None, user_id))
            conn.commit()

        try:
            r = _get_redis()
            r.publish(f"session_revoked:{user_id}", "deactivated")
            r.close()
        except Exception:  # noqa: S110
            pass

        log_audit(actor_id, actor_role, str(tenant_id) if tenant_id else None,
                  "user", user_id, "deactivated",
                  ip_address=_get_ip(), user_agent=_get_ua())
        return success({"deactivated": True})
    except Exception as exc:
        logger.error("deactivate_user_error: %s", exc, exc_info=True)
        return error("Erro ao desativar usuário", 500)


# ---------------------------------------------------------------------------
# Users — reactivate
# ---------------------------------------------------------------------------
@admin_bp.route("/users/<user_id>/reactivate", methods=["POST"])
@require_superadmin
def reactivate_user(user_id: str):
    try:
        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tenant_id FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if not row:
                    return error("Usuário não encontrado", 404)
                tenant_id = row["tenant_id"]

        # Reativar também consome assento (tenants.max_seats — migration 051)
        if tenant_id:
            from app.core.exceptions import ConflictError
            from app.domain.services.seat_service import check_seat_available
            from app.infrastructure.database.repositories.tenant_policy_repository import (
                TenantPolicyRepository,
            )
            try:
                check_seat_available(TenantPolicyRepository(pool), str(tenant_id))
            except ConflictError as seat_exc:
                return error(seat_exc.message, 409)

        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users
                    SET is_active = true, deactivated_at = NULL, deactivated_by = NULL
                    WHERE id = %s
                """, (user_id,))
            conn.commit()

        log_audit(actor_id, actor_role, str(tenant_id) if tenant_id else None,
                  "user", user_id, "reactivated",
                  ip_address=_get_ip(), user_agent=_get_ua())
        return success({"reactivated": True})
    except Exception as exc:
        logger.error("reactivate_user_error: %s", exc, exc_info=True)
        return error("Erro ao reativar usuário", 500)


# ---------------------------------------------------------------------------
# Users — force password reset
# ---------------------------------------------------------------------------
@admin_bp.route("/users/<user_id>/force-password-reset", methods=["POST"])
@require_superadmin
def force_password_reset(user_id: str):
    try:
        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tenant_id FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if not row:
                    return error("Usuário não encontrado", 404)
                tenant_id = row["tenant_id"]
                cur.execute(
                    "UPDATE users SET force_password_reset = true WHERE id = %s",
                    (user_id,),
                )
            conn.commit()

        try:
            r = _get_redis()
            r.set(f"force_reset:{user_id}", "1", ex=86400)
            r.close()
        except Exception:  # noqa: S110
            pass

        log_audit(actor_id, actor_role, str(tenant_id) if tenant_id else None,
                  "user", user_id, "force_password_reset",
                  ip_address=_get_ip(), user_agent=_get_ua())
        return success({"forced": True})
    except Exception as exc:
        logger.error("force_password_reset_error: %s", exc, exc_info=True)
        return error("Erro ao forçar reset de senha", 500)


# ---------------------------------------------------------------------------
# Users — sessions
# ---------------------------------------------------------------------------
@admin_bp.route("/users/<user_id>/sessions", methods=["GET"])
@require_superadmin
def get_user_sessions(user_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT id, jti, ip_address, user_agent, created_at, expires_at
                    FROM public.active_sessions
                    WHERE user_id = %s AND revoked_at IS NULL AND expires_at > NOW()
                    ORDER BY created_at DESC
                """, (user_id,))
            rows = cur.fetchall()
            sessions = [_clean_row(dict(r)) for r in rows]
        return success({"sessions": sessions})
    except Exception as exc:
        logger.error("get_sessions_error: %s", exc, exc_info=True)
        return error("Erro ao buscar sessões", 500)


@admin_bp.route("/users/<user_id>/sessions", methods=["DELETE"])
@require_superadmin
def revoke_user_sessions(user_id: str):
    try:
        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tenant_id FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if not row:
                    return error("Usuário não encontrado", 404)
                tenant_id = row["tenant_id"]
                cur.execute("""
                    UPDATE public.active_sessions
                    SET revoked_at = NOW(), revoked_by = %s
                    WHERE user_id = %s AND revoked_at IS NULL
                """, (str(actor_id) if actor_id else None, user_id))
            conn.commit()

        try:
            r = _get_redis()
            r.publish(f"session_revoked:{user_id}", "admin_revoked")
            r.close()
        except Exception:  # noqa: S110
            pass

        log_audit(actor_id, actor_role, str(tenant_id) if tenant_id else None,
                  "user", user_id, "sessions_revoked",
                  ip_address=_get_ip(), user_agent=_get_ua())
        return success({"revoked": True})
    except Exception as exc:
        logger.error("revoke_sessions_error: %s", exc, exc_info=True)
        return error("Erro ao revogar sessões", 500)


# ---------------------------------------------------------------------------
# Permissions matrix
# ---------------------------------------------------------------------------
@admin_bp.route("/permissions/matrix", methods=["GET"])
@require_superadmin
def permissions_matrix():
    from app.constants import ROLE_PERMISSIONS
    return success({"matrix": ROLE_PERMISSIONS})


# ---------------------------------------------------------------------------
# Training Approvals — list
# ---------------------------------------------------------------------------
@admin_bp.route("/training-approvals", methods=["GET"])
@require_superadmin
def list_training_approvals():
    try:
        _, per_page, offset = _page_params()
        status_filter = request.args.get("status", "pending")
        tenant_filter = request.args.get("tenant_id")
        module_filter = request.args.get("module")

        conditions = ["1=1"]
        params: list = []
        if status_filter:
            conditions.append("ta.status = %s")
            params.append(status_filter)
        if tenant_filter:
            conditions.append("ta.tenant_id = %s")
            params.append(tenant_filter)
        if module_filter:
            conditions.append("ta.module = %s")
            params.append(module_filter)
        where = " AND ".join(conditions)

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM public.training_approvals ta WHERE {where}",  # noqa: S608
                tuple(params),
            )
            total = cur.fetchone()["count"]

            cur.execute(f"""
                    SELECT ta.*, t.name AS tenant_name, u.email AS reviewer_email
                    FROM public.training_approvals ta
                    LEFT JOIN public.tenants t ON t.id = ta.tenant_id
                    LEFT JOIN public.users u ON u.id = ta.reviewed_by
                    WHERE {where}
                    ORDER BY ta.created_at DESC
                    LIMIT %s OFFSET %s
                """, tuple(params) + (per_page, offset))  # noqa: S608
            rows = cur.fetchall()
            items = [_clean_row(dict(r)) for r in rows]

        return success({"items": items, "total": total})
    except Exception as exc:
        logger.error("list_approvals_error: %s", exc, exc_info=True)
        return error("Erro ao listar aprovações", 500)


# ---------------------------------------------------------------------------
# Training Approvals — get detail
# ---------------------------------------------------------------------------
@admin_bp.route("/training-approvals/<approval_id>", methods=["GET"])
@require_superadmin
def get_training_approval(approval_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT ta.*, t.name AS tenant_name
                    FROM public.training_approvals ta
                    LEFT JOIN public.tenants t ON t.id = ta.tenant_id
                    WHERE ta.id = %s
                """, (approval_id,))
            row = cur.fetchone()
            if not row:
                return error("Aprovação não encontrada", 404)
            approval = _clean_row(dict(row))

        # Gerar presigned URLs para imagens do dataset
        sample_keys = approval.get("dataset_sample_keys") or []
        if isinstance(sample_keys, str):
            try:
                sample_keys = json.loads(sample_keys)
            except Exception:
                sample_keys = []

        sample_urls = []
        if sample_keys:
            try:
                from app.infrastructure.storage.r2_storage import R2Storage
                r2 = R2Storage()
                for key in sample_keys[:10]:
                    url = r2.generate_presigned_download_url(key, ttl=300)
                    sample_urls.append(url)
            except Exception as e:
                logger.warning("r2_presigned_failed: %s", e)

        approval["dataset_sample_urls"] = sample_urls
        return success({"approval": approval})
    except Exception as exc:
        logger.error("get_approval_error: %s", exc, exc_info=True)
        return error("Erro ao buscar aprovação", 500)


# ---------------------------------------------------------------------------
# Training Approvals — approve
# ---------------------------------------------------------------------------
@admin_bp.route("/training-approvals/<approval_id>/approve", methods=["POST"])
@require_superadmin
def approve_training(approval_id: str):
    try:
        data = request.get_json() or {}
        notes = data.get("notes", "")
        actor_id, actor_role = _get_actor()

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, training_job_id, tenant_schema FROM public.training_approvals WHERE id = %s",  # noqa: E501
                    (approval_id,),
                )
                row = cur.fetchone()
                if not row:
                    return error("Aprovação não encontrada", 404)
                tenant_id = row["tenant_id"]
                job_id = row["training_job_id"]
                tenant_schema = row["tenant_schema"]

                cur.execute("""
                    UPDATE public.training_approvals
                    SET status = 'approved', reviewed_by = %s,
                        reviewed_at = NOW(), reviewer_notes = %s
                    WHERE id = %s
                """, (str(actor_id) if actor_id else None, notes, approval_id))
            conn.commit()

        try:
            r = _get_redis()
            r.publish(f"training_approved:{job_id}", approval_id)
            r.publish(f"notification:{tenant_schema}",
                      json.dumps({"type": "training_approved", "job_id": str(job_id)}))
            r.close()
        except Exception:  # noqa: S110
            pass

        log_audit(actor_id, actor_role, str(tenant_id), "training_approval",
                  approval_id, "approved", new_value={"notes": notes},
                  ip_address=_get_ip(), user_agent=_get_ua())
        return success({"approved": True})
    except Exception as exc:
        logger.error("approve_training_error: %s", exc, exc_info=True)
        return error("Erro ao aprovar treinamento", 500)


# ---------------------------------------------------------------------------
# Training Approvals — reject
# ---------------------------------------------------------------------------
@admin_bp.route("/training-approvals/<approval_id>/reject", methods=["POST"])
@require_superadmin
def reject_training(approval_id: str):
    try:
        data = request.get_json() or {}
        reason = (data.get("reason") or "").strip()
        if not reason:
            return error("Motivo de rejeição é obrigatório", 400)

        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, training_job_id, tenant_schema FROM public.training_approvals WHERE id = %s",  # noqa: E501
                    (approval_id,),
                )
                row = cur.fetchone()
                if not row:
                    return error("Aprovação não encontrada", 404)
                tenant_id = row["tenant_id"]
                job_id = row["training_job_id"]
                tenant_schema = row["tenant_schema"]

                cur.execute("""
                    UPDATE public.training_approvals
                    SET status = 'rejected', reviewed_by = %s,
                        reviewed_at = NOW(), rejection_reason = %s
                    WHERE id = %s
                """, (str(actor_id) if actor_id else None, reason, approval_id))
            conn.commit()

        try:
            r = _get_redis()
            r.publish(f"training_rejected:{job_id}", reason)
            r.publish(f"notification:{tenant_schema}",
                      json.dumps({"type": "training_rejected", "job_id": str(job_id), "reason": reason}))  # noqa: E501
            r.close()
        except Exception:  # noqa: S110
            pass

        log_audit(actor_id, actor_role, str(tenant_id), "training_approval",
                  approval_id, "training_rejected", new_value={"reason": reason},
                  ip_address=_get_ip(), user_agent=_get_ua())
        return success({"rejected": True})
    except Exception as exc:
        logger.error("reject_training_error: %s", exc, exc_info=True)
        return error("Erro ao rejeitar treinamento", 500)


# ---------------------------------------------------------------------------
# Workers — list all
# ---------------------------------------------------------------------------
@admin_bp.route("/workers", methods=["GET"])
@require_superadmin
def list_workers():
    try:
        from app.infrastructure.queue.worker_registry import get_all_workers_status
        workers = get_all_workers_status()
        return success({"workers": workers})
    except Exception as exc:
        logger.error("list_workers_error: %s", exc, exc_info=True)
        return error("Erro ao buscar workers", 500)


# ---------------------------------------------------------------------------
# Workers — detail by schema
# ---------------------------------------------------------------------------
@admin_bp.route("/workers/<tenant_schema>", methods=["GET"])
@require_superadmin
def get_worker_detail(tenant_schema: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT wr.*, t.name AS tenant_name
                    FROM public.worker_registry wr
                    JOIN public.tenants t ON t.id = wr.tenant_id
                    WHERE wr.tenant_schema = %s AND wr.active = true
                """, (tenant_schema,))
            row = cur.fetchone()
            worker = _clean_row(dict(row)) if row else {}

            # Métricas das últimas 24h
            if row:
                worker_id = str(row["id"])
                cur.execute("""
                        SELECT gpu_pct, vram_used_gb, fps_avg, cameras_active, recorded_at
                        FROM public.worker_metrics
                        WHERE worker_id = %s AND recorded_at >= NOW() - INTERVAL '24 hours'
                        ORDER BY recorded_at DESC LIMIT 200
                    """, (worker_id,))
                metric_rows = cur.fetchall()
                worker["metrics_24h"] = [_clean_row(dict(r)) for r in metric_rows]

        from app.infrastructure.queue.worker_registry import get_worker_metrics, get_worker_status
        worker["status"] = get_worker_status(tenant_schema)
        worker["live_metrics"] = get_worker_metrics(tenant_schema)

        return success({"worker": worker})
    except Exception as exc:
        logger.error("get_worker_detail_error: %s", exc, exc_info=True)
        return error("Erro ao buscar worker", 500)


# ---------------------------------------------------------------------------
# Workers — restart (send command via Redis)
# ---------------------------------------------------------------------------
@admin_bp.route("/workers/<tenant_schema>/restart", methods=["POST"])
@require_superadmin
def restart_worker(tenant_schema: str):
    try:
        actor_id, actor_role = _get_actor()
        r = _get_redis()
        r.set(f"worker_command:{tenant_schema}", "restart", ex=120)
        r.close()

        log_audit(actor_id, actor_role, None, "worker", tenant_schema,
                  "worker_restart", ip_address=_get_ip(), user_agent=_get_ua())
        return success({"command_sent": "restart", "schema": tenant_schema})
    except Exception as exc:
        logger.error("restart_worker_error: %s", exc, exc_info=True)
        return error("Erro ao enviar comando de restart", 500)


# ---------------------------------------------------------------------------
# Workers — metrics history
# ---------------------------------------------------------------------------
@admin_bp.route("/workers/<tenant_schema>/metrics", methods=["GET"])
@require_superadmin
def get_worker_metrics_history(tenant_schema: str):
    try:
        period = request.args.get("period", "24h")
        intervals = {"1h": "1 hour", "24h": "24 hours", "7d": "7 days"}
        interval = intervals.get(period, "24 hours")

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM public.worker_registry WHERE tenant_schema = %s AND active = true",
                (tenant_schema,),
            )
            row = cur.fetchone()
            if not row:
                return success({"metrics": []})
            worker_id = str(row["id"])

            cur.execute(f"""
                    SELECT gpu_pct, vram_used_gb, fps_avg, cameras_active, recorded_at
                    FROM public.worker_metrics
                    WHERE worker_id = %s AND recorded_at >= NOW() - INTERVAL '{interval}'
                    ORDER BY recorded_at ASC
                """, (worker_id,))  # noqa: S608
            rows = cur.fetchall()
            metrics = [_clean_row(dict(r)) for r in rows]

        return success({"metrics": metrics})
    except Exception as exc:
        logger.error("worker_metrics_error: %s", exc, exc_info=True)
        return error("Erro ao buscar métricas do worker", 500)


# ---------------------------------------------------------------------------
# Workers — heartbeat (X-Worker-Secret, sem JWT)
# ---------------------------------------------------------------------------
@admin_bp.route("/workers/heartbeat", methods=["POST"])
def worker_heartbeat():
    """
    Endpoint para worker on-premise publicar heartbeat.
    Autenticado por X-Worker-Secret header (não JWT).
    """
    try:
        worker_secret = current_app.config.get("WORKER_SECRET", "")
        provided_secret = request.headers.get("X-Worker-Secret", "")

        if not worker_secret or provided_secret != worker_secret:
            return error("Não autorizado", 401)

        data = request.get_json() or {}
        tenant_schema = (data.get("tenant_schema") or "").strip()
        if not tenant_schema:
            return error("tenant_schema é obrigatório", 400)

        metrics = {
            "hostname": data.get("hostname"),
            "software_version": data.get("software_version"),
            "gpu_model": data.get("gpu_model"),
            "gpu_pct": data.get("gpu_pct", 0),
            "vram_used_gb": data.get("vram_used_gb", 0),
            "fps_avg": data.get("fps_avg", 0),
            "cameras_active": data.get("cameras_active", 0),
        }

        from app.infrastructure.queue.worker_registry import publish_heartbeat
        publish_heartbeat(tenant_schema, metrics)

        # Verificar e retornar comando pendente
        command = None
        try:
            r = _get_redis()
            cmd = r.get(f"worker_command:{tenant_schema}")
            if cmd:
                command = cmd
                r.delete(f"worker_command:{tenant_schema}")
            r.close()
        except Exception:  # noqa: S110
            pass

        return success({"command": command})
    except Exception as exc:
        logger.error("worker_heartbeat_error: %s", exc, exc_info=True)
        return error("Erro no heartbeat", 500)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------
@admin_bp.route("/plans", methods=["GET"])
@require_superadmin
def list_plans():
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM public.plans ORDER BY name")
            rows = cur.fetchall()
            plans = [_clean_row(dict(r)) for r in rows]
        return success({"plans": plans})
    except Exception as exc:
        logger.error("list_plans_error: %s", exc, exc_info=True)
        return error("Erro ao listar planos", 500)


@admin_bp.route("/plans", methods=["POST"])
@require_superadmin
def create_plan():
    try:
        data = request.get_json() or {}
        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.plans
                      (slug, name, modules_allowed, max_cameras,
                       video_retention_days, requires_training_approval, price_per_camera)
                    VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s::jsonb)
                    RETURNING *
                """, (
                    data.get("slug"), data.get("name"),
                    json.dumps(data.get("modules_allowed", [])),
                    data.get("max_cameras", 10),
                    data.get("video_retention_days", 7),
                    data.get("requires_training_approval", False),
                    json.dumps(data.get("price_per_camera", {})),
                ))
                plan = _clean_row(dict(cur.fetchone()))
            conn.commit()

        log_audit(actor_id, actor_role, None, "plan", plan["id"], "created",
                  new_value=data, ip_address=_get_ip(), user_agent=_get_ua())
        return success({"plan": plan}, status=201)
    except Exception as exc:
        logger.error("create_plan_error: %s", exc, exc_info=True)
        return error("Erro ao criar plano", 500)


@admin_bp.route("/plans/<plan_id>", methods=["PATCH"])
@require_superadmin
def update_plan(plan_id: str):
    try:
        data = request.get_json() or {}
        actor_id, actor_role = _get_actor()
        allowed = {"name", "modules_allowed", "max_cameras", "video_retention_days",
                   "requires_training_approval", "price_per_camera", "active"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return error("Nenhum campo válido", 400)

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                for field, val in updates.items():
                    if field in ("modules_allowed", "price_per_camera"):
                        cur.execute(
                            f"UPDATE public.plans SET {field} = %s::jsonb WHERE id = %s",  # noqa: S608
                            (json.dumps(val), plan_id),
                        )
                    else:
                        cur.execute(
                            f"UPDATE public.plans SET {field} = %s WHERE id = %s",  # noqa: S608
                            (val, plan_id),
                        )
            conn.commit()

        log_audit(actor_id, actor_role, None, "plan", plan_id, "updated",
                  new_value=updates, ip_address=_get_ip(), user_agent=_get_ua())
        return success({"updated": True})
    except Exception as exc:
        logger.error("update_plan_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar plano", 500)


@admin_bp.route("/plans/<plan_id>/tenants", methods=["GET"])
@require_superadmin
def get_plan_tenants(plan_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT slug FROM public.plans WHERE id = %s", (plan_id,)
            )
            row = cur.fetchone()
            if not row:
                return error("Plano não encontrado", 404)
            slug = row["slug"]
            cur.execute(
                "SELECT id, name, slug, is_active, created_at FROM tenants WHERE plan = %s",
                (slug,),
            )
            rows = cur.fetchall()
            tenants = [_clean_row(dict(r)) for r in rows]
        return success({"tenants": tenants})
    except Exception as exc:
        logger.error("plan_tenants_error: %s", exc, exc_info=True)
        return error("Erro ao buscar tenants do plano", 500)


# ---------------------------------------------------------------------------
# Feature Flags — global
# ---------------------------------------------------------------------------
@admin_bp.route("/feature-flags", methods=["GET"])
@require_superadmin
def list_feature_flags():
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM public.platform_feature_flags ORDER BY flag_key")
            rows = cur.fetchall()
            flags = [_clean_row(dict(r)) for r in rows]
        return success({"flags": flags})
    except Exception as exc:
        logger.error("list_flags_error: %s", exc, exc_info=True)
        return error("Erro ao listar feature flags", 500)


@admin_bp.route("/feature-flags/<flag_key>", methods=["PATCH"])
@require_superadmin
def update_feature_flag(flag_key: str):
    try:
        data = request.get_json() or {}
        flag_value = bool(data.get("value", False))
        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.platform_feature_flags
                      (flag_key, flag_value, updated_by)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (flag_key) DO UPDATE
                      SET flag_value = EXCLUDED.flag_value,
                          updated_by = EXCLUDED.updated_by,
                          updated_at = NOW()
                """, (flag_key, flag_value, str(actor_id) if actor_id else None))
            conn.commit()

        log_audit(actor_id, actor_role, None, "feature_flag", flag_key, "updated",
                  new_value={"value": flag_value}, ip_address=_get_ip(), user_agent=_get_ua())
        return success({"updated": True})
    except Exception as exc:
        logger.error("update_flag_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar feature flag", 500)


@admin_bp.route("/feature-flags/tenant/<tenant_id>", methods=["GET"])
@require_superadmin
def get_tenant_feature_flags(tenant_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT feature_flags FROM tenants WHERE id = %s", (tenant_id,)
            )
            row = cur.fetchone()
            if not row:
                return error("Tenant não encontrado", 404)
            flags = row["feature_flags"] or {}
            if isinstance(flags, str):
                flags = json.loads(flags)
        return success({"flags": flags})
    except Exception as exc:
        logger.error("tenant_flags_error: %s", exc, exc_info=True)
        return error("Erro ao buscar feature flags do tenant", 500)


@admin_bp.route("/feature-flags/tenant/<tenant_id>", methods=["PATCH"])
@require_superadmin
def update_tenant_feature_flag(tenant_id: str):
    try:
        data = request.get_json() or {}
        flag_key = data.get("key")
        flag_value = data.get("value")
        if flag_key is None or flag_value is None:
            return error("key e value são obrigatórios", 400)

        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE tenants
                    SET feature_flags = COALESCE(feature_flags, '{}')::jsonb
                        || %s::jsonb
                    WHERE id = %s
                """, (json.dumps({flag_key: flag_value}), tenant_id))
            conn.commit()

        log_audit(actor_id, actor_role, tenant_id, "tenant_feature_flag", tenant_id,
                  "updated", new_value={flag_key: flag_value},
                  ip_address=_get_ip(), user_agent=_get_ua())
        return success({"updated": True})
    except Exception as exc:
        logger.error("update_tenant_flag_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar feature flag do tenant", 500)


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------
_SLA_HOURS = {"critical": 1, "high": 4, "normal": 24, "low": 72}


@admin_bp.route("/tickets", methods=["GET"])
@require_superadmin
def list_tickets():
    try:
        _, per_page, offset = _page_params()
        now = datetime.utcnow()

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT st.id, st.tenant_id, st.subject, st.category,
                           st.priority, st.status, st.created_at, st.updated_at,
                           st.first_responded_at,
                           t.name AS tenant_name
                    FROM public.support_tickets st
                    LEFT JOIN public.tenants t ON t.id = st.tenant_id
                    ORDER BY st.created_at DESC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
            rows = cur.fetchall()
            tickets = []
            for row in rows:
                t = _clean_row(dict(row))
                sla_h = _SLA_HOURS.get(t.get("priority", "normal"), 24)
                if t.get("created_at") and not t.get("first_responded_at"):
                    created = row["created_at"]
                    if created and hasattr(created, "replace"):
                        elapsed = (now - created.replace(tzinfo=None)).total_seconds() / 3600
                        t["sla_breached"] = elapsed > sla_h
                    else:
                        t["sla_breached"] = False
                else:
                    t["sla_breached"] = False
                tickets.append(t)

            cur.execute("SELECT COUNT(*) FROM public.support_tickets")
            total = cur.fetchone()["count"]

        return success({"items": tickets, "total": total})
    except Exception as exc:
        logger.error("list_tickets_error: %s", exc, exc_info=True)
        return error("Erro ao listar tickets", 500)


@admin_bp.route("/tickets/stats", methods=["GET"])
@require_superadmin
def ticket_stats():
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'open') AS open_count,
                        COUNT(*) FILTER (WHERE priority = 'critical') AS critical_count,
                        COUNT(*) FILTER (WHERE priority = 'high') AS high_count,
                        COUNT(*) FILTER (WHERE priority = 'normal') AS normal_count,
                        COUNT(*) FILTER (WHERE priority = 'low') AS low_count
                    FROM public.support_tickets
                """)
            row = cur.fetchone()
            stats = _clean_row(dict(row))
        return success({"stats": stats})
    except Exception as exc:
        logger.error("ticket_stats_error: %s", exc, exc_info=True)
        return error("Erro ao buscar stats de tickets", 500)


@admin_bp.route("/tickets/<ticket_id>", methods=["GET"])
@require_superadmin
def get_ticket(ticket_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT st.*, t.name AS tenant_name
                    FROM public.support_tickets st
                    LEFT JOIN public.tenants t ON t.id = st.tenant_id
                    WHERE st.id = %s
                """, (ticket_id,))
            row = cur.fetchone()
            if not row:
                return error("Ticket não encontrado", 404)
            ticket = _clean_row(dict(row))

            cur.execute("""
                    SELECT tm.*, u.email AS author_email
                    FROM public.ticket_messages tm
                    LEFT JOIN public.users u ON u.id = tm.author_id
                    WHERE tm.ticket_id = %s
                    ORDER BY tm.created_at
                """, (ticket_id,))
            msg_rows = cur.fetchall()
            ticket["messages"] = [_clean_row(dict(r)) for r in msg_rows]

        return success({"ticket": ticket})
    except Exception as exc:
        logger.error("get_ticket_error: %s", exc, exc_info=True)
        return error("Erro ao buscar ticket", 500)


@admin_bp.route("/tickets/<ticket_id>/reply", methods=["POST"])
@require_superadmin
def reply_ticket(ticket_id: str):
    try:
        data = request.get_json() or {}
        content = (data.get("content") or "").strip()
        is_internal = bool(data.get("is_internal", False))
        if not content:
            return error("content é obrigatório", 400)

        actor_id, _ = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.ticket_messages
                      (ticket_id, author_id, content, is_internal)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, created_at
                """, (ticket_id, str(actor_id) if actor_id else None, content, is_internal))
                msg_row = cur.fetchone()

                cur.execute(
                    "UPDATE public.support_tickets SET updated_at = NOW() WHERE id = %s",
                    (ticket_id,),
                )
            conn.commit()

        return success({"message_id": str(msg_row["id"])}, status=201)
    except Exception as exc:
        logger.error("reply_ticket_error: %s", exc, exc_info=True)
        return error("Erro ao responder ticket", 500)


@admin_bp.route("/tickets/<ticket_id>", methods=["PATCH"])
@require_superadmin
def update_ticket(ticket_id: str):
    try:
        data = request.get_json() or {}
        allowed = {"status", "priority", "assigned_to"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return error("Nenhum campo válido", 400)

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                for field, val in updates.items():
                    cur.execute(
                        f"UPDATE public.support_tickets SET {field} = %s, updated_at = NOW() WHERE id = %s",  # noqa: E501, S608
                        (val, ticket_id),
                    )
            conn.commit()

        return success({"updated": True})
    except Exception as exc:
        logger.error("update_ticket_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar ticket", 500)


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------
@admin_bp.route("/audit-log", methods=["GET"])
@require_superadmin
def list_audit_log():
    try:
        _, per_page, offset = _page_params()
        tenant_filter = request.args.get("tenant_id")
        actor_filter = request.args.get("actor_id")
        action_filter = request.args.get("action")
        target_type_filter = request.args.get("target_type")
        date_from = request.args.get("date_from")
        date_to = request.args.get("date_to")

        conditions = ["1=1"]
        params: list = []
        if tenant_filter:
            conditions.append("al.tenant_id = %s")
            params.append(tenant_filter)
        if actor_filter:
            conditions.append("al.actor_id = %s")
            params.append(actor_filter)
        if action_filter:
            conditions.append("al.action = %s")
            params.append(action_filter)
        if target_type_filter:
            conditions.append("al.target_type = %s")
            params.append(target_type_filter)
        if date_from:
            conditions.append("al.created_at >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("al.created_at <= %s")
            params.append(date_to)
        where = " AND ".join(conditions)

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM public.audit_log al WHERE {where}", tuple(params)  # noqa: S608
            )
            total = cur.fetchone()["count"]

            cur.execute(f"""
                    SELECT al.id, al.action, al.target_type, al.target_id,
                           al.actor_role, al.created_at, al.ip_address,
                           u.email AS actor_email,
                           t.name AS tenant_name
                    FROM public.audit_log al
                    LEFT JOIN public.users u ON u.id = al.actor_id
                    LEFT JOIN public.tenants t ON t.id = al.tenant_id
                    WHERE {where}
                    ORDER BY al.created_at DESC
                    LIMIT %s OFFSET %s
                """, tuple(params) + (per_page, offset))  # noqa: S608
            rows = cur.fetchall()
            items = [_clean_row(dict(r)) for r in rows]

        return success({"items": items, "total": total})
    except Exception as exc:
        logger.error("list_audit_log_error: %s", exc, exc_info=True)
        return error("Erro ao buscar audit log", 500)


@admin_bp.route("/audit-log/export", methods=["GET"])
@require_superadmin
def export_audit_log():
    try:
        tenant_filter = request.args.get("tenant_id")
        action_filter = request.args.get("action")
        date_from = request.args.get("date_from")
        date_to = request.args.get("date_to")

        conditions = ["1=1"]
        params: list = []
        if tenant_filter:
            conditions.append("al.tenant_id = %s")
            params.append(tenant_filter)
        if action_filter:
            conditions.append("al.action = %s")
            params.append(action_filter)
        if date_from:
            conditions.append("al.created_at >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("al.created_at <= %s")
            params.append(date_to)
        where = " AND ".join(conditions)

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(f"""
                    SELECT al.created_at, u.email AS actor_email, al.actor_role,
                           t.name AS tenant_name, al.target_type, al.target_id,
                           al.action, al.ip_address
                    FROM public.audit_log al
                    LEFT JOIN public.users u ON u.id = al.actor_id
                    LEFT JOIN public.tenants t ON t.id = al.tenant_id
                    WHERE {where}
                    ORDER BY al.created_at DESC
                    LIMIT 10000
                """, tuple(params))  # noqa: S608
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([
                v.isoformat() if hasattr(v, "isoformat") else (str(v) if v is not None else "")
                for v in row.values()
            ])

        date_str = datetime.utcnow().strftime("%Y%m%d")
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit-log-{date_str}.csv"
            },
        )
    except Exception as exc:
        logger.error("export_audit_log_error: %s", exc, exc_info=True)
        return error("Erro ao exportar audit log", 500)


# ---------------------------------------------------------------------------
# Announcements (admin)
# ---------------------------------------------------------------------------
@admin_bp.route("/announcements", methods=["GET"])
@require_superadmin
def list_announcements():
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT pa.*, u.email AS created_by_email
                    FROM public.platform_announcements pa
                    LEFT JOIN public.users u ON u.id = pa.created_by
                    WHERE pa.expires_at IS NULL OR pa.expires_at > NOW()
                    ORDER BY pa.created_at DESC
                """)
            rows = cur.fetchall()
            items = [_clean_row(dict(r)) for r in rows]
        return success({"announcements": items})
    except Exception as exc:
        logger.error("list_announcements_error: %s", exc, exc_info=True)
        return error("Erro ao listar comunicados", 500)


@admin_bp.route("/announcements", methods=["POST"])
@require_superadmin
def create_announcement():
    try:
        data = request.get_json() or {}
        actor_id, actor_role = _get_actor()
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                data.get("scheduled_at") or "NOW()"
                cur.execute("""
                    INSERT INTO public.platform_announcements
                      (title, content, type, target, target_tenant_id,
                       scheduled_at, published_at, expires_at, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s,
                            CASE WHEN %s IS NULL THEN NOW() ELSE %s::timestamptz END,
                            %s, %s)
                    RETURNING id, title, created_at
                """, (
                    data.get("title"), data.get("content"),
                    data.get("type", "info"), data.get("target", "all"),
                    data.get("target_tenant_id"),
                    data.get("scheduled_at"),
                    data.get("scheduled_at"), data.get("scheduled_at"),
                    data.get("expires_at"),
                    str(actor_id) if actor_id else None,
                ))
                row = cur.fetchone()
                announcement = _clean_row(dict(row))
            conn.commit()

        try:
            r = _get_redis()
            target = data.get("target_tenant_id") or "all"
            r.publish(f"announcement:{target}", json.dumps({
                "id": announcement["id"], "title": announcement["title"]
            }))
            r.close()
        except Exception:  # noqa: S110
            pass

        return success({"announcement": announcement}, status=201)
    except Exception as exc:
        logger.error("create_announcement_error: %s", exc, exc_info=True)
        return error("Erro ao criar comunicado", 500)


@admin_bp.route("/announcements/<announcement_id>", methods=["PATCH"])
@require_superadmin
def update_announcement(announcement_id: str):
    try:
        data = request.get_json() or {}
        allowed = {"title", "content", "type", "target", "expires_at", "scheduled_at"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return error("Nenhum campo válido", 400)

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                for field, val in updates.items():
                    cur.execute(
                        f"UPDATE public.platform_announcements SET {field} = %s WHERE id = %s",  # noqa: S608
                        (val, announcement_id),
                    )
            conn.commit()
        return success({"updated": True})
    except Exception as exc:
        logger.error("update_announcement_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar comunicado", 500)


@admin_bp.route("/announcements/<announcement_id>", methods=["DELETE"])
@require_superadmin
def delete_announcement(announcement_id: str):
    try:
        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                # Soft delete via expires_at = NOW()
                cur.execute(
                    "UPDATE public.platform_announcements SET expires_at = NOW() WHERE id = %s",
                    (announcement_id,),
                )
            conn.commit()
        return success({"deleted": True})
    except Exception as exc:
        logger.error("delete_announcement_error: %s", exc, exc_info=True)
        return error("Erro ao deletar comunicado", 500)


# ---------------------------------------------------------------------------
# Platform Health
# ---------------------------------------------------------------------------
@admin_bp.route("/health/platform", methods=["GET"])
@require_superadmin
def platform_health():
    import time
    services = {}

    # PostgreSQL
    try:
        start = time.time()
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        latency = round((time.time() - start) * 1000, 1)
        services["database"] = {"status": "healthy", "latency_ms": latency}
    except Exception as exc:
        services["database"] = {"status": "critical", "details": str(exc)}

    # Redis
    try:
        start = time.time()
        r = _get_redis()
        r.ping()
        r.close()
        latency = round((time.time() - start) * 1000, 1)
        services["redis"] = {"status": "healthy", "latency_ms": latency}
    except Exception as exc:
        services["redis"] = {"status": "critical", "details": str(exc)}

    # R2
    try:
        from app.infrastructure.storage.r2_storage import R2Storage
        start = time.time()
        r2 = R2Storage()
        r2.exists("health-check-probe")
        latency = round((time.time() - start) * 1000, 1)
        services["r2"] = {"status": "healthy", "latency_ms": latency}
    except Exception as exc:
        services["r2"] = {"status": "degraded", "details": str(exc)}

    # Celery (via Redis queue length)
    celery_queues = {}
    try:
        r = _get_redis()
        for q in ["inference", "extraction", "training", "versioning", "quality_recording"]:
            celery_queues[q] = r.llen(q) or 0
        r.close()
        services["celery"] = {"status": "healthy"}
    except Exception as exc:
        services["celery"] = {"status": "degraded", "details": str(exc)}

    statuses = [s.get("status", "unknown") for s in services.values()]
    if "critical" in statuses:
        overall = "critical"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return success({
        "status": overall,
        "services": services,
        "celery_queues": celery_queues,
    })


@admin_bp.route("/health/metrics", methods=["GET"])
@require_superadmin
def health_metrics():
    try:
        celery_queues = {}
        try:
            r = _get_redis()
            for q in ["inference", "extraction", "training", "versioning",
                      "quality_recording", "quality_clips", "quality_cep"]:
                celery_queues[q] = r.llen(q) or 0
            r.close()
        except Exception:  # noqa: S110
            pass

        return success({
            "errors_24h": 0,
            "avg_response_ms": 0,
            "celery_queues": celery_queues,
        })
    except Exception as exc:
        logger.error("health_metrics_error: %s", exc, exc_info=True)
        return error("Erro ao buscar métricas de saúde", 500)


# ---------------------------------------------------------------------------
# Client-facing — Announcements (qualquer role autenticada)
# ---------------------------------------------------------------------------
@client_bp.route("/announcements", methods=["GET"])
@jwt_required()
def get_client_announcements():
    try:
        from app.core.auth import get_tenant_id
        tenant_id = get_tenant_id()

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT pa.id, pa.title, pa.content, pa.type, pa.published_at
                    FROM public.platform_announcements pa
                    WHERE pa.published_at <= NOW()
                      AND (pa.expires_at IS NULL OR pa.expires_at > NOW())
                      AND (pa.target = 'all' OR pa.target_tenant_id = %s)
                      AND NOT EXISTS (
                        SELECT 1 FROM public.announcement_reads ar
                        WHERE ar.announcement_id = pa.id AND ar.tenant_id = %s
                      )
                    ORDER BY pa.published_at DESC
                """, (str(tenant_id), str(tenant_id)))
            rows = cur.fetchall()
            items = [_clean_row(dict(r)) for r in rows]

        return success({"announcements": items})
    except Exception as exc:
        logger.error("client_announcements_error: %s", exc, exc_info=True)
        return error("Erro ao buscar comunicados", 500)


@client_bp.route("/announcements/<announcement_id>/read", methods=["POST"])
@jwt_required()
def mark_announcement_read(announcement_id: str):
    try:
        from app.core.auth import get_tenant_id
        tenant_id = get_tenant_id()

        pool = _pool()
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.announcement_reads (announcement_id, tenant_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (announcement_id, str(tenant_id)))
            conn.commit()

        return success({"read": True})
    except Exception as exc:
        logger.error("mark_read_error: %s", exc, exc_info=True)
        return error("Erro ao marcar comunicado como lido", 500)
