"""
Módulo de Qualidade — Task de extração de frames para anotação.

Fila: quality_annotation
Responsabilidade: extrair frames do clip NOK a 1fps, filtrar blur/brilho,
fazer upload no R2 e registrar em quality_annotation_frames.
"""
import logging
import os
from pathlib import Path

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

# Threshold de blur: variância do Laplaciano abaixo disso → frame descartado
BLUR_THRESHOLD = 100.0
# Threshold de brilho: média V (HSV) abaixo disso → frame muito escuro → descartado
BRIGHTNESS_THRESHOLD = 40.0


def _get_pool():
    from app.infrastructure.database.connection import DatabasePool
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado")
    return pool


def _get_storage():
    from app.infrastructure.storage.r2_storage import R2Storage
    return R2Storage.get_instance()


def _get_redis():
    import redis as _redis
    return _redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
        socket_timeout=5,
    )


def _is_frame_usable(frame_path: Path) -> bool:
    """
    Verifica qualidade do frame via OpenCV.
    Retorna False se borrado ou muito escuro.
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(frame_path))
        if img is None:
            return False

        # Blur check: Laplacian variance
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if lap_var < BLUR_THRESHOLD:
            logger.debug(
                "quality_annotation_blur_reject: path=%s var=%.1f",
                frame_path.name, lap_var
            )
            return False

        # Brightness check: média do canal V em HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        v_mean = float(np.mean(hsv[:, :, 2]))
        if v_mean < BRIGHTNESS_THRESHOLD:
            logger.debug("quality_annotation_dark_reject: path=%s v=%.1f", frame_path.name, v_mean)
            return False

        return True

    except ImportError:
        # OpenCV não instalado no serviço de API — aceitar todos os frames
        logger.warning("quality_annotation_opencv_missing: accepting all frames")
        return True
    except Exception as exc:
        logger.warning("quality_annotation_frame_check_error: %s err=%s", frame_path.name, exc)
        return True


@celery.task(
    bind=True,
    queue="quality_annotation",
    max_retries=3,
    name="app.infrastructure.queue.tasks.quality_annotation.prepare_quality_frames",
    default_retry_delay=30,
)
def prepare_quality_frames(self, inspection_id: str, tenant_schema: str):
    """
    Extrai frames do clip NOK para workspace de anotação.

    Fluxo:
    1. Buscar clip_r2_key da inspeção
    2. Se clip não disponível → encerrar (pode ser chamado antes do clip estar pronto)
    3. Baixar clip do R2
    4. FFmpeg: extrair 1 frame/segundo
    5. Para cada frame: blur + brilho check
    6. Upload frames aprovados para quality-frames/{tenant}/{inspection_id}/N.jpg
    7. INSERT em quality_annotation_frames para cada frame
    8. UPDATE inspection: annotation_status = 'ready'
    9. Publicar Redis: quality:annotation_ready:{inspection_id}
    """
    import subprocess

    logger.info("quality_annotation_start: inspection=%s", inspection_id)

    pool = _get_pool()

    # 1. Buscar clip da inspeção
    with pool.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SET search_path TO %s, public", (tenant_schema,))
        cur.execute(
            "SELECT clip_r2_key, clip_status FROM quality_inspections WHERE id = %s",
            (inspection_id,)
        )
        row = cur.fetchone()

    if row is None:
        logger.error("quality_annotation_no_inspection: %s", inspection_id)
        return {"status": "error", "reason": "inspection_not_found"}

    # 2. Clip ainda não disponível
    if row["clip_status"] != "available" or not row["clip_r2_key"]:
        logger.warning("quality_annotation_clip_not_ready: inspection=%s status=%s",
                       inspection_id, row["clip_status"])
        return {"status": "skipped", "reason": "clip_not_available"}

    clip_r2_key = row["clip_r2_key"]

    try:
        storage = _get_storage()

        # 3. Baixar clip
        tmp_dir = Path(f"/tmp/quality_annotation/{inspection_id}")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        clip_path = tmp_dir / "clip.mp4"
        frames_dir = tmp_dir / "frames"
        frames_dir.mkdir(exist_ok=True)

        logger.info("quality_annotation_download: key=%s", clip_r2_key)
        clip_data = storage.download_bytes(clip_r2_key)
        clip_path.write_bytes(clip_data)

        # 4. Extrair 1fps com FFmpeg
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_path),
            "-vf", "fps=1",
            "-q:v", "3",
            str(frames_dir / "%04d.jpg"),
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg extração falhou: {result.stderr.decode()[-200:]}")

        # 5 + 6. Filtrar e fazer upload
        frame_files = sorted(frames_dir.glob("*.jpg"))
        uploaded_frames = []
        frame_seq = 1

        for frame_file in frame_files:
            if not _is_frame_usable(frame_file):
                continue

            r2_key = f"quality-frames/{tenant_schema}/{inspection_id}/{frame_seq:04d}.jpg"
            frame_data = frame_file.read_bytes()
            storage.upload_bytes(r2_key, frame_data, content_type="image/jpeg")
            uploaded_frames.append(r2_key)
            frame_seq += 1

        if not uploaded_frames:
            logger.warning("quality_annotation_no_frames: inspection=%s", inspection_id)
            return {"status": "error", "reason": "no_usable_frames"}

        # 7. INSERT em quality_annotation_frames
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            for seq, r2_key in enumerate(uploaded_frames, start=1):
                cur.execute("""
                    INSERT INTO quality_annotation_frames
                        (inspection_id, frame_sequence, r2_key, status)
                    VALUES (%s, %s, %s, 'pending')
                    ON CONFLICT DO NOTHING
                """, (inspection_id, seq, r2_key))

        # 8. UPDATE inspection annotation_status
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                UPDATE quality_inspections
                SET annotation_status = 'ready'
                WHERE id = %s
            """, (inspection_id,))

        # 9. Publicar evento Redis
        try:
            import json
            r = _get_redis()
            r.publish(f"quality:annotation_ready:{inspection_id}", json.dumps({
                "inspection_id": inspection_id,
                "frame_count": len(uploaded_frames),
            }))
        except Exception as exc:
            logger.warning("quality_annotation_publish_error: %s err=%s", inspection_id, exc)

        logger.info(
            "quality_annotation_done: inspection=%s frames=%d",
            inspection_id, len(uploaded_frames)
        )
        return {"status": "ok", "frame_count": len(uploaded_frames)}

    except Exception as exc:
        logger.error("quality_annotation_error: inspection=%s err=%s", inspection_id, exc)
        raise self.retry(countdown=30, exc=exc) from exc

    finally:
        # Limpar arquivos temporários
        try:
            tmp_dir = Path(f"/tmp/quality_annotation/{inspection_id}")
            import shutil
            shutil.rmtree(str(tmp_dir), ignore_errors=True)
        except Exception:
            pass
