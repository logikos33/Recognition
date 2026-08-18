"""
Issue #419 — `training_jobs.started_at` mentia por ~8×.

Medido no job `f31f5381`:

| fonte | início | fim | duração |
|---|---|---|---|
| `training_jobs` | 11:44:54 | 11:45:41 | **0,8 min** |
| `pod.log` (R2)  | 11:38:43 | 11:45:08 | **6,4 min** |

O dispatch JÁ carimba `started_at` antes de provisionar o pod
(`tasks/training.py`, `WHEN started_at IS NULL THEN NOW()`). Só que o primeiro
callback do pod passava por `update_job_status(status='running')`, que fazia
`started_at = NOW()` seco — **sobrescrevendo** o carimbo do dispatch e jogando
fora provisionamento, download e boa parte do treino.

Qualquer conta de custo, throughput ou SLA feita com
`completed_at - started_at` saía errada por 8×.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.training_repository import TrainingRepository


def _repo():
    cur = MagicMock()
    cur.fetchone.return_value = {"id": str(uuid4())}

    @contextmanager
    def _conn_ctx():
        conn = MagicMock()
        conn.cursor.return_value = cur
        yield conn

    pool = MagicMock()
    pool.get_connection.side_effect = _conn_ctx
    return TrainingRepository(pool), cur


def _sql_do_update(cur) -> str:
    return " ".join(cur.execute.call_args.args[0].split())


class TestStartedAtPrimeiraEscritaVence:
    def test_running_nao_sobrescreve_started_at_existente(self):
        repo, cur = _repo()
        repo.update_job_status(uuid4(), "running", progress=10)
        sql = _sql_do_update(cur)
        assert "started_at = COALESCE(started_at, NOW())" in sql
        assert "started_at = NOW()" not in sql, (
            "NOW() seco apaga o carimbo do dispatch — é o bug de 8× do #419"
        )

    def test_completed_ainda_carimba_completed_at(self):
        repo, cur = _repo()
        repo.update_job_status(uuid4(), "completed", progress=100)
        assert "completed_at = NOW()" in _sql_do_update(cur)

    def test_status_intermediario_nao_mexe_em_started_at(self):
        repo, cur = _repo()
        repo.update_job_status(uuid4(), "queued", progress=0)
        assert "started_at" not in _sql_do_update(cur)
