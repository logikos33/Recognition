"""Repository: Frame Annotations + YOLO Classes."""
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class AnnotationRepository(BaseRepository):
    """Queries SQL para frame_annotations e yolo_classes."""

    # --- YOLO Classes ---

    def create_class(
        self, user_id: UUID, name: str, color: str = "#3b82f6"
    ) -> dict[str, Any]:
        """Cria classe YOLO."""
        return self._execute_mutation(
            "INSERT INTO yolo_classes (user_id, name, color) "
            "VALUES (%s, %s, %s) RETURNING *",
            (str(user_id), name, color),
        )  # type: ignore[return-value]

    def get_classes_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista classes do usuário."""
        return self._execute(
            "SELECT * FROM yolo_classes WHERE user_id = %s ORDER BY id",
            (str(user_id),),
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
        """Salva batch de anotações (delete + insert)."""
        self.delete_by_frame(frame_id)
        count = 0
        for ann in annotations:
            self.create_annotation(
                frame_id=frame_id,
                class_id=ann["class_id"],
                x_center=ann["x_center"],
                y_center=ann["y_center"],
                width=ann["width"],
                height=ann["height"],
            )
            count += 1
        return count
