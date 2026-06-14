"""Repository: políticas de plataforma por tenant (migration 051).

Fontes:
  - tenants.max_seats / tenants.single_session / tenants.rate_limit_per_minute
  - plans.api_rate_per_minute (default por tier, via tenants.plan → plans.slug)
"""
from typing import Any, Optional

from app.infrastructure.database.repositories.base import BaseRepository


class TenantPolicyRepository(BaseRepository):
    """Leitura de limites/políticas do tenant (seats, sessão única, rate limit)."""

    def get_rate_limit_per_minute(self, tenant_id: str) -> Optional[int]:
        """Rate limit efetivo do tenant (override > plano). None = sem registro."""
        row = self._execute_one(
            """
            SELECT COALESCE(t.rate_limit_per_minute, p.api_rate_per_minute) AS rpm
            FROM tenants t
            LEFT JOIN plans p ON p.slug = t.plan
            WHERE t.id = %s
            """,
            (str(tenant_id),),
        )
        if not row or row.get("rpm") is None:
            return None
        return int(row["rpm"])

    def get_seat_policy(self, tenant_id: str) -> dict[str, Any]:
        """Retorna {'max_seats': int|None, 'single_session': bool} do tenant."""
        row = self._execute_one(
            "SELECT max_seats, single_session FROM tenants WHERE id = %s",
            (str(tenant_id),),
        )
        if not row:
            return {"max_seats": None, "single_session": False}
        return {
            "max_seats": row.get("max_seats"),
            "single_session": bool(row.get("single_session")),
        }

    def count_active_users(self, tenant_id: str) -> int:
        """Conta usuários ativos do tenant (consumo de assentos)."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM users "
            "WHERE tenant_id = %s AND is_active = true",
            (str(tenant_id),),
        )
        return int(row["count"]) if row else 0
