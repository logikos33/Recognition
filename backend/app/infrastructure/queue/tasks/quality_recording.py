"""
Módulo de Qualidade — Task de gravação contínua de câmeras.

Fila: quality_recording
Responsabilidade: gravar câmeras com active_module='quality' em segmentos de 5 min no R2.
Buffer: 48h — segmentos mais antigos são deletados automaticamente.

REGRA CRÍTICA: verificar active_module == 'quality' ANTES de iniciar qualquer gravação.
Câmeras de outros módulos (epi, counting) NÃO devem ser gravadas por este worker.
"""
import logging
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

# Duração de cada segmento em segundos (5 minutos)
SEGMENT_DURATION = int(os.environ.get("QUALITY_SEGMENT_DURATION", "300"))

# Retenção do buffer: quantas horas manter os segmentos no R2
BUFFER_HOURS = int(os.environ.get("QUALITY_BUFFER_HOURS", "48"))

# Chave Redis que controla se a gravação deve continuar
def _active_key(camera_id: str) -> str:
    return f"quality:recording:{camera_id}:active"


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


def _verify_quality_module(camera_id: str, tenant_schema: str) -> bool:
    """
    Verifica que a câmera ainda tem active_module='quality'.
    Essencial para evitar gravar câmeras de outros módulos.
    """
    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute(
                "SELECT active_module FROM cameras WHERE id = %s",
                (camera_id,)
            )
            row = cur.fetchone()
            if row is None:
                return False
            return row["active_module"] == "quality"
    except Exception as exc:
        logger.error("quality_verify_module_error: camera=%s err=%s", camera_id, exc)
        return False


def _get_rtsp_url(camera_id: str, tenant_schema: str) -> str | None:
    """Busca a RTSP URL da câmera no banco."""
    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("SELECT rtsp_url FROM cameras WHERE id = %s", (camera_id,))
            row = cur.fetchone()
            return row["rtsp_url"] if row else None
    except Exception as exc:
        logger.error("quality_rtsp_url_error: camera=%s err=%s", camera_id, exc)
        return None


def _insert_segment(
    camera_id: str,
    tenant_schema: str,
    segment_start: datetime,
    segment_end: datetime,
    r2_key: str,
    size_bytes: int,
) -> None:
    """Registra segmento no banco após upload bem-sucedido."""
    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            duration = int((segment_end - segment_start).total_seconds())
            cur.execute("""
                INSERT INTO quality_recording_segments
                    (camera_id, segment_start, segment_end,
                     duration_seconds, r2_key, size_bytes, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'available')
            """, (camera_id, segment_start, segment_end, duration, r2_key, size_bytes))
    except Exception as exc:
        logger.error("quality_insert_segment_error: camera=%s err=%s", camera_id, exc)


def _cleanup_old_segments(camera_id: str, tenant_schema: str) -> None:
    """
    Deleta segmentos mais velhos que BUFFER_HOURS do R2 e atualiza o banco.
    Chamado a cada segmento fechado.
    """
    try:
        cutoff = datetime.now(UTC) - timedelta(hours=BUFFER_HOURS)
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                SELECT id, r2_key FROM quality_recording_segments
                WHERE camera_id = %s AND segment_start < %s AND status = 'available'
            """, (camera_id, cutoff))
            old_segments = cur.fetchall()

        if not old_segments:
            return

        storage = _get_storage()
        deleted_count = 0
        for seg in old_segments:
            try:
                storage.delete_object(seg["r2_key"])
                pool2 = _get_pool()
                with pool2.get_connection() as conn2:
                    cur2 = conn2.cursor()
                    cur2.execute("SET search_path TO %s, public", (tenant_schema,))
                    cur2.execute(
                        "UPDATE quality_recording_segments SET status = 'deleted' WHERE id = %s",
                        (seg["id"],)
                    )
                deleted_count += 1
            except Exception as exc:
                logger.warning("quality_cleanup_segment_error: id=%s err=%s", seg["id"], exc)

        if deleted_count:
            logger.info("quality_cleanup: camera=%s deleted=%d", camera_id, deleted_count)

    except Exception as exc:
        logger.error("quality_cleanup_error: camera=%s err=%s", camera_id, exc)


@celery.task(
    bind=True,
    queue="quality_recording",
    max_retries=10,
    name="app.infrastructure.queue.tasks.quality_recording.record_quality_camera",
    default_retry_delay=30,
)
def record_quality_camera(self, camera_id: str, tenant_schema: str):
    """
    Grava câmera de qualidade em segmentos de SEGMENT_DURATION segundos no R2.

    Fila: quality_recording
    Máx retries: 10 com backoff exponencial em falha RTSP.

    Fluxo:
    1. Verificar active_module == 'quality' — se não, encerrar silenciosamente
    2. Validar RTSP URL com RTSPUrlValidator
    3. FFmpeg segmentação → segmentos em /tmp/quality_recordings/{camera_id}/
    4. A cada segmento fechado: upload R2, INSERT no banco, cleanup >48h
    5. Monitorar Redis quality:recording:{camera_id}:active — parar se ausente
    """
    logger.info("quality_recording_start: camera=%s tenant=%s", camera_id, tenant_schema)

    # 1. Verificar active_module
    if not _verify_quality_module(camera_id, tenant_schema):
        logger.info("quality_recording_skip: camera=%s not quality module", camera_id)
        return {"status": "skipped", "reason": "not_quality_module"}

    # 2. Buscar e validar RTSP URL
    rtsp_url = _get_rtsp_url(camera_id, tenant_schema)
    if not rtsp_url:
        logger.error("quality_recording_no_rtsp: camera=%s", camera_id)
        raise self.retry(countdown=60, exc=RuntimeError("RTSP URL não encontrada"))

    try:
        from app.core.validators import RTSPUrlValidator
        RTSPUrlValidator.validate(rtsp_url)
    except Exception as exc:
        logger.error(
            "quality_recording_invalid_rtsp: camera=%s url=%s err=%s",
            camera_id, rtsp_url[:30], exc
        )
        return {"status": "error", "reason": "invalid_rtsp"}

    # 3. Preparar diretório temporário
    tmp_dir = Path(f"/tmp/quality_recordings/{camera_id}")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    r = _get_redis()
    storage = _get_storage()

    # 4. Registrar que a gravação está ativa
    r.setex(_active_key(camera_id), SEGMENT_DURATION * 4, "1")

    # Padrão do nome do arquivo por timestamp
    output_pattern = str(tmp_dir / "%Y-%m-%d_%H-%M-%S.mp4")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-an",  # sem áudio
        "-f", "segment",
        "-segment_time", str(SEGMENT_DURATION),
        "-segment_format", "mp4",
        "-strftime", "1",
        output_pattern,
    ]

    logger.info("quality_recording_ffmpeg_start: camera=%s", camera_id)
    segment_start_time = datetime.now(UTC)

    try:
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        processed_segments: set = set()

        while True:
            # Verificar se deve parar
            if not r.exists(_active_key(camera_id)):
                logger.info("quality_recording_stop: camera=%s", camera_id)
                proc.terminate()
                break

            # Verificar se processo FFmpeg ainda vive
            if proc.poll() is not None:
                stderr_output = proc.stderr.read() if proc.stderr else ""
                logger.error(
                    "quality_recording_ffmpeg_died: camera=%s stderr=%s",
                    camera_id, stderr_output[-300:]
                )
                break

            # Renovar chave Redis (heartbeat)
            r.setex(_active_key(camera_id), SEGMENT_DURATION * 4, "1")

            # Verificar segmentos fechados (arquivo mais antigo que não processamos)
            segment_files = sorted(tmp_dir.glob("*.mp4"))
            # O arquivo mais recente ainda pode estar sendo escrito pelo FFmpeg
            # Processar todos exceto o último
            for seg_file in segment_files[:-1]:
                if seg_file.name in processed_segments:
                    continue
                try:
                    # Upload para R2
                    seg_time_str = seg_file.stem  # "2024-01-15_08-30-00"
                    date_part = seg_time_str[:10]  # "2024-01-15"
                    time_part = seg_time_str[11:]  # "08-30-00"
                    r2_key = (
                        f"quality-recordings/{tenant_schema}/"
                        f"{camera_id}/{date_part}/{time_part}.mp4"
                    )

                    with open(seg_file, "rb") as f:
                        seg_data = f.read()

                    storage.upload_bytes(r2_key, seg_data, content_type="video/mp4")
                    size_bytes = len(seg_data)

                    # Calcular timestamps do segmento
                    seg_end_time = datetime.now(UTC)

                    _insert_segment(
                        camera_id=camera_id,
                        tenant_schema=tenant_schema,
                        segment_start=segment_start_time,
                        segment_end=seg_end_time,
                        r2_key=r2_key,
                        size_bytes=size_bytes,
                    )
                    segment_start_time = seg_end_time

                    # Remover arquivo local
                    seg_file.unlink(missing_ok=True)
                    processed_segments.add(seg_file.name)

                    logger.info(
                        "quality_segment_uploaded: camera=%s key=%s size=%d",
                        camera_id, r2_key, size_bytes
                    )

                    # Cleanup de segmentos antigos (>48h)
                    _cleanup_old_segments(camera_id, tenant_schema)

                except Exception as exc:
                    logger.error(
                        "quality_segment_upload_error: camera=%s file=%s err=%s",
                        camera_id, seg_file.name, exc
                    )

            time.sleep(10)

    except Exception as exc:
        logger.error("quality_recording_error: camera=%s err=%s", camera_id, exc)
        raise self.retry(
            countdown=min(30 * (2 ** self.request.retries), 300),
            exc=exc,
        ) from exc
    finally:
        # Limpar arquivos temporários residuais
        try:
            for f in tmp_dir.glob("*.mp4"):
                f.unlink(missing_ok=True)
        except Exception:
            pass
        logger.info("quality_recording_ended: camera=%s", camera_id)

    return {"status": "stopped", "camera_id": camera_id}
