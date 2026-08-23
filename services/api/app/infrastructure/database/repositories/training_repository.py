"""Repository: Training Jobs + Trained Models."""
import json
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
        *,
        dataset_version_id: UUID | str | None = None,
        framework: str | None = None,
        base_model: str | None = None,
        hyperparams: dict[str, Any] | None = None,
        gpu_provider: str | None = None,
        callback_token: str | None = None,
        tenant_id: UUID | str | None = None,
    ) -> dict[str, Any]:
        """Cria job de treinamento.

        Campos do pipeline MLOps (migration 097) são keyword-only opcionais —
        callers legados (user_id, preset, model_size, total_epochs) continuam
        funcionando; colunas omitidas usam os defaults do schema
        (framework='rfdetr', hyperparams='{}').

        tenant_id SEMPRE é gravado: explícito ou derivado de users.tenant_id
        (job com tenant NULL é invisível ao auto-retraining, que filtra
        WHERE tenant_id = %s — mesmo padrão COALESCE do create_model).
        """
        columns = ["user_id", "preset", "model_size", "total_epochs"]
        placeholders = ["%s", "%s", "%s", "%s"]
        values: list[Any] = [str(user_id), preset, model_size, total_epochs]

        optional: list[tuple[str, str, Any]] = [
            ("dataset_version_id", "%s",
             str(dataset_version_id) if dataset_version_id else None),
            ("framework", "%s", framework),
            ("base_model", "%s", base_model),
            ("hyperparams", "%s::jsonb",
             json.dumps(hyperparams) if hyperparams is not None else None),
            ("gpu_provider", "%s", str(gpu_provider) if gpu_provider else None),
            ("callback_token", "%s", callback_token),
        ]
        for column, placeholder, value in optional:
            if value is not None:
                columns.append(column)
                placeholders.append(placeholder)
                values.append(value)

        columns.append("tenant_id")
        placeholders.append(
            "COALESCE(%s::uuid, (SELECT tenant_id FROM users WHERE id = %s::uuid))"
        )
        values.extend([str(tenant_id) if tenant_id else None, str(user_id)])

        return self._execute_mutation(
            f"INSERT INTO training_jobs ({', '.join(columns)}) "  # noqa: S608
            f"VALUES ({', '.join(placeholders)}) RETURNING *",
            tuple(values),
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
        fields = ["status = %s"]
        values: list[Any] = [status]

        if progress is not None:
            fields.append("progress = %s")
            values.append(progress)
        if current_epoch is not None:
            fields.append("current_epoch = %s")
            values.append(current_epoch)
        if metrics is not None:
            # FUNDE, nao substitui. `metrics = %s` era o 5o "dois escritores": o
            # callback de progresso do pod e o worker gravam em chaves de topo
            # diferentes (`stage` vs `provenance`/`gpu_cost`) e quem escrevia por
            # ultimo apagava o outro — a proveniencia do job sumia sem erro nenhum.
            #
            # A fusao e do BANCO, atomica, dentro do mesmo UPDATE: fazer
            # SELECT -> merge em Python -> UPDATE reabriria a corrida entre os
            # dois escritores, so que maior.
            #
            # `||` e merge RASO: chaves de topo distintas convivem (resolve o
            # caso real). Se um dia dois escritores disputarem o MESMO objeto
            # aninhado, o objeto inteiro e substituido — ai e jsonb_set por chave.
            fields.append("metrics = COALESCE(metrics, '{}'::jsonb) || %s::jsonb")
            values.append(json.dumps(metrics))
        if error_message is not None:
            fields.append("error_message = %s")
            values.append(error_message)
        if status == "running":
            # COALESCE, não NOW() seco: o dispatch já carimba started_at antes
            # de provisionar o pod (tasks/training.py, `WHEN started_at IS NULL`).
            # Sobrescrever aqui, no primeiro callback do pod, jogava fora
            # provisionamento + download + boa parte do treino — o job
            # f31f5381 mediu 0,8 min contra os 6,4 min reais do pod.log,
            # errado por 8× (issue #419). Primeira escrita vence.
            fields.append("started_at = COALESCE(started_at, NOW())")
        if status in ("completed", "failed", "stopped"):
            fields.append("completed_at = NOW()")

        values.append(str(job_id))
        return self._execute_mutation(
            f"UPDATE training_jobs SET {', '.join(fields)} "
            "WHERE id = %s RETURNING *",
            tuple(values),
        )

    # --- Trained Models ---

    def get_model_by_job_id(self, job_id: UUID) -> Optional[dict[str, Any]]:
        """Busca modelo já registrado para um job (guarda anti-duplicação).

        trained_models.job_id NÃO tem UNIQUE — o fluxo de registro DEVE
        chamar este método antes de create_model (ajuste vinculante #2,
        evita dupla inserção Celery × bridge). Retorna o mais recente.
        """
        return self._execute_one(
            "SELECT * FROM trained_models WHERE job_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (str(job_id),),
        )

    def create_model(self, data: dict[str, Any]) -> dict[str, Any]:
        """Registra modelo treinado.

        created_by default = user_id; origin default = 'unknown';
        tenant_id derivado via users.tenant_id (migration 090).
        Campos do registry MLOps (migration 098 — framework, r2_onnx_key,
        r2_weights_key, metrics, dataset_version_id, module_code) são
        opcionais: incluídos no INSERT apenas quando presentes em data
        (colunas omitidas usam defaults do schema — retrocompat).
        """
        columns = [
            "user_id", "job_id", "name", "model_path", "map50",
            "precision", "recall", "created_by", "origin", "tenant_id",
        ]
        placeholders = [
            "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s",
            "COALESCE(%s, (SELECT tenant_id FROM users WHERE id = %s))",
        ]
        values: list[Any] = [
            str(data["user_id"]),
            str(data["job_id"]) if data.get("job_id") else None,
            data["name"],
            data["model_path"],
            data.get("map50"),
            data.get("precision"),
            data.get("recall"),
            str(data.get("created_by") or data["user_id"]),
            data.get("origin") or "unknown",
            str(data["tenant_id"]) if data.get("tenant_id") else None,
            str(data["user_id"]),
        ]

        optional: list[tuple[str, str, Any]] = [
            ("framework", "%s", data.get("framework")),
            ("r2_onnx_key", "%s", data.get("r2_onnx_key")),
            ("r2_weights_key", "%s", data.get("r2_weights_key")),
            ("metrics", "%s::jsonb",
             json.dumps(data["metrics"]) if data.get("metrics") is not None else None),
            ("dataset_version_id", "%s",
             str(data["dataset_version_id"]) if data.get("dataset_version_id") else None),
            ("module_code", "%s", data.get("module_code")),
        ]
        for column, placeholder, value in optional:
            if value is not None:
                columns.append(column)
                placeholders.append(placeholder)
                values.append(value)

        return self._execute_mutation(
            f"INSERT INTO trained_models ({', '.join(columns)}) "  # noqa: S608
            f"VALUES ({', '.join(placeholders)}) RETURNING *",
            tuple(values),
        )  # type: ignore[return-value]

    def get_models_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista modelos do usuário, com dono (owner_name/owner_email).

        SELECT explícito (todas as colunas da 003 + 052 + 090 + 098) — o JOIN
        com users deriva o nome/email do dono via created_by (fallback
        user_id). `framework` (migration 098 — "yolox"/"rfdetr") incluído
        para a UI mostrar o backend de detecção efetivo por modelo/câmera
        (task-083) — antes o payload não carregava essa informação e a tela
        de atribuição de modelo não tinha como exibi-la. `metrics` (JSONB,
        098) incluído pela task "treino honesto" (C2) — carrega o marcador
        {'simulated': true} pra artefatos simulados, além de `origin`.
        """
        return self._execute(
            """
            SELECT tm.id, tm.user_id, tm.job_id, tm.name, tm.model_path,
                   tm.map50, tm.precision, tm.recall, tm.is_active,
                   tm.created_at, tm.scenario_config,
                   tm.created_by, tm.origin, tm.tenant_id, tm.framework,
                   tm.metrics,
                   COALESCE(NULLIF(u.name, ''), u.email) AS owner_name,
                   u.email AS owner_email
            FROM trained_models tm
            LEFT JOIN users u ON u.id = COALESCE(tm.created_by, tm.user_id)
            WHERE tm.user_id = %s
            ORDER BY tm.created_at DESC
            """,
            (str(user_id),),
        )

    def get_model_for_tenant(
        self, model_id: UUID, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Busca modelo treinado validando que pertence ao tenant.

        trained_models TEM tenant_id desde a migration 090, mas linhas legadas
        podem estar com tenant_id NULL — a posse é validada via JOIN com users
        (dono do modelo deve ser do tenant), que cobre legado e novo.

        module_code (migration 098, NOT NULL DEFAULT 'epi') é incluído para
        permitir aos callers validar que o modelo pertence ao módulo alvo
        antes de atribuí-lo a uma câmera (Task 045 — fix de segurança/gaps).
        """
        return self._execute_one(
            """
            SELECT tm.id, tm.name, tm.model_path, tm.is_active, tm.created_at,
                   tm.module_code
            FROM trained_models tm
            JOIN users u ON u.id = tm.user_id
            WHERE tm.id = %s AND u.tenant_id = %s
            """,
            (str(model_id), str(tenant_id)),
        )

    def get_current_running_job(self, user_id: UUID) -> Optional[dict[str, Any]]:
        """Busca o job mais recente em execução (pending ou running) do usuário."""
        return self._execute_one(
            "SELECT * FROM training_jobs "
            "WHERE user_id = %s AND status IN ('pending', 'running') "
            "ORDER BY created_at DESC LIMIT 1",
            (str(user_id),),
        )

    def get_latest_job(self, user_id: UUID) -> Optional[dict[str, Any]]:
        """Busca o job mais recente do usuário (qualquer status)."""
        return self._execute_one(
            "SELECT * FROM training_jobs WHERE user_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (str(user_id),),
        )

    def stop_job(self, job_id: UUID, user_id: UUID) -> Optional[dict[str, Any]]:
        """Marca job como stopped (somente se pertencer ao usuário e estiver ativo)."""
        return self._execute_mutation(
            "UPDATE training_jobs SET status = 'stopped', completed_at = NOW() "
            "WHERE id = %s AND user_id = %s AND status IN ('pending', 'running') "
            "RETURNING *",
            (str(job_id), str(user_id)),
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

    def model_name_exists_for_tenant(self, tenant_id: str, name: str) -> bool:
        """True se existe um trained_models.name igual ao dado, do tenant.

        Task "treino não pode mentir" (dashboard/training-metrics guard):
        antes de aceitar um ingest de curva de treino, confirma que
        `model_name` corresponde a um modelo REAL do tenant — senão qualquer
        usuário autenticado fabricava métricas para um `model_name` inventado.
        Mesmo padrão JOIN via users usado em `get_model_for_tenant`/
        `list_for_tenant` (cobre linhas legadas com tenant_id NULL).
        """
        row = self._execute_one(
            """
            SELECT 1
            FROM trained_models tm
            JOIN users u ON u.id = tm.user_id
            WHERE u.tenant_id = %s AND tm.name = %s
            LIMIT 1
            """,
            (str(tenant_id), name),
        )
        return row is not None

    def get_active_for_tenant(self, tenant_id: str) -> Optional[dict[str, Any]]:
        """Retorna o modelo marcado is_active=TRUE do tenant (herança).

        trained_models TEM tenant_id desde a migration 090; o JOIN com users
        permanece para cobrir linhas legadas com tenant_id NULL. map50
        incluído para os KPIs do dashboard (WS3, aditivo).
        """
        return self._execute_one(
            """
            SELECT tm.id, tm.name, tm.model_path, tm.is_active, tm.map50, tm.created_at
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

        Valida posse via JOIN com users (cobre linhas legadas com tenant_id
        NULL — a coluna existe desde a 090). Retorna o model atualizado ou
        None se não encontrado/não autorizado.
        """
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
