"""
Recognition — Auth Routes.

POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import create_access_token, jwt_required

from app.core.auth import get_current_user_id
from app.core.responses import success, error
from app.core.exceptions import AuthenticationError, EpiMonitorError
from app.domain.services.auth_service import AuthService
from app.extensions import limiter
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _get_auth_service() -> AuthService:
    """Factory: cria AuthService com dependências."""
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AuthService(UserRepository(pool))


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per hour")
def register():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - auth
    summary: Registrar novo usuário
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [email, password, name]
          properties:
            email: {type: string}
            password: {type: string}
            name: {type: string}
    responses:
      201:
        description: Usuário criado
      400:
        description: Dados inválidos
    """
    try:
        data = request.get_json() or {}
        service = _get_auth_service()
        user = service.register(
            email=data.get("email", ""),
            password=data.get("password", ""),
            name=data.get("name", ""),
        )
        # Sem token no register — usuário deve fazer login explicitamente (ADR-0017)
        return success({"user": user, "message": "Conta criada. Faça login para continuar."}, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("register_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - auth
    summary: Login com email e senha
    parameters:
      - in: body
        name: body
        required: true
        schema:
          properties:
            email: {type: string, example: admin@epimonitor.com}
            password: {type: string, example: "EpiMonitor@2024!"}
    responses:
      200:
        description: Token JWT retornado
      400:
        description: Credenciais inválidas
    """
    try:
        data = request.get_json() or {}
        service = _get_auth_service()
        user = service.login(
            email=data.get("email", ""),
            password=data.get("password", ""),
        )
        # Validar campos obrigatórios do tenant — sem fallback silencioso (ADR-0017)
        tenant_schema = user.get("tenant_schema")
        if not tenant_schema:
            raise AuthenticationError(
                "Usuário sem tenant atribuído. Contate o administrador."
            )
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            raise AuthenticationError(
                "Usuário sem tenant_id. Possível corrupção de banco."
            )
        role = user.get("role")
        if not role:
            raise AuthenticationError(
                "Usuário sem role atribuída. Contate o administrador."
            )

        modules_raw = user.get("modules_enabled") or []
        # modules_enabled pode vir como list ou como string JSON do psycopg2
        if isinstance(modules_raw, str):
            import json as _json
            try:
                modules_raw = _json.loads(modules_raw)
            except Exception:
                modules_raw = []

        additional_claims = {
            "tenant_id": str(tenant_id),
            "tenant_schema": tenant_schema,
            "email": user.get("email", ""),
            "role": role,
            "modules": modules_raw,
        }
        token = create_access_token(identity=str(user["id"]), additional_claims=additional_claims)

        # Sessões concorrentes: registra sessão e aplica single_session do
        # tenant ("última sessão ganha") — best-effort, nunca bloqueia o login
        _register_session(token, str(user["id"]), str(tenant_id))

        # Remover campos internos do response
        user_response = {
            k: v for k, v in user.items()
            if k not in ("password_hash", "tenant_schema", "modules_enabled")
        }
        user_response["tenant_schema"] = tenant_schema
        user_response["modules"] = modules_raw

        return success({"token": token, "user": user_response})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("login_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def _register_session(token: str, user_id: str, tenant_id: str) -> None:
    """Registra sessão em active_sessions e aplica política single_session.

    Best-effort: qualquer falha é logada e ignorada — bookkeeping de sessão
    nunca pode impedir um login válido.
    """
    try:
        from datetime import datetime, timezone

        from flask_jwt_extended import decode_token

        from app.domain.services.session_service import register_login_session
        from app.infrastructure.database.repositories.session_repository import (
            SessionRepository,
        )
        from app.infrastructure.database.repositories.tenant_policy_repository import (
            TenantPolicyRepository,
        )

        payload = decode_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            return
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

        pool = DatabasePool.get_instance()
        if pool is None:
            return

        register_login_session(
            session_repo=SessionRepository(pool),
            policy_repo=TenantPolicyRepository(pool),
            user_id=user_id,
            tenant_id=tenant_id,
            jti=jti,
            expires_at=expires_at,
            ip_address=request.remote_addr,
            user_agent=(request.headers.get("User-Agent") or "")[:500],
        )
    except Exception as exc:
        logger.warning("session_register_failed: %s", exc)


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - auth
    summary: Logout — revoga o token atual (blocklist do jti)
    security:
      - Bearer: []
    responses:
      200:
        description: Token revogado
      401:
        description: Token inválido
    """
    try:
        from datetime import datetime, timezone

        from flask_jwt_extended import get_jwt

        from app.domain.services.session_service import revoke_jti

        claims = get_jwt()
        jti = claims.get("jti")
        exp = claims.get("exp")
        expires_at = (
            datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None
        )
        # Blocklist Redis (caminho consultado pelo token_in_blocklist_loader)
        revoke_jti(jti, expires_at)
        # Best-effort: marca a sessão como revogada no banco
        _revoke_session_record(jti)
        return success({"message": "Logout efetuado. Token revogado."})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("logout_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def _revoke_session_record(jti: str | None) -> None:
    """Marca a sessão do jti como revogada em active_sessions (best-effort)."""
    if not jti:
        return
    try:
        from app.infrastructure.database.repositories.session_repository import (
            SessionRepository,
        )

        pool = DatabasePool.get_instance()
        if pool is None:
            return
        SessionRepository(pool).revoke_by_jti(jti)
    except Exception as exc:
        logger.warning("revoke_session_record_failed: %s", exc)


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - auth
    summary: Perfil do usuário autenticado
    security:
      - Bearer: []
    responses:
      200:
        description: Dados do usuário
      401:
        description: Token inválido
    """
    try:
        user_id = get_current_user_id()
        service = _get_auth_service()
        user = service.get_user(user_id)
        return success(user)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("me_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
