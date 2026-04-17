"""
CORE tenant.py — Middleware de isolamento multi-tenant por schema PostgreSQL.

Layer: core
Pattern: Decorator, Whitelist validation

Fluxo de request:
  1. JWT decodificado → extrai tenant_schema e role (via app/core/auth.py)
  2. schema validado contra whitelist (SELECT schema_name FROM tenants)
  3. Decorators @require_superadmin / @require_admin verificam role

Regras de segurança (INVIOLÁVEIS):
  - NUNCA interpolar schema_name de input externo direto em SQL
  - Sempre validar contra get_schema_whitelist() antes de SET search_path
  - Whitelist cached por 60s para evitar query por request

Related: app/core/auth.py (get_role, get_tenant_schema), app/api/v1/admin/routes.py
"""
import functools
import logging
import time
from collections.abc import Callable
from typing import Any

from flask_jwt_extended import verify_jwt_in_request

# Importar helpers JWT de auth.py — fonte única de verdade
from app.core.auth import get_modules_enabled, get_role, get_tenant_schema  # noqa: F401
from app.core.exceptions import AuthorizationError

logger = logging.getLogger(__name__)

# Cache TTL para whitelist de schemas (segundos)
_SCHEMA_WHITELIST_TTL = 60
_schema_cache: dict[str, Any] = {}


def get_schema_whitelist() -> set[str]:
    """
    Retorna conjunto de schema_names válidos do banco.

    Cache de 60s para evitar query a cada request.
    Sempre inclui 'public' como schema base válido.
    """
    now = time.time()

    # Retornar cache se ainda válido
    if _schema_cache and now - _schema_cache.get("ts", 0) < _SCHEMA_WHITELIST_TTL:
        return _schema_cache["schemas"]

    try:
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return {"public"}

        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT schema_name FROM tenants "
                "WHERE schema_name IS NOT NULL AND is_active = true"
            )
            rows = cur.fetchall()
            schemas = {row[0] for row in rows} | {"public"}

        _schema_cache["schemas"] = schemas
        _schema_cache["ts"] = now
        logger.debug("schema_whitelist_refreshed: %s", schemas)
        return schemas

    except Exception as exc:
        logger.warning("schema_whitelist_failed: %s", exc)
        return {"public"}


def invalidate_schema_cache() -> None:
    """Força refresh do cache na próxima chamada. Usar após criar novo tenant."""
    _schema_cache.clear()


def validate_schema(schema_name: str) -> bool:
    """Verifica se schema está na whitelist de tenants ativos."""
    return schema_name in get_schema_whitelist()


def require_superadmin(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator: JWT obrigatório + role == 'superadmin'.
    Retorna 403 AuthorizationError se role insuficiente.
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        verify_jwt_in_request()
        role = get_role()
        if role != "superadmin":
            raise AuthorizationError("Acesso restrito a superadmin")
        return fn(*args, **kwargs)

    return wrapper


def require_admin(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator: JWT obrigatório + role in ('superadmin', 'admin').
    Retorna 403 AuthorizationError se role insuficiente.
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        verify_jwt_in_request()
        role = get_role()
        if role not in ("superadmin", "admin"):
            raise AuthorizationError("Acesso restrito a administradores")
        return fn(*args, **kwargs)

    return wrapper


def require_permission(permission: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator factory: exige permissão específica baseada em ROLE_PERMISSIONS.

    Uso: @require_permission("annotate_frames")
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            verify_jwt_in_request()
            role = get_role()
            from app.constants import ROLE_PERMISSIONS
            allowed = ROLE_PERMISSIONS.get(permission, [])
            if role not in allowed:
                raise AuthorizationError(
                    f"Permissão insuficiente — requer: {permission}"
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def log_audit(
    actor_id: Any,
    actor_role: str,
    tenant_id: Any,
    target_type: str,
    target_id: Any,
    action: str,
    old_value: Any = None,
    new_value: Any = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    Registra ação no public.audit_log.

    Nunca levanta exceção — falhas são logadas silenciosamente para não
    interromper o fluxo principal do endpoint.
    """
    try:
        import json

        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return

        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                    INSERT INTO public.audit_log
                      (actor_id, actor_role, tenant_id, target_type, target_id,
                       action, old_value, new_value, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                (
                    str(actor_id) if actor_id else None,
                    actor_role,
                    str(tenant_id) if tenant_id else None,
                    target_type,
                    str(target_id) if target_id else None,
                    action,
                    json.dumps(old_value) if old_value is not None else None,
                    json.dumps(new_value) if new_value is not None else None,
                    ip_address,
                    (user_agent or "")[:500] if user_agent else None,
                ),
            )
    except Exception as exc:
        logger.error("audit_log_failed: action=%s err=%s", action, exc)


def set_search_path(conn: Any, schema_name: str) -> None:
    """
    Define search_path da conexão para o schema do tenant.

    SEGURANÇA: Sempre validar schema_name contra whitelist antes de chamar.
    NUNCA chamar com input direto do usuário sem validar primeiro.

    Exemplo de uso correto:
        schema = get_tenant_schema()
        if validate_schema(schema):
            set_search_path(conn, schema)
        else:
            raise AuthorizationError(f"Schema inválido: {schema}")
    """
    if not validate_schema(schema_name):
        logger.error("set_search_path_rejected: schema=%s not in whitelist", schema_name)
        raise AuthorizationError(f"Schema inválido: {schema_name}")

    with conn.cursor() as cur:
        # Interpolação direta é segura aqui PORQUE schema_name foi validado
        # contra whitelist do banco antes de chegar neste ponto.
        cur.execute(f"SET search_path TO {schema_name}, public")  # noqa: S608
