"""
Testes unitários — CountingLineOperation (CD-01 / task-038).

Puros (sem DB, sem app context): instanciam a operação e simulam sequências
de frames encadeando state → state_next.

Geometria usada:
- Linha VERTICAL em x=0.5: lado positivo ('in') = esquerda (px < 0.5).
- Linha HORIZONTAL em y=0.5: lado positivo ('in') = abaixo (py > 0.5).
"""
from app.domain.services.operations.canonical.counting_line import CountingLineOperation

FW, FH = 640, 360
V_LINE = [[0.5, 0.0], [0.5, 1.0]]
H_LINE = [[0.0, 0.5], [1.0, 0.5]]


def _det(nx, ny=0.8, cls="roll", conf=0.9, track_id=1, w=40.0, h=80.0):
    """Detecção cujo ponto inferior central da bbox fica em (nx, ny) normalizado."""
    cx = nx * FW
    bottom = ny * FH
    return {
        "class": cls,
        "confidence": conf,
        "bbox": [cx - w / 2, bottom - h, w, h],
        "track_id": track_id,
    }


def _run(op, frames):
    """Roda evaluate frame a frame encadeando o estado. Retorna lista de outputs."""
    state: dict = {}
    outputs = []
    for dets in frames:
        out = op.evaluate(dets, {"width": FW, "height": FH}, state)
        state = out["state_next"]
        outputs.append(out)
    return outputs


def _run_xs(op, xs, track_id=1):
    """Sequência de posições x (linha vertical). None = frame sem detecção."""
    frames = [[] if x is None else [_det(x, track_id=track_id)] for x in xs]
    return _run(op, frames)


def _counts(outputs):
    return outputs[-1]["result"]["counts"]


class TestValidateConfig:
    """Validação de config — campos novos com default (retrocompat)."""

    def _op(self, **overrides):
        config = {"target_class": "roll", "line_points": V_LINE, **overrides}
        return CountingLineOperation(config), config

    def test_config_minima_valida(self):
        op, config = self._op()
        assert op.validate_config(config) == []

    def test_config_antiga_sem_campos_novos_continua_valida(self):
        # Config "antiga": só os obrigatórios — defaults cobrem o resto.
        op, config = self._op()
        for campo in (
            "anchor_point", "confirm_samples", "direction_debounce_frames",
            "confirmation_band", "track_memory_frames", "direction",
        ):
            assert campo not in config
        assert op.validate_config(config) == []

    def test_target_class_obrigatorio(self):
        op = CountingLineOperation({"line_points": V_LINE})
        assert any("target_class" in e for e in op.validate_config({"line_points": V_LINE}))

    def test_line_points_precisa_de_dois_pontos(self):
        op, config = self._op(line_points=[[0.5, 0.0]])
        assert any("line_points" in e for e in op.validate_config(config))
        op, config = self._op(line_points=[[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]])
        assert any("line_points" in e for e in op.validate_config(config))

    def test_line_points_coincidentes_rejeitados(self):
        op, config = self._op(line_points=[[0.5, 0.5], [0.5, 0.5]])
        assert any("coincidentes" in e for e in op.validate_config(config))

    def test_confirm_samples_invalidos(self):
        for valor in (0, -1, 2.5, True, "3"):
            op, config = self._op(confirm_samples=valor)
            assert any("confirm_samples" in e for e in op.validate_config(config)), valor

    def test_confirm_samples_um_e_valido(self):
        op, config = self._op(confirm_samples=1)
        assert op.validate_config(config) == []

    def test_direction_debounce_frames_invalidos(self):
        for valor in (-1, 1.5, True):
            op, config = self._op(direction_debounce_frames=valor)
            assert any("direction_debounce_frames" in e for e in op.validate_config(config)), valor

    def test_direction_debounce_zero_e_valido(self):
        op, config = self._op(direction_debounce_frames=0)
        assert op.validate_config(config) == []

    def test_confirmation_band_invalida(self):
        for valor in (-0.1, 0.6, True):
            op, config = self._op(confirmation_band=valor)
            assert any("confirmation_band" in e for e in op.validate_config(config)), valor

    def test_anchor_point_invalido(self):
        op, config = self._op(anchor_point="top_left")
        assert any("anchor_point" in e for e in op.validate_config(config))

    def test_direction_invalida(self):
        op, config = self._op(direction="sideways")
        assert any("direction" in e for e in op.validate_config(config))

    def test_track_memory_frames_invalido(self):
        op, config = self._op(track_memory_frames=0)
        assert any("track_memory_frames" in e for e in op.validate_config(config))


class TestAnchorPoint:
    """Ponto de referência: inferior central (default) vs centróide."""

    def _config(self, anchor=None):
        config = {"target_class": "roll", "line_points": H_LINE, "confirm_samples": 3}
        if anchor is not None:
            config["anchor_point"] = anchor
        return config

    def test_bottom_center_default_cruza_quando_a_base_cruza(self):
        # Base da bbox cruza a linha horizontal; centróide (40px acima) não.
        op = CountingLineOperation(self._config())
        outs = _run(op, [
            [_det(0.5, ny=0.30)],
            [_det(0.5, ny=0.40)],
            [_det(0.5, ny=0.55)],
        ])
        assert _counts(outs) == {"in": 1, "out": 0, "net": 1}

    def test_centroid_nao_cruza_na_mesma_sequencia(self):
        op = CountingLineOperation(self._config(anchor="centroid"))
        outs = _run(op, [
            [_det(0.5, ny=0.30)],
            [_det(0.5, ny=0.40)],
            [_det(0.5, ny=0.55)],
        ])
        assert _counts(outs) == {"in": 0, "out": 0, "net": 0}


class TestConfirmSamples:
    """Track novo só conta após ser visto em confirm_samples frames."""

    def _op(self, **overrides):
        return CountingLineOperation({
            "target_class": "roll",
            "line_points": V_LINE,
            "direction_debounce_frames": 0,
            **overrides,
        })

    def test_cruzamento_antes_de_n_amostras_nao_conta(self):
        op = self._op(confirm_samples=3)
        outs = _run_xs(op, [0.55, 0.45, 0.45])
        assert _counts(outs) == {"in": 0, "out": 0, "net": 0}

    def test_cruzamento_na_enesima_amostra_conta(self):
        op = self._op(confirm_samples=3)
        outs = _run_xs(op, [0.55, 0.55, 0.45])
        assert _counts(outs) == {"in": 1, "out": 0, "net": 1}

    def test_cruzamento_apos_n_amostras_conta(self):
        op = self._op(confirm_samples=3)
        outs = _run_xs(op, [0.55, 0.55, 0.55, 0.45])
        assert _counts(outs) == {"in": 1, "out": 0, "net": 1}

    def test_default_e_tres_amostras(self):
        # Sem confirm_samples na config: cruzamento no 2º frame é ruído.
        op = self._op()
        outs = _run_xs(op, [0.55, 0.45])
        assert _counts(outs) == {"in": 0, "out": 0, "net": 0}

    def test_confirm_samples_um_conta_imediato(self):
        op = self._op(confirm_samples=1)
        outs = _run_xs(op, [0.55, 0.45])
        assert _counts(outs) == {"in": 1, "out": 0, "net": 1}


class TestDirectionDebounce:
    """Mesmo track não conta duas vezes na mesma direção dentro da janela."""

    def _op(self, debounce):
        return CountingLineOperation({
            "target_class": "roll",
            "line_points": V_LINE,
            "confirm_samples": 1,
            "direction_debounce_frames": debounce,
        })

    def test_recontagem_na_mesma_direcao_bloqueada_dentro_da_janela(self):
        op = self._op(debounce=5)
        # f2 in (conta), f3 out (conta), f4 in (bloqueado: 4-2 <= 5),
        # f5 out (bloqueado: 5-3 <= 5), f9 in (9-2 > 5 → conta).
        outs = _run_xs(op, [0.55, 0.45, 0.55, 0.45, 0.55, 0.55, 0.55, 0.55, 0.45])
        assert _counts(outs) == {"in": 2, "out": 1, "net": 1}

    def test_debounce_zero_nao_bloqueia(self):
        op = self._op(debounce=0)
        outs = _run_xs(op, [0.55, 0.45, 0.55, 0.45])
        assert _counts(outs) == {"in": 2, "out": 1, "net": 1}


class TestHysteresisBand:
    """Zona de confirmação: oscilação sobre a linha não gera contagens múltiplas."""

    def _op(self, band):
        return CountingLineOperation({
            "target_class": "roll",
            "line_points": V_LINE,
            "confirm_samples": 1,
            "direction_debounce_frames": 0,
            "confirmation_band": band,
        })

    def test_oscilacao_dentro_da_banda_conta_uma_vez(self):
        op = self._op(band=0.05)
        # Cruza de verdade (0.6 → 0.4), depois fica oscilando em cima da linha.
        outs = _run_xs(op, [0.6, 0.4, 0.48, 0.53, 0.47, 0.54, 0.49])
        assert _counts(outs) == {"in": 1, "out": 0, "net": 1}

    def test_saida_completa_da_banda_confirma_retorno(self):
        op = self._op(band=0.05)
        outs = _run_xs(op, [0.6, 0.4, 0.48, 0.53, 0.47, 0.6])
        assert _counts(outs) == {"in": 1, "out": 1, "net": 0}

    def test_sem_banda_oscilacao_contaria_multiplas_vezes(self):
        # Contraste: é exatamente o defeito que a banda elimina.
        op = self._op(band=0.0)
        outs = _run_xs(op, [0.6, 0.4, 0.48, 0.53, 0.47, 0.54, 0.49])
        counts = _counts(outs)
        assert counts["in"] + counts["out"] > 1


class TestNetCount:
    """Vai-e-volta conta saldo líquido correto (bidirecional in/out/both)."""

    def _op(self, direction="both"):
        return CountingLineOperation({
            "target_class": "roll",
            "line_points": V_LINE,
            "confirm_samples": 1,
            "direction_debounce_frames": 0,
            "direction": direction,
        })

    def test_vai_e_volta_saldo_zero(self):
        op = self._op()
        outs = _run_xs(op, [0.55, 0.45, 0.55, 0.45, 0.55])
        assert _counts(outs) == {"in": 2, "out": 2, "net": 0}
        assert outs[-1]["metric_value"] == {"in": 2, "out": 2, "net": 0}

    def test_direction_in_expoe_so_entradas(self):
        op = self._op(direction="in")
        outs = _run_xs(op, [0.45, 0.55])
        # Só houve cruzamento 'out': métrica 'in' fica 0 e condição não dispara.
        assert outs[-1]["metric_value"] == 0
        assert outs[-1]["condition_satisfied"] is False

    def test_direction_out_expoe_so_saidas(self):
        op = self._op(direction="out")
        outs = _run_xs(op, [0.45, 0.55])
        assert outs[-1]["metric_value"] == 1
        assert outs[-1]["condition_satisfied"] is True


class TestStateExpiration:
    """counted_track_ids e tracks expiram — estado não cresce para sempre."""

    def test_track_sumido_e_expirado_do_estado(self):
        op = CountingLineOperation({
            "target_class": "roll",
            "line_points": V_LINE,
            "confirm_samples": 1,
            "track_memory_frames": 5,
        })
        outs = _run_xs(op, [0.55, 0.45] + [None] * 6)
        state = outs[-1]["state_next"]
        assert _counts(outs) == {"in": 1, "out": 0, "net": 1}
        assert state["tracks"] == {}
        assert state["counted_track_ids"] == {}

    def test_track_ativo_permanece_no_estado(self):
        op = CountingLineOperation({
            "target_class": "roll",
            "line_points": V_LINE,
            "confirm_samples": 1,
            "track_memory_frames": 5,
        })
        outs = _run_xs(op, [0.55, 0.45, 0.45])
        state = outs[-1]["state_next"]
        assert "t:1" in state["tracks"]
        assert "t:1" in state["counted_track_ids"]


class TestRetrocompatAndEmptyState:
    """Config antiga (mínima) e estado vazio funcionam com defaults."""

    def test_estado_vazio_nao_crasha(self):
        op = CountingLineOperation({"target_class": "roll", "line_points": V_LINE})
        out = op.evaluate([], {"width": FW, "height": FH}, {})
        assert out["result"]["counts"] == {"in": 0, "out": 0, "net": 0}
        assert out["condition_satisfied"] is False
        for key in ("frame_index", "counts", "tracks", "counted_track_ids"):
            assert key in out["state_next"]

    def test_config_minima_conta_com_defaults(self):
        # bottom_center + confirm_samples=3 + debounce=5 aplicados por default.
        op = CountingLineOperation({"target_class": "roll", "line_points": V_LINE})
        outs = _run_xs(op, [0.55, 0.55, 0.45])
        assert _counts(outs) == {"in": 1, "out": 0, "net": 1}

    def test_classe_errada_e_confianca_baixa_ignoradas(self):
        op = CountingLineOperation({
            "target_class": "roll", "line_points": V_LINE, "confirm_samples": 1,
        })
        outs = _run(op, [
            [_det(0.55, cls="person"), _det(0.55, conf=0.2, track_id=2)],
            [_det(0.45, cls="person"), _det(0.45, conf=0.2, track_id=2)],
        ])
        assert _counts(outs) == {"in": 0, "out": 0, "net": 0}


class TestPositionalFallback:
    """Detecção sem track_id usa tracking best-effort por posição."""

    def test_fallback_posicional_conta_cruzamento(self):
        op = CountingLineOperation({
            "target_class": "roll",
            "line_points": V_LINE,
            "confirm_samples": 2,
            "direction_debounce_frames": 0,
        })
        outs = _run_xs(op, [0.52, 0.48], track_id=None)
        assert _counts(outs) == {"in": 1, "out": 0, "net": 1}
        assert "p:0" in outs[-1]["state_next"]["counted_track_ids"]
