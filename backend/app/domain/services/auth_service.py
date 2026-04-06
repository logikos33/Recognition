"""
EPI Monitor V2 — Auth Service.

Lógica de negócio de autenticação. NÃO conhece Flask.
"""
import logging
from uuid import UUID

from app.core.auth import check_password, hash_password
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class AuthService:
    """Use cases de autenticação."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def register(
        self, email: str, password: str, name: str
    ) -> dict:
        """Registra novo usuário. Retorna dict do usuário (sem hash)."""
        email = email.strip().lower()
        name = name.strip()

        if not all([email, password, name]):
            raise ValidationError("email, password e name são obrigatórios")
        if len(password) < 6:
            raise ValidationError("Senha: mínimo 6 caracteres")

        if self._user_repo.exists_by_email(email):
            raise ConflictError("Email já cadastrado")

        hashed = hash_password(password)
        user = self._user_repo.create(email, hashed, name)
        user["id"] = str(user["id"])
        return user

    def login(self, email: str, password: str) -> dict:
        """Autentica usuário. Retorna dict do usuário (sem hash)."""
        email = email.strip().lower()
        if not email or not password:
            raise ValidationError("email e password obrigatórios")

        user = self._user_repo.get_by_email(email)
        if not user or not user.get("is_active"):
            raise AuthenticationError("Credenciais inválidas")

        if not check_password(password, user["password_hash"]):
            raise AuthenticationError("Credenciais inválidas")

        result = {
            k: str(v) if k == "id" else v
            for k, v in user.items()
            if k != "password_hash"
        }
        return result

    def get_user(self, user_id: UUID) -> dict:
        """Busca usuário por ID."""
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("Usuário", str(user_id))
        user["id"] = str(user["id"])
        return user
