"""Repository: Modules and Module Classes."""

from app.infrastructure.database.repositories.base import BaseRepository


class ModuleRepository(BaseRepository):
    """Queries SQL para tabelas tenant_modules e module_classes."""

    def get_by_tenant(self, tenant_id: str) -> list:
        """Lista módulos habilitados do tenant."""
        return self._execute(
            "SELECT * FROM tenant_modules WHERE tenant_id = %s ORDER BY activated_at",
            (tenant_id,),
        )

    def get_tenant_module(self, tenant_id: str, module_code: str) -> dict | None:
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

    def upsert_tenant_module(self, tenant_id: str, module_code: str) -> dict | None:
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

    def toggle_class_active(
        self, module_code: str, class_id: str, is_active: bool
    ) -> "dict | None":
        """Ativa ou desativa uma classe do módulo.

        WHERE inclui module_code (não só id) — task-073/achado #6: impede que
        um class_id de OUTRO module_code seja alterado através desta rota
        (module_classes é catálogo global sem tenant_id; o isolamento real
        acontece via tenant_has_module() no service + este filtro por
        module_code). Retorna None se a classe não existe ou pertence a
        outro módulo, permitindo 404 uniforme sem vazar existência.
        """
        return self._execute_mutation(
            "UPDATE module_classes SET is_active = %s "
            "WHERE id = %s AND module_code = %s RETURNING *",
            (is_active, class_id, module_code),
        )
