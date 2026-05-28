"""
Testes unitarios para GateService.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.quality.gate_service import GateService


SCHEMA = "tenant_test"
PIECE_ID = "piece-uuid-001"
REWORK_ID = "rework-uuid-001"


def _make_piece(status="idle", **kwargs):
    base = {
        "id": PIECE_ID,
        "status": status,
        "piece_number": "12345",
        "work_order": "OP001",
        "total_rework_count": 0,
    }
    base.update(kwargs)
    return base


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
def mock_redis():
    r = MagicMock()
    r.publish.return_value = 1
    return r


@pytest.fixture
def service(mock_pool, mock_redis):
    pool, _conn, _cur = mock_pool
    return GateService(pool, mock_redis)


def test_create_piece_publishes_redis(service, mock_pool, mock_redis):
    """create_piece deve publicar no canal quality:station_state:{schema} do Redis."""
    _pool, _conn, cur = mock_pool
    created_piece = _make_piece(status="idle")
    cur.fetchone.return_value = created_piece

    with patch(
        "app.api.v1.quality.gate_repository.GateRepository.create_piece",
        return_value=created_piece,
    ):
        service.create_piece(SCHEMA, "12345", work_order="OP001")

    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    channel = call_args[0][0]
    assert channel == f"quality:station_state:{SCHEMA}"


def test_identify_piece_transitions_state(service):
    """identify_piece deve chamar update_piece_status com status 'identified'."""
    idle_piece = _make_piece(status="idle")
    identified_piece = _make_piece(status="identified")

    with patch(
        "app.api.v1.quality.gate_repository.GateRepository.get_piece",
        return_value=idle_piece,
    ), patch(
        "app.api.v1.quality.gate_repository.GateRepository.update_piece_status",
        return_value=identified_piece,
    ) as mock_update:
        result = service.identify_piece(SCHEMA, PIECE_ID, "12345")

    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][2] == "identified"
    assert result["status"] == "identified"


def test_identify_piece_not_found_raises_value_error(service):
    """identify_piece deve levantar ValueError quando a peca nao existe."""
    with patch(
        "app.api.v1.quality.gate_repository.GateRepository.get_piece",
        return_value=None,
    ):
        with pytest.raises(ValueError, match="not found|nao encontrada|não encontrada"):
            service.identify_piece(SCHEMA, "nonexistent-id", "12345")


def test_start_inspection_dispatches_celery(service):
    """start_inspection deve chamar run_quality_gate_inspection.delay quando camera_id fornecido."""
    identified_piece = _make_piece(status="identified")
    validating_piece = _make_piece(status="validating_v1")

    mock_task = MagicMock()
    mock_task.delay = MagicMock()

    with patch(
        "app.api.v1.quality.gate_repository.GateRepository.get_piece",
        return_value=identified_piece,
    ), patch(
        "app.api.v1.quality.gate_repository.GateRepository.update_piece_status",
        return_value=validating_piece,
    ), patch.dict(
        "sys.modules",
        {
            "app.infrastructure.queue.tasks.quality_inference": MagicMock(
                run_quality_gate_inspection=mock_task
            )
        },
    ):
        service.start_inspection(SCHEMA, PIECE_ID, camera_id="cam-uuid-001")

    mock_task.delay.assert_called_once()


def test_process_result_ok_advances_state(service):
    """process_inspection_result com result='ok' deve chamar update_piece_status com proximo estado."""
    validating_piece = _make_piece(status="validating_v1")
    next_piece = _make_piece(status="validating_v2")

    with patch(
        "app.api.v1.quality.gate_repository.GateRepository.get_piece",
        return_value=validating_piece,
    ), patch(
        "app.api.v1.quality.gate_repository.GateRepository.update_piece_status",
        return_value=next_piece,
    ) as mock_update:
        result = service.process_inspection_result(
            SCHEMA, PIECE_ID, result="ok", confidence=0.95
        )

    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][2] == "validating_v2"
    assert result["status"] == "validating_v2"


def test_process_result_nok_creates_rework(service):
    """process_inspection_result com result='nok' deve criar registro de retrabalho."""
    validating_piece = _make_piece(status="validating_v1")
    rework_piece = _make_piece(status="rework_v1", total_rework_count=1)

    with patch(
        "app.api.v1.quality.gate_repository.GateRepository.get_piece",
        return_value=validating_piece,
    ), patch(
        "app.api.v1.quality.gate_repository.GateRepository.update_piece_status",
        return_value=rework_piece,
    ), patch(
        "app.api.v1.quality.gate_repository.GateRepository.create_rework",
        return_value={"id": REWORK_ID},
    ) as mock_create_rework:
        service.process_inspection_result(
            SCHEMA, PIECE_ID, result="nok", confidence=0.30
        )

    mock_create_rework.assert_called_once()


def test_mark_false_positive_reverts_to_identified(service):
    """mark_false_positive deve chamar update_piece_status com 'identified'."""
    validating_piece = _make_piece(status="validating_v1")
    identified_piece = _make_piece(status="identified")

    with patch(
        "app.api.v1.quality.gate_repository.GateRepository.get_piece",
        return_value=validating_piece,
    ), patch(
        "app.api.v1.quality.gate_repository.GateRepository.update_piece_status",
        return_value=identified_piece,
    ) as mock_update:
        result = service.mark_false_positive(SCHEMA, PIECE_ID)

    mock_update.assert_called_once()
    assert mock_update.call_args[0][2] == "identified"
    assert result["status"] == "identified"


def test_complete_rework_calculates_duration(service, mock_pool):
    """complete_rework deve calcular duration_seconds > 0 a partir de started_at."""
    from datetime import UTC, datetime, timedelta

    pool, conn, cur = mock_pool
    started_at = datetime.now(UTC) - timedelta(minutes=5)

    # O service faz dict(row) — precisamos que o row seja um dict-like real
    # que funcione com dict(). Usamos um dict diretamente via fetchone.
    rework_dict = {
        "id": REWORK_ID,
        "piece_id": PIECE_ID,
        "started_at": started_at,
    }
    # Cria um objeto que simula RealDictRow e pode ser passado para dict()
    class FakeRow(dict):
        pass

    cur.fetchone.return_value = FakeRow(rework_dict)
    completed_rework = {"id": REWORK_ID, "duration_seconds": 300}

    with patch(
        "app.api.v1.quality.gate_repository.GateRepository.complete_rework",
        return_value=completed_rework,
    ) as mock_complete:
        result = service.complete_rework(SCHEMA, REWORK_ID)

    mock_complete.assert_called_once()
    call_args = mock_complete.call_args[0]
    duration_passed = call_args[3]
    assert duration_passed > 0, "duration_seconds deve ser maior que zero"
    assert result["duration_seconds"] == 300
