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
def register():  # type: ignore[no-untyped-def]
    """Registrar novo usuário."""
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
def login():  # type: ignore[no-untyped-def]
    """Login do usuário."""
    try:
        data = request.get_json() or {}
        service = _get_auth_service()
        user = service.login(
            email=data.get("email", ""),
            password=data.get("password", ""),
        )
        token = create_access_token(identity=str(user["id"]))
        return success({"token": token, "user": user})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("login_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():  # type: ignore[no-untyped-def]
    """Perfil do usuário autenticado."""
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
