"""Repository: Training Frames."""
import json
from typing import Any
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class FrameRepository(BaseRepository):
    """Queries SQL para tabela training_frames."""

    def create(
        self,
        video_id: UUID,
        frame_number: int,
        filename: str,
        timestamp_seconds: float | None = None,
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

    def get_by_id(self, frame_id: UUID) -> dict[str, Any] | None:
        """Busca frame por ID sem verificação de posse.

        INTERNAL USE ONLY — use get_by_id_and_user() in API handlers.
        Safe for Celery tasks where user context is not available.
        """
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

    def get_next_unannotated(self, video_id: UUID) -> dict[str, Any] | None:
        """Busca próximo frame não anotado (FIFO)."""
        return self._execute_one(
            "SELECT * FROM training_frames "
            "WHERE video_id = %s AND is_annotated = FALSE "
            "ORDER BY frame_number ASC LIMIT 1",
            (str(video_id),),
        )

    def mark_annotated(self, frame_id: UUID) -> dict[str, Any] | None:
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
            (status, json.dumps(scores or {}), str(frame_id)),
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

    # AI_NOTE: US-021 — Surface pre-annotations from JSONB for AnnotationInterface
    def get_pre_annotations(self, frame_id: UUID) -> "list[dict] | None":
        """Retorna pré-anotações DINO/SAM do frame (JSONB), ou None se não houver."""
        row = self._execute_one(
            "SELECT pre_annotations FROM training_frames WHERE id = %s",
            (str(frame_id),),
        )
        if not row:
            return None
        return row.get("pre_annotations")  # list[dict] ou None

    def get_annotated_by_video(self, video_id: UUID, user_id: UUID) -> "list[dict]":
        """Lista frames anotados de um vídeo verificando posse via user_id.

        JOIN em training_videos garante que apenas o dono do vídeo obtém resultados
        (mesmo padrão de count_validated/get_by_id_and_user). Fix P0-01.
        """
        return self._execute(
            "SELECT tf.*, "
            "  COUNT(fa.id) AS annotation_count, "
            "  tf.validated_at IS NOT NULL AS is_validated "
            "FROM training_frames tf "
            "JOIN training_videos tv ON tv.id = tf.video_id "
            "LEFT JOIN frame_annotations fa ON fa.frame_id = tf.id "
            "WHERE tf.video_id = %s AND tv.user_id = %s AND tf.is_annotated = TRUE "
            "GROUP BY tf.id "
            "ORDER BY tf.frame_number ASC",
            (str(video_id), str(user_id)),
        )

    def get_by_id_and_user(self, frame_id: UUID, user_id: UUID) -> "dict | None":
        """Busca frame por ID validando posse via training_videos.user_id.

        AI_NOTE: US-022 security fix — evita IDOR ao validar frame.
        Retorna None se frame não existir ou não pertencer ao usuário.
        """
        return self._execute_one(
            "SELECT tf.* FROM training_frames tf "
            "JOIN training_videos tv ON tv.id = tf.video_id "
            "WHERE tf.id = %s AND tv.user_id = %s",
            (str(frame_id), str(user_id)),
        )

    def mark_validated(self, frame_id: UUID, user_id: UUID) -> "dict | None":
        """Marca frame como validado por humano (apenas frames do próprio usuário).

        AI_NOTE: UPDATE filtra por user_id via JOIN para garantir que somente
        o dono do vídeo pode validar o frame — prevenção de IDOR.
        """
        return self._execute_mutation(
            "UPDATE training_frames tf "
            "SET validated_by = %s, validated_at = NOW() "
            "FROM training_videos tv "
            "WHERE tf.id = %s AND tf.video_id = tv.id AND tv.user_id = %s "
            "RETURNING tf.*",
            (str(user_id), str(frame_id), str(user_id)),
        )

    def get_by_user_paginated(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 24,
        is_annotated: "bool | None" = None,
        order: str = "desc",
    ) -> "dict[str, Any]":
        """Lista frames do usuário com paginação e filtros.

        Usado pela galeria de imagens de treino (Tab 1).
        Filtra por user_id via JOIN em training_videos.
        """
        offset = (page - 1) * page_size

        conditions = ["tv.user_id = %s"]
        params: list[Any] = [str(user_id)]

        if is_annotated is not None:
            conditions.append("tf.is_annotated = %s")
            params.append(is_annotated)

        where = " AND ".join(conditions)
        order_dir = "DESC" if order == "desc" else "ASC"

        count_row = self._execute_one(
            "SELECT COUNT(*) AS total FROM training_frames tf "
            f"JOIN training_videos tv ON tv.id = tf.video_id WHERE {where}",
            tuple(params),
        )
        total = int(count_row["total"]) if count_row else 0

        frames = self._execute(
            "SELECT tf.id, tf.video_id, tf.frame_number, tf.filename, "
            "tf.is_annotated, tf.created_at, "
            "tv.original_filename AS video_name "
            "FROM training_frames tf "
            f"JOIN training_videos tv ON tv.id = tf.video_id WHERE {where} "
            f"ORDER BY tf.created_at {order_dir} LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        return {
            "frames": list(frames),
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def count_validated(self, video_id: UUID, user_id: UUID) -> dict:
        """Conta frames validados e anotados de um vídeo (verificando posse).

        AI_NOTE: JOIN em training_videos garante que user_id é dono do vídeo.
        """
        row = self._execute_one(
            "SELECT "
            "  COUNT(*) FILTER (WHERE tf.is_annotated = TRUE) AS annotated, "
            "  COUNT(*) FILTER (WHERE tf.validated_at IS NOT NULL) AS validated, "
            "  COUNT(*) AS total "
            "FROM training_frames tf "
            "JOIN training_videos tv ON tv.id = tf.video_id "
            "WHERE tf.video_id = %s AND tv.user_id = %s",
            (str(video_id), str(user_id)),
        )
        return (
            {
                "annotated": int(row["annotated"] or 0),
                "validated": int(row["validated"] or 0),
                "total": int(row["total"] or 0),
            }
            if row
            else {"annotated": 0, "validated": 0, "total": 0}
        )
