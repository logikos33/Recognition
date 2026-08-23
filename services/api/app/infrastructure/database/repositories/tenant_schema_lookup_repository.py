"""
Recognition — TenantSchemaLookupRepository.

Resolve o `tenant_schema` (= room do SocketIO, ver app/core/socket_auth.py) a
partir dos identificadores que chegam nos canais Redis do bridge
(app/core/socket_bridge.py): câmera, operação, job de treino e tenant_id.

Só leitura, só `public.*`. Toda query SQL aqui, nunca no bridge.
"""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class TenantSchemaLookupRepository(BaseRepository):
    """Lookups id → schema_name para roteamento por tenant."""

    def schema_for_camera(self, camera_id: str) -> str | None:
        row = self._execute_one(
            """
            SELECT t.schema_name
            FROM public.cameras c
            JOIN public.tenants t ON t.id = c.tenant_id
            WHERE c.id = %s
            """,
            (camera_id,),
        )
        return _schema(row)

    def schema_for_operation(self, operation_id: int) -> str | None:
        row = self._execute_one(
            """
            SELECT t.schema_name
            FROM public.operations o
            JOIN public.tenants t ON t.id = o.tenant_id
            WHERE o.id = %s
            """,
            (operation_id,),
        )
        return _schema(row)

    def schema_for_training_job(self, job_id: str) -> str | None:
        row = self._execute_one(
            """
            SELECT t.schema_name
            FROM public.training_jobs j
            JOIN public.tenants t ON t.id = j.tenant_id
            WHERE j.id = %s
            """,
            (job_id,),
        )
        return _schema(row)

    def schema_for_tenant(self, tenant_id: str) -> str | None:
        row = self._execute_one(
            "SELECT schema_name FROM public.tenants WHERE id = %s",
            (tenant_id,),
        )
        return _schema(row)


def _schema(row: dict[str, Any] | None) -> str | None:
    return str(row["schema_name"]) if row and row.get("schema_name") else None
