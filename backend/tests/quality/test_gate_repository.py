"""
Testes unitarios para GateRepository.
"""
from unittest.mock import MagicMock, call

import pytest

from app.api.v1.quality.gate_repository import GateRepository


SCHEMA = "tenant_test"
PIECE_ID = "piece-uuid-001"
REWORK_ID = "rework-uuid-001"


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = None
    cur.fetchall.return_value = []
    conn.__enter__ = lambda s: conn
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    pool.get_connection.return_value = conn
    return pool, conn, cur


@pytest.fixture
def repo(mock_pool):
    pool, _conn, _cur = mock_pool
    return GateRepository(pool)


def _fake_row(**fields):
    """Cria objeto simulando RealDictCursor row."""
    row = MagicMock()
    row.items.return_value = list(fields.items())
    row.__iter__ = lambda s: iter(fields.items())
    row.get = lambda k, d=None: fields.get(k, d)
    return row


def test_create_piece_executes_insert(repo, mock_pool):
    """create_piece deve executar uma query INSERT na tabela quality_pieces."""
    _pool, _conn, cur = mock_pool
    row = _fake_row(id="new-uuid", status="idle", piece_number="12345")
    cur.fetchone.return_value = row

    repo.create_piece(SCHEMA, {
        "piece_number": "12345",
        "work_order": "OP001",
        "product_type": "Produto A",
        "status": "idle",
        "operator_id": None,
        "tenant_id": "tenant-uuid",
    })

    sql_calls = [str(c) for c in cur.execute.call_args_list]
    assert any("INSERT" in c.upper() for c in sql_calls), (
        "Esperado chamada cur.execute com INSERT"
    )


def test_get_piece_returns_dict(repo, mock_pool):
    """get_piece deve retornar dict quando row encontrado."""
    _pool, _conn, cur = mock_pool
    row = _fake_row(id=PIECE_ID, status="idle", piece_number="12345")
    cur.fetchone.return_value = row

    result = repo.get_piece(SCHEMA, PIECE_ID)

    assert isinstance(result, dict)
    assert result.get("id") == PIECE_ID or result.get("status") == "idle"


def test_get_piece_returns_none_when_not_found(repo, mock_pool):
    """get_piece deve retornar None quando fetchone retorna None."""
    _pool, _conn, cur = mock_pool
    cur.fetchone.return_value = None

    result = repo.get_piece(SCHEMA, "nonexistent-id")

    assert result is None


def test_list_pieces_with_status_filter_includes_status_in_sql(repo, mock_pool):
    """get_pieces com filtro de status deve incluir 'status' na query SQL."""
    _pool, _conn, cur = mock_pool
    cur.fetchall.return_value = []

    repo.get_pieces(SCHEMA, filters={"status": "idle"})

    executed_sqls = [str(c) for c in cur.execute.call_args_list]
    assert any("status" in c.lower() for c in executed_sqls), (
        "Esperado 'status' na query SQL quando filtro de status fornecido"
    )


def test_create_rework_sets_piece_id(repo, mock_pool):
    """create_rework deve executar INSERT com piece_id no payload."""
    _pool, _conn, cur = mock_pool
    row = _fake_row(id=REWORK_ID, piece_id=PIECE_ID, validation_type="v1")
    cur.fetchone.return_value = row

    repo.create_rework(SCHEMA, {
        "piece_id": PIECE_ID,
        "validation_type": "v1",
        "defect_type": None,
        "defect_description": None,
        "photo_before_path": None,
        "photo_before_r2_key": None,
        "operator_id": None,
        "tenant_id": "tenant-uuid",
    })

    # Verifica que piece_id aparece nos parametros passados ao execute
    all_calls_params = [str(c) for c in cur.execute.call_args_list]
    assert any(PIECE_ID in c for c in all_calls_params), (
        f"Esperado piece_id={PIECE_ID!r} nos parametros do INSERT"
    )


def test_create_station_inserts_correctly(repo, mock_pool):
    """create_or_update_station deve executar INSERT na tabela quality_stations."""
    _pool, _conn, cur = mock_pool
    row = _fake_row(id="station-uuid", station_code="BANCADA_A", name="Bancada A")
    cur.fetchone.return_value = row

    repo.create_or_update_station(SCHEMA, {
        "station_code": "BANCADA_A",
        "name": "Bancada A",
        "description": None,
        "current_piece_id": None,
        "camera_ids": None,
        "tenant_id": "tenant-uuid",
    })

    sql_calls = [str(c) for c in cur.execute.call_args_list]
    assert any("INSERT" in c.upper() for c in sql_calls), (
        "Esperado chamada cur.execute com INSERT para quality_stations"
    )


def test_get_overview_stats_returns_dict(repo, mock_pool):
    """get_overview_stats deve retornar dict com chaves de metricas."""
    _pool, _conn, cur = mock_pool
    stats_row = _fake_row(
        pieces_today=10,
        pieces_approved=8,
        pieces_nok=2,
        nok_rate=20.0,
    )
    rework_row = _fake_row(rework_count=3)
    cur.fetchone.side_effect = [stats_row, rework_row]

    result = repo.get_overview_stats(SCHEMA)

    assert isinstance(result, dict)
    assert "pieces_today" in result or "rework_count" in result
