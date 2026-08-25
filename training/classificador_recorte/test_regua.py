"""A régua tem de reprovar quem merece — inclusive quem parece bom.

Três armadilhas que este arquivo fixa:

  · abstenção alta com precisão alta NÃO é qualidade (o vício do limiar do
    #536: prever menos erra menos);
  · precisão que empata com a linha de base é a distribuição, não o modelo;
  · quase-duplicata entre treino e campo mede memória, não generalização —
    medido no acervo real: 2 dos 62 frames de teste tinham cosseno 1,000 com
    um frame de treino.

Roda sem rede e sem GPU: `pytest training/classificador_recorte/test_regua.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch", reason="régua precisa de torch")

sys.path.insert(0, str(Path(__file__).parent))
import regua  # noqa: E402


def _logits(pares: list[tuple[int, float]], n_classes: int):
    """Constrói logits que produzem (classe_prevista, confiança) pedidos."""
    saida = torch.zeros(len(pares), n_classes)
    for i, (classe, conf) in enumerate(pares):
        # softmax de [0..0, x, 0..0] dá conf = e^x / (e^x + n-1)
        resto = n_classes - 1
        x = torch.log(torch.tensor(conf * resto / (1 - conf)))
        saida[i, classe] = x
    return saida


class TestAbstencaoEhContada:
    def test_limiar_alto_vira_abstencao_nao_acerto(self):
        # 4 exemplos da classe 0, todos previstos como 0 mas com confiança 0,6
        logits = _logits([(0, 0.6)] * 4, 2)
        alvo = torch.zeros(4, dtype=torch.long)
        baixo = regua.avalia(logits, alvo, ["a", "b"], 0.50)
        alto = regua.avalia(logits, alvo, ["a", "b"], 0.90)
        assert baixo["por_classe"]["a"]["recall"] == 1.0
        assert alto["por_classe"]["a"]["recall"] == 0.0, "abaixo do limiar não é acerto"
        assert alto["por_classe"]["a"]["abstencao"] == 1.0
        assert alto["abstencao_geral"] == 1.0

    def test_precisao_de_quem_se_cala_nao_e_none_disfarcada(self):
        """Sem predição nenhuma, precisão é None — não 0%, nem 100%."""
        logits = _logits([(0, 0.55)] * 3, 2)
        alvo = torch.zeros(3, dtype=torch.long)
        r = regua.avalia(logits, alvo, ["a", "b"], 0.90)
        assert r["por_classe"]["a"]["precisao"] is None
        assert r["por_classe"]["a"]["n_previsto"] == 0


class TestPrecisaoSeparaAcertoDeChute:
    def test_metade_certa_metade_errada(self):
        logits = _logits([(0, 0.99)] * 4, 2)
        alvo = torch.tensor([0, 0, 1, 1])
        r = regua.avalia(logits, alvo, ["a", "b"], 0.50)
        assert r["por_classe"]["a"]["precisao"] == 0.5
        assert r["por_classe"]["a"]["recall"] == 1.0
        assert r["por_classe"]["b"]["recall"] == 0.0

    def test_classe_ausente_do_campo_nao_inventa_numero(self):
        logits = _logits([(0, 0.99)] * 3, 2)
        alvo = torch.zeros(3, dtype=torch.long)
        r = regua.avalia(logits, alvo, ["a", "b"], 0.50)
        assert r["por_classe"]["b"]["recall"] is None
        assert r["por_classe"]["b"]["n_verdade"] == 0


class TestQuaseDuplicataSaiDoCampo:
    def _cenario(self, vetor_teste):
        frames = [
            {"frame_id": "tr1", "split": "train"},
            {"frame_id": "te1", "split": "test"},
        ]
        X = torch.tensor([[1.0, 0.0, 0.0], vetor_teste])
        return frames, X, {"tr1": 0, "te1": 1}

    def test_identico_e_pego(self):
        frames, X, idx = self._cenario([1.0, 0.0, 0.0])
        assert regua._quase_duplicatas(frames, X, idx, "test") == {"te1"}

    def test_diferente_fica(self):
        frames, X, idx = self._cenario([0.0, 1.0, 0.0])
        assert regua._quase_duplicatas(frames, X, idx, "test") == set()

    def test_escala_nao_engana_o_cosseno(self):
        """Mesma direção, norma diferente = mesma imagem em outro brilho."""
        frames, X, idx = self._cenario([5.0, 0.0, 0.0])
        assert regua._quase_duplicatas(frames, X, idx, "test") == {"te1"}

    def test_sem_treino_nao_explode(self):
        frames = [{"frame_id": "te1", "split": "test"}]
        X = torch.tensor([[1.0, 0.0]])
        assert regua._quase_duplicatas(frames, X, {"te1": 0}, "test") == set()


class TestOsPisosSaoOsDaAdr:
    def test_precisao_minima_e_a_da_adr_0067(self):
        assert regua.PRECISAO_MINIMA == 0.50

    def test_n_minimo_impede_afirmar_sobre_punhado(self):
        """'Sem Óculos' tinha 66,7% sobre n=3 no A/B do #536 — sorte."""
        assert regua.N_MINIMO_PARA_AFIRMAR >= 10

    def test_corte_de_duplicata_pega_frames_consecutivos(self):
        """0,98 pegaria só arquivo idêntico; 0,95 pega o mesmo instante."""
        assert regua.SIMILARIDADE_DUPLICATA <= 0.95
