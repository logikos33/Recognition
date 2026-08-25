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


def _call_at(pool: _MockPool, index: int):
    """Query de índice arbitrário — os agregados de polaridade fazem DUAS:
    primeiro o catálogo de presença, depois o agregado."""
    call = pool.mock_cursor.execute.call_args_list[index]
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

    def test_presence_class_is_not_counted_as_violation(self):
        """ADR-0063: "Protetor auditivo" (presença) não é linha de violação.

        Mesmo defeito de polaridade de `violation_hours_by_class` — este
        agregado alimenta o `by_class` de /events/summary e o drift monitor.
        """
        repo, pool = _make_repo()
        pool.mock_cursor.fetchall.return_value = [{"n": "protetor auditivo"}]
        repo.violations_by_class(str(uuid4()), FROM_TS, TO_TS, module_code="epi")
        sql, params = _last_call(pool)
        assert "lower(v->>'class') <> ALL(%s::text[])" in sql
        assert ["protetor auditivo"] in params

    def test_presence_catalog_is_module_scoped(self):
        """A consulta de presença que precede o agregado leva o módulo junto."""
        repo, pool = _make_repo()
        repo.violations_by_class(str(uuid4()), FROM_TS, TO_TS, module_code="epi")
        sql, params = _call_at(pool, 0)
        assert "is_violation IS FALSE" in sql
        assert "module_code = %s" in sql
        assert "epi" in params

    def test_params_follow_condition_order(self):
        """A lista de presença entra ANTES do filtro de class_names no WHERE."""
        repo, pool = _make_repo()
        pool.mock_cursor.fetchall.return_value = [{"n": "capacete"}]
        tenant = str(uuid4())
        repo.violations_by_class(
            tenant, FROM_TS, TO_TS, module_code="epi", class_names=["no_helmet"]
        )
        sql, params = _last_call(pool)
        assert sql.index("<> ALL(%s::text[])") < sql.index("= ANY(%s)")
        assert list(params) == [tenant, FROM_TS, TO_TS, "epi", ["capacete"], ["no_helmet"]]


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


class TestPresenceClassNames:
    """ADR-0063 — o catálogo de presença é POR MÓDULO.

    Sem escopo, o catálogo global (migration 009) devolvia junto as classes de
    `fueling` (truck/plate/pallet, todas `is_violation = false`): num agregado
    de EPI, um alerta de 'truck' virava CONFORMIDADE de EPI.
    """

    def test_module_scoped_filters_both_tables(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.presence_class_names(tenant, "epi")
        sql, params = _last_call(pool)
        assert sql.count("module_code = %s") == 2  # module_classes E yolo_classes
        assert tuple(params) == ("epi", tenant, "epi")

    def test_without_module_keeps_previous_scope(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.presence_class_names(tenant)
        sql, params = _last_call(pool)
        assert "module_code" not in sql
        assert tuple(params) == (tenant,)

    def test_module_code_never_interpolated(self):
        repo, pool = _make_repo()
        malicious = "epi'; DROP TABLE alerts; --"
        repo.presence_class_names(str(uuid4()), malicious)
        sql, params = _last_call(pool)
        assert malicious not in sql
        assert malicious in params


class TestComplianceAggregates:

    def test_camera_hours_with_violation_tenant_scoped(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        since = FROM_TS
        repo.camera_hours_with_violation(tenant, "epi", since)
        sql, params = _last_call(pool)
        assert "a.tenant_id = %s" in sql
        assert "COUNT(DISTINCT (a.camera_id, date_trunc('hour', a.created_at)))" in sql
        # ADR-0063: hora-câmega só de EPI PRESENTE não é hora de violação —
        # contar tudo invertia o compliance_rate que se apoia neste número.
        # O 4º param é a lista de classes de presença (parametrizada).
        assert "NOT (" in sql
        assert params[:3] == (tenant, "epi", since)
        assert params[3] == []

    def test_violation_hours_by_class_tenant_scoped(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.violation_hours_by_class(tenant, "epi", FROM_TS)
        sql, params = _last_call(pool)
        assert "a.tenant_id = %s" in sql
        assert "jsonb_array_elements" in sql
        # ADR-0063: classe de presença não forma grupo de "violação por classe".
        assert "lower(v->>'class') <> ALL(%s::text[])" in sql
        assert params[:3] == (tenant, "epi", FROM_TS)
        assert params[3] == []

    def test_presence_catalog_is_module_scoped_in_both_aggregates(self):
        """O catálogo consultado é o do MÓDULO do agregado, não o de todos."""
        for chamada in (
            lambda r: r.camera_hours_with_violation(str(uuid4()), "epi", FROM_TS),
            lambda r: r.violation_hours_by_class(str(uuid4()), "epi", FROM_TS),
        ):
            repo, pool = _make_repo()
            chamada(repo)
            sql, params = _call_at(pool, 0)
            assert "is_violation IS FALSE" in sql
            assert "module_code = %s" in sql
            assert "epi" in params


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
