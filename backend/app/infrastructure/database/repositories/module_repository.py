"""Repository: Modules and Module Classes."""
from typing import Optional

from app.infrastructure.database.repositories.base import BaseRepository


class ModuleRepository(BaseRepository):
    """Queries SQL para tabelas tenant_modules e module_classes."""

    def get_by_tenant(self, tenant_id: str) -> list:
        """Lista módulos habilitados do tenant."""
        return self._execute(
            "SELECT * FROM tenant_modules WHERE tenant_id = %s ORDER BY activated_at",
            (tenant_id,),
        )

    def get_tenant_module(self, tenant_id: str, module_code: str) -> Optional[dict]:
        """Retorna módulo específico do tenant."""
        return self._execute_one(
            "SELECT * FROM tenant_modules WHERE tenant_id = %s AND module_code = %s",
            (tenant_id, module_code),
        )

    def get_classes(self, module_code: str) -> list:
        """Lista classes YOLO do módulo ordenadas por class_id."""
        return self._execute(
            "SELECT * FROM module_classes WHERE module_code = %s ORDER BY class_id",
            (module_code,),
        )

    def upsert_tenant_module(self, tenant_id: str, module_code: str) -> Optional[dict]:
        """Ativa módulo para tenant (cria ou reativa)."""
        return self._execute_mutation(
            """
            INSERT INTO tenant_modules (tenant_id, module_code, enabled)
            VALUES (%s, %s, true)
            ON CONFLICT (tenant_id, module_code) DO UPDATE SET enabled = true
            RETURNING *
            """,
            (tenant_id, module_code),
        )
