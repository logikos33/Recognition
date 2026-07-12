"""Repository: Model Deployments (migration 100)."""
import json
from typing import Any, Optional
from uuid import UUID

from app.constants import DeploymentStatus
from app.infrastructure.database.repositories.base import BaseRepository


class ModelDeploymentRepository(BaseRepository):
    """Queries SQL para tabela public.model_deployments. Tenant-scoped (C-01).

    Registry-level: histórico completo de deployments modelo↔câmera↔módulo
    com config de geometria (ADR-0032). Pin/canary rápido permanece em
    {schema}.models (ModelRolloutRepository) — semânticas separadas (ADR-0037).
    """

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Registra deployment (status default 'active')."""
        return self._execute_mutation(
            "INSERT INTO model_deployments "
            "(tenant_id, model_id, camera_id, module_code, config, status, deployed_by) "
            "VALUES (%s, %s, %s, COALESCE(%s, 'epi'), %s::jsonb, "
            "        COALESCE(%s, 'active'), %s) RETURNING *",
            (
                str(data["tenant_id"]),
                str(data["model_id"]),
                str(data["camera_id"]),
                data.get("module_code"),
                json.dumps(data.get("config", {})),
                str(data["status"]) if data.get("status") else None,
                str(data["deployed_by"]) if data.get("deployed_by") else None,
            ),
        )  # type: ignore[return-value]

    def get_by_id(self, deployment_id: UUID, tenant_id: str) -> Optional[dict[str, Any]]:
        """Busca deployment por ID validando posse do tenant."""
        return self._execute_one(
            "SELECT * FROM model_deployments WHERE id = %s AND tenant_id = %s",
            (str(deployment_id), str(tenant_id)),
        )

    def get_active_for_camera(
        self, tenant_id: str, camera_id: UUID, module_code: str = "epi"
    ) -> Optional[dict[str, Any]]:
        """Deployment ativo de uma câmera+módulo (inference resolver)."""
        return self._execute_one(
            "SELECT * FROM model_deployments "
            "WHERE tenant_id = %s AND camera_id = %s AND module_code = %s "
            "AND status = 'active' ORDER BY created_at DESC LIMIT 1",
            (str(tenant_id), str(camera_id), module_code),
        )

    def list_for_camera(
        self, tenant_id: str, camera_id: UUID, module_code: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Histórico de deployments de uma câmera (rollback usa o anterior)."""
        if module_code:
            return self._execute(
                "SELECT * FROM model_deployments "
                "WHERE tenant_id = %s AND camera_id = %s AND module_code = %s "
                "ORDER BY created_at DESC",
                (str(tenant_id), str(camera_id), module_code),
            )
        return self._execute(
            "SELECT * FROM model_deployments "
            "WHERE tenant_id = %s AND camera_id = %s ORDER BY created_at DESC",
            (str(tenant_id), str(camera_id)),
        )

    def list_by_model(self, model_id: UUID, tenant_id: str) -> list[dict[str, Any]]:
        """Todos os deployments de um modelo (linhagem — GET /api/v1/models/<id>)."""
        return self._execute(
            "SELECT * FROM model_deployments "
            "WHERE model_id = %s AND tenant_id = %s ORDER BY created_at DESC",
            (str(model_id), str(tenant_id)),
        )

    def deactivate(
        self,
        deployment_id: UUID,
        tenant_id: str,
        status: str = DeploymentStatus.INACTIVE,
    ) -> Optional[dict[str, Any]]:
        """Desativa um deployment (status inactive|rolled_back + deactivated_at)."""
        return self._execute_mutation(
            "UPDATE model_deployments SET status = %s, deactivated_at = NOW() "
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            (str(status), str(deployment_id), str(tenant_id)),
        )

    def deactivate_active_for_camera(
        self, tenant_id: str, camera_id: UUID, module_code: str = "epi"
    ) -> int:
        """Desativa deployments ativos da câmera+módulo (passo do upsert).

        Retorna rowcount — 0 se não havia deployment ativo.
        """
        return self._execute_mutation_no_return(
            "UPDATE model_deployments SET status = 'inactive', deactivated_at = NOW() "
            "WHERE tenant_id = %s AND camera_id = %s AND module_code = %s "
            "AND status = 'active'",
            (str(tenant_id), str(camera_id), module_code),
        )
