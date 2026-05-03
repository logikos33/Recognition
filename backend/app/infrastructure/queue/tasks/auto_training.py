"""
EPI Monitor V2 — Auto-Retraining Check Task (Celery Beat).

Verifica periodicamente se algum tenant atingiu o limiar de crescimento de
frames anotados e, em caso positivo, dispara automaticamente um novo job de
treinamento via `dispatch_training`.

Env vars:
  AUTO_TRAIN_ENABLED         "true" | "false"  (default "false")
  AUTO_TRAIN_THRESHOLD_PCT   int               (default 10)
"""
import logging
import os
from datetime import datetime, timezone

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

_EPOCH_ZERO = datetime(1970, 1, 1, tzinfo=timezone.utc)


@celery.task(
    name="app.infrastructure.queue.tasks.auto_training.check_auto_retraining",
    bind=True,
)
def check_auto_retraining(self) -> dict:
    """Verifica crescimento de frames anotados por tenant e dispara re-treino automático.

    Returns:
        dict com contagem de tenants verificados e disparados.
    """
    if os.environ.get("AUTO_TRAIN_ENABLED", "false").lower() != "true":
        logger.debug("auto_train_check: disabled (AUTO_TRAIN_ENABLED != true)")
        return {"checked": 0, "triggered": 0, "skipped_disabled": True}

    threshold_pct = int(os.environ.get("AUTO_TRAIN_THRESHOLD_PCT", "10"))

    pool = DatabasePool.get_instance()
    if pool is None:
        logger.error("auto_train_check: DatabasePool not initialized")
        return {"checked": 0, "triggered": 0, "error": "pool_not_initialized"}

    # Busca todos os tenants ativos
    try:
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, schema_name FROM tenants WHERE is_active = true"
                )
                tenants = cur.fetchall()
    except Exception as exc:
        logger.error("auto_train_check: failed to fetch tenants err=%s", exc, exc_info=True)
        return {"checked": 0, "triggered": 0, "error": str(exc)}

    checked = 0
    triggered = 0

    for tenant in tenants:
        tenant_id = tenant["id"]
        try:
            _check_and_trigger_tenant(pool, tenant_id, threshold_pct)
            checked += 1
            # Re-lê triggered após possível disparo
        except _TrainingTriggered:
            checked += 1
            triggered += 1
        except Exception as exc:
            logger.error(
                "auto_train_check: tenant=%s err=%s", tenant_id, exc, exc_info=True
            )

    logger.info(
        "auto_train_check: done checked=%d triggered=%d threshold=%d%%",
        checked, triggered, threshold_pct,
    )
    return {"checked": checked, "triggered": triggered}


class _TrainingTriggered(Exception):
    """Sinaliza que o treinamento foi disparado para este tenant (fluxo normal)."""


def _check_and_trigger_tenant(pool: DatabasePool, tenant_id: str, threshold_pct: int) -> None:
    """Verifica e, se necessário, dispara treinamento para um único tenant.

    Raises:
        _TrainingTriggered: quando o treinamento é disparado com sucesso.
    """
    with pool.get_connection() as conn:
        with conn.cursor() as cur:
            # Último job de treino concluído
            cur.execute(
                """SELECT finished_at
                   FROM training_jobs
                   WHERE tenant_id = %s AND status = 'completed'
                   ORDER BY finished_at DESC
                   LIMIT 1""",
                (tenant_id,),
            )
            last_row = cur.fetchone()
            last_trained_at = last_row["finished_at"] if last_row else _EPOCH_ZERO

            # Frames anotados APÓS o último treino (novos)
            cur.execute(
                """SELECT COUNT(*) AS cnt
                   FROM training_frames
                   WHERE tenant_id = %s
                     AND is_annotated = true
                     AND created_at > %s""",
                (tenant_id, last_trained_at),
            )
            new_frames = cur.fetchone()["cnt"]

            # Frames anotados ATÉ o último treino (base)
            cur.execute(
                """SELECT COUNT(*) AS cnt
                   FROM training_frames
                   WHERE tenant_id = %s
                     AND is_annotated = true
                     AND created_at <= %s""",
                (tenant_id, last_trained_at),
            )
            base_frames = cur.fetchone()["cnt"]

    growth_pct = new_frames / max(base_frames, 1) * 100

    logger.info(
        "auto_train_check: tenant=%s new=%d base=%d growth=%.1f%% threshold=%d%%",
        tenant_id, new_frames, base_frames, growth_pct, threshold_pct,
    )

    if growth_pct >= threshold_pct:
        # Import local para evitar import circular no module-load
        from app.infrastructure.queue.tasks.training import dispatch_training  # noqa: PLC0415

        dispatch_training.delay(str(tenant_id))
        logger.info(
            "auto_train_triggered: tenant=%s growth=%.1f%%", tenant_id, growth_pct
        )
        raise _TrainingTriggered()
