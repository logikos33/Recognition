"""
Tests: CountingLineOperation — confirm_samples + direction_debounce_frames (R6).

Linha horizontal y=0.5. Posições de teste compartilham a mesma chave de posição
(round(cy,2)=0.5) mas ficam em lados opostos:
  CY_ABOVE=0.499 → side<0  (acima da linha)
  CY_BELOW=0.501 → side>0  (abaixo da linha)
"""
from app.domain.services.operations.canonical.counting_line import CountingLineOperation

# ── Constantes de cena ────────────────────────────────────────────────────────

FRAME_META = {"width": 100, "height": 100}
LINE = [[0.0, 0.5], [1.0, 0.5]]
CX = 0.5
CY_ABOVE = 0.499   # round(0.499,2)==0.5; side = 0.499-0.5 = -0.001 (negativo)
CY_BELOW = 0.501   # round(0.501,2)==0.5; side = 0.501-0.5 = +0.001 (positivo)

CONFIG_BASE = {
    "line_points": LINE,
    "direction": "both",
    "target_class": "person",
    "confidence_threshold": 0.5,
}


def _det(cy: float, cx: float = CX, cls: str = "person", conf: float = 0.9) -> dict:
    """Detection com centro normalizado (cx, cy). bbox=[x1,y1,w,h] com w=h=0."""
    fw, fh = FRAME_META["width"], FRAME_META["height"]
    return {"class": cls, "confidence": conf, "bbox": [cx * fw, cy * fh, 0, 0]}


def _run(op: CountingLineOperation, frames: list[list[dict]]) -> list[dict]:
    """Executa op frame a frame, propagando estado."""
    state: dict = {}
    results = []
    for dets in frames:
        result = op.evaluate(dets, FRAME_META, state)
        state = result["state_next"]
        results.append(result)
    return results


# ── confirm_samples ───────────────────────────────────────────────────────────


class TestConfirmSamples:
    def test_default_3_counts_only_after_third_frame(self):
        """Com confirm_samples=3 (default), cruzamento só é contado após 3 frames no novo lado."""
        op = CountingLineOperation({**CONFIG_BASE})
        frames = [
            [_det(CY_ABOVE)],  # frame 1: acima (estabelece prev_side)
            [_det(CY_BELOW)],  # frame 2: cruza → pending frames=1
            [_det(CY_BELOW)],  # frame 3: ainda abaixo → frames=2
            [_det(CY_BELOW)],  # frame 4: ainda abaixo → frames=3 → CONFIRMA
        ]
        results = _run(op, frames)
        assert results[1]["result"]["count_in"] == 0, "frame 2: ainda não confirmado"
        assert results[2]["result"]["count_in"] == 0, "frame 3: ainda não confirmado"
        assert results[3]["result"]["count_in"] == 1, "frame 4: deve confirmar"

    def test_noise_1_frame_does_not_count(self):
        """1 frame isolado no novo lado (ruído) não conta com confirm_samples=3."""
        op = CountingLineOperation({**CONFIG_BASE})
        frames = [
            [_det(CY_ABOVE)],
            [_det(CY_BELOW)],  # cruzamento breve
            [_det(CY_ABOVE)],  # volta
        ]
        results = _run(op, frames)
        assert results[-1]["result"]["count_in"] == 0

    def test_noise_2_frames_does_not_count(self):
        """2 frames no novo lado seguidos de retorno não contam com confirm_samples=3."""
        op = CountingLineOperation({**CONFIG_BASE})
        frames = [
            [_det(CY_ABOVE)],
            [_det(CY_BELOW)],
            [_det(CY_BELOW)],
            [_det(CY_ABOVE)],  # cancela pending
        ]
        results = _run(op, frames)
        assert results[-1]["result"]["count_in"] == 0

    def test_confirm_samples_1_counts_immediately(self):
        """confirm_samples=1 reproduz comportamento original — conta no 1º frame de cruzamento."""
        op = CountingLineOperation({**CONFIG_BASE, "confirm_samples": 1})
        frames = [
            [_det(CY_ABOVE)],
            [_det(CY_BELOW)],  # conta imediatamente
        ]
        results = _run(op, frames)
        assert results[1]["result"]["count_in"] == 1

    def test_confirm_samples_2_counts_on_second_frame(self):
        """confirm_samples=2: confirma após 2 frames no novo lado."""
        op = CountingLineOperation({**CONFIG_BASE, "confirm_samples": 2})
        frames = [
            [_det(CY_ABOVE)],
            [_det(CY_BELOW)],  # pending frames=1 < 2
            [_det(CY_BELOW)],  # frames=2 → CONFIRMA
        ]
        results = _run(op, frames)
        assert results[1]["result"]["count_in"] == 0
        assert results[2]["result"]["count_in"] == 1

    def test_count_out_direction(self):
        """Cruzamento na direção 'out' (abaixo → acima) é contado corretamente."""
        op = CountingLineOperation({**CONFIG_BASE, "confirm_samples": 3})
        frames = [
            [_det(CY_BELOW)],  # abaixo (estabelece prev)
            [_det(CY_ABOVE)],  # cruza out → pending
            [_det(CY_ABOVE)],
            [_det(CY_ABOVE)],  # confirma out
        ]
        results = _run(op, frames)
        assert results[3]["result"]["count_out"] == 1
        assert results[3]["result"]["count_in"] == 0

    def test_consecutive_crossings_both_counted(self):
        """Dois cruzamentos consecutivos (in + out) sem debounce são contados separadamente."""
        op = CountingLineOperation({**CONFIG_BASE, "confirm_samples": 1, "direction_debounce_frames": 0})
        frames = [
            [_det(CY_ABOVE)],
            [_det(CY_BELOW)],  # in
            [_det(CY_ABOVE)],  # out (sem debounce)
        ]
        results = _run(op, frames)
        assert results[1]["result"]["count_in"] == 1
        assert results[2]["result"]["count_out"] == 1

    def test_defaults_absent_from_config(self):
        """Ausência de confirm_samples e direction_debounce_frames usa defaults (3 e 5)."""
        op = CountingLineOperation({**CONFIG_BASE})
        # Sem os campos, confirm_samples=3 → 2 frames não contam
        frames = [
            [_det(CY_ABOVE)],
            [_det(CY_BELOW)],
            [_det(CY_BELOW)],
        ]
        results = _run(op, frames)
        assert results[-1]["result"]["count_in"] == 0  # ainda não (precisa de 3 frames)


# ── direction_debounce_frames ─────────────────────────────────────────────────


class TestDirectionDebounce:
    def test_reversal_within_window_not_counted(self):
        """Reversão imediata dentro da janela de debounce não é contada."""
        op = CountingLineOperation({**CONFIG_BASE, "confirm_samples": 1, "direction_debounce_frames": 5})
        frames = [
            [_det(CY_ABOVE)],
            [_det(CY_BELOW)],  # in → count_in=1, debounce frame=2
            [_det(CY_ABOVE)],  # out → debounced (frame_count=3, 3-2=1 < 5)
        ]
        results = _run(op, frames)
        assert results[1]["result"]["count_in"] == 1
        assert results[2]["result"]["count_out"] == 0
        assert results[2]["result"]["count_in"] == 1  # count_in inalterado

    def test_reversal_after_window_is_counted(self):
        """Reversão após expirar o debounce é contada normalmente."""
        op = CountingLineOperation({**CONFIG_BASE, "confirm_samples": 1, "direction_debounce_frames": 3})
        # in no frame 2 (frame_count=2), out no frame 6 (frame_count=6), diff=4 >= 3
        frames = [
            [_det(CY_ABOVE)],    # frame 1
            [_det(CY_BELOW)],    # frame 2: in, debounce recorded
            [_det(CY_BELOW)],    # frame 3
            [_det(CY_BELOW)],    # frame 4
            [_det(CY_BELOW)],    # frame 5
            [_det(CY_ABOVE)],    # frame 6: out, 6-2=4 >= 3 → não debounced
        ]
        results = _run(op, frames)
        assert results[1]["result"]["count_in"] == 1
        assert results[5]["result"]["count_out"] == 1

    def test_debounce_0_no_debounce(self):
        """direction_debounce_frames=0 desativa debounce — reversão imediata é contada."""
        op = CountingLineOperation({**CONFIG_BASE, "confirm_samples": 1, "direction_debounce_frames": 0})
        frames = [
            [_det(CY_ABOVE)],
            [_det(CY_BELOW)],  # in
            [_det(CY_ABOVE)],  # out — sem debounce
        ]
        results = _run(op, frames)
        assert results[1]["result"]["count_in"] == 1
        assert results[2]["result"]["count_out"] == 1

    def test_same_direction_not_debounced(self):
        """Mesmo sentido consecutivo NÃO é bloqueado pelo debounce (não é reversão)."""
        op = CountingLineOperation({**CONFIG_BASE, "confirm_samples": 1, "direction_debounce_frames": 10})
        # Dois objetos diferentes cruzando na mesma direção
        cx2 = 0.3
        frames = [
            [_det(CY_ABOVE, cx=CX), _det(CY_ABOVE, cx=cx2)],
            [_det(CY_BELOW, cx=CX), _det(CY_BELOW, cx=cx2)],  # dois "in"
        ]
        results = _run(op, frames)
        # Dois objetos com chaves diferentes → ambos contados
        assert results[1]["result"]["count_in"] == 2

    def test_debounce_with_confirm_samples(self):
        """Debounce funciona combinado com confirm_samples > 1."""
        op = CountingLineOperation({**CONFIG_BASE, "confirm_samples": 2, "direction_debounce_frames": 5})
        frames = [
            [_det(CY_ABOVE)],   # frame 1
            [_det(CY_BELOW)],   # frame 2: pending frames=1
            [_det(CY_BELOW)],   # frame 3: frames=2 → CONFIRMA in, debounce frame=3
            [_det(CY_ABOVE)],   # frame 4: pending out frames=1
            [_det(CY_ABOVE)],   # frame 5: frames=2 → tentaria confirmar out, mas 5-3=2 < 5 → debounced
        ]
        results = _run(op, frames)
        assert results[2]["result"]["count_in"] == 1
        assert results[4]["result"]["count_out"] == 0  # debounced


# ── validate_config ───────────────────────────────────────────────────────────


class TestValidateConfig:
    def _op(self, config: dict) -> CountingLineOperation:
        return CountingLineOperation(config)

    def _base(self, **extra) -> dict:
        return {
            "line_points": LINE,
            "direction": "both",
            "target_class": "person",
            **extra,
        }

    def test_valid_without_new_fields(self):
        op = self._op(self._base())
        assert op.validate_config(op.config) == []

    def test_valid_confirm_samples_1(self):
        op = self._op(self._base(confirm_samples=1))
        assert op.validate_config(op.config) == []

    def test_valid_confirm_samples_large(self):
        op = self._op(self._base(confirm_samples=100))
        assert op.validate_config(op.config) == []

    def test_invalid_confirm_samples_zero(self):
        op = self._op(self._base(confirm_samples=0))
        errors = op.validate_config(op.config)
        assert any("confirm_samples" in e for e in errors)

    def test_invalid_confirm_samples_negative(self):
        op = self._op(self._base(confirm_samples=-1))
        errors = op.validate_config(op.config)
        assert any("confirm_samples" in e for e in errors)

    def test_invalid_confirm_samples_float(self):
        op = self._op(self._base(confirm_samples=2.5))
        errors = op.validate_config(op.config)
        assert any("confirm_samples" in e for e in errors)

    def test_invalid_confirm_samples_bool(self):
        # bool é subclasse de int no Python — deve ser rejeitado explicitamente
        op = self._op(self._base(confirm_samples=True))
        errors = op.validate_config(op.config)
        assert any("confirm_samples" in e for e in errors)

    def test_valid_debounce_zero(self):
        op = self._op(self._base(direction_debounce_frames=0))
        assert op.validate_config(op.config) == []

    def test_valid_debounce_positive(self):
        op = self._op(self._base(direction_debounce_frames=10))
        assert op.validate_config(op.config) == []

    def test_invalid_debounce_negative(self):
        op = self._op(self._base(direction_debounce_frames=-1))
        errors = op.validate_config(op.config)
        assert any("direction_debounce" in e for e in errors)

    def test_invalid_debounce_float(self):
        op = self._op(self._base(direction_debounce_frames=1.5))
        errors = op.validate_config(op.config)
        assert any("direction_debounce" in e for e in errors)

    def test_invalid_debounce_bool(self):
        op = self._op(self._base(direction_debounce_frames=False))
        errors = op.validate_config(op.config)
        assert any("direction_debounce" in e for e in errors)

    def test_invalid_both_fields(self):
        op = self._op(self._base(confirm_samples=0, direction_debounce_frames=-2))
        errors = op.validate_config(op.config)
        assert any("confirm_samples" in e for e in errors)
        assert any("direction_debounce" in e for e in errors)
