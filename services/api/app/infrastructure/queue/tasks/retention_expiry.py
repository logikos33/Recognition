"""
Expiração de evidências R2 por tier de retenção — task-047.

Fila: quality_cep (reutiliza fila de manutenção existente)
Agendamento sugerido: diário às 02:00 (via Celery Beat)

Lógica:
  Para cada tenant ativo:
    1. Obtém retenção efetiva: cameras.retention_days → tenants.default_retention_days
       → plans.video_retention_days → 7 (fallback).
    2. Busca alertas com evidence_r2_key mais antigos que a cutoff.
    3. Deleta do R2 e nulifica evidence_r2_key (mantém o alerta para auditoria).
    4. Loga contagem por câmera/tenant.

Isolamento: NUNCA deleta fora do escopo do tenant/câmera.
"""
import logging
from datetime import UTC, datetime, timedelta

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

_DEFAULT_RETENTION_DAYS = 7
_BATCH_SIZE = 500


def _get_pool():
    from app.infrastructure.database.connection import DatabasePool
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado")
    return pool


def _get_storage():
    from app.infrastructure.storage.local_storage import get_storage
    return get_storage()


def _get_tenant_rows() -> list[dict]:
    """Retorna tenants ativos com retenção efetiva (override + plano + fallback)."""
    pool = _get_pool()
    with pool.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT t.id, t.schema_name, "
            "       COALESCE(t.default_retention_days, p.video_retention_days, %s) "
            "           AS effective_retention_days "
            "FROM public.tenants t "
            "LEFT JOIN public.plans p ON p.slug = t.plan "
            "WHERE t.is_active = true AND t.schema_name IS NOT NULL "
            "  AND t.schema_name <> '' AND t.schema_name <> 'public'",
            (_DEFAULT_RETENTION_DAYS,),
        )
        return cur.fetchall()


def _get_cameras_for_tenant(tenant_id: str, tenant_retention: int) -> list[dict]:
    """Retorna câmeras do tenant com retenção efetiva por câmera."""
    pool = _get_pool()
    with pool.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, COALESCE(retention_days, %s) AS effective_days "
            "FROM public.cameras WHERE tenant_id = %s",
            (tenant_retention, str(tenant_id)),
        )
        return cur.fetchall()


def _expire_camera_evidence(
    schema: str,
    camera_id: str,
    effective_days: int,
    storage,
) -> int:
    """
    Deleta evidências R2 de uma câmera mais antigas que effective_days.
    Retorna contagem de objetos deletados.
    """
    cutoff = datetime.now(UTC) - timedelta(days=effective_days)
    pool = _get_pool()
    deleted = 0

    with pool.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SET search_path TO %s, public", (schema,))
        cur.execute(
            "SELECT id, evidence_r2_key FROM alerts "
            "WHERE camera_id = %s "
            "  AND created_at < %s "
            "  AND evidence_r2_key IS NOT NULL "
            "LIMIT %s",
            (str(camera_id), cutoff, _BATCH_SIZE),
        )
        old_alerts = cur.fetchall()

    for alert in old_alerts:
        r2_key = alert.get("evidence_r2_key") or alert.get("evidence_key")
        if not r2_key:
            continue
        try:
            storage.delete(r2_key)
            deleted += 1
        except Exception as exc:
            logger.warning(
                "retention_delete_r2_error: schema=%s camera=%s key=%s err=%s",
                schema, camera_id, r2_key, exc,
            )
            continue

        try:
            pool2 = _get_pool()
            with pool2.get_connection() as conn2:
                cur2 = conn2.cursor()
                cur2.execute("SET search_path TO %s, public", (schema,))
                cur2.execute(
                    "UPDATE alerts SET evidence_r2_key = NULL WHERE id = %s",
                    (alert["id"],),
                )
        except Exception as exc:
            logger.warning(
                "retention_nullify_error: schema=%s alert=%s err=%s",
                schema, alert["id"], exc,
            )

    return deleted


@celery.task(
    queue="quality_cep",
    name="app.infrastructure.queue.tasks.retention_expiry.expire_evidence_by_retention",
)
def expire_evidence_by_retention():
    """
    Job diário: expira evidências R2 conforme tier de retenção por câmera/tenant.

    Escopo garantido: nunca deleta fora do tenant/câmera via schema + camera_id.
    """
    logger.info("retention_expiry_start: %s", datetime.now(UTC).isoformat())
    storage = _get_storage()
    total_deleted = 0
    total_cameras = 0

    try:
        tenants = _get_tenant_rows()
    except Exception as exc:
        logger.error("retention_expiry_tenant_query_error: %s", exc)
        return

    for tenant in tenants:
        tenant_id = tenant["id"]
        schema = tenant["schema_name"]
        tenant_retention = int(tenant["effective_retention_days"])

        try:
            cameras = _get_cameras_for_tenant(str(tenant_id), tenant_retention)
        except Exception as exc:
            logger.error(
                "retention_expiry_cameras_error: tenant=%s err=%s", tenant_id, exc
            )
            continue

        for cam in cameras:
            camera_id = cam["id"]
            effective_days = int(cam["effective_days"])
            try:
                n = _expire_camera_evidence(schema, str(camera_id), effective_days, storage)
                if n:
                    logger.info(
                        "retention_expired: schema=%s camera=%s days=%d deleted=%d",
                        schema, camera_id, effective_days, n,
                    )
                total_deleted += n
                total_cameras += 1
            except Exception as exc:
                logger.error(
                    "retention_expiry_camera_error: schema=%s camera=%s err=%s",
                    schema, camera_id, exc,
                )

    logger.info(
        "retention_expiry_done: cameras=%d total_deleted=%d",
        total_cameras, total_deleted,
    )
