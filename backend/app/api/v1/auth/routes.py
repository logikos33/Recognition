"""
EPI Monitor V2 — Auth Routes.

POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import create_access_token, jwt_required

from app.core.auth import get_current_user_id
from app.core.responses import success, error
from app.core.exceptions import EpiMonitorError
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
        token = create_access_token(identity=str(user["id"]))
        return success({"token": token, "user": user}, status=201)
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
        # Extrair dados do tenant para incluir no JWT
        # tenant_schema e modules_enabled vêm do JOIN com tenants (user_repository)
        tenant_id = str(user.get("tenant_id") or "00000000-0000-0000-0000-000000000001")
        tenant_schema = user.get("tenant_schema") or "public"
        modules_raw = user.get("modules_enabled") or ["epi", "counting", "basic"]
        # modules_enabled pode vir como list ou como string JSON do psycopg2
        if isinstance(modules_raw, str):
            import json as _json
            try:
                modules_raw = _json.loads(modules_raw)
            except Exception:
                modules_raw = ["epi", "counting", "basic"]

        additional_claims = {
            "tenant_id": tenant_id,
            "tenant_schema": tenant_schema,
            "email": user.get("email", ""),
            "role": user.get("role", "operator"),
            "modules": modules_raw,
        }
        token = create_access_token(identity=str(user["id"]), additional_claims=additional_claims)

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
