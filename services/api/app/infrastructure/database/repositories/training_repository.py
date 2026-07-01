"""Repository: Training Jobs + Trained Models."""
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class TrainingRepository(BaseRepository):
    """Queries SQL para training_jobs e trained_models."""

    # --- Training Jobs ---

    def create_job(
        self,
        user_id: UUID,
        preset: str = "balanced",
        model_size: str = "yolo26n",
        total_epochs: int = 100,
    ) -> dict[str, Any]:
        """Cria job de treinamento."""
        return self._execute_mutation(
            "INSERT INTO training_jobs (user_id, preset, model_size, total_epochs) "
            "VALUES (%s, %s, %s, %s) RETURNING *",
            (str(user_id), preset, model_size, total_epochs),
        )  # type: ignore[return-value]

    def get_job_by_id(self, job_id: UUID) -> Optional[dict[str, Any]]:
        """Busca job por ID."""
        return self._execute_one(
            "SELECT * FROM training_jobs WHERE id = %s",
            (str(job_id),),
        )

    def get_jobs_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista jobs do usuário."""
        return self._execute(
            "SELECT * FROM training_jobs WHERE user_id = %s "
            "ORDER BY created_at DESC",
            (str(user_id),),
        )

    def update_job_status(
        self,
        job_id: UUID,
        status: str,
        progress: Optional[int] = None,
        current_epoch: Optional[int] = None,
        metrics: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Atualiza status do job."""
        import json
        fields = ["status = %s"]
        values: list[Any] = [status]

        if progress is not None:
            fields.append("progress = %s")
            values.append(progress)
        if current_epoch is not None:
            fields.append("current_epoch = %s")
            values.append(current_epoch)
        if metrics is not None:
            fields.append("metrics = %s::jsonb")
            values.append(json.dumps(metrics))
        if error_message is not None:
            fields.append("error_message = %s")
            values.append(error_message)
        if status == "running":
            fields.append("started_at = NOW()")
        if status in ("completed", "failed", "stopped"):
            fields.append("completed_at = NOW()")

        values.append(str(job_id))
        return self._execute_mutation(
            f"UPDATE training_jobs SET {', '.join(fields)} "
            "WHERE id = %s RETURNING *",
            tuple(values),
        )

    # --- Trained Models ---

    def create_model(self, data: dict[str, Any]) -> dict[str, Any]:
        """Registra modelo treinado."""
        return self._execute_mutation(
            "INSERT INTO trained_models "
            "(user_id, job_id, name, model_path, map50, precision, recall) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (
                str(data["user_id"]),
                str(data["job_id"]) if data.get("job_id") else None,
                data["name"],
                data["model_path"],
                data.get("map50"),
                data.get("precision"),
                data.get("recall"),
            ),
        )  # type: ignore[return-value]

    def get_models_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista modelos do usuário."""
        return self._execute(
            "SELECT * FROM trained_models WHERE user_id = %s "
            "ORDER BY created_at DESC",
            (str(user_id),),
        )

    def get_model_for_tenant(
        self, model_id: UUID, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Busca modelo treinado validando que pertence ao tenant.

        trained_models não tem tenant_id (migration 003) — a posse é derivada
        via JOIN com users (dono do modelo deve ser do tenant).
        """
        return self._execute_one(
            """
            SELECT tm.id, tm.name, tm.model_path, tm.is_active, tm.created_at
            FROM trained_models tm
            JOIN users u ON u.id = tm.user_id
            WHERE tm.id = %s AND u.tenant_id = %s
            """,
            (str(model_id), str(tenant_id)),
        )

    def activate_model(self, model_id: UUID, user_id: UUID) -> Optional[dict[str, Any]]:
        """Ativa modelo (desativa outros do mesmo usuário)."""
        self._execute_mutation_no_return(
            "UPDATE trained_models SET is_active = FALSE WHERE user_id = %s",
            (str(user_id),),
        )
        return self._execute_mutation(
            "UPDATE trained_models SET is_active = TRUE "
            "WHERE id = %s RETURNING *",
            (str(model_id),),
        )

    def list_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        """Lista todos os modelos treinados do tenant (JOIN via users.tenant_id)."""
        return self._execute(
            """
            SELECT tm.id, tm.name, tm.model_path, tm.is_active, tm.created_at
            FROM trained_models tm
            JOIN users u ON u.id = tm.user_id
            WHERE u.tenant_id = %s
            ORDER BY tm.created_at DESC
            """,
            (str(tenant_id),),
        )

    def get_active_for_tenant(self, tenant_id: str) -> Optional[dict[str, Any]]:
        """Retorna o modelo marcado is_active=TRUE do tenant (herança)."""
        return self._execute_one(
            """
            SELECT tm.id, tm.name, tm.model_path, tm.is_active, tm.created_at
            FROM trained_models tm
            JOIN users u ON u.id = tm.user_id
            WHERE u.tenant_id = %s AND tm.is_active = TRUE
            ORDER BY tm.created_at DESC
            LIMIT 1
            """,
            (str(tenant_id),),
        )

    def update_scenario_config(
        self, model_id: UUID, tenant_id: str, config: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Salva configuração de cenário em trained_models.scenario_config.

        Valida posse via JOIN com users (trained_models não tem tenant_id direto).
        Retorna o model atualizado ou None se não encontrado/não autorizado.
        """
        import json

        # Verificar que o modelo pertence ao tenant antes de atualizar
        row = self._execute_one(
            """
            SELECT tm.id
            FROM trained_models tm
            JOIN users u ON u.id = tm.user_id
            WHERE tm.id = %s AND u.tenant_id = %s
            """,
            (str(model_id), str(tenant_id)),
        )
        if not row:
            return None

        return self._execute_mutation(
            """
            UPDATE trained_models
            SET scenario_config = %s::jsonb
            WHERE id = %s
            RETURNING id, name, model_path, is_active, created_at, scenario_config
            """,
            (json.dumps(config), str(model_id)),
        )

    def get_scenario_config(
        self, model_id: UUID, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Busca configuração de cenário de um modelo, validando tenant."""
        return self._execute_one(
            """
            SELECT tm.id, tm.name, tm.scenario_config
            FROM trained_models tm
            JOIN users u ON u.id = tm.user_id
            WHERE tm.id = %s AND u.tenant_id = %s
            """,
            (str(model_id), str(tenant_id)),
        )
        )
