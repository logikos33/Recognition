"""Repository: Training Videos."""
from typing import Any
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class VideoRepository(BaseRepository):
    """Queries SQL para tabela training_videos."""

    def create(
        self,
        user_id: UUID,
        filename: str,
        original_filename: str | None = None,
        file_size: int | None = None,
    ) -> dict[str, Any]:
        """Cria registro de vídeo."""
        return self._execute_mutation(
            "INSERT INTO training_videos "
            "(user_id, filename, original_filename, file_size) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING *",
            (str(user_id), filename, original_filename, file_size),
        )  # type: ignore[return-value]

    def get_by_id(self, video_id: UUID) -> dict[str, Any] | None:
        """Busca vídeo por ID."""
        return self._execute_one(
            "SELECT * FROM training_videos WHERE id = %s",
            (str(video_id),),
        )

    def get_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista vídeos do usuário."""
        return self._execute(
            "SELECT * FROM training_videos WHERE user_id = %s "
            "ORDER BY created_at DESC",
            (str(user_id),),
        )

    def delete(self, video_id: UUID) -> bool:
        """Deleta vídeo e seus frames em transação única."""
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM training_frames WHERE video_id = %s",
                (str(video_id),),
            )
            cur.execute(
                "DELETE FROM training_videos WHERE id = %s RETURNING id",
                (str(video_id),),
            )
            row = cur.fetchone()
            return row is not None

    def get_total_storage(self, user_id: UUID) -> int:
        """Retorna total de bytes armazenados pelo usuário."""
        row = self._execute_one(
            "SELECT COALESCE(SUM(file_size), 0) AS total "
            "FROM training_videos WHERE user_id = %s",
            (str(user_id),),
        )
        return int(row["total"]) if row else 0

    def update_status(
        self,
        video_id: UUID,
        status: str,
        error_message: str | None = None,
        frame_count: int | None = None,
        frames_expected: int | None = None,
    ) -> dict[str, Any] | None:
        """Atualiza status do vídeo."""
        if frames_expected is not None and frame_count is not None:
            return self._execute_mutation(
                "UPDATE training_videos "
                "SET status = %s, error_message = %s, frame_count = %s, frames_expected = %s "
                "WHERE id = %s RETURNING *",
                (status, error_message, frame_count, frames_expected, str(video_id)),
            )
        if frames_expected is not None:
            return self._execute_mutation(
                "UPDATE training_videos "
                "SET status = %s, error_message = %s, frames_expected = %s "
                "WHERE id = %s RETURNING *",
                (status, error_message, frames_expected, str(video_id)),
            )
        if frame_count is not None:
            return self._execute_mutation(
                "UPDATE training_videos "
                "SET status = %s, error_message = %s, frame_count = %s "
                "WHERE id = %s RETURNING *",
                (status, error_message, frame_count, str(video_id)),
            )
        return self._execute_mutation(
            "UPDATE training_videos "
            "SET status = %s, error_message = %s "
            "WHERE id = %s RETURNING *",
            (status, error_message, str(video_id)),
        )

    def update_progress(self, video_id: UUID, frames_extracted: int) -> None:
        """Atualiza contagem de frames extraídos durante extração (progress live)."""
        self._execute_mutation_no_return(
            "UPDATE training_videos SET frame_count = %s WHERE id = %s",
            (frames_extracted, str(video_id)),
        )

    def update_duration(self, video_id: UUID, duration_seconds: float) -> None:
        """Persiste duração calculada do vídeo."""
        self._execute_mutation_no_return(
            "UPDATE training_videos SET duration_seconds = %s WHERE id = %s",
            (duration_seconds, str(video_id)),
        )
