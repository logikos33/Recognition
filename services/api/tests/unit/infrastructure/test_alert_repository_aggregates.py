"""
Tests: AlertRepository — agregados BI (mutirão WS3).

Cobertura:
  - count_in_window / violations_by_class / top_cameras_by_alerts
  - camera_hours_with_violation / violation_hours_by_class
  - timeline_by_bucket aceita bucket='week' (antes degradava para hour)
  - tenant_id sempre presente no SQL e nos params (C-01)
  - filtros passados como parâmetros %s — zero f-string de input (C-05)
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.alert_repository import AlertRepository

FROM_TS = datetime(2026, 6, 1, tzinfo=timezone.utc)
TO_TS = datetime(2026, 6, 8, tzinfo=timezone.utc)


class _MockPool:
    def __init__(self) -> None:
        self.mock_cursor = MagicMock()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = {"count": 0}
        self.mock_conn = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.mock_conn


def _make_repo() -> tuple[AlertRepository, _MockPool]:
    pool = _MockPool()
    return AlertRepository(pool), pool  # type: ignore[arg-type]


def _last_call(pool: _MockPool):
    call = pool.mock_cursor.execute.call_args_list[-1]
    return call[0][0], call[0][1]


class TestCountInWindow:

    def test_tenant_scoped(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.count_in_window(tenant, FROM_TS, TO_TS)
        sql, params = _last_call(pool)
        assert "a.tenant_id = %s" in sql
        assert params[0] == tenant

    def test_module_and_camera_filters_parametrized(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        cams = [str(uuid4()), str(uuid4())]
        repo.count_in_window(tenant, FROM_TS, TO_TS, module_code="epi", camera_ids=cams)
        sql, params = _last_call(pool)
        assert "a.module_code = %s" in sql
        assert "a.camera_id IN (%s,%s)" in sql
        assert "epi" in params
        for cam in cams:
            assert cam in params

    def test_returns_zero_when_no_row(self):
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = None
        assert repo.count_in_window(str(uuid4()), FROM_TS, TO_TS) == 0


class TestViolationsByClass:

    def test_tenant_scoped_and_jsonb_expansion(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.violations_by_class(tenant, FROM_TS, TO_TS)
        sql, params = _last_call(pool)
        assert "a.tenant_id = %s" in sql
        assert "jsonb_array_elements" in sql
        assert "GROUP BY v->>'class'" in sql
        assert params[0] == tenant

    def test_class_names_filter_parametrized(self):
        repo, pool = _make_repo()
        repo.violations_by_class(
            str(uuid4()), FROM_TS, TO_TS, class_names=["no_helmet", "no_vest"]
        )
        sql, params = _last_call(pool)
        assert "v->>'class' = ANY(%s)" in sql
        assert ["no_helmet", "no_vest"] in params

    def test_malicious_class_name_never_interpolated(self):
        repo, pool = _make_repo()
        malicious = "'; DROP TABLE alerts; --"
        repo.violations_by_class(str(uuid4()), FROM_TS, TO_TS, class_names=[malicious])
        sql, params = _last_call(pool)
        assert malicious not in sql
        assert [malicious] in params


class TestTopCamerasByAlerts:

    def test_tenant_scoped_with_camera_join(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.top_cameras_by_alerts(tenant, FROM_TS, TO_TS, module_code="epi", limit=10)
        sql, params = _last_call(pool)
        assert "a.tenant_id = %s" in sql
        assert "LEFT JOIN cameras c ON a.camera_id = c.id AND c.tenant_id = a.tenant_id" in sql
        assert "LIMIT %s" in sql
        assert params[0] == tenant
        assert params[-1] == 10


class TestComplianceAggregates:

    def test_camera_hours_with_violation_tenant_scoped(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        since = FROM_TS
        repo.camera_hours_with_violation(tenant, "epi", since)
        sql, params = _last_call(pool)
        assert "a.tenant_id = %s" in sql
        assert "COUNT(DISTINCT (a.camera_id, date_trunc('hour', a.created_at)))" in sql
        assert params == (tenant, "epi", since)

    def test_violation_hours_by_class_tenant_scoped(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.violation_hours_by_class(tenant, "epi", FROM_TS)
        sql, params = _last_call(pool)
        assert "a.tenant_id = %s" in sql
        assert "jsonb_array_elements" in sql
        assert params == (tenant, "epi", FROM_TS)


class TestTimelineWeekBucket:

    def test_week_bucket_accepted(self):
        """Antes: 'week' fora do allowlist do repo → degradava para hour (mismatch rota↔repo)."""
        repo, pool = _make_repo()
        repo.timeline_by_bucket(str(uuid4()), FROM_TS, TO_TS, bucket="week")
        sql, _ = _last_call(pool)
        assert "date_trunc('week'" in sql

    def test_invalid_bucket_still_falls_back_to_hour(self):
        repo, pool = _make_repo()
        repo.timeline_by_bucket(str(uuid4()), FROM_TS, TO_TS, bucket="month'; DROP--")
        sql, _ = _last_call(pool)
        assert "date_trunc('hour'" in sql


class TestDriftAggregates:
    """WS-C3 — sinal consumido por tasks/model_drift.py."""

    def test_distinct_cameras_in_window_tenant_scoped(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        pool.mock_cursor.fetchall.return_value = [
            {"camera_id": "cam-1"}, {"camera_id": "cam-2"},
        ]
        result = repo.distinct_cameras_in_window(tenant, FROM_TS, TO_TS)
        sql, params = _last_call(pool)
        assert "DISTINCT camera_id" in sql
        assert "tenant_id = %s" in sql
        assert params == (tenant, FROM_TS, TO_TS)
        assert result == ["cam-1", "cam-2"]

    def test_avg_confidence_in_window_tenant_scoped(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        pool.mock_cursor.fetchone.return_value = {"avg_confidence": 0.73}
        result = repo.avg_confidence_in_window(tenant, FROM_TS, TO_TS, camera_ids=["cam-1"])
        sql, params = _last_call(pool)
        assert "AVG(a.confidence)" in sql
        assert "a.tenant_id = %s" in sql
        assert params[0] == tenant
        assert result == 0.73

    def test_avg_confidence_in_window_no_alerts_returns_zero(self):
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = {"avg_confidence": None}
        result = repo.avg_confidence_in_window(str(uuid4()), FROM_TS, TO_TS)
        assert result == 0.0
