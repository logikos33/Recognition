"""Repository: IP Cameras."""
import json
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class CameraRepository(BaseRepository):
    """Queries SQL para tabela cameras."""

    _SELECT_COLS = (
        "id, tenant_id, name, location, description, manufacturer, "
        "host, port, username, channel, subtype, rtsp_url_override, "
        "is_active, last_seen, last_error, last_tested_at, updated_at, created_at"
    )

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria câmera."""
        return self._execute_mutation(
            "INSERT INTO cameras "
            "(tenant_id, name, location, description, manufacturer, "
            "host, port, username, password_encrypted, channel, subtype) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            f"RETURNING {self._SELECT_COLS}",
            (
                str(data["tenant_id"]),
                data["name"],
                data.get("location"),
                data.get("description"),
                data.get("manufacturer", "generic"),
                data["host"],
                data.get("port", 554),
                data.get("username", "admin"),
                data.get("password_encrypted"),
                data.get("channel", 1),
                data.get("subtype", 0),
            ),
        )  # type: ignore[return-value]

    def get_by_id(self, camera_id: UUID) -> Optional[dict[str, Any]]:
        """Busca câmera por ID (inclui password_encrypted para stream)."""
        return self._execute_one(
            "SELECT *, password_encrypted FROM cameras WHERE id = %s",
            (str(camera_id),),
        )

    def get_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista câmeras do tenant (sem password)."""
        return self._execute(
            f"SELECT {self._SELECT_COLS} FROM cameras "
            "WHERE tenant_id = %s ORDER BY created_at DESC",
            (str(user_id),),
        )

    def get_all(self) -> list[dict[str, Any]]:
        """Lista todas as câmeras (admin). Sem password."""
        return self._execute(
            f"SELECT {self._SELECT_COLS} FROM cameras "
            "ORDER BY created_at DESC",
        )

    def update(
        self, camera_id: UUID, data: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Atualiza câmera."""
        fields = []
        values: list[Any] = []
        for key in ("name", "location", "description", "manufacturer",
                     "host", "port", "username", "password_encrypted",
                     "channel", "subtype", "rtsp_url_override", "is_active"):
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key])

        if not fields:
            return self.get_by_id(camera_id)

        values.append(str(camera_id))
        return self._execute_mutation(
            f"UPDATE cameras SET {', '.join(fields)} "
            f"WHERE id = %s RETURNING {self._SELECT_COLS}",
            tuple(values),
        )

    def update_last_tested(self, camera_id: UUID, error: Optional[str]) -> None:
        """Registra resultado do último teste de conectividade."""
        self._execute_mutation_no_return(
            "UPDATE cameras SET last_tested_at = NOW(), last_error = %s WHERE id = %s",
            (error, str(camera_id)),
        )

    def delete(self, camera_id: UUID) -> int:
        """Deleta câmera."""
        return self._execute_mutation_no_return(
            "DELETE FROM cameras WHERE id = %s",
            (str(camera_id),),
        )

    def count_by_module(self, tenant_id: str, module_code: str) -> int:
        """Conta câmeras de um tenant por módulo."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM cameras WHERE tenant_id = %s AND module_code = %s",
            (tenant_id, module_code),
        )
        return row["count"] if row else 0

    def count_by_status(self, tenant_id: str, module_code: str, status: str) -> int:
        """Conta câmeras de um tenant/módulo por status (is_active)."""
        is_active = status == "active"
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM cameras WHERE tenant_id = %s AND module_code = %s AND is_active = %s",
            (tenant_id, module_code, is_active),
        )
        return row["count"] if row else 0

    def count_active_all(self, tenant_id: str) -> int:
        """Conta todas as câmeras ativas do tenant (todos os módulos)."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM cameras WHERE tenant_id = %s AND is_active = true",
            (tenant_id,),
        )
        return row["count"] if row else 0

    def count_all(self, tenant_id: str) -> int:
        """Conta todas as câmeras do tenant."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM cameras WHERE tenant_id = %s",
            (tenant_id,),
        )
        return row["count"] if row else 0

    def update_module(self, camera_id: str, module: str) -> None:
        """Atualiza o módulo ativo da câmera."""
        self._execute_mutation_no_return(
            "UPDATE cameras SET active_module = %s WHERE id = %s",
            (module, str(camera_id)),
        )

    def update_schedule(self, camera_id: str, rules: list) -> None:
        """Atualiza as regras de agendamento JSONB da câmera."""
        self._execute_mutation_no_return(
            "UPDATE cameras SET schedule_rules = %s::jsonb WHERE id = %s",
            (json.dumps(rules), str(camera_id)),
        )

    # --- Atribuição de modelo por câmera (Task 045 — migration 026) ---

    # Colunas de modelo por módulo. Whitelist — NUNCA interpolar input do
    # usuário direto no SQL (mapeamento fixo módulo → coluna).
    MODEL_COLUMNS: dict[str, str] = {
        "epi": "model_epi_id",
        "quality": "model_quality_id",
        "counting": "model_counting_id",
    }

    def get_model_assignments(
        self, camera_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Retorna model_epi_id/model_quality_id/model_counting_id da câmera (filtra tenant)."""
        return self._execute_one(
            "SELECT id, model_epi_id, model_quality_id, model_counting_id "
            "FROM cameras WHERE id = %s AND tenant_id = %s",
            (str(camera_id), str(tenant_id)),
        )

    def set_model_assignment(
        self,
        camera_id: str,
        tenant_id: str,
        module: str,
        model_id: Optional[str],
    ) -> Optional[dict[str, Any]]:
        """Atribui (ou remove, com model_id=None) o modelo de um módulo da câmera.

        Coluna resolvida via whitelist MODEL_COLUMNS — module inválido raises KeyError.
        """
        column = self.MODEL_COLUMNS[module]
        return self._execute_mutation(
            f"UPDATE cameras SET {column} = %s "  # noqa: S608 — coluna de whitelist fixa
            "WHERE id = %s AND tenant_id = %s "
            "RETURNING id, model_epi_id, model_quality_id, model_counting_id",
            (str(model_id) if model_id else None, str(camera_id), str(tenant_id)),
        )
