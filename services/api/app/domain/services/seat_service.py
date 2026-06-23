"""
DOMAIN seat_service.py — Enforcement de assentos (seats) por tenant.

Layer: domain
Pattern: Service (framework-agnostic)

Key exports:
  - check_seat_available(policy_repo, tenant_id):
      Lê tenants.max_seats (NULL = ilimitado) e conta usuários ativos.
      Raises ConflictError com mensagem clara quando o limite foi atingido.
      Retorna {"used": int, "max": int|None} quando há assento disponível.

Constraints:
  - Chamado ANTES de criar/convidar usuário (admin POST /api/v1/admin/users).
  - Fail-closed apenas quando o limite é conhecido e atingido; erros de
    leitura de política são propagados ao caller (não mascarar).

Related: app/infrastructure/database/repositories/tenant_policy_repository.py,
         app/api/v1/admin/routes.py (create_user)
"""
import logging
from typing import Any

from app.core.exceptions import ConflictError

logger = logging.getLogger(__name__)


def check_seat_available(policy_repo: Any, tenant_id: str) -> dict[str, Any]:
    """Verifica se o tenant tem assento livre para um novo usuário ativo.

    Args:
        policy_repo: TenantPolicyRepository (ou mock) com
                     get_seat_policy(tenant_id) e count_active_users(tenant_id).
        tenant_id:   UUID (str) do tenant.

    Returns:
        {"used": int, "max": int | None}

    Raises:
        ConflictError: quando count(usuários ativos) >= max_seats.
    """
    policy = policy_repo.get_seat_policy(tenant_id)
    max_seats = policy.get("max_seats")
    used = policy_repo.count_active_users(tenant_id)

    if max_seats is not None and used >= int(max_seats):
        logger.warning(
            "seat_limit_reached: tenant=%s used=%d max=%d", tenant_id, used, max_seats
        )
        raise ConflictError(
            f"Limite de assentos atingido ({used}/{max_seats}). "
            "Desative um usuário ou contrate assentos adicionais."
        )

    return {"used": used, "max": max_seats}
