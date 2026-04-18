"""
Admin Versions & Changelog — Endpoints de versionamento do sistema.

Layer: api/v1/admin
Pattern: Blueprint isolado do routes.py principal para minimizar blast radius.

Grupos de endpoints:
  Versions   GET|POST /api/v1/admin/versions
             GET      /api/v1/admin/versions/<id>
             POST     /api/v1/admin/versions/<id>/rollback
  Changelog  GET|POST /api/v1/admin/changelog

Conceitos:
  - Version = checkpoint manual criado pelo admin (como git tag)
  - Changelog = entrada individual de mudança (auto ou manual)
  - Rollback = restaura modules_enabled, plan, feature_flags de cada tenant
    a partir do config_snapshot armazenado na versão. NÃO altera schema.

Snapshot format (config_snapshot JSONB):
  {
    "tenants": [
      {"id": "uuid", "slug": "rvb", "plan": "standard",
       "modules_enabled": ["epi", "basic"], "feature_flags": {}, "is_active": true}
    ],
    "plans": [
      {"id": "uuid", "slug": "standard", "modules_allowed": [...]}
    ]
  }
"""
import json
import logging

from flask import Blueprint, request

from app.core.auth import get_current_user_id, get_role
from app.core.responses import error, success
from app.core.tenant import log_audit, log_change, require_superadmin
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

admin_versions_bp = Blueprint(
    "admin_versions", __name__, url_prefix="/api/v1/admin"
)


# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------

def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _clean(row: dict) -> dict:
    """Serializa UUIDs e datetimes para JSON. Idêntico ao _clean_row de routes.py."""
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
    try:
        return get_current_user_id(), get_role()
    except Exception:
        return None, "superadmin"


def _build_snapshot(cur) -> dict:
    """
    Coleta estado atual de configuração para armazenar no snapshot da versão.

    Captura apenas dados configuráveis e reversíveis:
    - Módulos habilitados por tenant
    - Plano por tenant
    - Feature flags por tenant
    - Definições de planos
    """
    # Tenants: módulos, plano, flags
    cur.execute("""
        SELECT id, slug, plan, modules_enabled, feature_flags, is_active
        FROM public.tenants
        ORDER BY created_at
    """)
    tenants = []
    for r in cur.fetchall():
        tenants.append({
            "id": str(r["id"]),
            "slug": r["slug"],
            "plan": r["plan"],
            "modules_enabled": r["modules_enabled"] or [],
            "feature_flags": r["feature_flags"] or {},
            "is_active": r["is_active"],
        })

    # Planos: definições de módulos permitidos
    cur.execute("SELECT id, slug, name, modules_allowed FROM public.plans ORDER BY slug")
    plans = []
    for r in cur.fetchall():
        plans.append({
            "id": str(r["id"]),
            "slug": r["slug"],
            "name": r["name"],
            "modules_allowed": r["modules_allowed"] or [],
        })

    return {"tenants": tenants, "plans": plans}


# ---------------------------------------------------------------------------
# GET /api/v1/admin/versions — listar versões
# ---------------------------------------------------------------------------
@admin_versions_bp.route("/versions", methods=["GET"])
@require_superadmin
def list_versions():
    """
    Retorna lista de versões em ordem decrescente.
    Inclui contagem de changelog entries por versão.
    """
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT
                  v.id, v.version, v.version_type, v.title, v.description,
                  v.created_at, v.is_current, v.rolled_back_at,
                  u.email AS created_by_email,
                  COUNT(c.id) AS changelog_count
                FROM public.system_versions v
                LEFT JOIN public.users u ON u.id = v.created_by
                LEFT JOIN public.system_changelog c ON c.version_id = v.id
                GROUP BY v.id, u.email
                ORDER BY v.created_at DESC
                LIMIT 100
            """)
            versions = [_clean(dict(r)) for r in cur.fetchall()]

        return success({"versions": versions})
    except Exception as exc:
        logger.error("list_versions_error: %s", exc, exc_info=True)
        return error("Erro ao listar versões", 500)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/versions — criar nova versão (checkpoint)
# ---------------------------------------------------------------------------
@admin_versions_bp.route("/versions", methods=["POST"])
@require_superadmin
def create_version():
    """
    Cria novo checkpoint de versão com snapshot da configuração atual.

    Body:
      version      string  obrigatório  ex: "1.2.0"
      version_type string  obrigatório  'major' | 'minor' | 'patch'
      title        string  obrigatório  título descritivo
      description  string  opcional     detalhamento da versão

    O snapshot captura automaticamente o estado de todos os tenants e planos.
    Marcar versão anterior como is_current=false e nova como is_current=true.
    """
    data = request.get_json() or {}
    version = (data.get("version") or "").strip()
    version_type = data.get("version_type", "patch")
    title = (data.get("title") or "").strip()
    description = data.get("description")

    if not version or not title:
        return error("version e title são obrigatórios", 400)
    if version_type not in ("major", "minor", "patch"):
        return error("version_type deve ser major, minor ou patch", 400)

    actor_id, actor_role = _get_actor()

    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            # Verificar duplicata de versão
            cur.execute(
                "SELECT id FROM public.system_versions WHERE version = %s", (version,)
            )
            if cur.fetchone():
                return error(f"Versão {version} já existe", 409)

            # Coletar snapshot do estado atual
            snapshot = _build_snapshot(cur)

            # Desmarcar versão atual anterior
            cur.execute(
                "UPDATE public.system_versions SET is_current = false WHERE is_current = true"
            )

            # Inserir nova versão
            cur.execute("""
                INSERT INTO public.system_versions
                  (version, version_type, title, description, created_by,
                   config_snapshot, is_current)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, true)
                RETURNING id, version, version_type, title, created_at
            """, (
                version, version_type, title, description,
                str(actor_id) if actor_id else None,
                json.dumps(snapshot),
            ))
            row = cur.fetchone()
            new_id = str(row["id"])

            # Changelog entry automática para criação de versão
            cur.execute("""
                INSERT INTO public.system_changelog
                  (version_id, category, importance, title, affected_area, created_by)
                VALUES (%s, 'infra', %s, %s, 'system', %s)
            """, (
                new_id,
                "critical" if version_type == "major"
                else "high" if version_type == "minor" else "normal",
                f"Versão {version} criada — {title}",
                str(actor_id) if actor_id else None,
            ))

        conn.commit()

        log_audit(
            actor_id, actor_role, None, "system_version", new_id, "created",
            new_value={"version": version, "type": version_type, "title": title},
        )
        log_change(
            actor_id, actor_role,
            f"Versão {version} ({version_type}) criada: {title}",
            category="infra",
            importance="critical" if version_type == "major" else "high",
            description=description,
            affected_area="system",
            version_id=new_id,
        )

        return success({"version_id": new_id, "version": version}, status=201)
    except Exception as exc:
        logger.error("create_version_error: %s", exc, exc_info=True)
        return error("Erro ao criar versão", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/versions/<version_id> — detalhe da versão
# ---------------------------------------------------------------------------
@admin_versions_bp.route("/versions/<version_id>", methods=["GET"])
@require_superadmin
def get_version(version_id: str):
    """
    Retorna detalhe de uma versão: metadados + changelog entries + snapshot resumido.
    O config_snapshot completo é retornado para possibilitar preview do rollback.
    """
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT v.*, u.email AS created_by_email,
                       rb.email AS rolled_back_by_email
                FROM public.system_versions v
                LEFT JOIN public.users u ON u.id = v.created_by
                LEFT JOIN public.users rb ON rb.id = v.rolled_back_by
                WHERE v.id = %s
            """, (version_id,))
            row = cur.fetchone()
            if not row:
                return error("Versão não encontrada", 404)

            version = _clean(dict(row))

            # Changelog entries desta versão
            cur.execute("""
                SELECT c.*, u.email AS created_by_email
                FROM public.system_changelog c
                LEFT JOIN public.users u ON u.id = c.created_by
                WHERE c.version_id = %s
                ORDER BY c.created_at DESC
            """, (version_id,))
            version["changelog"] = [_clean(dict(r)) for r in cur.fetchall()]

        return success({"version": version})
    except Exception as exc:
        logger.error("get_version_error: %s", exc, exc_info=True)
        return error("Erro ao buscar versão", 500)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/versions/<version_id>/rollback — restaurar configuração
# ---------------------------------------------------------------------------
@admin_versions_bp.route("/versions/<version_id>/rollback", methods=["POST"])
@require_superadmin
def rollback_version(version_id: str):
    """
    Restaura configuração de tenants a partir do snapshot da versão.

    Escopo do rollback (apenas configuração, nunca schema):
    - tenants.modules_enabled
    - tenants.plan
    - tenants.feature_flags

    Versão alvo é marcada como is_current=true.
    Ação registrada em audit_log e system_changelog para rastreabilidade.

    Body:
      confirm  boolean  obrigatório (true) — confirmação explícita do admin
    """
    data = request.get_json() or {}
    if not data.get("confirm"):
        return error("Confirme o rollback enviando confirm: true", 400)

    actor_id, actor_role = _get_actor()

    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, version, title, config_snapshot"
                " FROM public.system_versions WHERE id = %s",
                (version_id,),
            )
            row = cur.fetchone()
            if not row:
                return error("Versão não encontrada", 404)

            snapshot = row["config_snapshot"] or {}
            if isinstance(snapshot, str):
                snapshot = json.loads(snapshot)

            tenants_snap = snapshot.get("tenants", [])
            if not tenants_snap:
                return error("Snapshot não contém dados de tenants para restaurar", 422)

            restored_count = 0
            for t in tenants_snap:
                cur.execute("""
                    UPDATE public.tenants
                    SET plan           = %s,
                        modules_enabled = %s::jsonb,
                        feature_flags  = %s::jsonb
                    WHERE id = %s
                """, (
                    t.get("plan"),
                    json.dumps(t.get("modules_enabled", [])),
                    json.dumps(t.get("feature_flags", {})),
                    t["id"],
                ))
                restored_count += cur.rowcount

            # Atualizar is_current
            cur.execute(
                "UPDATE public.system_versions SET is_current = false WHERE is_current = true"
            )
            cur.execute("""
                UPDATE public.system_versions
                SET is_current = true,
                    rolled_back_at = NULL,
                    rolled_back_by = NULL
                WHERE id = %s
            """, (version_id,))

            # Marcar versão anterior como rolled_back
            cur.execute("""
                UPDATE public.system_versions
                SET rolled_back_at = NOW(), rolled_back_by = %s
                WHERE is_current = false AND rolled_back_at IS NULL AND id != %s
                  AND created_at > (SELECT created_at FROM public.system_versions WHERE id = %s)
            """, (
                str(actor_id) if actor_id else None,
                version_id, version_id,
            ))

        conn.commit()

        version_label = f"{row['version']} — {row['title']}"
        log_audit(
            actor_id, actor_role, None, "system_version", version_id, "rollback",
            new_value={"tenants_restored": restored_count, "version": row["version"]},
        )
        log_change(
            actor_id, actor_role,
            f"Rollback para versão {version_label}",
            category="infra",
            importance="critical",
            description=f"Configuração de {restored_count} tenant(s) restaurada.",
            affected_area="system",
            version_id=version_id,
        )

        return success({
            "rolled_back_to": row["version"],
            "tenants_restored": restored_count,
        })
    except Exception as exc:
        logger.error("rollback_version_error: %s", exc, exc_info=True)
        return error("Erro ao fazer rollback", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/changelog — listar entradas de changelog
# ---------------------------------------------------------------------------
@admin_versions_bp.route("/changelog", methods=["GET"])
@require_superadmin
def list_changelog():
    """
    Retorna changelog paginado com filtros.

    Query params:
      category      string  filtro por categoria
      importance    string  filtro por nível de importância
      affected_area string  filtro por área
      version_id    string  filtro por versão específica
      page          int     página (default 1)
      per_page      int     por página (max 100, default 30)
    """
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 30))))
        offset = (page - 1) * per_page

        conditions = ["1=1"]
        params: list = []

        if cat := request.args.get("category"):
            conditions.append("c.category = %s")
            params.append(cat)
        if imp := request.args.get("importance"):
            conditions.append("c.importance = %s")
            params.append(imp)
        if area := request.args.get("affected_area"):
            conditions.append("c.affected_area = %s")
            params.append(area)
        if vid := request.args.get("version_id"):
            conditions.append("c.version_id = %s")
            params.append(vid)

        where = " AND ".join(conditions)

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM public.system_changelog c WHERE {where}",  # noqa: S608
                tuple(params),
            )
            total = cur.fetchone()["count"]

            cur.execute(f"""
                SELECT c.*, v.version AS version_label, u.email AS created_by_email
                FROM public.system_changelog c
                LEFT JOIN public.system_versions v ON v.id = c.version_id
                LEFT JOIN public.users u ON u.id = c.created_by
                WHERE {where}
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
            """, (*params, per_page, offset))  # noqa: S608
            items = [_clean(dict(r)) for r in cur.fetchall()]

        return success({"items": items, "total": total, "page": page, "per_page": per_page})
    except Exception as exc:
        logger.error("list_changelog_error: %s", exc, exc_info=True)
        return error("Erro ao listar changelog", 500)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/changelog — criar entrada manual de changelog
# ---------------------------------------------------------------------------
@admin_versions_bp.route("/changelog", methods=["POST"])
@require_superadmin
def create_changelog_entry():
    """
    Cria entrada manual no changelog (sem vínculo obrigatório a versão).

    Body:
      title         string  obrigatório
      category      string  default 'config'
      importance    string  default 'normal'
      description   string  opcional
      affected_area string  opcional
      version_id    string  opcional — vincular a versão existente
    """
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    if not title:
        return error("title é obrigatório", 400)

    category = data.get("category", "config")
    importance = data.get("importance", "normal")
    description = data.get("description")
    affected_area = data.get("affected_area")
    version_id = data.get("version_id")

    if category not in ("feature", "fix", "config", "security", "breaking", "infra"):
        return error("category inválida", 400)
    if importance not in ("critical", "high", "normal", "low"):
        return error("importance inválida", 400)

    actor_id, _ = _get_actor()

    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            # Verificar versão se informada
            if version_id:
                cur.execute(
                    "SELECT id FROM public.system_versions WHERE id = %s", (version_id,)
                )
                if not cur.fetchone():
                    return error("version_id não encontrado", 404)

            cur.execute("""
                INSERT INTO public.system_changelog
                  (version_id, category, importance, title, description,
                   affected_area, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
            """, (
                version_id,
                category, importance, title, description,
                affected_area,
                str(actor_id) if actor_id else None,
            ))
            row = cur.fetchone()
        conn.commit()

        return success({"id": str(row["id"])}, status=201)
    except Exception as exc:
        logger.error("create_changelog_error: %s", exc, exc_info=True)
        return error("Erro ao criar entrada de changelog", 500)
