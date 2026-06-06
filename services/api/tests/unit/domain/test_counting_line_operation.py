"""
Tests — CountingLineOperation multi-amostra (task-038, contenção R6).

Posições: cx=0.498 e cx=0.502 arredondam para key "0.5,0.5" mas ficam
em lados opostos da linha x=0.5 — necessário para que o histórico
acumule sob a mesma chave posicional ao longo dos frames.

  SIDE_A (cx=0.498): side_val > 0  →  A→B = count_out
  SIDE_B (cx=0.502): side_val < 0  →  B→A = count_in
"""
from app.domain.services.operations.canonical.counting_line import CountingLineOperation

_LINE = [[0.5, 0.0], [0.5, 1.0]]
_SIDE_A = 0.498  # rounds to key "0.5,0.5", side > 0
_SIDE_B = 0.502  # rounds to key "0.5,0.5", side < 0
FRAME_W = 100
FRAME_H = 100


def _make_det(cx_norm: float, cy_norm: float = 0.5, cls: str = "person", conf: float = 0.9) -> dict:
    x = cx_norm * FRAME_W - 5
    y = cy_norm * FRAME_H - 5
    return {"class": cls, "confidence": conf, "bbox": [x, y, 10, 10]}


def _frame_meta() -> dict:
    return {"width": FRAME_W, "height": FRAME_H}


def _op(confirm: int = 3, debounce: int = 5, direction: str = "both") -> CountingLineOperation:
    return CountingLineOperation(
        config={
            "line_points": _LINE,
            "direction": direction,
            "target_class": "person",
            "confidence_threshold": 0.1,
            "confirm_samples": confirm,
            "direction_debounce_frames": debounce,
        }
    )


def _dets(side: str) -> list:
    """'A' → SIDE_A, 'B' → SIDE_B, '-' → sem detecção."""
    if side == "A":
        return [_make_det(_SIDE_A)]
    if side == "B":
        return [_make_det(_SIDE_B)]
    return []


def _run_seq(op: CountingLineOperation, sides: list[str]) -> dict:
    state: dict = {}
    for s in sides:
        result = op.evaluate(_dets(s), _frame_meta(), state)
        state = result["state_next"]
    return state


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def _base(self, **kw) -> dict:
        cfg = {"line_points": [[0.0, 0.5], [1.0, 0.5]], "direction": "both", "target_class": "person"}
        cfg.update(kw)
        return cfg

    def test_valid_without_new_fields(self):
        op = CountingLineOperation(config={})
        assert op.validate_config(self._base()) == []

    def test_valid_with_new_fields(self):
        op = CountingLineOperation(config={})
        assert op.validate_config(self._base(confirm_samples=5, direction_debounce_frames=10)) == []

    def test_confirm_samples_zero_rejected(self):
        op = CountingLineOperation(config={})
        errors = op.validate_config(self._base(confirm_samples=0))
        assert any("confirm_samples" in e for e in errors)

    def test_confirm_samples_negative_rejected(self):
        op = CountingLineOperation(config={})
        errors = op.validate_config(self._base(confirm_samples=-1))
        assert any("confirm_samples" in e for e in errors)

    def test_confirm_samples_one_valid(self):
        op = CountingLineOperation(config={})
        assert op.validate_config(self._base(confirm_samples=1)) == []

    def test_confirm_samples_float_rejected(self):
        op = CountingLineOperation(config={})
        errors = op.validate_config(self._base(confirm_samples=2.5))
        assert any("confirm_samples" in e for e in errors)

    def test_confirm_samples_bool_rejected(self):
        op = CountingLineOperation(config={})
        errors = op.validate_config(self._base(confirm_samples=True))
        assert any("confirm_samples" in e for e in errors)

    def test_debounce_zero_valid(self):
        op = CountingLineOperation(config={})
        assert op.validate_config(self._base(direction_debounce_frames=0)) == []

    def test_debounce_negative_rejected(self):
        op = CountingLineOperation(config={})
        errors = op.validate_config(self._base(direction_debounce_frames=-1))
        assert any("direction_debounce_frames" in e for e in errors)

    def test_debounce_float_rejected(self):
        op = CountingLineOperation(config={})
        errors = op.validate_config(self._base(direction_debounce_frames=3.0))
        assert any("direction_debounce_frames" in e for e in errors)

    def test_debounce_bool_rejected(self):
        op = CountingLineOperation(config={})
        errors = op.validate_config(self._base(direction_debounce_frames=False))
        assert any("direction_debounce_frames" in e for e in errors)


# ---------------------------------------------------------------------------
# confirm_samples — confirmação só após N frames consecutivos no novo lado
# ---------------------------------------------------------------------------


class TestConfirmSamples:
    def test_no_crossing_before_confirm_samples(self):
        """A×3 (estabelece lado), B×2 (< confirm_samples=3) → não conta."""
        op = _op(confirm=3, debounce=0)
        state = _run_seq(op, ["A", "A", "A", "B", "B"])
        assert state["count_out"] == 0

    def test_crossing_confirmed_after_exactly_confirm_samples(self):
        """A×3, depois B×3 (= confirm_samples) → conta exatamente 1."""
        op = _op(confirm=3, debounce=0)
        state = _run_seq(op, ["A", "A", "A", "B", "B", "B"])
        assert state["count_out"] == 1

    def test_noise_single_frame_does_not_count(self):
        """1 frame no novo lado (ruído) não conta com confirm_samples=3."""
        op = _op(confirm=3, debounce=0)
        state = _run_seq(op, ["A", "A", "A"])
        r = op.evaluate(_dets("B"), _frame_meta(), state)
        assert r["state_next"]["count_out"] == 0

    def test_noise_two_frames_do_not_count(self):
        """2 frames no novo lado (ruído) não contam com confirm_samples=3."""
        op = _op(confirm=3, debounce=0)
        state = _run_seq(op, ["A", "A", "A"])
        state2 = state
        for _ in range(2):
            r = op.evaluate(_dets("B"), _frame_meta(), state2)
            state2 = r["state_next"]
        assert state2["count_out"] == 0

    def test_confirm_samples_1_counts_immediately(self):
        """confirm_samples=1 conta na primeira mudança de lado (comportamento original)."""
        op = _op(confirm=1, debounce=0)
        state = _run_seq(op, ["A"])
        r = op.evaluate(_dets("B"), _frame_meta(), state)
        assert r["state_next"]["count_out"] == 1

    def test_confirm_samples_2_requires_two_frames(self):
        """confirm_samples=2: 1 frame no novo lado não conta, 2 frames conta."""
        op = _op(confirm=2, debounce=0)
        state = _run_seq(op, ["A", "A"])
        r1 = op.evaluate(_dets("B"), _frame_meta(), state)
        assert r1["state_next"]["count_out"] == 0
        r2 = op.evaluate(_dets("B"), _frame_meta(), r1["state_next"])
        assert r2["state_next"]["count_out"] == 1

    def test_interruption_resets_accumulation(self):
        """A×3, B×2 (sem confirmar), A×1 (interrupção), B×3 → conta 1 cruzamento."""
        op = _op(confirm=3, debounce=0)
        state = _run_seq(op, ["A", "A", "A", "B", "B", "A", "B", "B", "B"])
        assert state["count_out"] == 1

    def test_defaults_confirm_3(self):
        """Config sem campos novos usa confirm_samples=3 por padrão."""
        op = CountingLineOperation(
            config={
                "line_points": _LINE,
                "direction": "both",
                "target_class": "person",
                "confidence_threshold": 0.1,
            }
        )
        # 2 frames no novo lado: não confirma (default confirm=3)
        state = _run_seq(op, ["A", "A", "A", "B", "B"])
        assert state["count_out"] == 0
        # 3º frame confirma
        r = op.evaluate(_dets("B"), _frame_meta(), state)
        assert r["state_next"]["count_out"] == 1


# ---------------------------------------------------------------------------
# direction_debounce_frames — evita dupla contagem em reversão rápida
# ---------------------------------------------------------------------------


class TestDirectionDebounce:
    def test_quick_reversal_does_not_double_count(self):
        """A→B conta (count_out=1); reversão rápida (<5 frames) não conta count_in."""
        op = _op(confirm=1, debounce=5)
        state = _run_seq(op, ["A", "B"])
        assert state["count_out"] == 1
        state2 = state
        for _ in range(3):
            r = op.evaluate(_dets("A"), _frame_meta(), state2)
            state2 = r["state_next"]
        assert state2["count_in"] == 0

    def test_crossing_counted_after_debounce_expires(self):
        """Após debounce expirar (3 frames), cruzamento legítimo de volta é contado."""
        op = _op(confirm=1, debounce=3)
        state = _run_seq(op, ["A", "B"])
        assert state["count_out"] == 1
        # 3 frames em B esgotam o debounce
        for _ in range(3):
            r = op.evaluate(_dets("B"), _frame_meta(), state)
            state = r["state_next"]
        # Volta para A: debounce=0, deve contar
        r = op.evaluate(_dets("A"), _frame_meta(), state)
        assert r["state_next"]["count_in"] == 1

    def test_debounce_zero_allows_immediate_reversal(self):
        """debounce=0 permite contar reversão imediata."""
        op = _op(confirm=1, debounce=0)
        state = _run_seq(op, ["A", "B"])
        assert state["count_out"] == 1
        r = op.evaluate(_dets("A"), _frame_meta(), state)
        assert r["state_next"]["count_in"] == 1

    def test_debounce_with_confirm_samples(self):
        """confirm=3 + debounce=5: confirmação A→B ok; reversão em 2 frames bloqueada."""
        op = _op(confirm=3, debounce=5)
        state = _run_seq(op, ["A", "A", "A", "B", "B", "B"])
        assert state["count_out"] == 1
        state2 = state
        for _ in range(2):
            r = op.evaluate(_dets("A"), _frame_meta(), state2)
            state2 = r["state_next"]
        assert state2["count_in"] == 0

    def test_multiple_crossings_accumulate(self):
        """A→B (count_out), debounce esgota, B→A (count_in): total = 2."""
        op = _op(confirm=1, debounce=2)
        # A(estabelece), B(conta out, debounce=2), B(debounce=1), B(debounce=0), A(conta in)
        state = _run_seq(op, ["A", "B", "B", "B", "A"])
        assert state["count_out"] == 1
        assert state["count_in"] == 1
        assert state["count_in"] + state["count_out"] == 2


# ---------------------------------------------------------------------------
# Filtro de direção (metric_value)
# ---------------------------------------------------------------------------


class TestDirectionFilter:
    def test_direction_in_only_counts_in(self):
        op = _op(confirm=1, debounce=0, direction="in")
        state = _run_seq(op, ["B"])
        r = op.evaluate(_dets("A"), _frame_meta(), state)
        assert r["metric_value"] == 1

    def test_direction_out_only_counts_out(self):
        op = _op(confirm=1, debounce=0, direction="out")
        state = _run_seq(op, ["A"])
        r = op.evaluate(_dets("B"), _frame_meta(), state)
        assert r["metric_value"] == 1

    def test_direction_both_metric_equals_count_total(self):
        op = _op(confirm=1, debounce=0, direction="both")
        state = _run_seq(op, ["A"])
        r = op.evaluate(_dets("B"), _frame_meta(), state)
        assert r["metric_value"] == r["result"]["count_total"]


# ---------------------------------------------------------------------------
# Estado inicial vazio
# ---------------------------------------------------------------------------


class TestEmptyState:
    def test_empty_state_does_not_crash(self):
        op = _op(confirm=3, debounce=5)
        r = op.evaluate([_make_det(_SIDE_A)], _frame_meta(), {})
        assert "state_next" in r
        assert r["result"]["count_in"] == 0
        assert r["result"]["count_out"] == 0

    def test_state_next_has_required_keys(self):
        op = _op()
        r = op.evaluate([], _frame_meta(), {})
        sn = r["state_next"]
        for key in ("count_in", "count_out", "side_history", "last_confirmed_side", "debounce_left"):
            assert key in sn

    def test_no_detections_preserves_counts(self):
        op = _op(confirm=1, debounce=0)
        state = _run_seq(op, ["A", "B"])  # count_out = 1
        r = op.evaluate([], _frame_meta(), state)
        assert r["state_next"]["count_out"] == 1
