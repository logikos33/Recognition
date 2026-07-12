"""
Recognition — NVR/DVR Frame Extraction Task (WS-B1, ADR-0034).

Busca segmentos de gravação (cascata ONVIF/ISAPI/RTSP — infrastructure/nvr/),
extrai frames por FFmpeg a cada N segundos de cada segmento, sobe pro
storage e cria registros em training_frames (source='nvr', recorder_id).

Mesmo padrão de tasks/extraction.py (vídeo enviado por upload): FFmpeg com
lista de args (nunca shell=True), URL sempre validada por RTSPUrlValidator
ANTES de chegar no FFmpeg (feito dentro de NvrClient.build_playback_url).
"""
import glob as glob_module
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from uuid import UUID, uuid4

from app.constants import FrameSource, R2Prefix
from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

_FFMPEG_TIMEOUT_SECONDS = 300
_MAX_FRAMES_PER_SEGMENT = 200  # teto de segurança — não deixa 1 segmento gigante travar o worker


def _get_recorder_repo():
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    from app.infrastructure.database.repositories.recorder_repository import (  # noqa: PLC0415
        RecorderRepository,
    )
    return RecorderRepository(DatabasePool.get_instance())


def _get_frame_repo():
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    from app.infrastructure.database.repositories.frame_repository import (  # noqa: PLC0415
        FrameRepository,
    )
    return FrameRepository(DatabasePool.get_instance())


@celery.task(
    bind=True, max_retries=1, queue="extraction",
    name="tasks.nvr_extraction.extract_nvr_frames",
)
def extract_nvr_frames(
    self,
    recorder_id: str,
    tenant_id: str,
    channel: int,
    start_iso: str,
    end_iso: str,
    interval_seconds: int = 5,
    module_code: str = "epi",
) -> dict:
    """Extrai frames de gravações NVR/DVR num intervalo (WS-B1).

    Fluxo: recorder → client (cascata por protocolo) → search_recordings
    (timeline) → por segmento, FFmpeg extrai 1 frame a cada
    interval_seconds → upload storage + FrameRepository.create
    (source=NVR, recorder_id, camera_id=None — recorder não tem 1:1 com
    `cameras`, o canal é o identificador dentro do gravador).
    """
    from app.domain.services.recorder_service import RecorderService  # noqa: PLC0415
    from app.infrastructure.nvr.factory import get_nvr_client  # noqa: PLC0415
    from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

    recorder_repo = _get_recorder_repo()
    recorder = recorder_repo.get_by_id(UUID(recorder_id), tenant_id)
    if not recorder:
        return {"status": "error", "reason": "recorder_not_found"}

    service = RecorderService(recorder_repo)
    password = service.decrypt_password(recorder.get("password_encrypted"))
    client = get_nvr_client(recorder, password)

    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00")).replace(tzinfo=None)
    end = datetime.fromisoformat(end_iso.replace("Z", "+00:00")).replace(tzinfo=None)

    try:
        segments = client.search_recordings(channel, start, end)
    except Exception as exc:
        logger.error(
            "nvr_extraction_search_failed: recorder=%s channel=%s err=%s",
            recorder_id, channel, exc, exc_info=True,
        )
        return {"status": "error", "reason": "search_failed", "detail": str(exc)[:300]}

    if not segments:
        return {"status": "completed", "segments": 0, "frames": 0}

    storage = get_storage(tenant_id)
    frame_repo = _get_frame_repo()
    total_frames = 0
    errors: list[str] = []

    for segment in segments:
        try:
            playback_url = client.build_playback_url(segment)
        except Exception as exc:
            errors.append(f"playback_url segment={segment.playback_ref}: {exc}")
            continue

        tmp_dir = tempfile.mkdtemp(prefix="nvr_extract_")
        try:
            output_pattern = os.path.join(tmp_dir, "frame_%04d.jpg")
            cmd = [
                "ffmpeg", "-threads", "0", "-i", playback_url,
                "-vf", f"fps=1/{max(1, interval_seconds)}",
                "-frames:v", str(_MAX_FRAMES_PER_SEGMENT),
                "-q:v", "2",
                output_pattern,
            ]
            result = subprocess.run(  # noqa: S603
                cmd, capture_output=True, text=True, timeout=_FFMPEG_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                errors.append(f"ffmpeg segment={segment.playback_ref}: {result.stderr[:200]}")
                continue

            extracted = sorted(glob_module.glob(os.path.join(tmp_dir, "frame_*.jpg")))
            for path in extracted:
                with open(path, "rb") as f:
                    data = f.read()
                r2_key = (
                    f"{R2Prefix.TRAINING_IMAGES}/{tenant_id}/nvr/"
                    f"{recorder_id}/{uuid4()}.jpg"
                )
                storage.upload_bytes(r2_key, data, "image/jpeg")
                frame_repo.create(
                    video_id=None,
                    frame_number=total_frames,
                    filename=r2_key,
                    source=FrameSource.NVR,
                    r2_key=r2_key,
                    recorder_id=UUID(recorder_id),
                    captured_at=segment.start,
                    tenant_id=tenant_id,
                    module_code=module_code,
                )
                total_frames += 1
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    logger.info(
        "nvr_extraction_done: recorder=%s channel=%s segments=%d frames=%d errors=%d",
        recorder_id, channel, len(segments), total_frames, len(errors),
    )
    return {
        "status": "completed",
        "segments": len(segments),
        "frames": total_frames,
        "errors": errors,
    }
