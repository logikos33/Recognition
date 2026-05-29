"""
Recognition — OperationRepository.

Acesso a dados de operações configuráveis e seus resultados.
Segue padrão BaseRepository: toda query SQL aqui, nunca fora.
Multi-tenant: todas queries filtram por tenant_id.
"""
import json
import logging
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class OperationRepository(BaseRepository):
    """Repository para operações e seus resultados."""

    def list_by_camera(self, tenant_id: str, camera_id: str) -> list[dict[str, Any]]:
        """Lista operações de uma câmera para o tenant informado."""
        return self._execute(
            """
            SELECT id, tenant_id, camera_id, module_id, type_id, name,
                   config, status, version, last_value_json, last_evaluated_at, created_at
            FROM operations
            WHERE tenant_id = %s AND camera_id = %s
            ORDER BY id ASC
            """,
            (tenant_id, camera_id),
        )

    def list_by_camera_and_module(
        self, tenant_id: str, camera_id: str, module_id: str
    ) -> list[dict[str, Any]]:
        """Lista operações filtrando por câmera e módulo."""
        return self._execute(
            """
            SELECT id, tenant_id, camera_id, module_id, type_id, name,
                   config, status, version, last_value_json, last_evaluated_at, created_at
            FROM operations
            WHERE tenant_id = %s AND camera_id = %s AND module_id = %s
            ORDER BY id ASC
            """,
            (tenant_id, camera_id, module_id),
        )

    def get_by_id(self, tenant_id: str, operation_id: int) -> dict[str, Any] | None:
        """Busca operação por ID garantindo isolamento multi-tenant."""
        return self._execute_one(
            """
            SELECT id, tenant_id, camera_id, module_id, type_id, name,
                   config, status, version, last_value_json, last_evaluated_at, created_at
            FROM operations
            WHERE tenant_id = %s AND id = %s
            """,
            (tenant_id, operation_id),
        )

    def create(
        self,
        tenant_id: str,
        camera_id: str,
        module_id: str,
        type_id: str,
        name: str,
        config: dict,
    ) -> dict[str, Any] | None:
        """Cria nova operação. Retorna row criada."""
        return self._execute_mutation(
            """
            INSERT INTO operations (tenant_id, camera_id, module_id, type_id, name, config)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, tenant_id, camera_id, module_id, type_id, name,
                      config, status, version, last_value_json, last_evaluated_at, created_at
            """,
            (tenant_id, camera_id, module_id, type_id, name, json.dumps(config)),
        )

    def update(
        self,
        tenant_id: str,
        operation_id: int,
        name: str,
        config: dict,
    ) -> dict[str, Any] | None:
        """Atualiza nome e config, incrementa version. Retorna row atualizada."""
        return self._execute_mutation(
            """
            UPDATE operations
            SET name = %s,
                config = %s::jsonb,
                version = version + 1
            WHERE tenant_id = %s AND id = %s
            RETURNING id, tenant_id, camera_id, module_id, type_id, name,
                      config, status, version, last_value_json, last_evaluated_at, created_at
            """,
            (name, json.dumps(config), tenant_id, operation_id),
        )

    def delete(self, tenant_id: str, operation_id: int) -> int:
        """Remove operação. Cascata remove operation_results. Retorna rowcount."""
        return self._execute_mutation_no_return(
            "DELETE FROM operations WHERE tenant_id = %s AND id = %s",
            (tenant_id, operation_id),
        )

    def count_results(self, operation_id: int) -> int:
        """Conta resultados históricos de uma operação."""
        row = self._execute_one(
            "SELECT COUNT(*) AS cnt FROM operation_results WHERE operation_id = %s",
            (operation_id,),
        )
        return int(row["cnt"]) if row else 0

    def list_results(
        self,
        operation_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retorna últimos N resultados de uma operação."""
        return self._execute(
            """
            SELECT id, operation_id, result_json, evaluated_at
            FROM operation_results
            WHERE operation_id = %s
            ORDER BY evaluated_at DESC
            LIMIT %s
            """,
            (operation_id, limit),
        )

    def update_live_value(
        self,
        operation_id: int,
        last_value_json: dict,
        status: str = "active",
    ) -> None:
        """Atualiza último valor calculado e timestamp. Chamado pelo worker."""
        self._execute_mutation_no_return(
            """
            UPDATE operations
            SET last_value_json = %s::jsonb,
                last_evaluated_at = NOW(),
                status = %s
            WHERE id = %s
            """,
            (json.dumps(last_value_json), status, operation_id),
        )

    def insert_result(self, operation_id: int, result_json: dict) -> None:
        """Insere resultado no histórico."""
        self._execute_mutation_no_return(
            """
            INSERT INTO operation_results (operation_id, result_json)
            VALUES (%s, %s::jsonb)
            """,
            (operation_id, json.dumps(result_json)),
        )
