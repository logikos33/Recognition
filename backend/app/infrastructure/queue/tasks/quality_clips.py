"""
Módulo de Qualidade — Tasks de geração de clips e snapshots de referência.

Fila: quality_clips
Responsabilidade:
  - generate_quality_clip: recorta ±30s de um segmento gravado para inspeção NOK
  - capture_reference_snapshot: captura frame do stream para primeiro OK de um lote
"""
import logging
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


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


def _publish_redis(channel: str, payload: dict) -> None:
    """Publica evento no Redis. Best-effort."""
    import json
    try:
        r = _get_redis()
        r.publish(channel, json.dumps(payload))
    except Exception as exc:
        logger.warning("quality_clips_publish_error: channel=%s err=%s", channel, exc)


@celery.task(
    bind=True,
    queue="quality_clips",
    max_retries=3,
    name="app.infrastructure.queue.tasks.quality_clips.generate_quality_clip",
    default_retry_delay=15,
)
def generate_quality_clip(
    self,
    inspection_id: str,
    camera_id: str,
    inspection_timestamp: str,
    tenant_schema: str,
):
    """
    Gera clip de ±30s ao redor de uma inspeção NOK.

    Fluxo:
    1. Buscar segmento de gravação que contém o timestamp da inspeção
    2. Se não encontrado → marcar clip_status='unavailable', encerrar
    3. Baixar segmento do R2
    4. FFmpeg: recortar offset ±30s
    5. Upload R2: quality-clips/{tenant}/{camera_id}/{inspection_id}.mp4
    6. UPDATE quality_inspections SET clip_status='available'
    7. Publicar Redis: quality:clip_ready:{inspection_id}
    """
    logger.info("quality_clip_start: inspection=%s camera=%s", inspection_id, camera_id)

    try:
        inspection_dt = datetime.fromisoformat(inspection_timestamp)
    except ValueError:
        logger.error("quality_clip_invalid_timestamp: %s", inspection_timestamp)
        return {"status": "error", "reason": "invalid_timestamp"}

    pool = _get_pool()

    try:
        # 1. Buscar segmento que contém o timestamp
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                SELECT id, r2_key, segment_start, segment_end
                FROM quality_recording_segments
                WHERE camera_id = %s
                  AND segment_start <= %s
                  AND segment_end >= %s
                  AND status = 'available'
                ORDER BY segment_start DESC
                LIMIT 1
            """, (camera_id, inspection_dt, inspection_dt))
            seg_row = cur.fetchone()

        # 2. Segmento não encontrado
        if seg_row is None:
            logger.warning(
                "quality_clip_no_segment: inspection=%s ts=%s",
                inspection_id, inspection_timestamp
            )
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SET search_path TO %s, public", (tenant_schema,))
                cur.execute(
                    "UPDATE quality_inspections SET clip_status = 'unavailable' WHERE id = %s",
                    (inspection_id,)
                )
            return {"status": "unavailable", "reason": "no_segment_found"}

        storage = _get_storage()
        segment_r2_key = seg_row["r2_key"]
        segment_start_dt = seg_row["segment_start"]
        if hasattr(segment_start_dt, 'tzinfo') and segment_start_dt.tzinfo is None:
            segment_start_dt = segment_start_dt.replace(tzinfo=UTC)

        # 3. Baixar segmento do R2
        tmp_dir = Path(f"/tmp/quality_clips/{inspection_id}")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        segment_path = tmp_dir / "segment.mp4"
        clip_path = tmp_dir / "clip.mp4"

        logger.info("quality_clip_download: key=%s", segment_r2_key)
        segment_data = storage.download_bytes(segment_r2_key)
        segment_path.write_bytes(segment_data)

        # 4. Calcular offset: posição da inspeção no segmento - 30s
        offset_total = (inspection_dt - segment_start_dt).total_seconds() - 30.0
        offset = max(0.0, offset_total)
        duration = 60.0  # clip de 60s (±30s)

        # Garantir que não ultrapassa o fim do segmento
        segment_duration = (seg_row["segment_end"] - seg_row["segment_start"]).total_seconds()
        if offset + duration > segment_duration:
            duration = max(1.0, segment_duration - offset)

        # FFmpeg: recortar clip
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", str(segment_path),
            "-ss", str(offset),
            "-t", str(duration),
            "-c", "copy",
            str(clip_path),
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg falhou: {result.stderr.decode()[-300:]}")

        # 5. Upload do clip para R2
        r2_key = f"quality-clips/{tenant_schema}/{camera_id}/{inspection_id}.mp4"
        clip_data = clip_path.read_bytes()
        storage.upload_bytes(r2_key, clip_data, content_type="video/mp4")

        clip_start = inspection_dt - timedelta(seconds=30)
        clip_end = clip_start + timedelta(seconds=duration)

        # 6. UPDATE inspection
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                UPDATE quality_inspections
                SET clip_r2_key = %s,
                    clip_start = %s,
                    clip_end = %s,
                    clip_status = 'available'
                WHERE id = %s
            """, (r2_key, clip_start, clip_end, inspection_id))

        # 7. Publicar evento
        _publish_redis(f"quality:clip_ready:{inspection_id}", {
            "inspection_id": inspection_id,
            "clip_status": "available",
        })

        logger.info("quality_clip_done: inspection=%s key=%s", inspection_id, r2_key)
        return {"status": "available", "clip_r2_key": r2_key}

    except Exception as exc:
        logger.error("quality_clip_error: inspection=%s err=%s", inspection_id, exc)
        raise self.retry(countdown=15, exc=exc) from exc

    finally:
        # Limpar arquivos temporários
        try:
            tmp_dir = Path(f"/tmp/quality_clips/{inspection_id}")
            for f in tmp_dir.glob("*"):
                f.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except Exception:
            pass


@celery.task(
    queue="quality_clips",
    name="app.infrastructure.queue.tasks.quality_clips.capture_reference_snapshot",
)
def capture_reference_snapshot(camera_id: str, tenant_schema: str, production_order: str):
    """
    Captura frame do stream RTSP como snapshot de referência do primeiro OK de um lote.

    Chamado automaticamente quando a primeira inspeção OK ocorre após
    mudança de production_order.
    """
    logger.info("quality_snapshot_start: camera=%s order=%s", camera_id, production_order)

    try:
        pool = _get_pool()

        # Buscar RTSP URL
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("SELECT rtsp_url FROM cameras WHERE id = %s", (camera_id,))
            row = cur.fetchone()
            if row is None:
                logger.error("quality_snapshot_no_camera: camera=%s", camera_id)
                return {"status": "error"}
            rtsp_url = row["rtsp_url"]

        tmp_path = Path(f"/tmp/quality_snapshot_{camera_id}.jpg")

        # FFmpeg: capturar 1 frame
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-frames:v", "1",
            "-q:v", "2",
            str(tmp_path),
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            stderr_tail = result.stderr.decode()[-200:]
            logger.error(
                "quality_snapshot_ffmpeg_error: camera=%s err=%s",
                camera_id, stderr_tail
            )
            return {"status": "error"}

        # Upload para R2
        from datetime import datetime
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        r2_key = f"quality-snapshots/{tenant_schema}/{camera_id}/{production_order}/{ts}.jpg"

        storage = _get_storage()
        frame_data = tmp_path.read_bytes()
        storage.upload_bytes(r2_key, frame_data, content_type="image/jpeg")
        tmp_path.unlink(missing_ok=True)

        # INSERT snapshot + atualizar config da câmera
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                INSERT INTO quality_reference_snapshots
                    (camera_id, production_order, r2_key)
                VALUES (%s, %s, %s)
            """, (camera_id, production_order, r2_key))
            cur.execute("""
                UPDATE quality_camera_config
                SET reference_snapshot_r2_key = %s, updated_at = NOW()
                WHERE camera_id = %s
            """, (r2_key, camera_id))

        logger.info("quality_snapshot_done: camera=%s key=%s", camera_id, r2_key)
        return {"status": "ok", "r2_key": r2_key}

    except Exception as exc:
        logger.error("quality_snapshot_error: camera=%s err=%s", camera_id, exc)
        return {"status": "error", "reason": str(exc)}
