"""
Tests: tasks/model_drift.py — drift monitor (WS-C3, Celery Beat).

Cobre:
  - nome da task + beat schedule (mesmo padrão X-5 de test_auto_training_beat.py)
  - _compute_window_for_camera: sem modelo resolvido pula; já computado
    (exists_for_window) pula; sem baseline grava drift_score=0; com baseline
    calcula |Δavg_confidence| + L1(distribuição); dispara auto-retraining
    quando acima do limiar
  - compute_drift_metrics: agrega tenants ativos, continua após erro de 1 tenant
"""
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# Mesmo guard de test_auto_training_beat.py / test_inference_auto_capture.py —
# evita stub de celery_app poluído por outro arquivo de teste.
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_MODEL_DRIFT_KEY = "app.infrastructure.queue.tasks.model_drift"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_MODEL_DRIFT_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue import celery_app as celery_app_module  # noqa: E402
from app.infrastructure.queue.tasks import model_drift  # noqa: E402

TENANT_ID = "11111111-1111-1111-1111-111111111111"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"
MODEL_ID = "55555555-5555-5555-5555-555555555555"
WINDOW_START = datetime(2026, 7, 11, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 7, 12, tzinfo=timezone.utc)


class TestTaskNameConsistency:
    def test_task_name_follows_pipeline_short_pattern(self):
        assert model_drift.compute_drift_metrics.name == "tasks.model_drift.compute_drift_metrics"

    def test_beat_schedule_references_exact_task_name(self):
        beat = celery_app_module.celery.conf.beat_schedule
        entry = beat["model-drift-check"]
        assert entry["task"] == model_drift.compute_drift_metrics.name
        assert entry["options"]["queue"] == "training"


class TestComputeWindowForCamera:
    def _repos(self, monkeypatch, resolved=None, already_exists=False):
        alert_repo = MagicMock()
        drift_repo = MagicMock()
        monkeypatch.setattr(
            model_drift, "_resolve_effective_model",
            lambda camera_id: resolved if resolved is not None else {"model_id": MODEL_ID},
        )
        drift_repo.exists_for_window.return_value = already_exists
        alert_repo.count_in_window.return_value = 10
        alert_repo.avg_confidence_in_window.return_value = 0.8
        alert_repo.violations_by_class.return_value = [
            {"class": "no_helmet", "count": 8}, {"class": "no_vest", "count": 2},
        ]
        drift_repo.get_baseline.return_value = None
        return alert_repo, drift_repo

    def test_no_model_resolved_skips(self, monkeypatch):
        alert_repo, drift_repo = self._repos(monkeypatch, resolved=None)
        monkeypatch.setattr(model_drift, "_resolve_effective_model", lambda camera_id: None)

        result = model_drift._compute_window_for_camera(
            alert_repo, drift_repo, TENANT_ID, CAMERA_ID, WINDOW_START, WINDOW_END
        )
        assert result is False
        drift_repo.create.assert_not_called()

    def test_already_computed_skips(self, monkeypatch):
        alert_repo, drift_repo = self._repos(monkeypatch, already_exists=True)
        result = model_drift._compute_window_for_camera(
            alert_repo, drift_repo, TENANT_ID, CAMERA_ID, WINDOW_START, WINDOW_END
        )
        assert result is False
        drift_repo.create.assert_not_called()

    def test_no_baseline_drift_score_is_zero(self, monkeypatch):
        alert_repo, drift_repo = self._repos(monkeypatch)
        drift_repo.get_baseline.return_value = None

        result = model_drift._compute_window_for_camera(
            alert_repo, drift_repo, TENANT_ID, CAMERA_ID, WINDOW_START, WINDOW_END
        )
        assert result is True
        payload = drift_repo.create.call_args.args[0]
        assert payload["drift_score"] == 0.0
        assert payload["model_id"] == MODEL_ID
        assert payload["class_distribution"] == {"no_helmet": 0.8, "no_vest": 0.2}

    def test_drift_score_computed_against_baseline(self, monkeypatch):
        alert_repo, drift_repo = self._repos(monkeypatch)
        drift_repo.get_baseline.return_value = {
            "avg_confidence": 0.6,
            "class_distribution": {"no_helmet": 0.5, "no_vest": 0.5},
        }

        model_drift._compute_window_for_camera(
            alert_repo, drift_repo, TENANT_ID, CAMERA_ID, WINDOW_START, WINDOW_END
        )
        payload = drift_repo.create.call_args.args[0]
        # |0.8-0.6| + (|0.8-0.5| + |0.2-0.5|) = 0.2 + 0.6 = 0.8
        assert payload["drift_score"] == pytest.approx(0.8)

    def test_high_drift_triggers_auto_retraining(self, monkeypatch):
        alert_repo, drift_repo = self._repos(monkeypatch)
        drift_repo.get_baseline.return_value = {
            "avg_confidence": 0.0, "class_distribution": {},
        }
        mock_retrain = MagicMock()
        fake_auto_training = type(sys)("app.infrastructure.queue.tasks.auto_training")
        fake_auto_training.check_auto_retraining = mock_retrain
        monkeypatch.setitem(
            sys.modules, "app.infrastructure.queue.tasks.auto_training", fake_auto_training
        )

        model_drift._compute_window_for_camera(
            alert_repo, drift_repo, TENANT_ID, CAMERA_ID, WINDOW_START, WINDOW_END
        )
        mock_retrain.delay.assert_called_once()

    def test_low_drift_does_not_trigger_auto_retraining(self, monkeypatch):
        alert_repo, drift_repo = self._repos(monkeypatch)
        drift_repo.get_baseline.return_value = {
            "avg_confidence": 0.8, "class_distribution": {"no_helmet": 0.8, "no_vest": 0.2},
        }
        mock_retrain = MagicMock()
        fake_auto_training = type(sys)("app.infrastructure.queue.tasks.auto_training")
        fake_auto_training.check_auto_retraining = mock_retrain
        monkeypatch.setitem(
            sys.modules, "app.infrastructure.queue.tasks.auto_training", fake_auto_training
        )

        model_drift._compute_window_for_camera(
            alert_repo, drift_repo, TENANT_ID, CAMERA_ID, WINDOW_START, WINDOW_END
        )
        mock_retrain.delay.assert_not_called()


class TestComputeForTenant:
    def test_iterates_cameras_and_counts_computed(self, monkeypatch):
        alert_repo = MagicMock()
        alert_repo.distinct_cameras_in_window.return_value = [CAMERA_ID, "other-camera"]
        monkeypatch.setattr(model_drift, "_get_alert_repo", lambda: alert_repo)
        monkeypatch.setattr(model_drift, "_get_drift_repo", lambda: MagicMock())
        monkeypatch.setattr(
            model_drift, "_compute_window_for_camera",
            MagicMock(side_effect=[True, False]),
        )

        computed = model_drift._compute_for_tenant(TENANT_ID, WINDOW_START, WINDOW_END)
        assert computed == 1


class _FakeCursor:
    def __init__(self, fetchall_result):
        self._result = fetchall_result

    def execute(self, *a, **k):
        pass

    def fetchall(self):
        return self._result

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, fetchall_result):
        self._cursor = _FakeCursor(fetchall_result)

    def cursor(self):
        return self._cursor


class _FakePool:
    def __init__(self, tenants):
        self._tenants = tenants

    @contextmanager
    def get_connection(self):
        yield _FakeConn(self._tenants)


class TestComputeDriftMetrics:
    def test_pool_not_initialized_returns_error(self, monkeypatch):
        monkeypatch.setattr(model_drift.DatabasePool, "get_instance", staticmethod(lambda: None))
        result = model_drift.compute_drift_metrics.apply().get()
        assert result["error"] == "pool_not_initialized"

    def test_checks_all_active_tenants_and_continues_after_error(self, monkeypatch):
        pool = _FakePool([{"id": "tenant-1"}, {"id": "tenant-2"}])
        monkeypatch.setattr(model_drift.DatabasePool, "get_instance", staticmethod(lambda: pool))
        monkeypatch.setattr(
            model_drift, "_compute_for_tenant",
            MagicMock(side_effect=[RuntimeError("db blip"), 3]),
        )

        result = model_drift.compute_drift_metrics.apply().get()
        assert result["checked"] == 1
        assert result["computed"] == 3

    def test_no_tenants_returns_zero(self, monkeypatch):
        pool = _FakePool([])
        monkeypatch.setattr(model_drift.DatabasePool, "get_instance", staticmethod(lambda: pool))
        result = model_drift.compute_drift_metrics.apply().get()
        assert result == {"checked": 0, "computed": 0}
