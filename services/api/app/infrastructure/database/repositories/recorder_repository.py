"""Repository: Recorders (NVR/DVR — migration 099)."""
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository

# Colunas atualizáveis via update() — allowlist interna (nunca input direto).
_UPDATABLE_FIELDS = (
    "name",
    "host",
    "port",
    "username",
    "password_encrypted",
    "protocol",
    "manufacturer",
    "channels",
    "retention_days",
)


class RecorderRepository(BaseRepository):
    """Queries SQL para tabela public.recorders. Todas tenant-scoped (C-01)."""

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria recorder. password_encrypted já vem cifrado (Fernet) do service."""
        return self._execute_mutation(
            "INSERT INTO recorders "
            "(tenant_id, name, host, port, username, password_encrypted, "
            " protocol, manufacturer, channels, retention_days, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, 'onvif'), %s, "
            "        COALESCE(%s, 0), %s, %s) RETURNING *",
            (
                str(data["tenant_id"]),
                data["name"],
                data["host"],
                data.get("port", 80),
                data.get("username"),
                data.get("password_encrypted"),
                data.get("protocol"),
                data.get("manufacturer"),
                data.get("channels"),
                data.get("retention_days"),
                str(data["created_by"]) if data.get("created_by") else None,
            ),
        )  # type: ignore[return-value]

    def get_by_id(self, recorder_id: UUID, tenant_id: str) -> Optional[dict[str, Any]]:
        """Busca recorder por ID validando posse do tenant."""
        return self._execute_one(
            "SELECT * FROM recorders WHERE id = %s AND tenant_id = %s",
            (str(recorder_id), str(tenant_id)),
        )

    def list_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        """Lista recorders do tenant."""
        return self._execute(
            "SELECT * FROM recorders WHERE tenant_id = %s ORDER BY created_at DESC",
            (str(tenant_id),),
        )

    def update(
        self, recorder_id: UUID, tenant_id: str, data: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Atualiza campos permitidos do recorder (allowlist interna)."""
        fields: list[str] = []
        values: list[Any] = []
        for column in _UPDATABLE_FIELDS:
            if column in data:
                fields.append(f"{column} = %s")
                values.append(data[column])
        if not fields:
            return self.get_by_id(recorder_id, tenant_id)

        values.extend([str(recorder_id), str(tenant_id)])
        return self._execute_mutation(
            f"UPDATE recorders SET {', '.join(fields)} "  # noqa: S608
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            tuple(values),
        )

    def update_status(
        self,
        recorder_id: UUID,
        tenant_id: str,
        status: str,
        last_error: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Atualiza status de conectividade + last_tested_at (teste de conexão)."""
        return self._execute_mutation(
            "UPDATE recorders SET status = %s, last_tested_at = NOW(), last_error = %s "
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            (str(status), last_error, str(recorder_id), str(tenant_id)),
        )

    def delete(self, recorder_id: UUID, tenant_id: str) -> int:
        """Remove recorder do tenant. Retorna rowcount (0 = não encontrado)."""
        return self._execute_mutation_no_return(
            "DELETE FROM recorders WHERE id = %s AND tenant_id = %s",
            (str(recorder_id), str(tenant_id)),
        )
