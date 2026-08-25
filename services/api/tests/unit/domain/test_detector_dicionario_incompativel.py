"""O detector denuncia dicionário de classe que não bate com o modelo (#542).

A correção do #542 fecha o caminho servido, mas fecha UM caminho. Este guarda
vale para qualquer construção, presente ou futura: o modelo diz quantas classes
emite, e se o dicionário tem outro tamanho os rótulos vão sair de outro
domínio.

Medido no modelo real: construído como o caminho servido fazia, o v15 emite 12
classes contra um dicionário COCO de 91 — e o guarda avisa. Com a taxonomia
certa, silêncio.

Aviso e não exceção de propósito: derrubar a inferência de 28 câmeras por um
dicionário suspeito seria pior que o defeito.
"""
from __future__ import annotations

import logging

from app.domain.detectors.base import Detector


class _Falso(Detector):
    """Detector mínimo — só o que o guarda olha."""

    def __init__(self, class_names):
        self._class_names = list(class_names)

    def predict(self, frame):  # pragma: no cover — não é o alvo do teste
        return []


_RVB12 = [f"c{i}" for i in range(12)]
_COCO91 = [f"coco{i}" for i in range(91)]


def test_dicionario_maior_que_o_modelo_avisa(caplog):
    """O caso do #542: modelo de 12 classes, dicionário COCO de 91.

    Ninguém reclamava porque um dicionário maior "cabe" — o índice 8 existe
    nos dois, só significa outra coisa.
    """
    d = _Falso(_COCO91)
    with caplog.at_level(logging.WARNING):
        d._confere_dicionario(12)

    assert "detector_dicionario_incompativel" in caplog.text
    assert "12" in caplog.text and "91" in caplog.text


def test_dicionario_menor_que_o_modelo_tambem_avisa(caplog):
    """Modelo re-treinado com classe nova + dicionário velho em cache."""
    d = _Falso(_RVB12)
    with caplog.at_level(logging.WARNING):
        d._confere_dicionario(13)
    assert "detector_dicionario_incompativel" in caplog.text


def test_dicionario_compativel_fica_em_silencio(caplog):
    d = _Falso(_RVB12)
    with caplog.at_level(logging.WARNING):
        d._confere_dicionario(12)
    assert caplog.text == ""


def test_avisa_uma_vez_so(caplog):
    """`predict` roda a cada frame — avisar sempre viraria ruído e some no log."""
    d = _Falso(_COCO91)
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            d._confere_dicionario(12)
    assert caplog.text.count("detector_dicionario_incompativel") == 1


def test_sem_dicionario_nao_inventa_alarme(caplog):
    d = _Falso([])
    with caplog.at_level(logging.WARNING):
        d._confere_dicionario(12)
    assert caplog.text == ""


def test_modelo_sem_classes_nao_inventa_alarme(caplog):
    """Saída degenerada é outro problema — não é este guarda que o denuncia."""
    d = _Falso(_RVB12)
    with caplog.at_level(logging.WARNING):
        d._confere_dicionario(0)
    assert caplog.text == ""


def test_o_guarda_e_por_instancia_nao_por_classe():
    """Um detector avisado não pode calar o próximo — o flag é de instância."""
    a, b = _Falso(_COCO91), _Falso(_COCO91)
    a._confere_dicionario(12)
    assert b._dicionario_conferido is False
