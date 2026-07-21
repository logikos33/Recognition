"""
Tests: OperationsEngine — o motor que avalia operações contra o stream de
detecção e popula `operation_results` em produção (fora do /test).

Puro/unitário: sem Redis, sem banco. Repo, relógio e publisher são injetados.
Segue o padrão de test_operation_registry.py (salva/restaura `_types`).
"""
import pytest

from app.domain.services.operations.base import BaseOperation
from app.domain.services.operations.engine import OperationsEngine
from app.domain.services.operations.registry import OperationTypeRegistry


# --------------------------------------------------------------------------- stubs
class _CounterOp(BaseOperation):
    """Conta frames (prova estado entre frames) e satisfaz condição quando há
    >= threshold detecções (prova mudança de condição)."""

    type_id = "test_counter"
    type_label = "Counter"
    available_modules = ["*"]

    def validate_config(self, config):
        return []

    def evaluate(self, detections, frame_meta, state):
        count = int(state.get("count", 0)) + 1
        condition = len(detections) >= int(self.config.get("threshold", 1))
        return {
            "result": {"count": count},
            "metric_value": count,
            "condition_satisfied": condition,
            "state_next": {"count": count},
        }


class _BoomOp(BaseOperation):
    type_id = "test_boom"
    type_label = "Boom"
    available_modules = ["*"]

    def validate_config(self, config):
        return []

    def evaluate(self, detections, frame_meta, state):
        raise RuntimeError("kaboom")


class _FakeClock:
    def __init__(self, t: float = 100.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t


class _FakeRepo:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.by_id = {r["id"]: r for r in self.rows}
        self.results = []          # (op_id, payload)
        self.live = []             # (op_id, payload, status)

    def list_all_active(self):
        return [r for r in self.rows if r.get("status") != "inactive"]

    def get_active_by_id(self, operation_id):
        return self.by_id.get(operation_id)

    def insert_result(self, operation_id, result_json):
        self.results.append((operation_id, result_json))

    def update_live_value(self, operation_id, last_value_json, status="active"):
        self.live.append((operation_id, last_value_json, status))


def _row(op_id, camera_id="camA", type_id="test_counter", version=1, config=None, status="active"):
    return {
        "id": op_id, "tenant_id": "t-1", "camera_id": camera_id, "module_id": "generic",
        "type_id": type_id, "name": f"op{op_id}", "config": config or {"threshold": 1},
        "status": status, "version": version, "last_value_json": None,
        "last_evaluated_at": None, "created_at": None,
    }


@pytest.fixture(autouse=True)
def _isolate_registry():
    saved = dict(OperationTypeRegistry._types)
    OperationTypeRegistry.register(_CounterOp)
    OperationTypeRegistry.register(_BoomOp)
    yield
    OperationTypeRegistry._types = saved


# --------------------------------------------------------------------------- tests
def test_load_all_groups_by_camera():
    repo = _FakeRepo([_row(1, "camA"), _row(2, "camA"), _row(3, "camB"), _row(4, status="inactive")])
    eng = OperationsEngine(repo, now=_FakeClock().now)
    n = eng.load_all()
    assert n == 3  # inativa não entra
    assert eng.stats() == {"operations": 3, "cameras": 2}


def test_first_frame_persists_and_updates_live_and_publishes():
    published = []
    repo = _FakeRepo([_row(1, "camA")])
    eng = OperationsEngine(repo, publish=lambda ch, p: published.append((ch, p)), now=_FakeClock().now)
    eng.load_all()
    evaluated = eng.process_frame("camA", [{"class": "person"}], {"width": 640, "height": 360})
    assert evaluated == 1
    assert repo.results == [(1, {"result": {"count": 1}, "metric_value": 1, "condition_satisfied": True})]
    assert len(repo.live) == 1 and repo.live[0][2] == "active"
    assert published and published[0][0] == "operations:status:1"


def test_state_carried_across_frames():
    clock = _FakeClock()
    repo = _FakeRepo([_row(1, "camA")])
    eng = OperationsEngine(repo, now=clock.now)
    eng.load_all()
    eng.process_frame("camA", [{"c": 1}], {})
    clock.t += 10  # passa o intervalo → novo persist
    eng.process_frame("camA", [{"c": 1}], {})
    # count acumulou: 1 no primeiro, 2 no segundo → estado carregou entre frames
    assert repo.results[-1][1]["metric_value"] == 2


def test_throttle_suppresses_persist_within_interval_without_change():
    clock = _FakeClock()
    repo = _FakeRepo([_row(1, "camA")])
    eng = OperationsEngine(repo, now=clock.now, result_interval_s=5.0, live_interval_s=2.0)
    eng.load_all()
    eng.process_frame("camA", [{"c": 1}], {})   # persiste (condição None→True)
    clock.t += 1                                 # < 5s, condição igual
    eng.process_frame("camA", [{"c": 1}], {})
    assert len(repo.results) == 1                # throttled


def test_condition_change_forces_persist_within_interval():
    clock = _FakeClock()
    repo = _FakeRepo([_row(1, "camA", config={"threshold": 1})])
    eng = OperationsEngine(repo, now=clock.now)
    eng.load_all()
    eng.process_frame("camA", [{"c": 1}], {})    # condição True
    clock.t += 1                                 # < 5s
    eng.process_frame("camA", [], {})            # 0 detecções → condição False → muda
    assert len(repo.results) == 2
    assert repo.results[-1][1]["condition_satisfied"] is False


def test_unknown_camera_returns_zero():
    repo = _FakeRepo([_row(1, "camA")])
    eng = OperationsEngine(repo, now=_FakeClock().now)
    eng.load_all()
    assert eng.process_frame("camZ", [{"c": 1}], {}) == 0
    assert repo.results == []


def test_error_isolation_one_op_fails_other_survives():
    repo = _FakeRepo([_row(1, "camA", type_id="test_boom"), _row(2, "camA", type_id="test_counter")])
    eng = OperationsEngine(repo, now=_FakeClock().now)
    eng.load_all()
    evaluated = eng.process_frame("camA", [{"c": 1}], {})
    assert evaluated == 1  # só a boa conta como avaliada
    # a boa persistiu resultado
    assert any(op_id == 2 for op_id, _ in repo.results)
    # a ruim virou status 'error'
    assert any(op_id == 1 and status == "error" for op_id, _, status in repo.live)


def test_reload_version_change_rebuilds_and_resets_state():
    repo = _FakeRepo([_row(1, "camA", version=1)])
    eng = OperationsEngine(repo, now=_FakeClock().now)
    eng.load_all()
    eng.process_frame("camA", [{"c": 1}], {})   # count=1
    # operador editou → nova versão no banco
    repo.by_id[1] = _row(1, "camA", version=2, config={"threshold": 2})
    assert eng.reload_operation(1) is True
    eng.process_frame("camA", [{"c": 1}], {})   # estado resetado → count volta a 1
    assert repo.results[-1][1]["metric_value"] == 1


def test_reload_removed_drops_operation():
    repo = _FakeRepo([_row(1, "camA")])
    eng = OperationsEngine(repo, now=_FakeClock().now)
    eng.load_all()
    repo.by_id.pop(1)  # deletada no banco
    assert eng.reload_operation(1) is False
    assert eng.process_frame("camA", [{"c": 1}], {}) == 0
    assert eng.stats()["operations"] == 0


def test_unknown_type_skipped_in_load():
    repo = _FakeRepo([_row(1, "camA", type_id="does_not_exist"), _row(2, "camA")])
    eng = OperationsEngine(repo, now=_FakeClock().now)
    assert eng.load_all() == 1  # só a de tipo conhecido
