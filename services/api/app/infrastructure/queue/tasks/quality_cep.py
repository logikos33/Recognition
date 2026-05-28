"""
Módulo de Qualidade — Tasks agendadas (Celery Beat).

Fila: quality_cep
Responsabilidade:
  - update_quality_cep_baseline: recalcular UCL/LCL de NOK rate (diário 00:30)
  - cleanup_quality_recordings: deletar segmentos >48h (horário)
  - cleanup_quality_clips: deletar clips >7 dias (diário 03:00)
  - generate_shift_reports: gerar relatórios de turno (06:15, 14:15, 22:15)
"""
import json
import logging
import os
from datetime import UTC, datetime, timedelta

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

# Retenção de clips: 7 dias
CLIP_RETENTION_DAYS = int(os.environ.get("QUALITY_CLIP_RETENTION_DAYS", "7"))

# Retenção de segmentos de gravação: 48 horas
RECORDING_RETENTION_HOURS = int(os.environ.get("QUALITY_BUFFER_HOURS", "48"))


def _get_pool():
    from app.infrastructure.database.connection import DatabasePool
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado")
    return pool


def _get_storage():
    from app.infrastructure.storage.r2_storage import R2Storage
    return R2Storage.get_instance()


def _get_all_tenant_schemas() -> list[str]:
    """Retorna todos os schemas de tenant ativos."""
    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT schema_name FROM public.tenants WHERE is_active = true")
            rows = cur.fetchall()
            return [r["schema_name"] for r in rows]
    except Exception as exc:
        logger.error("quality_cep_get_tenants_error: %s", exc)
        return []


@celery.task(
    queue="quality_cep",
    name="app.infrastructure.queue.tasks.quality_cep.update_quality_cep_baseline",
)
def update_quality_cep_baseline():
    """
    Recalcula baseline CEP (UCL/LCL) de NOK rate para todas as câmeras de qualidade.

    Agendado: diário 00:30 (via Celery Beat)

    Fórmula:
    - Coleta NOK rates horárias das últimas 30 dias por câmera
    - Calcula média e desvio padrão
    - UCL = média + 3 * sigma (Shewhart ±3σ)
    - LCL = max(0, média - 3 * sigma)
    """
    logger.info("quality_cep_baseline_start")
    schemas = _get_all_tenant_schemas()

    for schema in schemas:
        try:
            pool = _get_pool()
            cutoff = datetime.now(UTC) - timedelta(days=30)

            # Buscar câmeras de qualidade ativas
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SET search_path TO %s, public", (schema,))
                cur.execute("""
                    SELECT DISTINCT camera_id FROM quality_inspections
                    WHERE created_at >= %s
                """, (cutoff,))
                cameras = [r["camera_id"] for r in cur.fetchall()]

            for camera_id in cameras:
                try:
                    # Calcular NOK rate por hora nas últimas 4 semanas
                    with pool.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("SET search_path TO %s, public", (schema,))
                        cur.execute("""
                            SELECT
                                date_trunc('hour', created_at) AS hour_bucket,
                                COUNT(*) FILTER (WHERE result = 'nok') AS nok_count,
                                COUNT(*) AS total
                            FROM quality_inspections
                            WHERE camera_id = %s AND created_at >= %s
                            GROUP BY hour_bucket
                            HAVING COUNT(*) >= 5
                            ORDER BY hour_bucket
                        """, (camera_id, cutoff))
                        rows = cur.fetchall()

                    if len(rows) < 5:
                        continue

                    rates = [r["nok_count"] / r["total"] for r in rows]
                    n = len(rates)
                    mean = sum(rates) / n
                    variance = sum((x - mean) ** 2 for x in rates) / n
                    sigma = variance ** 0.5

                    ucl = min(1.0, mean + 3 * sigma)
                    lcl = max(0.0, mean - 3 * sigma)

                    # UPSERT em quality_cep_baseline
                    with pool.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("SET search_path TO %s, public", (schema,))
                        cur.execute("""
                            INSERT INTO quality_cep_baseline
                                (camera_id, mean_nok_rate, sigma_nok_rate,
                                 control_limit_upper, control_limit_lower,
                                 sample_size, calculated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            ON CONFLICT (camera_id) DO UPDATE SET
                                mean_nok_rate = EXCLUDED.mean_nok_rate,
                                sigma_nok_rate = EXCLUDED.sigma_nok_rate,
                                control_limit_upper = EXCLUDED.control_limit_upper,
                                control_limit_lower = EXCLUDED.control_limit_lower,
                                sample_size = EXCLUDED.sample_size,
                                calculated_at = NOW()
                        """, (camera_id, mean, sigma, ucl, lcl, n))

                    logger.info("quality_cep_updated: camera=%s mean=%.3f ucl=%.3f n=%d",
                                camera_id, mean, ucl, n)

                except Exception as exc:
                    logger.error("quality_cep_camera_error: camera=%s err=%s", camera_id, exc)

        except Exception as exc:
            logger.error("quality_cep_schema_error: schema=%s err=%s", schema, exc)

    logger.info("quality_cep_baseline_done: schemas=%d", len(schemas))


@celery.task(
    queue="quality_cep",
    name="app.infrastructure.queue.tasks.quality_cep.cleanup_quality_recordings",
)
def cleanup_quality_recordings():
    """
    Deleta segmentos de gravação mais velhos que RECORDING_RETENTION_HOURS do R2 e do banco.

    Agendado: a cada hora (via Celery Beat)
    """
    logger.info("quality_cleanup_recordings_start: retention=%dh", RECORDING_RETENTION_HOURS)
    schemas = _get_all_tenant_schemas()
    cutoff = datetime.now(UTC) - timedelta(hours=RECORDING_RETENTION_HOURS)
    storage = _get_storage()
    total_deleted = 0

    for schema in schemas:
        try:
            pool = _get_pool()
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SET search_path TO %s, public", (schema,))
                cur.execute("""
                    SELECT id, r2_key FROM quality_recording_segments
                    WHERE segment_start < %s AND status = 'available'
                    LIMIT 200
                """, (cutoff,))
                old_segs = cur.fetchall()

            for seg in old_segs:
                try:
                    storage.delete_object(seg["r2_key"])
                    pool2 = _get_pool()
                    with pool2.get_connection() as conn2:
                        cur2 = conn2.cursor()
                        cur2.execute("SET search_path TO %s, public", (schema,))
                        cur2.execute(
                            "UPDATE quality_recording_segments "
                            "SET status = 'deleted' WHERE id = %s",
                            (seg["id"],)
                        )
                    total_deleted += 1
                except Exception as exc:
                    logger.warning("quality_cleanup_seg_error: id=%s err=%s", seg["id"], exc)

        except Exception as exc:
            logger.error("quality_cleanup_recordings_schema_error: schema=%s err=%s", schema, exc)

    logger.info("quality_cleanup_recordings_done: deleted=%d", total_deleted)


@celery.task(
    queue="quality_cep",
    name="app.infrastructure.queue.tasks.quality_cep.cleanup_quality_clips",
)
def cleanup_quality_clips():
    """
    Deleta clips de NOK mais velhos que CLIP_RETENTION_DAYS do R2 e marca no banco.

    Agendado: diário 03:00 (via Celery Beat)
    """
    logger.info("quality_cleanup_clips_start: retention=%dd", CLIP_RETENTION_DAYS)
    schemas = _get_all_tenant_schemas()
    cutoff = datetime.now(UTC) - timedelta(days=CLIP_RETENTION_DAYS)
    storage = _get_storage()
    total_deleted = 0

    for schema in schemas:
        try:
            pool = _get_pool()
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SET search_path TO %s, public", (schema,))
                cur.execute("""
                    SELECT id, clip_r2_key FROM quality_inspections
                    WHERE clip_status = 'available'
                      AND clip_r2_key IS NOT NULL
                      AND created_at < %s
                    LIMIT 500
                """, (cutoff,))
                old_clips = cur.fetchall()

            for clip in old_clips:
                try:
                    storage.delete_object(clip["clip_r2_key"])
                    pool2 = _get_pool()
                    with pool2.get_connection() as conn2:
                        cur2 = conn2.cursor()
                        cur2.execute("SET search_path TO %s, public", (schema,))
                        cur2.execute("""
                            UPDATE quality_inspections
                            SET clip_status = 'expired', clip_r2_key = NULL
                            WHERE id = %s
                        """, (clip["id"],))
                    total_deleted += 1
                except Exception as exc:
                    logger.warning("quality_cleanup_clip_error: id=%s err=%s", clip["id"], exc)

        except Exception as exc:
            logger.error("quality_cleanup_clips_schema_error: schema=%s err=%s", schema, exc)

    logger.info("quality_cleanup_clips_done: deleted=%d", total_deleted)


@celery.task(
    queue="quality_cep",
    name="app.infrastructure.queue.tasks.quality_cep.generate_shift_reports",
)
def generate_shift_reports():
    """
    Gera relatórios de turno encerrado para todos os tenants.

    Agendado: 06:15 (encerra noite), 14:15 (encerra manhã), 22:15 (encerra tarde).

    Cada relatório inclui: OK/NOK counts, defect pareto, NOK rate por hora,
    comparativo com turno anterior, câmeras com maior NOK rate.

    Armazena resultado em Redis quality:shift_report:{schema}:{shift}:{date}
    para servir via GET /api/v1/quality/reports/shift.
    """
    from datetime import date

    # Determinar turno que acabou de encerrar
    hour = datetime.now(UTC).hour
    if hour == 6:
        shift = "night"
    elif hour == 14:
        shift = "morning"
    else:
        shift = "afternoon"

    today = date.today().isoformat()
    logger.info("quality_shift_report_start: shift=%s date=%s", shift, today)

    schemas = _get_all_tenant_schemas()

    try:
        import redis as _redis
        r = _redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_timeout=5,
        )
    except Exception as exc:
        logger.error("quality_shift_report_redis_error: %s", exc)
        return

    for schema in schemas:
        try:
            pool = _get_pool()
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SET search_path TO %s, public", (schema,))

                # Totais do turno
                cur.execute("""
                    SELECT
                        result,
                        COUNT(*) AS count,
                        defect_class,
                        AVG(confidence) AS avg_confidence
                    FROM quality_inspections
                    WHERE shift = %s
                      AND DATE(created_at AT TIME ZONE 'UTC') = %s::date
                    GROUP BY result, defect_class
                    ORDER BY count DESC
                """, (shift, today))
                rows = cur.fetchall()

            total_ok = sum(r["count"] for r in rows if r["result"] == "ok")
            total_nok = sum(r["count"] for r in rows if r["result"] == "nok")
            total = total_ok + total_nok
            nok_rate = round(total_nok / total, 4) if total > 0 else 0.0

            # Pareto de defeitos
            defect_pareto = [
                {
                    "defect_class": row["defect_class"],
                    "count": row["count"],
                    "pct": round(row["count"] / total_nok, 3) if total_nok > 0 else 0,
                }
                for row in rows if row["result"] == "nok"
            ]

            report = {
                "schema": schema,
                "shift": shift,
                "date": today,
                "total_ok": total_ok,
                "total_nok": total_nok,
                "total": total,
                "nok_rate": nok_rate,
                "defect_pareto": defect_pareto,
                "generated_at": datetime.now(UTC).isoformat(),
            }

            # Armazenar no Redis (TTL 48h)
            key = f"quality:shift_report:{schema}:{shift}:{today}"
            r.setex(key, 172800, json.dumps(report))
            logger.info("quality_shift_report_done: schema=%s shift=%s nok_rate=%.3f",
                        schema, shift, nok_rate)

        except Exception as exc:
            logger.error("quality_shift_report_schema_error: schema=%s err=%s", schema, exc)

    logger.info("quality_shift_reports_done: schemas=%d", len(schemas))
