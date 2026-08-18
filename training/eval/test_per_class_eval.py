"""Fixa o comportamento do casamento — a parte do harness que decide o número.

Sem estes testes o harness é uma caixa-preta que devolve um float convincente.
Cada caso aqui corresponde a uma escolha declarada no cabeçalho do módulo; se
alguém trocar a regra de casamento, um destes quebra e diz qual regra mudou.
"""
from __future__ import annotations

from training.eval.per_class_eval import avalia, iou

# Duas caixas de 10x10: uma em (0,0), outra longe. Sobreposição total = IoU 1.
A = [0.0, 0.0, 10.0, 10.0]
LONGE = [100.0, 100.0, 110.0, 110.0]
MEIO = [5.0, 0.0, 15.0, 10.0]          # IoU 1/3 com A — abaixo de 0,5


def test_iou_casos_de_borda() -> None:
    assert iou(A, A) == 1.0
    assert iou(A, LONGE) == 0.0
    assert abs(iou(A, MEIO) - 1 / 3) < 1e-9


def test_acerto_simples() -> None:
    r = avalia({1: [(0.9, "mascara", A)]}, {1: [("mascara", A)]})
    assert r["per_class"]["mascara"] == {
        "precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 1, "fp": 0, "fn": 0, "n_gt": 1,
    }


def test_classe_errada_conta_duas_vezes() -> None:
    """A escolha mais severa do harness, e a que mais move o número.

    A predicao rouba a GT no casamento (cego a classe), erra a classe, e a GT
    fica sem par. Resultado: 1 fp para a classe predita E 1 fn para a verdadeira.
    Casar dentro da classe daria fp=1, fn=1 tambem — mas em imagens densas as
    duas regras divergem, porque aqui a caixa CONSOME a GT de outra classe.
    """
    r = avalia({1: [(0.9, "Óculos", A)]}, {1: [("mascara", A)]})
    assert r["per_class"]["Óculos"]["fp"] == 1
    assert r["per_class"]["mascara"]["fn"] == 1
    assert r["per_class"]["mascara"]["tp"] == 0
    assert r["confusion"] == {"mascara->Óculos": 1}


def test_iou_insuficiente_nao_casa() -> None:
    r = avalia({1: [(0.9, "mascara", MEIO)]}, {1: [("mascara", A)]})
    assert r["per_class"]["mascara"]["tp"] == 0
    assert r["per_class"]["mascara"]["fp"] == 1
    assert r["per_class"]["mascara"]["fn"] == 1
    assert r["confusion"] == {"fundo->mascara": 1}   # nao encostou em GT nenhuma


def test_score_maior_leva_a_gt() -> None:
    """Guloso por score: a segunda caixa sobre a mesma GT vira falso positivo."""
    r = avalia(
        {1: [(0.4, "mascara", A), (0.9, "mascara", A)]},
        {1: [("mascara", A)]},
    )
    assert r["per_class"]["mascara"]["tp"] == 1
    assert r["per_class"]["mascara"]["fp"] == 1


def test_gt_sem_predicao_e_predicao_sem_gt() -> None:
    r = avalia({1: [(0.9, "Botas", LONGE)]}, {1: [("mascara", A)]})
    assert r["per_class"]["Botas"]["fp"] == 1
    assert r["per_class"]["mascara"]["fn"] == 1
    assert r["per_class"]["mascara"]["recall"] == 0.0


def test_imagem_sem_nada_nao_quebra() -> None:
    assert avalia({}, {})["per_class"] == {}
    assert avalia({1: []}, {1: []})["per_class"] == {}
