"""Repository: Frame Annotations + YOLO Classes."""
from typing import Any
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class AnnotationRepository(BaseRepository):
    """Queries SQL para frame_annotations e yolo_classes."""

    # --- YOLO Classes ---

    def create_class(
        self,
        user_id: UUID,
        name: str,
        color: str = "#3b82f6",
        tenant_id: "UUID | str | None" = None,
        module_code: "str | None" = None,
    ) -> dict[str, Any]:
        """Cria classe YOLO, tenant-scoped (migration 093).

        tenant_id omitido → derivado de users.tenant_id (mesmo backfill da 093);
        module_code omitido → 'epi' (default do schema). Retrocompatível com
        callers legados (user_id, name, color).
        """
        return self._execute_mutation(
            "INSERT INTO yolo_classes (user_id, name, color, tenant_id, module_code) "
            "VALUES (%s, %s, %s, "
            "COALESCE(%s, (SELECT tenant_id FROM users WHERE id = %s)), "
            "COALESCE(%s, 'epi')) RETURNING *",
            (
                str(user_id),
                name,
                color,
                str(tenant_id) if tenant_id else None,
                str(user_id),
                module_code,
            ),
        )  # type: ignore[return-value]

    def get_classes_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista classes do usuário (legado — preferir get_classes_for_tenant)."""
        return self._execute(
            "SELECT * FROM yolo_classes WHERE user_id = %s ORDER BY id",
            (str(user_id),),
        )

    def get_classes_for_tenant(
        self,
        tenant_id: str,
        user_id: "UUID | None" = None,
        module_code: str = "epi",
    ) -> list[dict[str, Any]]:
        """Lista classes do tenant+módulo, com fallback user_id p/ legado (093).

        Linhas anteriores ao backfill da 093 podem ter tenant_id NULL — o
        fallback via user_id garante que o dono continue vendo suas classes.
        """
        if user_id is not None:
            return self._execute(
                "SELECT * FROM yolo_classes "
                "WHERE (tenant_id = %s OR (tenant_id IS NULL AND user_id = %s)) "
                "AND module_code = %s ORDER BY id",
                (str(tenant_id), str(user_id), module_code),
            )
        return self._execute(
            "SELECT * FROM yolo_classes "
            "WHERE tenant_id = %s AND module_code = %s ORDER BY id",
            (str(tenant_id), module_code),
        )

    # --- Annotations ---

    def create_annotation(
        self,
        frame_id: UUID,
        class_id: int,
        x_center: float,
        y_center: float,
        width: float,
        height: float,
    ) -> dict[str, Any]:
        """Cria anotação de bounding box."""
        return self._execute_mutation(
            "INSERT INTO frame_annotations "
            "(frame_id, class_id, x_center, y_center, width, height) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
            (str(frame_id), class_id, x_center, y_center, width, height),
        )  # type: ignore[return-value]

    def get_by_frame(self, frame_id: UUID) -> list[dict[str, Any]]:
        """Lista anotações de um frame com nome da classe."""
        return self._execute(
            "SELECT a.*, c.name AS class_name, c.color AS class_color "
            "FROM frame_annotations a "
            "JOIN yolo_classes c ON a.class_id = c.id "
            "WHERE a.frame_id = %s ORDER BY a.created_at",
            (str(frame_id),),
        )

    def delete_by_frame(self, frame_id: UUID) -> int:
        """Deleta todas as anotações de um frame (para re-anotar)."""
        return self._execute_mutation_no_return(
            "DELETE FROM frame_annotations WHERE frame_id = %s",
            (str(frame_id),),
        )

    def save_batch(
        self, frame_id: UUID, annotations: list[dict[str, Any]]
    ) -> int:
        """Salva batch de anotações (delete + insert) em transação única.

        AI_NOTE: US-027 — operação atômica: DELETE + INSERTs na mesma conexão.
        Rollback automático preserva anotações anteriores em caso de falha parcial.
        """

        def _transaction(conn, cur) -> int:
            cur.execute(
                "DELETE FROM frame_annotations WHERE frame_id = %s",
                (str(frame_id),),
            )
            count = 0
            for ann in annotations:
                cur.execute(
                    "INSERT INTO frame_annotations "
                    "(frame_id, class_id, x_center, y_center, width, height) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        str(frame_id),
                        ann["class_id"],
                        ann["x_center"],
                        ann["y_center"],
                        ann["width"],
                        ann["height"],
                    ),
                )
                count += 1
            return count

        return self._execute_in_transaction(_transaction)
