"""
Tests: AlertRepository — all methods.

All DB calls go through a mocked DatabasePool (contextmanager pattern).
"""
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from unittest.mock import MagicMock

from app.infrastructure.database.repositories.alert_repository import AlertRepository


def _pool_with_cursor(mock_cursor):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _repo(mock_cursor=None):
    cur = mock_cursor or MagicMock()
    return AlertRepository(_pool_with_cursor(cur)), cur


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

class TestCreate:

    def test_returns_created_row(self):
        row = {"id": str(uuid4()), "camera_id": str(uuid4()), "confidence": 0.9}
        cur = MagicMock()
        cur.fetchone.return_value = row
        repo, _ = _repo(cur)
        result = repo.create(uuid4(), [{"class": "no_helmet"}], 0.9, "evidence/key.jpg")
        assert result["confidence"] == 0.9

    def test_violations_serialized_as_json(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        violations = [{"class": "no_helmet", "conf": 0.8}]
        repo.create(uuid4(), violations, 0.8, "k")
        params = cur.execute.call_args[0][1]
        # Second param should be JSON string
        assert json.loads(params[1]) == violations

    def test_camera_id_cast_to_str(self):
        camera_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create(camera_id, [], 0.5, "k")
        params = cur.execute.call_args[0][1]
        assert params[0] == str(camera_id)

    def test_timestamp_omitted_when_not_given(self):
        """Caminho ao vivo: sem `timestamp`, a coluna nem entra no INSERT —
        o DEFAULT NOW() do schema decide, comportamento inalterado."""
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create(uuid4(), [], 0.5, "k")
        query = cur.execute.call_args[0][0]
        assert "timestamp" not in query

    def test_timestamp_included_when_given(self):
        """Inferência retroativa: `timestamp` grava a hora REAL da captura,
        não a hora do INSERT — é o par que ProcedenciaBadge lê no front."""
        captured = datetime(2026, 8, 20, 12, 0, 0)
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create(uuid4(), [], 0.5, "k", timestamp=captured)
        query, params = cur.execute.call_args[0]
        assert "timestamp" in query
        assert params[-1] == captured


# ---------------------------------------------------------------------------
# exists_at_capture
# ---------------------------------------------------------------------------

class TestExistsAtCapture:

    def test_true_when_row_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"?column?": 1}
        repo, cur = _repo(cur)
        assert repo.exists_at_capture(uuid4(), datetime(2026, 8, 20, 12, 0, 0)) is True

    def test_false_when_no_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        assert repo.exists_at_capture(uuid4(), datetime(2026, 8, 20, 12, 0, 0)) is False

    def test_queries_by_camera_and_timestamp(self):
        camera_id = uuid4()
        captured = datetime(2026, 8, 20, 12, 0, 0)
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.exists_at_capture(camera_id, captured)
        params = cur.execute.call_args[0][1]
        assert params == (str(camera_id), captured)


# ---------------------------------------------------------------------------
# get_by_camera
# ---------------------------------------------------------------------------

class TestGetByCamera:
    """`tenant_id` é obrigatório desde o #545: a query era escopo puro de
    câmera e `GET /api/cameras/<id>/alerts` devolvia alerta de qualquer
    tenant. Estes testes chamavam sem o tenant — passavam justamente porque
    o defeito existia."""

    TENANT = "11111111-2222-3333-4444-555555555555"

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "a"}, {"id": "b"}]
        repo, _ = _repo(cur)
        result = repo.get_by_camera(uuid4(), self.TENANT)
        assert len(result) == 2

    def test_default_limit_offset(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_by_camera(uuid4(), self.TENANT)
        params = cur.execute.call_args[0][1]
        assert 50 in params  # default limit
        assert 0 in params   # default offset

    def test_custom_limit_offset(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_by_camera(uuid4(), self.TENANT, limit=10, offset=20)
        params = cur.execute.call_args[0][1]
        assert 10 in params
        assert 20 in params

    def test_o_tenant_entra_na_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_by_camera(uuid4(), self.TENANT)
        sql, params = cur.execute.call_args[0]
        assert "tenant_id = %s" in sql
        assert self.TENANT in params


# ---------------------------------------------------------------------------
# get_unacknowledged
# ---------------------------------------------------------------------------

class TestGetUnacknowledged:

    def test_no_camera_returns_all(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "x"}]
        repo, cur = _repo(cur)
        repo.get_unacknowledged()
        query = cur.execute.call_args[0][0]
        assert "camera_id" not in query

    def test_with_camera_filters_by_camera(self):
        cam_id = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_unacknowledged(camera_id=cam_id)
        params = cur.execute.call_args[0][1]
        assert str(cam_id) in params

    def test_acknowledged_false_in_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_unacknowledged()
        query = cur.execute.call_args[0][0]
        assert "acknowledged" in query.lower()


# ---------------------------------------------------------------------------
# acknowledge
# ---------------------------------------------------------------------------

class TestAcknowledge:

    def test_returns_updated_row(self):
        alert_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(alert_id), "acknowledged": True}
        repo, _ = _repo(cur)
        result = repo.acknowledge(alert_id, "tenant-a")
        assert result["acknowledged"] is True

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.acknowledge(uuid4(), "tenant-a") is None

    def test_sets_acknowledged_true_in_query(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.acknowledge(uuid4(), "tenant-a")
        query = cur.execute.call_args[0][0]
        assert "acknowledged = TRUE" in query or "acknowledged=TRUE" in query.replace(" ", "")


# ---------------------------------------------------------------------------
# count_by_camera
# ---------------------------------------------------------------------------

class TestCountByCamera:

    def test_returns_count(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 42}
        repo, _ = _repo(cur)
        assert repo.count_by_camera(uuid4()) == 42

    def test_no_row_returns_zero(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.count_by_camera(uuid4()) == 0


# ---------------------------------------------------------------------------
# list_with_filters
# ---------------------------------------------------------------------------

class TestListWithFilters:

    def _call(self, **kwargs):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 5}
        # `n` atende a query de classes de PRESENÇA (ADR-0065, chamada antes
        # da de itens); `id` atende a de itens. O mesmo mock serve às duas.
        cur.fetchall.return_value = [{"id": "a", "n": "protetor auditivo"}]
        repo, _ = _repo(cur)
        return repo.list_with_filters("tenant-1", **kwargs), cur

    def test_returns_items_and_total(self):
        result, _ = self._call()
        assert "items" in result
        assert "total" in result

    def test_total_from_count_query(self):
        result, _ = self._call()
        assert result["total"] == 5

    def test_tenant_id_in_params(self):
        _, cur = self._call()
        # Both count and items queries should have tenant-1
        all_params = [str(c) for c in cur.execute.call_args_list]
        assert any("tenant-1" in p for p in all_params)

    def test_camera_id_filter_added(self):
        _, cur = self._call(camera_id="cam-42")
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any("cam-42" in p for p in params_list)

    def test_start_date_filter_added(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _, cur = self._call(start_date=dt)
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(dt in p for p in params_list)

    def test_end_date_filter_added(self):
        dt = datetime(2026, 12, 31, tzinfo=timezone.utc)
        _, cur = self._call(end_date=dt)
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(dt in p for p in params_list)

    def test_violation_type_filter_added(self):
        _, cur = self._call(violation_type="no_helmet")
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(any("no_helmet" in str(p) for p in params) for params in params_list)

    def test_acknowledged_filter_added(self):
        _, cur = self._call(acknowledged=True)
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(True in p for p in params_list)

    def test_default_limit_offset(self):
        _, cur = self._call()
        # items query should have limit=20, offset=0
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(20 in p for p in params_list)


# ---------------------------------------------------------------------------
# total_situacoes — ux2/dedup: rajadas (câmera+classe em <60s), não linhas.
#
# Teste de MUTAÇÃO: sem banco real, prova que a query de rajada existe e usa
# a MESMA janela de `VerificationService` — se alguém apagar o bloco de
# `total_situacoes` (ou trocar a janela), `total_situacoes` volta a ser
# igual a `total` (linhas) e este teste reprova.
# ---------------------------------------------------------------------------

class TestListWithFiltersTotalSituacoes:

    def _call(self, count_row, situacoes_row, **kwargs):
        cur = MagicMock()
        # A ordem real de `execute` é: presence_class_names, violation_class_names,
        # COUNT(*) (linhas), total_situacoes (rajadas), itens. `fetchone` só é lido
        # pelas DUAS contagens (as outras usam `fetchall`) — por isso side_effect
        # de 2 valores já basta, na ORDEM em que aparecem no código-fonte.
        cur.fetchone.side_effect = [count_row, situacoes_row]
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        return repo.list_with_filters("tenant-1", **kwargs), cur

    @staticmethod
    def _busca_query(cur, pedaco: str):
        """Acha a chamada de `execute` cujo SQL contém `pedaco` — a suíte não
        depende da ORDEM exata das 5 queries de `list_with_filters`, só de
        que a query de rajada exista e carregue o filtro certo."""
        for call in cur.execute.call_args_list:
            sql, params = call[0]
            if pedaco in sql:
                return sql, params
        raise AssertionError(f"nenhuma query continha {pedaco!r}")

    def test_total_situacoes_no_payload(self):
        result, _ = self._call({"count": 66}, {"total_situacoes": 2})
        assert result["total"] == 66
        assert result["total_situacoes"] == 2

    def test_situacoes_query_usa_mesma_janela_do_dedup_de_verificacao(self):
        """Fonte única: `DEDUP_WINDOW_SECONDS` (app.core.rajada), a MESMA
        constante de `VerificationService._DEDUP_WINDOW_SECONDS` — não pode
        haver uma segunda janela hardcoded aqui."""
        from app.core.rajada import DEDUP_WINDOW_SECONDS

        _, cur = self._call({"count": 66}, {"total_situacoes": 2})
        sql, params = self._busca_query(cur, "LAG(created_at)")
        assert "PARTITION BY camera_id, classe" in sql
        assert DEDUP_WINDOW_SECONDS in params

    def test_situacoes_respeita_o_mesmo_where_do_count(self):
        """O filtro (câmera, período, kind…) tem de ser o MESMO nas duas
        contagens — total_situacoes de um recorte diferente do `total`
        mentiria sobre o MESMO texto na tela (achado #14 do padrão do
        projeto: contagem e lista com WHERE divergente)."""
        _, cur = self._call({"count": 1}, {"total_situacoes": 1}, camera_id="cam-42")
        sql_count, params_count = self._busca_query(cur, "SELECT COUNT(*) as count")
        sql_situacoes, params_situacoes = self._busca_query(cur, "LAG(created_at)")
        assert "camera_id" in sql_count and "cam-42" in params_count
        assert "camera_id" in sql_situacoes and "cam-42" in params_situacoes

    def test_fallback_para_total_sem_a_chave_nova(self):
        """Mock/repo antigo sem `total_situacoes` na linha: cai para `total`
        (linhas) em vez de KeyError — nunca 500 por causa de um campo novo."""
        result, _ = self._call({"count": 9}, {"count": 9})
        assert result["total_situacoes"] == 9


# ---------------------------------------------------------------------------
# event_kind — TRÊS estados (contrato A1, refina ADR-0065 §4)
#
# Teste de MUTAÇÃO: sem banco real (roda em qualquer CI), lê o TEXTO da query
# de itens que o repositório realmente emitiu. Se alguém reverter o CASE para
# binário (`WHEN compliance THEN 'compliance' ELSE 'violation'`), a 3ª
# ramificação some do texto e este teste reprova — não precisa de Postgres
# pra pegar essa regressão específica (a semântica fina, "indecidida vira
# observação de verdade", ainda depende do teste de integração real).
# ---------------------------------------------------------------------------

class TestEventKindTresEstados:

    def _items_query(self, cur) -> str:
        for call in cur.execute.call_args_list:
            sql = call[0][0]
            if "event_kind" in sql:
                return sql
        raise AssertionError("nenhuma chamada com 'event_kind' no SQL")

    def test_case_tem_tres_ramos_nao_dois(self):
        """FALHA se o CASE voltar a ser binário (só compliance/violation)."""
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 0}
        cur.fetchall.return_value = [{"n": "protetor auditivo"}]
        repo, cur = _repo(cur)
        repo.list_with_filters("tenant-1")
        sql = self._items_query(cur)
        assert "'compliance'" in sql
        assert "'violation'" in sql
        assert "'observacao'" in sql
        assert sql.count("WHEN") == 2, "CASE precisa de DOIS WHEN — um terceiro balde, não ELSE direto"

    def test_kind_observacao_gera_condicao_propria(self):
        """FALHA se kind='observacao' não filtrar nada (virar sinônimo de
        kind=None) — a query de contagem precisa ganhar uma condição NOVA."""
        cur_none = MagicMock()
        cur_none.fetchone.return_value = {"count": 0}
        cur_none.fetchall.return_value = [{"n": "protetor auditivo"}]
        repo_none, cur_none = _repo(cur_none)
        repo_none.list_with_filters("tenant-1")
        count_query_none = cur_none.execute.call_args_list[-2][0][0]

        cur_obs = MagicMock()
        cur_obs.fetchone.return_value = {"count": 0}
        cur_obs.fetchall.return_value = [{"n": "protetor auditivo"}]
        repo_obs, cur_obs = _repo(cur_obs)
        repo_obs.list_with_filters("tenant-1", kind="observacao")
        count_query_obs = cur_obs.execute.call_args_list[-2][0][0]

        assert count_query_obs != count_query_none
        assert "NOT" in count_query_obs

    def test_kind_violation_exige_classe_de_verdade_nao_so_not_compliance(self):
        """FALHA se kind='violation' voltar a ser 'NOT compliance' puro — a
        mentira original do contrato A1 (indecidida disfarçada de violação)."""
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 0}
        cur.fetchall.return_value = [{"n": "protetor auditivo"}]
        repo, cur = _repo(cur)
        repo.list_with_filters("tenant-1", kind="violation")
        count_query = cur.execute.call_args_list[-2][0][0]
        # `_IS_COMPLIANCE_SQL` usa `<> ALL(...)`; só `_IS_VIOLATION_SQL` usa
        # `= ANY(...)` — marcador que discrimina "só NOT compliance" (mentira
        # antiga) de "EXISTS classe de violação de verdade" (fix).
        assert "= ANY(" in count_query, (
            "kind=violation precisa checar _IS_VIOLATION_SQL (= ANY, classe "
            "de violação de verdade), não só 'NOT compliance' (<> ALL)"
        )


# ---------------------------------------------------------------------------
# list_for_camera_scenario
# ---------------------------------------------------------------------------

class TestListForCameraScenario:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "rule-1"}]
        repo, _ = _repo(cur)
        result = repo.list_for_camera_scenario("tenant-1", "cam-1")
        assert result == [{"id": "rule-1"}]

    def test_tenant_id_and_camera_id_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_for_camera_scenario("tenant-x", "cam-y")
        params = cur.execute.call_args[0][1]
        assert "tenant-x" in params
        assert "cam-y" in params

    def test_enabled_true_in_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_for_camera_scenario("t", "c")
        query = cur.execute.call_args[0][0]
        assert "enabled" in query.lower()


# ---------------------------------------------------------------------------
# count_since / count_all_since / count_by_hour
# ---------------------------------------------------------------------------

class TestCountSince:

    def test_returns_count(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 7}
        repo, _ = _repo(cur)
        assert repo.count_since("t-1", "epi", datetime.now(tz=timezone.utc)) == 7

    def test_no_row_returns_zero(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.count_since("t-1", "epi", datetime.now(tz=timezone.utc)) == 0

    def test_module_code_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 0}
        repo, cur = _repo(cur)
        repo.count_since("t-1", "fueling", datetime.now(tz=timezone.utc))
        params = cur.execute.call_args[0][1]
        assert "fueling" in params


class TestCountAllSince:

    def test_returns_count(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 15}
        repo, _ = _repo(cur)
        assert repo.count_all_since("t-1", datetime.now(tz=timezone.utc)) == 15

    def test_no_row_returns_zero(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.count_all_since("t-1", datetime.now(tz=timezone.utc)) == 0


class TestCountByHour:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"hour": "2026-01-01 10:00", "count": 3}]
        repo, _ = _repo(cur)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)
        result = repo.count_by_hour("t-1", start, end)
        assert len(result) == 1
        assert result[0]["count"] == 3

    def test_tenant_and_dates_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)
        repo.count_by_hour("tenant-99", start, end)
        params = cur.execute.call_args[0][1]
        assert "tenant-99" in params
        assert start in params
        assert end in params
