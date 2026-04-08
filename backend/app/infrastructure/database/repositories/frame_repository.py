"""Repository: Training Frames."""
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class FrameRepository(BaseRepository):
    """Queries SQL para tabela training_frames."""

    def create(
        self,
        video_id: UUID,
        frame_number: int,
        filename: str,
        timestamp_seconds: Optional[float] = None,
    ) -> dict[str, Any]:
        """Cria registro de frame."""
        return self._execute_mutation(
            "INSERT INTO training_frames "
            "(video_id, frame_number, filename, timestamp_seconds) "
            "VALUES (%s, %s, %s, %s) RETURNING *",
            (str(video_id), frame_number, filename, timestamp_seconds),
        )  # type: ignore[return-value]

    def create_bulk(self, frames: list[dict[str, Any]]) -> int:
        """Insere múltiplos frames. Retorna count."""
        return self._execute_many(
            "INSERT INTO training_frames "
            "(video_id, frame_number, filename, timestamp_seconds) "
            "VALUES (%(video_id)s, %(frame_number)s, %(filename)s, %(timestamp_seconds)s)",
            [(f,) for f in frames],  # type: ignore[arg-type]
        )

    def get_by_id(self, frame_id: UUID) -> Optional[dict[str, Any]]:
        """Busca frame por ID."""
        return self._execute_one(
            "SELECT * FROM training_frames WHERE id = %s",
            (str(frame_id),),
        )

    def get_by_video(self, video_id: UUID) -> list[dict[str, Any]]:
        """Lista frames de um vídeo."""
        return self._execute(
            "SELECT * FROM training_frames WHERE video_id = %s "
            "ORDER BY frame_number ASC",
            (str(video_id),),
        )

    def get_next_unannotated(self, video_id: UUID) -> Optional[dict[str, Any]]:
        """Busca próximo frame não anotado (FIFO)."""
        return self._execute_one(
            "SELECT * FROM training_frames "
            "WHERE video_id = %s AND is_annotated = FALSE "
            "ORDER BY frame_number ASC LIMIT 1",
            (str(video_id),),
        )

    def mark_annotated(self, frame_id: UUID) -> Optional[dict[str, Any]]:
        """Marca frame como anotado."""
        return self._execute_mutation(
            "UPDATE training_frames SET is_annotated = TRUE "
            "WHERE id = %s RETURNING *",
            (str(frame_id),),
        )

    def update_quality_status(
        self,
        frame_id: UUID,
        status: str,
        scores: dict | None = None,
    ) -> "dict[str, Any] | None":
        """Atualiza quality_status e quality_scores do frame."""
        return self._execute_mutation(
            "UPDATE training_frames SET quality_status = %s, quality_scores = %s "
            "WHERE id = %s RETURNING *",
            (status, __import__("json").dumps(scores or {}), str(frame_id)),
        )

    def get_approved_by_video(self, video_id: UUID) -> "list[dict[str, Any]]":
        """Lista frames aprovados no filtro de qualidade."""
        return self._execute(
            "SELECT * FROM training_frames "
            "WHERE video_id = %s AND quality_status != 'rejected' "
            "ORDER BY frame_number ASC",
            (str(video_id),),
        )

    def count_by_status(self, video_id: UUID) -> dict[str, int]:
        """Conta frames por status de anotação."""
        rows = self._execute(
            "SELECT is_annotated, COUNT(*) as count "
            "FROM training_frames WHERE video_id = %s "
            "GROUP BY is_annotated",
            (str(video_id),),
        )
        result = {"annotated": 0, "pending": 0, "total": 0}
        for row in rows:
            if row["is_annotated"]:
                result["annotated"] = row["count"]
            else:
                result["pending"] = row["count"]
        result["total"] = result["annotated"] + result["pending"]
        return result
