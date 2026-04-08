"""
EPI Monitor V2 — Frame Extraction Task.

Celery task: baixa vídeo do R2, extrai frames via FFmpeg scene detection,
faz upload dos frames para R2, cria registros no DB, despacha quality_filter.
"""
import json
import logging
import os
import shutil
import subprocess
import glob as glob_module
from uuid import UUID, uuid4

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


def _get_storage():
    from app.infrastructure.storage.local_storage import get_storage
    return get_storage()


def _get_frame_repo():
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.frame_repository import FrameRepository
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado no worker")
    return FrameRepository(pool)


def _get_video_repo():
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.video_repository import VideoRepository
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado no worker")
    return VideoRepository(pool)


@celery.task(bind=True, max_retries=3, queue="extraction", name="tasks.extraction.extract_frames")
def extract_frames(
    self,
    video_key: str,
    video_id: str,
    user_id: str,
    scene_threshold: float = 0.3,
) -> dict:
    """Extrai frames de vídeo usando FFmpeg scene detection.

    Pipeline:
    1. Baixa vídeo do R2 para /tmp
    2. FFmpeg com scene detection → JPEGs em /tmp
    3. Upload de cada frame para R2 (frames/{user_id}/{video_id}/frame_NNNN.jpg)
    4. Cria registro no DB via FrameRepository
    5. Despacha quality_filter para cada frame
    6. Atualiza status do vídeo para 'extracted'
    7. Limpa /tmp

    Args:
        video_key: Chave R2 do vídeo (ex: raw-videos/{user_id}/{video_id}/video.mp4)
        video_id: UUID do vídeo no banco
        user_id: UUID do usuário dono do vídeo
        scene_threshold: Limiar de scene detection (0-1)
    """
    tmp_video = f"/tmp/epi_video_{video_id}.mp4"
    tmp_frames_dir = f"/tmp/epi_frames/{video_id}"

    try:
        storage = _get_storage()

        # 1. Download vídeo do R2
        logger.info("extraction_download_start: video_id=%s, key=%s", video_id, video_key)
        video_data = storage.download_bytes(video_key)
        with open(tmp_video, "wb") as f:
            f.write(video_data)
        del video_data  # libera memória

        # 2. Extrair frames com FFmpeg
        os.makedirs(tmp_frames_dir, exist_ok=True)
        output_pattern = os.path.join(tmp_frames_dir, "frame_%04d.jpg")

        cmd = [
            "ffmpeg", "-i", tmp_video,
            "-vf", f"select=gt(scene\\,{scene_threshold})",
            "-vsync", "vfr",
            "-q:v", "2",
            output_pattern,
        ]

        logger.info("extraction_ffmpeg_start: video_id=%s, threshold=%s", video_id, scene_threshold)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            logger.error("ffmpeg_error: video_id=%s, stderr=%s", video_id, result.stderr[:500])
            raise RuntimeError(f"FFmpeg falhou: {result.stderr[:200]}")

        extracted = sorted(glob_module.glob(os.path.join(tmp_frames_dir, "frame_*.jpg")))
        logger.info("extraction_ffmpeg_done: video_id=%s, frames=%d", video_id, len(extracted))

        if not extracted:
            _update_video_status(video_id, "extracted", frame_count=0)
            return {"video_id": video_id, "frame_count": 0}

        # 3-5. Upload cada frame + criar DB record + despachar quality_filter
        frame_repo = _get_frame_repo()
        frame_count = 0

        for i, frame_path in enumerate(extracted):
            frame_key = f"frames/{user_id}/{video_id}/frame_{i:04d}.jpg"

            # Upload para R2
            storage.upload_file(frame_key, frame_path)

            # Criar registro no DB
            frame = frame_repo.create(
                video_id=UUID(video_id),
                frame_number=i,
                filename=frame_key,
                timestamp_seconds=None,
            )
            frame_id = str(frame["id"])

            # Despachar quality_filter
            from app.infrastructure.queue.tasks.quality import quality_filter
            quality_filter.delay(frame_key, frame_id, video_id)

            frame_count += 1

        # 6. Atualizar status do vídeo
        _update_video_status(video_id, "extracted", frame_count=frame_count)

        logger.info("extraction_complete: video_id=%s, frames=%d", video_id, frame_count)
        return {"video_id": video_id, "frame_count": frame_count}

    except subprocess.TimeoutExpired:
        logger.error("extraction_timeout: video_id=%s", video_id)
        _update_video_status(video_id, "error", error_message="FFmpeg timeout")
        raise self.retry(countdown=60)

    except Exception as exc:
        logger.error("extraction_failed: video_id=%s, error=%s", video_id, exc, exc_info=True)
        _update_video_status(video_id, "error", error_message=str(exc)[:200])
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))

    finally:
        # Sempre limpa /tmp
        if os.path.exists(tmp_video):
            os.remove(tmp_video)
        if os.path.exists(tmp_frames_dir):
            shutil.rmtree(tmp_frames_dir, ignore_errors=True)


def _update_video_status(
    video_id: str,
    status: str,
    error_message: str | None = None,
    frame_count: int | None = None,
) -> None:
    """Atualiza status do vídeo no DB."""
    try:
        video_repo = _get_video_repo()
        video_repo.update_status(UUID(video_id), status, error_message, frame_count)
    except Exception as exc:
        logger.error("update_video_status_failed: video_id=%s, error=%s", video_id, exc)
