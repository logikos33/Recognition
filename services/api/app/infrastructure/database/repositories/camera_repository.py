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
        "is_active, last_seen, last_error, last_tested_at, updated_at, created_at, "
        "fps_target, quality_preset, "
        "retention_days, detection_stream_url, video_codec, max_auth_failures"
    )

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria câmera."""
        return self._execute_mutation(
            "INSERT INTO public.cameras "
            "(tenant_id, user_id, name, location, description, manufacturer, "
            "host, port, username, password_encrypted, channel, subtype, "
            "detection_stream_url, video_codec, max_auth_failures) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            f"RETURNING {self._SELECT_COLS}",
            (
                str(data["tenant_id"]),
                str(data["user_id"]),
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
                data.get("detection_stream_url"),
                data.get("video_codec"),
                data.get("max_auth_failures", 5),
            ),
        )  # type: ignore[return-value]

    def get_by_id(self, camera_id: UUID) -> Optional[dict[str, Any]]:
        """Busca câmera por ID (inclui password_encrypted para stream)."""
        return self._execute_one(
            "SELECT *, password_encrypted FROM public.cameras WHERE id = %s",
            (str(camera_id),),
        )

    def get_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista câmeras do tenant (sem password)."""
        return self._execute(
            f"SELECT {self._SELECT_COLS} FROM public.cameras "
            "WHERE tenant_id = %s ORDER BY created_at DESC",
            (str(user_id),),
        )

    def get_all(self) -> list[dict[str, Any]]:
        """Lista todas as câmeras (admin). Sem password."""
        return self._execute(
            f"SELECT {self._SELECT_COLS} FROM public.cameras "
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
                     "channel", "subtype", "rtsp_url_override", "is_active",
                     "retention_days", "detection_stream_url", "video_codec", "max_auth_failures"):
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key])

        if not fields:
            return self.get_by_id(camera_id)

        values.append(str(camera_id))
        return self._execute_mutation(
            f"UPDATE public.cameras SET {', '.join(fields)} "
            f"WHERE id = %s RETURNING {self._SELECT_COLS}",
            tuple(values),
        )

    def update_retention(
        self, camera_id: UUID, tenant_id: str, retention_days: Optional[int]
    ) -> Optional[dict[str, Any]]:
        """Atualiza retention_days da câmera (None = herdar do tenant)."""
        return self._execute_mutation(
            f"UPDATE public.cameras SET retention_days = %s "
            "WHERE id = %s AND tenant_id = %s "
            f"RETURNING {self._SELECT_COLS}",
            (retention_days, str(camera_id), tenant_id),
        )

    def get_retention(
        self, camera_id: UUID, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Retorna id, retention_days e tenant_id da câmera para cálculo efetivo."""
        return self._execute_one(
            "SELECT id, retention_days, tenant_id FROM public.cameras "
            "WHERE id = %s AND tenant_id = %s",
            (str(camera_id), tenant_id),
        )

    def update_last_tested(self, camera_id: UUID, error: Optional[str]) -> None:
        """Registra resultado do último teste de conectividade."""
        self._execute_mutation_no_return(
            "UPDATE public.cameras SET last_tested_at = NOW(), last_error = %s WHERE id = %s",
            (error, str(camera_id)),
        )

    def update_config(
        self,
        camera_id: UUID,
        tenant_id: str,
        fps_target: int,
        quality_preset: str,
    ) -> Optional[dict[str, Any]]:
        """Atualiza fps_target e quality_preset da câmera (filtra tenant)."""
        return self._execute_mutation(
            "UPDATE public.cameras SET fps_target = %s, quality_preset = %s "
            "WHERE id = %s AND tenant_id = %s "
            f"RETURNING {self._SELECT_COLS}",
            (fps_target, quality_preset, str(camera_id), tenant_id),
        )

    def delete(self, camera_id: UUID) -> int:
        """Deleta câmera."""
        return self._execute_mutation_no_return(
            "DELETE FROM public.cameras WHERE id = %s",
            (str(camera_id),),
        )

    def count_by_module(self, tenant_id: str, module_code: str) -> int:
        """Conta câmeras de um tenant por módulo."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM public.cameras WHERE tenant_id = %s AND module_code = %s",
            (tenant_id, module_code),
        )
        return row["count"] if row else 0

    def count_by_status(self, tenant_id: str, module_code: str, status: str) -> int:
        """Conta câmeras de um tenant/módulo por status (is_active)."""
        is_active = status == "active"
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM public.cameras WHERE tenant_id = %s AND module_code = %s AND is_active = %s",
            (tenant_id, module_code, is_active),
        )
        return row["count"] if row else 0

    def count_active_all(self, tenant_id: str) -> int:
        """Conta todas as câmeras ativas do tenant (todos os módulos)."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM public.cameras WHERE tenant_id = %s AND is_active = true",
            (tenant_id,),
        )
        return row["count"] if row else 0

    def count_all(self, tenant_id: str) -> int:
        """Conta todas as câmeras do tenant."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM public.cameras WHERE tenant_id = %s",
            (tenant_id,),
        )
        return row["count"] if row else 0

    def get_by_id_and_tenant(self, camera_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        """Busca câmera por ID garantindo isolamento multi-tenant (C-01).

        Inclui active_module, schedule_rules e site_id para composição de cenário.
        """
        return self._execute_one(
            f"SELECT {self._SELECT_COLS}, active_module, schedule_rules, site_id "
            "FROM public.cameras WHERE id = %s AND tenant_id = %s",
            (str(camera_id), str(tenant_id)),
        )

    def update_module(self, camera_id: str, module: str) -> None:
        """Atualiza o módulo ativo da câmera."""
        self._execute_mutation_no_return(
            "UPDATE public.cameras SET active_module = %s WHERE id = %s",
            (module, str(camera_id)),
        )

    def update_schedule(self, camera_id: str, rules: list) -> None:
        """Atualiza as regras de agendamento JSONB da câmera."""
        self._execute_mutation_no_return(
            "UPDATE public.cameras SET schedule_rules = %s::jsonb WHERE id = %s",
            (json.dumps(rules), str(camera_id)),
        )

    def update_retention_days(
        self,
        camera_id: str,
        tenant_id: str,
        retention_days: Optional[int],
    ) -> bool:
        """Define tier de retenção por câmera. None = herdar do tenant."""
        result = self._execute_mutation(
            "UPDATE public.cameras SET retention_days = %s "
            "WHERE id = %s AND tenant_id = %s RETURNING id",
            (retention_days, str(camera_id), str(tenant_id)),
        )
        return result is not None

    MODEL_COLUMNS: dict[str, str] = {
        "epi": "model_epi_id",
        "quality": "model_quality_id",
        "counting": "model_counting_id",
    }

    def get_model_assignments(
        self, camera_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Retorna atribuições de modelo por módulo (filtra por tenant)."""
        return self._execute_one(
            "SELECT id, model_epi_id, model_quality_id, model_counting_id "
            "FROM public.cameras WHERE id = %s AND tenant_id = %s",
            (str(camera_id), str(tenant_id)),
        )

    def set_model_assignment(
        self,
        camera_id: str,
        tenant_id: str,
        module: str,
        model_id: Optional[str],
    ) -> Optional[dict[str, Any]]:
        """Persiste modelo ativo para o módulo especificado."""
        column = self.MODEL_COLUMNS[module]
        return self._execute_mutation(
            f"UPDATE public.cameras SET {column} = %s "
            "WHERE id = %s AND tenant_id = %s "
            "RETURNING id, model_epi_id, model_quality_id, model_counting_id",
            (model_id, str(camera_id), str(tenant_id)),
        )

    def get_module_and_models(
        self, camera_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Retorna active_module + atribuições de modelo (filtra por tenant)."""
        return self._execute_one(
            "SELECT id, active_module, model_epi_id, model_quality_id, model_counting_id "
            "FROM public.cameras WHERE id = %s AND tenant_id = %s",
            (str(camera_id), str(tenant_id)),
        )

    # --- Inventory (Task 052) ---

    _INVENTORY_COLS = (
        "id, tenant_id, name, location, description, manufacturer, "
        "host, port, username, channel, subtype, is_active, active_module, "
        "last_seen, last_error, last_tested_at, created_at, updated_at, "
        "site_id, brand, model, ip, rtsp_substream_url, "
        "codec_detected, substream_ok, max_connections, "
        "last_probe_at, probe_status, notes"
    )

    def get_inventory(
        self,
        tenant_id: Optional[str] = None,
        site_id: Optional[str] = None,
        brand: Optional[str] = None,
        probe_status: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Lista câmeras para o painel de inventário (superadmin).

        Filtra opcionalmente por tenant_id, site_id, brand e probe_status.
        Sem password — seguro retornar ao frontend.
        """
        conditions = ["1=1"]
        params: list[Any] = []
        if tenant_id:
            conditions.append("tenant_id = %s")
            params.append(tenant_id)
        if site_id:
            conditions.append("site_id = %s")
            params.append(site_id)
        if brand:
            conditions.append("brand ILIKE %s")
            params.append(f"%{brand}%")
        if probe_status:
            conditions.append("probe_status = %s")
            params.append(probe_status)
        where = " AND ".join(conditions)
        params.append(limit)
        return self._execute(
            f"SELECT {self._INVENTORY_COLS} FROM public.cameras "  # noqa: S608
            f"WHERE {where} ORDER BY created_at DESC LIMIT %s",
            tuple(params),
        )

    def update_probe_result(
        self,
        camera_id: str,
        probe_status: str,
        codec_detected: Optional[str],
        substream_ok: bool,
        last_error: Optional[str] = None,
    ) -> None:
        """Grava resultado de probe (TCP + ffprobe) na câmera."""
        self._execute_mutation_no_return(
            "UPDATE public.cameras "
            "SET probe_status = %s, codec_detected = %s, substream_ok = %s, "
            "    last_probe_at = NOW(), last_error = %s "
            "WHERE id = %s",
            (probe_status, codec_detected, substream_ok, last_error, camera_id),
        )

    def create_draft(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Cria câmera em modo draft (is_active=False) — usado no import em lote."""
        return self._execute_mutation(
            "INSERT INTO public.cameras "
            "(tenant_id, name, location, manufacturer, host, port, username, "
            " active_module, is_active, brand, model, ip, notes, probe_status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, false, %s, %s, %s, %s, 'pending') "
            f"RETURNING {self._INVENTORY_COLS}",
            (
                str(data["tenant_id"]),
                data["name"],
                data.get("location"),
                data.get("manufacturer", "generic"),
                data["host"],
                data.get("port", 554),
                data.get("username", "admin"),
                data.get("module", "epi"),
                data.get("brand"),
                data.get("model"),
                data.get("ip") or data["host"],
                data.get("notes"),
            ),
        )
