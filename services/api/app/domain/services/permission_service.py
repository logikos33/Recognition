"""
Recognition — PermissionService (WS7).

Resolve permissões EFETIVAS de um usuário combinando:
  1. default_roles da role base (registry canônico — app/core/permissions.py)
  2. + permissões marcadas na custom_role (users.custom_role_id, migration 052)
  3. + overrides allow=true / − overrides allow=false (migration 085)

Precedência: deny override > allow override > custom_role > role.
Superadmin: SEMPRE todas as permissões — imune a deny (anti-lockout).

O resultado entra no JWT como claim 'perms' no login (auth/routes.py) e é
consumido por has_permission/require_permission (app/core/tenant.py).
"""
import json
import logging
from typing import Any

from app.core.permissions import (
    all_permission_keys,
    normalize_key,
    permissions_for_role,
)
from app.infrastructure.database.repositories.custom_role_repository import (
    CustomRoleRepository,
)
from app.infrastructure.database.repositories.permission_override_repository import (
    PermissionOverrideRepository,
)

logger = logging.getLogger(__name__)


class PermissionService:
    """Resolução de permissões efetivas por usuário."""

    def __init__(
        self,
        override_repo: PermissionOverrideRepository,
        custom_role_repo: CustomRoleRepository,
    ) -> None:
        self._overrides = override_repo
        self._custom_roles = custom_role_repo

    def resolve_effective(self, user: dict[str, Any]) -> list[str]:
        """Permissões efetivas (chaves canônicas, ordenadas) de um usuário.

        `user` precisa de: id, role. Opcionais: tenant_id, custom_role_id
        (sem eles, custom_role/overrides são ignorados graciosamente).
        """
        role = str(user.get("role") or "")
        if role == "superadmin":
            # Superadmin é imune a deny — anti-lockout por construção
            return all_permission_keys()

        effective: set[str] = set(permissions_for_role(role))

        # Custom role (grant-only: só soma sobre a role base)
        for key in self._custom_role_grants(user):
            effective.add(key)

        # Overrides: allow soma, deny subtrai (deny vence allow de outras fontes)
        allows, denies = self._override_sets(user)
        effective |= allows
        effective -= denies

        return sorted(effective)

    def describe(self, user: dict[str, Any]) -> dict[str, Any]:
        """Detalhe completo para a UI de permissões por usuário (admin)."""
        role = str(user.get("role") or "")
        custom_role = self._custom_role_row(user)
        overrides = self._override_rows(user)
        return {
            "user_id": str(user.get("id")),
            "role": role,
            "custom_role": (
                {
                    "id": str(custom_role["id"]),
                    "name": custom_role["name"],
                    "permissions": self._parse_permissions(
                        custom_role.get("permissions")
                    ),
                }
                if custom_role
                else None
            ),
            "overrides": [
                {
                    "permission_key": o["permission_key"],
                    "allow": bool(o["allow"]),
                    "reason": o.get("reason"),
                    "granted_by": str(o["granted_by"]) if o.get("granted_by") else None,
                    "updated_at": (
                        o["updated_at"].isoformat()
                        if hasattr(o.get("updated_at"), "isoformat")
                        else o.get("updated_at")
                    ),
                }
                for o in overrides
            ],
            "role_permissions": permissions_for_role(role),
            "effective": self.resolve_effective(user),
        }

    # ── internals ─────────────────────────────────────────────────────────────

    def _custom_role_row(self, user: dict[str, Any]) -> dict[str, Any] | None:
        custom_role_id = user.get("custom_role_id")
        tenant_id = user.get("tenant_id")
        if not custom_role_id or not tenant_id:
            return None
        try:
            return self._custom_roles.get_by_id(str(custom_role_id), str(tenant_id))
        except Exception as exc:
            logger.warning("custom_role_lookup_failed: %s", exc)
            return None

    def _custom_role_grants(self, user: dict[str, Any]) -> set[str]:
        row = self._custom_role_row(user)
        if not row:
            return set()
        permissions = self._parse_permissions(row.get("permissions"))
        grants: set[str] = set()
        for key, enabled in permissions.items():
            canonical = normalize_key(str(key))
            if canonical and enabled:
                grants.add(canonical)
        return grants

    def _override_rows(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        user_id = user.get("id")
        if not user_id:
            return []
        try:
            return self._overrides.list_by_user(str(user_id))
        except Exception as exc:
            logger.warning("permission_overrides_lookup_failed: %s", exc)
            return []

    def _override_sets(self, user: dict[str, Any]) -> tuple[set[str], set[str]]:
        allows: set[str] = set()
        denies: set[str] = set()
        for row in self._override_rows(user):
            canonical = normalize_key(str(row.get("permission_key") or ""))
            if not canonical:
                continue
            if row.get("allow"):
                allows.add(canonical)
            else:
                denies.add(canonical)
        return allows, denies

    @staticmethod
    def _parse_permissions(raw: Any) -> dict[str, Any]:
        """permissions JSONB pode vir como dict ou string do psycopg2."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {}
            except (ValueError, TypeError):
                return {}
        return {}
