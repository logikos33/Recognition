"""
Tests: celery_app.py — schedule de beat CURADO.

Contexto (fix): as tasks agendadas não disparavam porque não havia processo
beat. Ligar o beat com o schedule cheio era destrutivo (os cleanups apagam R2)
e inútil para as que roteiam para filas sem consumidor. O schedule ativo foi
curado para conter só o que é seguro E consumível neste deploy.

Guard-rail (falha-antes/passa-depois):
  - ATIVO = { compliance-daily-report (reports), quality-cep-baseline +
    quality-shift-reports (quality_cep), model-drift-check (training),
    runpod-reconcile-pods (training),
    edge-propagation-reconcile-timeouts (training) } — todas com worker
    consumindo a fila (ver railway_start.py). runpod-reconcile-pods
    (camada 3/3 de garantia de morte de pods GPU, ver
    infrastructure/gpu/runpod_runner.py) só TERMINA pods RunPod
    órfãos/expirados — nunca cria GPU nem mexe em dado do produto, seguro
    por natureza (mesmo raciocínio de model-drift-check).
    edge-propagation-reconcile-timeouts (task "propagação no edge") é
    honestidade de estado pra propagação onsite — não há pod pra matar, só
    um UPDATE de status (mesmo raciocínio de segurança).
  - DEFERRED = os 2 cleanups destrutivos (R2) + wiser-retry + auto-retraining.
    NUNCA no ativo.
Se alguém reintroduzir um cleanup no schedule ativo, este teste falha.
"""
import sys

# Garante import REAL do celery_app mesmo que outro teste tenha instalado um
# stub transparente em sys.modules (mesmo padrão de test_auto_training_beat.py).
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    sys.modules.pop(_CELERY_APP_KEY, None)

from app.infrastructure.queue import celery_app  # noqa: E402

ALL_TEN = {
    "compliance-daily-report",
    "quality-cep-baseline",
    "quality-shift-reports",
    "model-drift-check",
    "runpod-reconcile-pods",
    "edge-propagation-reconcile-timeouts",
    "quality-cleanup-recordings",
    "quality-cleanup-clips",
    "quality-wiser-retry",
    "auto-retraining-check",
}
ACTIVE_EXPECTED = {
    "compliance-daily-report",
    "quality-cep-baseline",
    "quality-shift-reports",
    "model-drift-check",
    "runpod-reconcile-pods",
    "edge-propagation-reconcile-timeouts",
}
DEFERRED_EXPECTED = {
    "quality-cleanup-recordings",
    "quality-cleanup-clips",
    "quality-wiser-retry",
    "auto-retraining-check",
}
DESTRUCTIVE = {"quality-cleanup-recordings", "quality-cleanup-clips"}


def _active() -> set:
    return set(celery_app.celery.conf.beat_schedule.keys())


class TestCuratedBeatSchedule:
    def test_active_schedule_equals_safe_constant(self):
        assert _active() == set(celery_app.SAFE_BEAT_SCHEDULE.keys())

    def test_active_is_exactly_the_six_safe_tasks(self):
        assert _active() == ACTIVE_EXPECTED

    def test_compliance_daily_report_is_scheduled(self):
        entry = celery_app.celery.conf.beat_schedule["compliance-daily-report"]
        assert entry["task"] == (
            "app.infrastructure.queue.tasks.compliance."
            "generate_daily_compliance_reports"
        )
        assert entry["options"]["queue"] == "reports"

    def test_quality_cep_tasks_route_to_quality_cep_queue(self):
        # cep-baseline e shift-reports só rodam se o worker consumir 'quality_cep'
        beat = celery_app.celery.conf.beat_schedule
        assert beat["quality-cep-baseline"]["options"]["queue"] == "quality_cep"
        assert beat["quality-shift-reports"]["options"]["queue"] == "quality_cep"

    def test_runpod_reconcile_pods_is_scheduled_every_5min_on_training_queue(self):
        entry = celery_app.celery.conf.beat_schedule["runpod-reconcile-pods"]
        assert entry["task"] == "tasks.gpu_reconciler.reconcile_runpod_pods"
        assert entry["schedule"] == 300
        assert entry["options"]["queue"] == "training"

    def test_edge_propagation_reconcile_timeouts_is_scheduled_every_5min_on_training_queue(self):
        entry = celery_app.celery.conf.beat_schedule["edge-propagation-reconcile-timeouts"]
        assert entry["task"] == "tasks.gpu_reconciler.reconcile_edge_propagation_timeouts"
        assert entry["schedule"] == 300
        assert entry["options"]["queue"] == "training"

    def test_destructive_cleanups_never_active_and_are_deferred(self):
        assert DESTRUCTIVE.isdisjoint(_active())
        assert DESTRUCTIVE <= set(celery_app.DEFERRED_BEAT_SCHEDULE.keys())

    def test_deferred_holds_exactly_the_four_excluded(self):
        assert set(celery_app.DEFERRED_BEAT_SCHEDULE.keys()) == DEFERRED_EXPECTED

    def test_safe_and_deferred_do_not_overlap(self):
        assert set(celery_app.SAFE_BEAT_SCHEDULE).isdisjoint(
            celery_app.DEFERRED_BEAT_SCHEDULE
        )

    def test_no_task_is_silently_dropped(self):
        assert (
            set(celery_app.SAFE_BEAT_SCHEDULE) | set(celery_app.DEFERRED_BEAT_SCHEDULE)
            == ALL_TEN
        )
