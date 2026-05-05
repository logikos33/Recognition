"""
Recognition — Demo Video Repository.

Acesso SQL à tabela demo_videos.
Todos os métodos herdam BaseRepository — sem SQL fora desta classe.
"""
import logging
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class DemoVideoRepository(BaseRepository):
    """Repository para a tabela demo_videos."""

    def create(
        self,
        module: str,
        r2_key: str,
        r2_url: str,
        camera_id: str | None = None,
        label: str | None = None,
        file_size_bytes: int | None = None,
        duration_seconds: float | None = None,
        uploaded_by: str | None = None,
    ) -> dict[str, Any]:
        """Insere um registro de vídeo demo e retorna a linha criada."""
        return self._execute_mutation(  # type: ignore[return-value]
            """
            INSERT INTO demo_videos
                (module, camera_id, label, r2_key, r2_url,
                 file_size_bytes, duration_seconds, uploaded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (module, camera_id, label, r2_key, r2_url,
             file_size_bytes, duration_seconds, uploaded_by),
        )

    def list_active(
        self,
        module: str | None = None,
        camera_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista vídeos ativos, filtrando opcionalmente por módulo e/ou câmera."""
        conditions = ["active = true"]
        params: list[Any] = []

        if module:
            conditions.append("module = %s")
            params.append(module)
        if camera_id is not None:
            conditions.append("camera_id = %s")
            params.append(camera_id)

        where = " AND ".join(conditions)
        return self._execute(
            f"SELECT * FROM demo_videos WHERE {where} ORDER BY created_at DESC",
            tuple(params),
        )

    def get_for_camera(self, camera_id: str) -> dict[str, Any] | None:
        """Retorna o vídeo demo ativo para uma câmera.

        Prioridade: vídeo vinculado à câmera específica > vídeo vinculado ao módulo.
        Quando o upload não informa camera_id (modo módulo), o JOIN com cameras
        resolve pelo module_code da câmera.
        """
        return self._execute_one(
            """
            SELECT dv.*
            FROM demo_videos dv
            JOIN cameras c ON c.id = %s::uuid
            WHERE dv.active = true
              AND (
                  dv.camera_id = c.id
                  OR (dv.camera_id IS NULL AND dv.module = c.module_code)
              )
            ORDER BY dv.camera_id NULLS LAST, dv.created_at DESC
            LIMIT 1
            """,
            (camera_id,),
        )

    def soft_delete(self, video_id: int) -> bool:
        """Marca o registro como inativo (soft delete). Retorna True se encontrou."""
        result = self._execute_mutation(
            """
            UPDATE demo_videos
            SET active = false, updated_at = NOW()
            WHERE id = %s AND active = true
            RETURNING id
            """,
            (video_id,),
        )
        return result is not None
