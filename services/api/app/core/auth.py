"""
CORE auth.py — JWT authentication helpers and tenant extraction.

Layer: core
Pattern: Decorator, Utility

Key exports:
  - hash_password / check_password: bcrypt wrappers for password storage
  - get_current_user_id: extracts UUID from active JWT via flask_jwt_extended
  - jwt_required_custom: decorator that verifies JWT and injects current_user_id into kwargs
  - admin_required: decorator that verifies JWT and sets require_admin=True in kwargs
  - get_tenant_id: reads tenant_id claim from JWT; raises AuthenticationError if absent

Constraints:
  - All routes requiring auth must use jwt_required_custom or admin_required, not raw verify_jwt_in_request
  - admin_required delegates role enforcement to the calling service/repository
  - get_tenant_schema/get_tenant_id/get_role raise AuthenticationError — no silent fallbacks (ADR-0017)

Related: app/core/exceptions.py, app/constants.py, app/api/v1/auth/routes.py
"""
import functools
import logging
from typing import Any, Callable
from uuid import UUID

import bcrypt
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """Hash password com bcrypt. Retorna string pronta para o banco."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    """Verifica password contra hash bcrypt."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def get_current_user_id() -> UUID:
    """Extrai user_id do JWT token atual. Raises AuthenticationError."""
    try:
        identity = get_jwt_identity()
        return UUID(identity)
    except Exception as exc:
        raise AuthenticationError("Token inválido") from exc


def jwt_required_custom(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: verifica JWT e injeta user_id no kwargs."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        verify_jwt_in_request()
        kwargs["current_user_id"] = get_current_user_id()
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: verifica JWT + role admin."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        verify_jwt_in_request()
        user_id = get_current_user_id()
        # Role check delegado ao service/repository que busca o user
        kwargs["current_user_id"] = user_id
        kwargs["require_admin"] = True
        return fn(*args, **kwargs)

    return wrapper


def get_tenant_id() -> str:
    """Extrai tenant_id do JWT. Raises AuthenticationError se ausente."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        raise AuthenticationError(
            "JWT sem tenant_id — token inválido ou emitido antes do fix de segurança. "
            "Faça login novamente."
        )
    return tenant_id


def get_role() -> str:
    """Extrai role do JWT. Raises AuthenticationError se ausente."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    role = claims.get("role")
    if not role:
        raise AuthenticationError(
            "JWT sem role — token inválido ou emitido antes do fix de segurança. "
            "Faça login novamente."
        )
    return role


def get_tenant_schema() -> str:
    """Extrai tenant_schema do JWT. Raises AuthenticationError se ausente."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    schema = claims.get("tenant_schema")
    if not schema:
        raise AuthenticationError(
            "JWT sem tenant_schema — token inválido ou emitido antes do fix de segurança. "
            "Faça login novamente."
        )
    return schema


def get_modules_enabled() -> list[str]:
    """Extrai módulos habilitados do JWT. Retorna lista vazia como fallback."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    modules = claims.get("modules", [])
    return modules if isinstance(modules, list) else []
