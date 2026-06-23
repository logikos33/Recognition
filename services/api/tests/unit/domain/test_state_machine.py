"""Tests: PieceStateMachine — all transitions, validation types, and predicates."""
import pytest

from app.api.v1.quality.state_machine import PieceStateMachine, VALID_TRANSITIONS


class TestCanTransition:

    def test_valid_transition_idle_to_identified(self):
        sm = PieceStateMachine()
        assert sm.can_transition("idle", "identified") is True

    def test_invalid_transition_idle_to_approved(self):
        sm = PieceStateMachine()
        assert sm.can_transition("idle", "approved") is False

    def test_unknown_from_state_returns_false(self):
        sm = PieceStateMachine()
        assert sm.can_transition("nonexistent", "identified") is False

    def test_validating_v1_to_rework_v1(self):
        sm = PieceStateMachine()
        assert sm.can_transition("validating_v1", "rework_v1") is True

    def test_validating_v1_to_identified_false_positive(self):
        sm = PieceStateMachine()
        assert sm.can_transition("validating_v1", "identified") is True

    def test_terminal_approved_has_no_transitions(self):
        sm = PieceStateMachine()
        assert sm.can_transition("approved", "identified") is False

    def test_waiting_bench_b_to_validating_v3(self):
        sm = PieceStateMachine()
        assert sm.can_transition("waiting_bench_b", "validating_v3") is True


class TestTransition:

    def test_valid_transition_returns_new_state(self):
        sm = PieceStateMachine()
        assert sm.transition("idle", "identified") == "identified"

    def test_rework_v2_to_validating_v2(self):
        sm = PieceStateMachine()
        assert sm.transition("rework_v2", "validating_v2") == "validating_v2"

    def test_invalid_transition_raises_value_error(self):
        sm = PieceStateMachine()
        with pytest.raises(ValueError, match="Transição inválida"):
            sm.transition("idle", "approved")

    def test_error_message_includes_allowed_transitions(self):
        sm = PieceStateMachine()
        with pytest.raises(ValueError, match="identified"):
            sm.transition("idle", "validating_v1")

    def test_terminal_state_raises(self):
        sm = PieceStateMachine()
        with pytest.raises(ValueError):
            sm.transition("approved", "identified")


class TestGetValidationType:

    def test_validating_v1_returns_v1(self):
        sm = PieceStateMachine()
        assert sm.get_validation_type("validating_v1") == "v1"

    def test_validating_v2_returns_v2(self):
        sm = PieceStateMachine()
        assert sm.get_validation_type("validating_v2") == "v2"

    def test_validating_v3_returns_v3(self):
        sm = PieceStateMachine()
        assert sm.get_validation_type("validating_v3") == "v3"

    def test_non_validating_state_returns_none(self):
        sm = PieceStateMachine()
        assert sm.get_validation_type("idle") is None

    def test_rework_state_returns_none(self):
        sm = PieceStateMachine()
        assert sm.get_validation_type("rework_v1") is None

    def test_approved_returns_none(self):
        sm = PieceStateMachine()
        assert sm.get_validation_type("approved") is None


class TestGetReworkState:

    def test_v1_returns_rework_v1(self):
        sm = PieceStateMachine()
        assert sm.get_rework_state("v1") == "rework_v1"

    def test_v2_returns_rework_v2(self):
        sm = PieceStateMachine()
        assert sm.get_rework_state("v2") == "rework_v2"

    def test_v3_returns_rework_v3(self):
        sm = PieceStateMachine()
        assert sm.get_rework_state("v3") == "rework_v3"

    def test_invalid_type_raises_key_error(self):
        sm = PieceStateMachine()
        with pytest.raises(KeyError):
            sm.get_rework_state("v99")


class TestGetNextValidation:

    def test_v1_advances_to_validating_v2(self):
        sm = PieceStateMachine()
        assert sm.get_next_validation("v1") == "validating_v2"

    def test_v2_advances_to_waiting_bench_b(self):
        sm = PieceStateMachine()
        assert sm.get_next_validation("v2") == "waiting_bench_b"

    def test_v3_advances_to_approved(self):
        sm = PieceStateMachine()
        assert sm.get_next_validation("v3") == "approved"

    def test_invalid_returns_none(self):
        sm = PieceStateMachine()
        assert sm.get_next_validation("v99") is None


class TestIsTerminal:

    def test_approved_is_terminal(self):
        sm = PieceStateMachine()
        assert sm.is_terminal("approved") is True

    def test_rejected_is_terminal(self):
        sm = PieceStateMachine()
        assert sm.is_terminal("rejected") is True

    def test_idle_is_not_terminal(self):
        sm = PieceStateMachine()
        assert sm.is_terminal("idle") is False

    def test_validating_v1_is_not_terminal(self):
        sm = PieceStateMachine()
        assert sm.is_terminal("validating_v1") is False


class TestIsValidating:

    def test_validating_v1_is_validating(self):
        sm = PieceStateMachine()
        assert sm.is_validating("validating_v1") is True

    def test_validating_v2_is_validating(self):
        sm = PieceStateMachine()
        assert sm.is_validating("validating_v2") is True

    def test_validating_v3_is_validating(self):
        sm = PieceStateMachine()
        assert sm.is_validating("validating_v3") is True

    def test_idle_is_not_validating(self):
        sm = PieceStateMachine()
        assert sm.is_validating("idle") is False

    def test_rework_v1_is_not_validating(self):
        sm = PieceStateMachine()
        assert sm.is_validating("rework_v1") is False

    def test_approved_is_not_validating(self):
        sm = PieceStateMachine()
        assert sm.is_validating("approved") is False


class TestIsRework:

    def test_rework_v1_is_rework(self):
        sm = PieceStateMachine()
        assert sm.is_rework("rework_v1") is True

    def test_rework_v2_is_rework(self):
        sm = PieceStateMachine()
        assert sm.is_rework("rework_v2") is True

    def test_rework_v3_is_rework(self):
        sm = PieceStateMachine()
        assert sm.is_rework("rework_v3") is True

    def test_identified_is_not_rework(self):
        sm = PieceStateMachine()
        assert sm.is_rework("identified") is False

    def test_validating_v1_is_not_rework(self):
        sm = PieceStateMachine()
        assert sm.is_rework("validating_v1") is False


class TestValidTransitionsMap:
    """Sanity-check the module-level constant."""

    def test_idle_allows_only_identified(self):
        assert VALID_TRANSITIONS["idle"] == ["identified"]

    def test_approved_has_no_transitions(self):
        assert VALID_TRANSITIONS["approved"] == []

    def test_all_rework_states_have_one_valid_transition(self):
        for state in ("rework_v1", "rework_v2", "rework_v3"):
            assert len(VALID_TRANSITIONS[state]) == 1
