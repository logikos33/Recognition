"""
Recognition — Auth Routes.

POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
POST /api/auth/forgot-password
POST /api/auth/reset-password
"""
import logging
import os

from flask import Blueprint, request
from flask_jwt_extended import create_access_token, jwt_required

from app.core.auth import get_current_user_id
from app.core.responses import success, error
from app.core.exceptions import AuthenticationError, EpiMonitorError
from app.core import login_account_limiter
from app.domain.services.auth_service import AuthService
from app.domain.services.password_reset_service import PasswordResetService
from app.extensions import limiter
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.session_repository import SessionRepository
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _get_auth_service() -> AuthService:
    """Factory: cria AuthService com dependências."""
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AuthService(UserRepository(pool))


def _get_password_reset_service() -> PasswordResetService:
    """Factory: cria PasswordResetService com dependências."""
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return PasswordResetService(UserRepository(pool), SessionRepository(pool))


def _public_registration_enabled() -> bool:
    """Auto-registro público — OFF por padrão.

    Sem tenant no payload, o usuário nasce com role='operator' e SEM
    tenant_id; o próprio /login depois recusa essa conta ("Usuário sem tenant
    atribuído", ADR-0017). Ou seja: a rota aberta só sabia produzir conta
    órfã. Contas são criadas pelo administrador em /admin/users — rota
    POST /api/admin/users, que exige tenant_id e superadmin.

    Lido a cada request de propósito: liga/desliga sem redeploy.
    """
    return os.environ.get("ALLOW_PUBLIC_REGISTRATION", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _email_delivery_configured() -> bool:
    """True só quando o provedor de e-mail tem as envs mínimas p/ enviar.

    Espelha exatamente as condições que fazem resend_client/smtp_client
    levantarem RuntimeError. Sem isso, /forgot-password respondia "enviaremos
    um link" e o e-mail nunca saía (o erro é engolido por desenho, para não
    vazar existência de conta).
    """
    if not os.environ.get("EMAIL_FROM", "").strip():
        return False
    provider = os.environ.get("EMAIL_PROVIDER", "resend").strip().lower()
    if provider == "smtp":
        return bool(os.environ.get("SMTP_HOST", "").strip())
    return bool(os.environ.get("RESEND_API_KEY", "").strip())


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
      403:
        description: >
          Auto-registro desativado (padrão). Ligue ALLOW_PUBLIC_REGISTRATION
          para reabrir — contas normalmente são criadas pelo administrador.
    """
    if not _public_registration_enabled():
        return error(
            "Criação de conta pelo próprio usuário está desativada. "
            "Peça ao administrador da sua empresa para criar seu acesso.",
            403,
            error_code="registration_disabled",
        )
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
      429:
        description: Muitas tentativas de login (limite por IP ou por conta — D-34)
    """
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()

        # D-34: limite de tentativas por CONTA — complementa o limite por IP
        # do flask-limiter acima, que fica fraco atrás do ProxyFix (D-32: o
        # "IP" varia por conexão). Mensagem genérica: não revela se a conta
        # existe nem que está bloqueada (evita enumeração).
        if login_account_limiter.is_blocked(email):
            return error(
                "Muitas tentativas de login. Tente novamente em alguns minutos.",
                429,
            )

        service = _get_auth_service()
        try:
            user = service.login(email=email, password=data.get("password", ""))
        except AuthenticationError:
            login_account_limiter.register_failure(email)
            raise
        # Sucesso na verificação de credenciais — zera o contador de falhas
        # da conta (recomendação OWASP).
        login_account_limiter.reset(email)

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

        # WS7: permissões efetivas (role ∪ custom_role ± overrides) na claim
        # 'perms'. Best-effort: falha no cálculo NUNCA bloqueia o login —
        # token sai sem a claim e os gates caem no fallback por role.
        perms = _resolve_permissions(user)
        if perms is not None:
            additional_claims["perms"] = perms

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
        # WS7: permissões efetivas expostas p/ gating de UI
        if perms is not None:
            user_response["permissions"] = perms
        else:
            from app.core.permissions import permissions_for_role
            user_response["permissions"] = permissions_for_role(role)

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


def _resolve_permissions(user: dict) -> list | None:
    """Calcula permissões efetivas p/ claim 'perms' (WS7). Best-effort.

    Retorna None em qualquer falha — o chamador emite o token sem a claim
    e os gates usam o fallback por role (zero lockout).
    """
    try:
        from app.domain.services.permission_service import PermissionService
        from app.infrastructure.database.repositories.custom_role_repository import (
            CustomRoleRepository,
        )
        from app.infrastructure.database.repositories.permission_override_repository import (
            PermissionOverrideRepository,
        )

        pool = DatabasePool.get_instance()
        if pool is None:
            return None
        service = PermissionService(
            PermissionOverrideRepository(pool), CustomRoleRepository(pool)
        )
        return service.resolve_effective(user)
    except Exception as exc:
        logger.warning("perms_claim_failed: %s", exc)
        return None


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
        # WS7: permissões efetivas p/ gating de UI — best-effort com fallback
        perms = _resolve_permissions(user)
        if perms is not None:
            user["permissions"] = perms
        else:
            from app.core.permissions import permissions_for_role
            user["permissions"] = permissions_for_role(str(user.get("role") or ""))
        return success(user)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("me_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@auth_bp.route("/forgot-password", methods=["POST"])
@limiter.limit("5 per hour")
def forgot_password():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - auth
    summary: Solicita link de redefinição de senha por e-mail
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [email]
          properties:
            email: {type: string}
    responses:
      200:
        description: >
          Retornado para qualquer e-mail existente ou não — evita
          enumeração de contas.
      503:
        description: >
          Envio de e-mail não configurado no ambiente. Mensagem idêntica para
          qualquer e-mail (não vaza existência de conta).
    """
    # Envio não configurado: dizer a verdade em vez de prometer um e-mail que
    # nunca sai. Não vaza existência de conta — a resposta é idêntica para
    # qualquer e-mail (nem chega a consultar o banco). Quando o envio existe,
    # a resposta volta a ser a genérica de sempre.
    if not _email_delivery_configured():
        logger.warning("forgot_password_unavailable: envio de e-mail não configurado")
        return error(
            "A recuperação de senha por e-mail ainda não está disponível. "
            "Peça ao administrador para redefinir sua senha.",
            503,
            error_code="email_delivery_unconfigured",
        )
    try:
        data = request.get_json() or {}
        service = _get_password_reset_service()
        service.request_reset(data.get("email", ""))
    except Exception as exc:
        # Nunca vazar detalhe/erro interno — resposta é sempre neutra.
        logger.error("forgot_password_error: %s", exc, exc_info=True)
    return success(message="Se o e-mail existir, enviaremos um link de redefinição.")


@auth_bp.route("/reset-password", methods=["POST"])
@limiter.limit("10 per hour")
def reset_password():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - auth
    summary: Redefine a senha a partir do token recebido por e-mail
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [token, password]
          properties:
            token: {type: string}
            password: {type: string}
    responses:
      200:
        description: Senha redefinida
      400:
        description: Token inválido, expirado ou senha inválida
    """
    try:
        data = request.get_json() or {}
        service = _get_password_reset_service()
        service.reset_password(
            token=data.get("token", ""),
            new_password=data.get("password", ""),
        )
        return success(message="Senha redefinida. Faça login com a nova senha.")
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("reset_password_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
