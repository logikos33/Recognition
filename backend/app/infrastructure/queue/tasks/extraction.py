"""
EPI Monitor V2 — Frame Extraction Task.

Celery task: extrai frames de vídeo via FFmpeg scene detection.
"""
import logging
import os
import subprocess
import glob as glob_module
from uuid import uuid4

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3, queue="extraction", name="tasks.extraction.extract_frames")
def extract_frames(
    self,
    video_path: str,
    video_id: str,
    user_id: str,
    scene_threshold: float = 0.3,
    output_dir: str | None = None,
) -> dict:
    """Extrai frames de vídeo usando FFmpeg scene detection.

    Pipeline:
    1. FFmpeg com scene detection threshold
    2. Gera JPEGs numerados em output_dir
    3. Retorna lista de frames extraídos
    """
    if output_dir is None:
        output_dir = f"/tmp/epi_frames/{video_id}"

    os.makedirs(output_dir, exist_ok=True)
    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    try:
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", f"select=gt(scene\\,{scene_threshold})",
            "-vsync", "vfr",
            "-q:v", "2",
            output_pattern,
        ]

        logger.info(
            "extract_frames_start: video_id=%s, threshold=%s",
            video_id, scene_threshold,
        )

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode != 0:
            logger.error(
                "ffmpeg_error: video_id=%s, stderr=%s",
                video_id, result.stderr[:500],
            )
            raise RuntimeError(f"FFmpeg failed: {result.stderr[:200]}")

        extracted = sorted(glob_module.glob(os.path.join(output_dir, "frame_*.jpg")))

        logger.info(
            "extract_frames_done: video_id=%s, frames=%d",
            video_id, len(extracted),
        )

        return {
            "video_id": video_id,
            "frame_count": len(extracted),
            "output_dir": output_dir,
            "frames": [os.path.basename(f) for f in extracted],
        }

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg_timeout: video_id=%s", video_id)
        raise self.retry(countdown=60)
    except Exception as exc:
        logger.error(
            "extract_frames_failed: video_id=%s, error=%s",
            video_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc, countdown=30)
