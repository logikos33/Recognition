"""
Testes unitarios para PieceStateMachine.
"""
import pytest

from app.api.v1.quality.state_machine import VALID_TRANSITIONS, PieceStateMachine


@pytest.fixture
def sm():
    return PieceStateMachine()


def test_valid_transitions(sm):
    """Cada transicao presente em VALID_TRANSITIONS deve ser aceita sem erro."""
    for from_state, targets in VALID_TRANSITIONS.items():
        for to_state in targets:
            result = sm.transition(from_state, to_state)
            assert result == to_state, (
                f"transition({from_state!r}, {to_state!r}) should return {to_state!r}"
            )


def test_invalid_transition_raises(sm):
    """Transicao invalida deve levantar ValueError."""
    with pytest.raises(ValueError, match="Transicao invalida|Transição inválida"):
        sm.transition("idle", "approved")


def test_invalid_transition_from_approved_raises(sm):
    """Estado terminal approved nao tem transicoes — qualquer destino levanta ValueError."""
    with pytest.raises(ValueError):
        sm.transition("approved", "identified")


def test_get_validation_type_validating_v1(sm):
    """validating_v1 deve retornar 'v1'."""
    assert sm.get_validation_type("validating_v1") == "v1"


def test_get_validation_type_validating_v2(sm):
    """validating_v2 deve retornar 'v2'."""
    assert sm.get_validation_type("validating_v2") == "v2"


def test_get_validation_type_validating_v3(sm):
    """validating_v3 deve retornar 'v3'."""
    assert sm.get_validation_type("validating_v3") == "v3"


def test_get_validation_type_idle_returns_none(sm):
    """idle nao e estado de validacao — deve retornar None."""
    assert sm.get_validation_type("idle") is None


def test_get_rework_state_v1(sm):
    """'v1' deve mapear para 'rework_v1'."""
    assert sm.get_rework_state("v1") == "rework_v1"


def test_get_rework_state_v2(sm):
    """'v2' deve mapear para 'rework_v2'."""
    assert sm.get_rework_state("v2") == "rework_v2"


def test_get_rework_state_v3(sm):
    """'v3' deve mapear para 'rework_v3'."""
    assert sm.get_rework_state("v3") == "rework_v3"


def test_get_next_validation_v1(sm):
    """'v1' deve avancar para 'validating_v2'."""
    assert sm.get_next_validation("v1") == "validating_v2"


def test_get_next_validation_v2(sm):
    """'v2' deve avancar para 'waiting_bench_b'."""
    assert sm.get_next_validation("v2") == "waiting_bench_b"


def test_get_next_validation_v3(sm):
    """'v3' deve avancar para 'approved'."""
    assert sm.get_next_validation("v3") == "approved"


def test_is_terminal_approved(sm):
    """'approved' e terminal."""
    assert sm.is_terminal("approved") is True


def test_is_terminal_rejected(sm):
    """'rejected' e terminal."""
    assert sm.is_terminal("rejected") is True


def test_is_terminal_identified_is_false(sm):
    """'identified' nao e terminal."""
    assert sm.is_terminal("identified") is False


def test_is_validating_true_for_all_validating_states(sm):
    """Somente estados validating_* retornam True."""
    for state in ("validating_v1", "validating_v2", "validating_v3"):
        assert sm.is_validating(state) is True, f"{state} should be validating"


def test_is_validating_false_for_non_validating_states(sm):
    """Estados nao-validating devem retornar False."""
    for state in ("idle", "identified", "rework_v1", "approved", "waiting_bench_b"):
        assert sm.is_validating(state) is False, f"{state} should not be validating"


def test_is_rework_true_for_all_rework_states(sm):
    """Somente estados rework_* retornam True."""
    for state in ("rework_v1", "rework_v2", "rework_v3"):
        assert sm.is_rework(state) is True, f"{state} should be rework"


def test_is_rework_false_for_non_rework_states(sm):
    """Estados nao-rework devem retornar False."""
    for state in ("idle", "identified", "validating_v1", "approved"):
        assert sm.is_rework(state) is False, f"{state} should not be rework"
