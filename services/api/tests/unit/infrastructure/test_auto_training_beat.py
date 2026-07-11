"""
Tests: auto_training.py — Celery beat de re-treino automático (WS-C4 + X-5).

Bugs cobertos (falha-antes/passa-depois):
  - usava coluna finished_at (não existe em training_jobs; a real é completed_at)
  - chamava dispatch_training.delay(tenant_id) com 1 arg na posição de job_id
    (assinatura real: job_id + dataset_version_id) e sem criar o job row antes
  - tenant sem dataset_version pronta deve ser pulado com log (sem crash)
  - X-5: nome da task Celery no padrão curto do pipeline
    (tasks.<módulo>.<função>) e consistente com o beat schedule.
"""
import sys
import types
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# Garante import REAL de celery_app/auto_training mesmo que outro arquivo de
# teste tenha instalado um stub transparente de celery_app em sys.modules
# (padrão de tests/unit/domain/test_versioning_helpers.py). Stubs criados via
# types.ModuleType não têm __file__.
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_AUTO_TRAINING_KEY = "app.infrastructure.queue.tasks.auto_training"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_AUTO_TRAINING_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue import celery_app as celery_app_module  # noqa: E402
from app.infrastructure.queue.tasks import auto_training  # noqa: E402

_DT = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakePool:
    """Pool fake: get_connection() context manager + cursor com side_effects."""

    def __init__(self, fetchone_results: list) -> None:
        self.cursor = MagicMock()
        self.cursor.fetchone.side_effect = list(fetchone_results)
        self.conn = MagicMock()
        self.conn.cursor.return_value.__enter__.return_value = self.cursor
        self.conn.cursor.return_value.__exit__.return_value = False

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.conn

    def executed_sql(self) -> list[str]:
        return [str(call.args[0]) for call in self.cursor.execute.call_args_list]


@pytest.fixture
def fake_training(monkeypatch):
    """Substitui tasks.training por módulo fake (import local em auto_training)."""
    fake = types.ModuleType("app.infrastructure.queue.tasks.training")
    fake.dispatch_training = MagicMock()
    monkeypatch.setitem(
        sys.modules, "app.infrastructure.queue.tasks.training", fake
    )
    return fake


class TestTaskNameConsistency:
    """X-5: nome da task deve seguir o padrão curto e casar com o beat schedule."""

    def test_task_name_follows_pipeline_short_pattern(self):
        assert (
            auto_training.check_auto_retraining.name
            == "tasks.auto_training.check_auto_retraining"
        )

    def test_beat_schedule_references_exact_task_name(self):
        beat = celery_app_module.celery.conf.beat_schedule
        entry = beat["auto-retraining-check"]
        assert entry["task"] == auto_training.check_auto_retraining.name
        assert entry["options"]["queue"] == "training"


class TestCheckAndTriggerTenantQueries:
    """Coluna real é completed_at — finished_at não existe em training_jobs."""

    def test_uses_completed_at_not_finished_at(self, fake_training):
        pool = _FakePool([
            {"completed_at": _DT},
            {"cnt": 0},
            {"cnt": 100},
        ])
        # crescimento 0% < threshold → não dispara
        auto_training._check_and_trigger_tenant(pool, str(uuid4()), 10)

        all_sql = " ".join(pool.executed_sql())
        assert "finished_at" not in all_sql
        assert "completed_at" in all_sql
        assert fake_training.dispatch_training.delay.call_count == 0


class TestTriggerFlow:
    """Job row criado ANTES do dispatch; .delay(job_id, dataset_version_id)."""

    def test_creates_job_row_and_dispatches_with_job_and_dataset_ids(
        self, fake_training
    ):
        dv_id, job_id, user_id = uuid4(), uuid4(), uuid4()
        pool = _FakePool([
            {"completed_at": _DT},
            {"cnt": 50},
            {"cnt": 100},
            {"id": dv_id, "user_id": user_id},   # última dataset_version pronta
            {"id": job_id},                       # INSERT ... RETURNING id
        ])

        with pytest.raises(auto_training._TrainingTriggered):
            auto_training._check_and_trigger_tenant(pool, str(uuid4()), 10)

        fake_training.dispatch_training.delay.assert_called_once_with(
            str(job_id), str(dv_id)
        )
        assert any(
            "INSERT INTO training_jobs" in sql for sql in pool.executed_sql()
        )

    def test_no_dataset_version_skips_without_dispatch(self, fake_training):
        pool = _FakePool([
            {"completed_at": _DT},
            {"cnt": 50},
            {"cnt": 100},
            None,  # tenant sem dataset_version pronta
        ])

        # não levanta _TrainingTriggered nem crasha — apenas loga e pula
        auto_training._check_and_trigger_tenant(pool, str(uuid4()), 10)

        assert fake_training.dispatch_training.delay.call_count == 0
        assert not any(
            "INSERT INTO training_jobs" in sql for sql in pool.executed_sql()
        )

    def test_no_previous_completed_job_uses_epoch_zero(self, fake_training):
        dv_id, job_id, user_id = uuid4(), uuid4(), uuid4()
        pool = _FakePool([
            None,           # nenhum job concluído ainda
            {"cnt": 50},
            {"cnt": 0},
            {"id": dv_id, "user_id": user_id},
            {"id": job_id},
        ])

        with pytest.raises(auto_training._TrainingTriggered):
            auto_training._check_and_trigger_tenant(pool, str(uuid4()), 10)

        # 2ª query (frames novos) recebe o epoch zero como corte
        count_call = pool.cursor.execute.call_args_list[1]
        assert auto_training._EPOCH_ZERO in count_call.args[1]


class TestCheckAutoRetrainingTask:
    def test_disabled_env_returns_skipped(self, monkeypatch):
        monkeypatch.delenv("AUTO_TRAIN_ENABLED", raising=False)
        result = auto_training.check_auto_retraining()
        assert result == {"checked": 0, "triggered": 0, "skipped_disabled": True}
