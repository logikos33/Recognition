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
            "SELECT id, email, name, role, is_active, created_at, updated_at, "
            "tenant_id, custom_role_id "
            "FROM users WHERE id = %s",
            (str(user_id),),
        )

    def get_by_id_with_tenant(self, user_id: str) -> Optional[dict[str, Any]]:
        """
        Busca usuário por ID com JOIN em tenants (WS6 — impersonation).

        Retorna o mesmo shape de claims do login (tenant_schema,
        modules_enabled), SEM password_hash — impersonation nunca toca
        credenciais do alvo.
        """
        return self._execute_one(
            """
            SELECT
                u.id,
                u.email,
                u.name,
                u.role,
                u.is_active,
                u.created_at,
                u.tenant_id,
                u.custom_role_id,
                u.force_password_reset,
                t.schema_name  AS tenant_schema,
                t.modules_enabled AS modules_enabled
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE u.id = %s
            """,
            (str(user_id),),
        )

    def get_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """
        Busca usuário por email para login.

        Faz JOIN com tenants para retornar tenant_schema e modules_enabled
        necessários para compor os claims do JWT.
        """
        return self._execute_one(
            """
            SELECT
                u.id,
                u.email,
                u.name,
                u.role,
                u.password_hash,
                u.is_active,
                u.created_at,
                u.tenant_id,
                u.custom_role_id,
                u.force_password_reset,
                t.schema_name  AS tenant_schema,
                t.modules_enabled AS modules_enabled
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE u.email = %s
            """,
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

    def register_login(
        self, user_id: str, ip_address: str | None = None
    ) -> Optional[dict[str, Any]]:
        """Grava o acesso: last_login_at, last_login_ip e login_count + 1.

        As três colunas existem desde a migration 029 e eram servidas por
        GET /api/v1/admin/users, mas NENHUM caminho as escrevia — o painel
        mostrava "nunca acessou" para quem tinha acabado de entrar (issue
        #764). Sem esta escrita, o registro de acesso é enfeite.

        COALESCE no contador porque a coluna nasceu NULLable com DEFAULT 0:
        linhas anteriores à migration têm NULL, e NULL + 1 é NULL.
        """
        return self._execute_mutation(
            "UPDATE users SET last_login_at = NOW(), "
            "login_count = COALESCE(login_count, 0) + 1, "
            "last_login_ip = %s "
            "WHERE id = %s RETURNING id, last_login_at, login_count",
            (ip_address, str(user_id)),
        )

    def reset_password(self, user_id: str, password_hash: str) -> Optional[dict[str, Any]]:
        """Atualiza a senha e limpa force_password_reset (ADR-0042 Fase 2)."""
        return self._execute_mutation(
            "UPDATE users SET password_hash = %s, force_password_reset = false, "
            "updated_at = NOW() WHERE id = %s RETURNING id, email",
            (password_hash, str(user_id)),
        )
