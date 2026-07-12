"""
Recognition — Drift Monitor Task (WS-C3, ADR-0037, Celery Beat).

Compara o sinal de confiança/distribuição de classes da janela do dia
anterior (UTC) contra o baseline (primeira janela salva) por par
modelo×câmera, gravando o resultado em model_drift_metrics (migration
101). Idempotente por janela via DriftMetricsRepository.exists_for_window
(o beat roda 1x/dia — celery_app.py — mas o guard permite reexecução
manual sem duplicar).

class_distribution é persistido como PROPORÇÕES (soma 1.0), não contagens
brutas — necessário pra L1(distribuição) ser comparável entre janelas com
volumes de alerta diferentes.

LIMITAÇÃO DOCUMENTADA (mesma premissa da migration 101, não é bug novo):
o sinal vem de `alerts`, que só existe pra frames COM violação
(_has_violation em tasks/inference.py). Frames 100% conformes são
invisíveis a este cálculo — um tenant com compliance melhorando (menos
violações) gera MENOS dado pro drift, não mais confiança no modelo.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

_DRIFT_SCORE_ALERT_THRESHOLD = float(os.environ.get("DRIFT_SCORE_ALERT_THRESHOLD", "0.3"))


def _get_alert_repo():  # type: ignore[no-untyped-def]
    from app.infrastructure.database.repositories.alert_repository import AlertRepository
    return AlertRepository(DatabasePool.get_instance())


def _get_drift_repo():  # type: ignore[no-untyped-def]
    from app.infrastructure.database.repositories.drift_metrics_repository import (
        DriftMetricsRepository,
    )
    return DriftMetricsRepository(DatabasePool.get_instance())


def _resolve_effective_model(camera_id: str) -> dict | None:
    """Mesma cascata usada pela inferência ao vivo (model_deployments ativo
    → cameras.model_{module}_id → trained_models) — import local evita
    ciclo no module-load do worker."""
    from app.infrastructure.queue.tasks.inference import _resolve_camera_model
    return _resolve_camera_model(str(camera_id))


def _normalize(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def _l1_distance(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    return sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)


def _compute_window_for_camera(
    alert_repo, drift_repo, tenant_id: str, camera_id: str,
    window_start: datetime, window_end: datetime,
) -> bool:
    """Calcula e grava a janela de drift de uma câmera. Retorna True se
    gravou (False se pulou — sem modelo resolvido ou já computado)."""
    resolved = _resolve_effective_model(camera_id)
    if not resolved or not resolved.get("model_id"):
        return False

    model_id = resolved["model_id"]
    if drift_repo.exists_for_window(model_id, camera_id, tenant_id, window_start):
        return False

    detections_count = alert_repo.count_in_window(
        tenant_id, window_start, window_end, camera_ids=[camera_id]
    )
    avg_confidence = alert_repo.avg_confidence_in_window(
        tenant_id, window_start, window_end, camera_ids=[camera_id]
    )
    class_counts = {
        row["class"]: row["count"]
        for row in alert_repo.violations_by_class(
            tenant_id, window_start, window_end, camera_ids=[camera_id]
        )
    }
    class_distribution = _normalize(class_counts)

    baseline = drift_repo.get_baseline(model_id, camera_id, tenant_id)
    if baseline is None:
        drift_score = 0.0
    else:
        baseline_confidence = baseline.get("avg_confidence") or 0.0
        baseline_distribution = baseline.get("class_distribution") or {}
        drift_score = abs(avg_confidence - baseline_confidence) + _l1_distance(
            class_distribution, baseline_distribution
        )

    drift_repo.create({
        "tenant_id": tenant_id,
        "model_id": model_id,
        "camera_id": camera_id,
        "window_start": window_start,
        "window_end": window_end,
        "detections_count": detections_count,
        "avg_confidence": avg_confidence,
        "class_distribution": class_distribution,
        "drift_score": drift_score,
    })

    if drift_score > _DRIFT_SCORE_ALERT_THRESHOLD:
        logger.warning(
            "drift_alert_high: tenant=%s camera=%s model=%s score=%.4f",
            tenant_id, camera_id, model_id, drift_score,
        )
        try:
            from app.infrastructure.queue.tasks.auto_training import check_auto_retraining
            check_auto_retraining.delay()
        except Exception as exc:  # noqa: BLE001
            logger.warning("drift_retrain_trigger_failed: err=%s", exc)

    return True


def _compute_for_tenant(
    tenant_id: str, window_start: datetime, window_end: datetime
) -> int:
    alert_repo = _get_alert_repo()
    drift_repo = _get_drift_repo()

    camera_ids = alert_repo.distinct_cameras_in_window(tenant_id, window_start, window_end)
    computed = 0
    for camera_id in camera_ids:
        if _compute_window_for_camera(
            alert_repo, drift_repo, tenant_id, camera_id, window_start, window_end
        ):
            computed += 1
    return computed


@celery.task(
    bind=True,
    name="tasks.model_drift.compute_drift_metrics",
    queue="training",
)
def compute_drift_metrics(self) -> dict:
    """Janela: dia UTC anterior completo (00:00 a 00:00). Percorre tenants
    ativos, dentro de cada um só as câmeras que geraram alerta na janela.
    """
    pool = DatabasePool.get_instance()
    if pool is None:
        logger.error("model_drift_check: DatabasePool not initialized")
        return {"checked": 0, "computed": 0, "error": "pool_not_initialized"}

    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    window_end = window_start + timedelta(days=1)

    try:
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM tenants WHERE is_active = true")
                tenants = cur.fetchall()
    except Exception as exc:
        logger.error("model_drift_check: failed to fetch tenants err=%s", exc, exc_info=True)
        return {"checked": 0, "computed": 0, "error": str(exc)}

    checked = 0
    computed = 0
    for tenant in tenants:
        tenant_id = str(tenant["id"])
        try:
            computed += _compute_for_tenant(tenant_id, window_start, window_end)
            checked += 1
        except Exception as exc:
            logger.error(
                "model_drift_check: tenant=%s err=%s", tenant_id, exc, exc_info=True
            )

    logger.info(
        "model_drift_check: done checked=%d computed=%d window=%s/%s",
        checked, computed, window_start.isoformat(), window_end.isoformat(),
    )
    return {"checked": checked, "computed": computed}
