"""
Recognition — Video Service.

Coordena pipeline de upload, extração de frames e status.
NÃO conhece Flask, Celery ou HTTP — lógica pura de negócio.
"""
import logging
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.core.validators import VideoUploadValidator
from app.infrastructure.database.repositories.video_repository import VideoRepository
from app.infrastructure.database.repositories.frame_repository import FrameRepository

logger = logging.getLogger(__name__)


class VideoService:
    """Use cases do pipeline de vídeo."""

    def __init__(
        self,
        video_repo: VideoRepository,
        frame_repo: FrameRepository,
    ) -> None:
        self._video_repo = video_repo
        self._frame_repo = frame_repo

    def create_video(
        self,
        user_id: UUID,
        filename: str,
        original_filename: str | None = None,
        file_size: int | None = None,
    ) -> dict:
        """Cria registro de vídeo após upload.

        `filename` is the full storage key (e.g. raw-videos/{user_id}/{id}/file.mp4).
        Callers are responsible for sanitizing the filename component before
        constructing the key. We only validate the extension here.
        """
        VideoUploadValidator.validate_extension(filename)
        video = self._video_repo.create(
            user_id=user_id,
            filename=filename,  # store storage key as-is — slashes are path separators
            original_filename=original_filename or filename,
            file_size=file_size,
        )
        video["id"] = str(video["id"])
        return video

    def get_video(self, video_id: UUID) -> dict:
        """Busca vídeo por ID."""
        video = self._video_repo.get_by_id(video_id)
        if not video:
            raise NotFoundError("Vídeo", str(video_id))
        video["id"] = str(video["id"])
        return video

    def list_videos(self, user_id: UUID) -> list[dict]:
        """Lista vídeos do usuário."""
        videos = self._video_repo.get_by_user(user_id)
        for v in videos:
            v["id"] = str(v["id"])
        return videos

    def get_video_frames(self, video_id: UUID) -> list[dict]:
        """Lista frames aprovados (quality_status != rejected) de um vídeo."""
        video = self._video_repo.get_by_id(video_id)
        if not video:
            raise NotFoundError("Vídeo", str(video_id))
        try:
            frames = self._frame_repo.get_approved_by_video(video_id)
        except Exception:
            # Fallback: migration ainda não aplicada → retorna todos
            frames = self._frame_repo.get_by_video(video_id)
        for f in frames:
            f["id"] = str(f["id"])
        return frames

    def get_frame_counts(self, video_id: UUID) -> dict:
        """Retorna contagem de frames por status."""
        return self._frame_repo.count_by_status(video_id)

    def delete_video(self, video_id: UUID) -> bool:
        """Deleta vídeo e frames do DB. Storage cleanup é responsabilidade do caller."""
        video = self._video_repo.get_by_id(video_id)
        if not video:
            raise NotFoundError("Vídeo", str(video_id))
        return self._video_repo.delete(video_id)

    def get_storage_stats(self, user_id: UUID) -> dict:
        """Retorna estatísticas de armazenamento do usuário."""
        used = self._video_repo.get_total_storage(user_id)
        limit = 5 * 1024 * 1024 * 1024  # 5 GB
        return {
            "used_bytes": used,
            "limit_bytes": limit,
            "used_formatted": _format_bytes(used),
            "limit_formatted": "5 GB",
            "percentage": round((used / limit) * 100, 1) if limit > 0 else 0,
        }

    def update_status(
        self,
        video_id: UUID,
        status: str,
        error_message: str | None = None,
        frame_count: int | None = None,
        frames_expected: int | None = None,
    ) -> dict:
        """Atualiza status do vídeo."""
        result = self._video_repo.update_status(
            video_id, status, error_message, frame_count, frames_expected
        )
        if not result:
            raise NotFoundError("Vídeo", str(video_id))
        result["id"] = str(result["id"])
        return result


def _format_bytes(size: int) -> str:
    """Formata bytes em unidade legível."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024  # type: ignore[assignment]
    return f"{size:.1f} TB"
