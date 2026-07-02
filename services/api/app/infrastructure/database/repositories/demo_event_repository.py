"""Repository: Demo Events (eventos mock de demonstração — tabela apartada demo_events).

Tabela APARTADA de alerts de propósito: seed/remoção de demo NUNCA toca alertas reais.
Toda query filtra por tenant_id (C-01).
"""
from typing import Any, Optional

from app.infrastructure.database.repositories.base import BaseRepository


class DemoEventRepository(BaseRepository):
    """Queries SQL para a tabela demo_events."""

    def create_batch(self, tenant_id: str, rows: list[dict[str, Any]]) -> int:
        """Insere um lote de eventos demo. Retorna a quantidade inserida.

        Cada row: camera_id, camera_label, module_code, violations (JSON string),
        confidence, batch_id, created_by, created_at.
        """
        if not rows:
            return 0
        params_list = [
            (
                tenant_id,
                row.get("camera_id"),
                row["camera_label"],
                row["module_code"],
                row["violations"],
                row["confidence"],
                row["batch_id"],
                row.get("created_by"),
                row["created_at"],
            )
            for row in rows
        ]
        return self._execute_many(
            "INSERT INTO demo_events "
            "(tenant_id, camera_id, camera_label, module_code, violations, "
            " confidence, batch_id, created_by, created_at) "
            "VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)",
            params_list,
        )

    def counts_by_module(self, tenant_id: str) -> list[dict[str, Any]]:
        """Contagem de eventos demo por módulo do tenant + último seed."""
        return self._execute(
            "SELECT module_code, COUNT(*) AS count, MAX(seeded_at) AS last_seeded_at "
            "FROM demo_events WHERE tenant_id = %s "
            "GROUP BY module_code ORDER BY module_code",
            (tenant_id,),
        )

    def delete_by_tenant(self, tenant_id: str, module_code: Optional[str] = None) -> int:
        """Remove eventos demo do tenant (opcionalmente por módulo).

        DELETE físico é intencional e seguro: tabela apartada — alerts jamais é tocada.
        """
        if module_code:
            return self._execute_mutation_no_return(
                "DELETE FROM demo_events WHERE tenant_id = %s AND module_code = %s",
                (tenant_id, module_code),
            )
        return self._execute_mutation_no_return(
            "DELETE FROM demo_events WHERE tenant_id = %s",
            (tenant_id,),
        )

    def tenant_exists(self, tenant_id: str) -> bool:
        """Verifica se o tenant existe (validação do seed superadmin)."""
        row = self._execute_one(
            "SELECT id FROM tenants WHERE id = %s",
            (tenant_id,),
        )
        return row is not None

    def first_camera_of_tenant(self, tenant_id: str) -> Optional[dict[str, Any]]:
        """Retorna a primeira câmera do tenant (para associar aos eventos demo) ou None."""
        return self._execute_one(
            "SELECT id, name FROM cameras WHERE tenant_id = %s ORDER BY created_at LIMIT 1",
            (tenant_id,),
        )
