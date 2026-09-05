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

    def test_only_true_violation_class_counted(self):
        """Contrato A1: só quem é VIOLAÇÃO DE VERDADE (`violation_class_names`)
        forma linha aqui — nem presença ("Protetor auditivo"), nem classe
        INDECIDIDA (fora do catálogo, `is_violation IS NULL`). Antes filtrava
        só `<> presence` — o que ainda deixava a classe indecidida contar como
        violação (o MESMO alerta que `/epi/eventos` mostra como "Não
        definida"). Este agregado alimenta o `by_class` de `/events/summary`
        e o drift monitor."""
        repo, pool = _make_repo()
        pool.mock_cursor.fetchall.return_value = [{"n": "sem protetor de ouvido"}]
        repo.violations_by_class(str(uuid4()), FROM_TS, TO_TS, module_code="epi")
        sql, params = _last_call(pool)
        assert "lower(v->>'class') = ANY(%s::text[])" in sql
        assert ["sem protetor de ouvido"] in params

    def test_violation_catalog_is_module_scoped(self):
        """A consulta de violação que precede o agregado leva o módulo junto."""
        repo, pool = _make_repo()
        repo.violations_by_class(str(uuid4()), FROM_TS, TO_TS, module_code="epi")
        sql, params = _call_at(pool, 0)
        assert "is_violation IS TRUE" in sql
        assert "module_code = %s" in sql
        assert "epi" in params

    def test_params_follow_condition_order(self):
        """A lista de violação entra ANTES do filtro de class_names no WHERE."""
        repo, pool = _make_repo()
        pool.mock_cursor.fetchall.return_value = [{"n": "capacete"}]
        tenant = str(uuid4())
        repo.violations_by_class(
            tenant, FROM_TS, TO_TS, module_code="epi", class_names=["no_helmet"]
        )
        sql, params = _last_call(pool)
        assert sql.index("= ANY(%s::text[])") < sql.index("= ANY(%s)")
        # Os 4 params do escopo de módulo (migration 134) entram logo depois do
        # module_code, na mesma ordem em que o predicado aparece no WHERE —
        # ver `escopo_params`. Sem eles a taxa de conformidade contaria
        # violação de câmera que o dono não declarou no módulo.
        assert list(params) == [
            tenant, FROM_TS, TO_TS, "epi",
            tenant, "epi", tenant, "epi",
            ["capacete"], ["no_helmet"],
        ]


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
    """ADR-0065 — o catálogo de presença é POR MÓDULO.

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
        # ADR-0065: hora-câmega só de EPI PRESENTE não é hora de violação —
        # contar tudo invertia o compliance_rate que se apoia neste número.
        # O 4º param é a lista de classes de presença (parametrizada).
        assert "NOT (" in sql
        assert params[:3] == (tenant, "epi", since)
        assert params[3] == []

    def test_camera_hours_sem_until_nao_ganha_teto(self):
        """O Dashboard chama sem `until` e continua sem limite superior."""
        repo, pool = _make_repo()
        repo.camera_hours_with_violation(str(uuid4()), "epi", FROM_TS)
        sql, _ = _last_call(pool)
        assert "a.created_at <= %s" not in sql

    def test_camera_hours_com_until_fecha_a_janela_pelo_topo(self):
        """Issue #797: o relatório apura períodos FECHADOS. Sem o teto, o
        "mês anterior" contaria violação até AGORA — o mesmo defeito que
        `count_since` → `count_in_window` já corrigiu na contagem de eventos.

        A ordem dos params importa: o teto entra ANTES das duas listas de
        classes, senão o psycopg2 casa `until` com um `text[]`.
        """
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.camera_hours_with_violation(tenant, "epi", FROM_TS, TO_TS)
        sql, params = _last_call(pool)
        assert "a.created_at >= %s" in sql
        assert "a.created_at <= %s" in sql
        assert params[:4] == (tenant, "epi", FROM_TS, TO_TS)
        assert params[4] == [] and params[5] == []
        assert sql.count("%s") == len(params)

    def test_violation_hours_by_class_tenant_scoped(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.violation_hours_by_class(tenant, "epi", FROM_TS)
        sql, params = _last_call(pool)
        assert "a.tenant_id = %s" in sql
        assert "jsonb_array_elements" in sql
        # Contrato A1: só violação DE VERDADE forma grupo (nem presença, nem
        # classe indecidida — `violation_class_names`, não `<> presença`).
        assert "lower(v->>'class') = ANY(%s::text[])" in sql
        assert params[:3] == (tenant, "epi", FROM_TS)
        assert params[3] == []

    def test_violation_catalog_is_module_scoped_in_both_aggregates(self):
        """O catálogo consultado é o do MÓDULO do agregado, não o de todos."""
        for chamada in (
            lambda r: r.camera_hours_with_violation(str(uuid4()), "epi", FROM_TS),
            lambda r: r.violation_hours_by_class(str(uuid4()), "epi", FROM_TS),
        ):
            repo, pool = _make_repo()
            chamada(repo)
            sql, params = _call_at(pool, 0)
            assert "is_violation IS TRUE" in sql
            assert "module_code = %s" in sql
            assert "epi" in params


class TestCaptureProfile:
    """O eixo de tempo do perfil é a CAPTURA, e isso não pode regredir.

    `created_at` é quando a linha entrou no banco. Numa carga em lote os dois
    campos divergem por dias — medido no DEV, a captura se espalha das 10h às
    19h (o dia da fábrica) e o `created_at` empilha em 3 horários (as vezes em
    que o processo de ingestão rodou). Trocar de volta transforma "em que
    horário a fábrica gera violação" em "a que horas o servidor gravou", e o
    erro passa despercebido porque continua desenhando um gráfico plausível.
    """

    def test_agrupa_e_filtra_por_timestamp_nunca_por_created_at(self):
        repo, pool = _make_repo()
        repo.capture_profile(str(uuid4()), FROM_TS, TO_TS, "epi")
        sql, _ = _last_call(pool)
        assert "date_trunc('hour', a.timestamp)" in sql
        assert "a.timestamp >= %s" in sql
        assert "a.created_at" not in sql

    def test_tenant_scoped(self):
        repo, pool = _make_repo()
        tenant = str(uuid4())
        repo.capture_profile(tenant, FROM_TS, TO_TS)
        sql, params = _last_call(pool)
        assert "a.tenant_id = %s" in sql
        assert tenant in params

    def test_tres_baldes_de_polaridade_e_nao_dois(self):
        """Conformidade (EPI em uso) e classe indecidida não são violação."""
        repo, pool = _make_repo()
        repo.capture_profile(str(uuid4()), FROM_TS, TO_TS, "epi")
        sql, _ = _last_call(pool)
        assert "'conformidade'" in sql
        assert "'violacao'" in sql
        assert "'indefinido'" in sql

    def test_situacao_le_a_mesma_janela_de_captura(self):
        """Dois cartões da mesma tela sobre o MESMO conjunto de eventos."""
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = {"total": 423, "nao_reconhecidos": 396}
        situacao = repo.review_situation(str(uuid4()), FROM_TS, TO_TS, "epi")
        sql, _ = _last_call(pool)
        assert "a.timestamp >= %s" in sql
        assert "a.created_at" not in sql
        assert situacao["total"] == 423


class TestTimelineTimeColumn:

    def test_default_continua_sendo_a_ingestao(self):
        """Opt-in: quem já chamava a timeline não pode ver o eixo mudar."""
        repo, pool = _make_repo()
        repo.timeline_by_bucket(str(uuid4()), FROM_TS, TO_TS, include_demo=False)
        sql, _ = _last_call(pool)
        assert "a.created_at" in sql
        assert "a.timestamp" not in sql

    def test_captura_troca_a_coluna_do_ramo_alerts(self):
        repo, pool = _make_repo()
        repo.timeline_by_bucket(
            str(uuid4()), FROM_TS, TO_TS, include_demo=False, time_column="timestamp"
        )
        sql, _ = _last_call(pool)
        assert "a.timestamp" in sql
        assert "a.created_at" not in sql

    def test_demo_events_fica_em_created_at_porque_nao_tem_timestamp(self):
        """`demo_events` não tem coluna `timestamp` — a UNION quebraria."""
        repo, pool = _make_repo()
        repo.timeline_by_bucket(
            str(uuid4()), FROM_TS, TO_TS, include_demo=True, time_column="timestamp"
        )
        sql, _ = _last_call(pool)
        assert "SELECT a.timestamp AS ts" in sql
        assert "SELECT d.created_at AS ts" in sql
        assert "d.timestamp" not in sql

    def test_coluna_fora_da_whitelist_cai_no_default(self):
        repo, pool = _make_repo()
        repo.timeline_by_bucket(
            str(uuid4()), FROM_TS, TO_TS, include_demo=False,
            time_column="created_at FROM alerts; DROP TABLE alerts--",
        )
        sql, _ = _last_call(pool)
        assert "DROP" not in sql
        assert "a.created_at" in sql


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
