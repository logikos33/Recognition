"""Repository: Users."""
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Queries SQL para tabela users."""

    def create(
        self,
        email: str,
        password_hash: str,
        name: str,
        role: str = "operator",
    ) -> dict[str, Any]:
        """Cria usuário. Retorna dict com dados do usuário."""
        return self._execute_mutation(
            "INSERT INTO users (email, password_hash, name, role) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, email, name, role, is_active, created_at",
            (email, password_hash, name, role),
        )  # type: ignore[return-value]

    def get_by_id(self, user_id: UUID) -> Optional[dict[str, Any]]:
        """Busca usuário por ID."""
        return self._execute_one(
            "SELECT id, email, name, role, is_active, created_at, updated_at "
            "FROM users WHERE id = %s",
            (str(user_id),),
        )

    def get_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Busca usuário por email (inclui password_hash para login)."""
        return self._execute_one(
            "SELECT id, email, name, role, password_hash, is_active, created_at "
            "FROM users WHERE email = %s",
            (email,),
        )

    def exists_by_email(self, email: str) -> bool:
        """Verifica se email já existe."""
        row = self._execute_one(
            "SELECT EXISTS(SELECT 1 FROM users WHERE email = %s) AS exists",
            (email,),
        )
        return row["exists"] if row else False

    def update_active(self, user_id: UUID, is_active: bool) -> Optional[dict[str, Any]]:
        """Ativa/desativa usuário."""
        return self._execute_mutation(
            "UPDATE users SET is_active = %s, updated_at = NOW() "
            "WHERE id = %s RETURNING id, email, name, role, is_active",
            (is_active, str(user_id)),
        )
