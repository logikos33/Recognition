"""
Recognition — Frame Extraction Task.

Celery task: baixa vídeo do R2, extrai frames via FFmpeg scene detection,
faz upload dos frames para R2, cria registros no DB, despacha quality_filter.
"""
import glob as glob_module
import logging
import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import UUID

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
    fps: float | None = None,
) -> dict:
    """Extrai frames de vídeo usando FFmpeg a intervalo fixo (fps).

    Pipeline:
    1. Baixa vídeo do R2 para /tmp
    2. FFmpeg fps=N → JPEGs em /tmp (ordens de magnitude mais rápido que scene detection)
    3. Upload paralelo de cada frame para R2 (frames/{user_id}/{video_id}/frame_NNNN.jpg)
    4. Cria registro no DB via FrameRepository com timestamp_seconds calculado
    5. Despacha quality_filter para cada frame
    6. Atualiza status do vídeo para 'extracted'
    7. Limpa /tmp

    Args:
        video_key: Chave R2 do vídeo (ex: raw-videos/{user_id}/{video_id}/video.mp4)
        video_id: UUID do vídeo no banco
        user_id: UUID do usuário dono do vídeo
        fps: Frames por segundo a extrair (default: env EXTRACTION_FPS ou 1.0)
    """
    effective_fps = fps or float(os.environ.get("EXTRACTION_FPS", "1.0"))
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
            "ffmpeg", "-threads", "0", "-i", tmp_video,
            "-vf", f"fps={effective_fps}",
            "-q:v", "2",
            output_pattern,
        ]

        logger.info("extraction_ffmpeg_start: video_id=%s, fps=%s", video_id, effective_fps)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            logger.error("ffmpeg_error: video_id=%s, stderr=%s", video_id, result.stderr[:500])
            raise RuntimeError(f"FFmpeg falhou: {result.stderr[:200]}")

        extracted = sorted(glob_module.glob(os.path.join(tmp_frames_dir, "frame_*.jpg")))
        logger.info("extraction_ffmpeg_done: video_id=%s, frames=%d", video_id, len(extracted))

        if not extracted:
            _update_video_status(video_id, "extracted", frame_count=0)
            return {"video_id": video_id, "frame_count": 0}

        # 3-5. Upload paralelo de frames + criar DB records + despachar quality_filter
        frame_repo = _get_frame_repo()
        video_repo = _get_video_repo()
        from app.infrastructure.queue.tasks.quality import quality_filter

        # Sinaliza início do upload e registra total esperado
        _update_video_status(video_id, "extracting", frames_expected=len(extracted))

        def _upload_frame(args: tuple) -> str:
            idx, frame_path = args
            frame_key = f"frames/{user_id}/{video_id}/frame_{idx:04d}.jpg"
            storage.upload_file(frame_key, frame_path, "image/jpeg")
            frame = frame_repo.create(
                video_id=UUID(video_id),
                frame_number=idx,
                filename=frame_key,
                timestamp_seconds=round(idx / effective_fps, 3),
            )
            return str(frame["id"]), frame_key

        lock = threading.Lock()
        completed_count = 0

        frame_ids: list[tuple[str, str]] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_upload_frame, (i, p)): i for i, p in enumerate(extracted)}
            for fut in as_completed(futures):
                frame_ids.append(fut.result())
                with lock:
                    completed_count += 1
                    if completed_count % 5 == 0:
                        try:
                            video_repo.update_progress(UUID(video_id), completed_count)
                            logger.debug(
                                "extraction_progress: video_id=%s, completed=%d",
                                video_id, completed_count,
                            )
                        except Exception as exc:
                            logger.debug(
                                "progress_update_failed: video_id=%s, error=%s",
                                video_id, exc,
                            )

        for frame_id, frame_key in frame_ids:
            quality_filter.delay(frame_key, frame_id, video_id)

        frame_count = len(frame_ids)

        # 6. Atualizar status do vídeo
        _update_video_status(
            video_id, "extracted", frame_count=frame_count, frames_expected=frame_count
        )

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
    frames_expected: int | None = None,
) -> None:
    """Atualiza status do vídeo no DB."""
    try:
        video_repo = _get_video_repo()
        video_repo.update_status(
            UUID(video_id), status, error_message, frame_count, frames_expected
        )
    except Exception as exc:
        logger.error("update_video_status_failed: video_id=%s, error=%s", video_id, exc)


