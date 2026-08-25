"""Falha de inferência não pode ser publicada como "nada de errado".

`predict()` devolve `[]` tanto quando não viu nada quanto quando explodiu, e o
laço publicava `has_violation: false` nos dois casos — mais o caso em que o
detector nem carregou. A grade ao vivo (`useMonitoringSocket` →
`CameraGrid`) lê esse payload e pinta a câmera de verde.

Num produto de segurança, "não consegui olhar" pintado como "está tudo certo"
é o erro caro: ninguém vai investigar uma câmera que parece conforme.
"""
from app.domain.detectors.base import Detector


class _Falso(Detector):
    """Detector mínimo para exercitar o contrato."""

    def __init__(self, pronto: bool = True, explode: bool = False) -> None:
        self._pronto = pronto
        self._explode = explode

    @property
    def is_ready(self) -> bool:
        return self._pronto

    def predict(self, frame):  # type: ignore[override]
        if self._explode:
            self.ultimo_erro = "RuntimeError: onnx morreu"
            return []
        return []


def _estado(detector: Detector) -> bool:
    """Reproduz a decisão do laço (inference.py) sobre `inferencia_ok`."""
    inferencia_ok = bool(detector.is_ready)
    if detector.is_ready:
        detector.ultimo_erro = None
        detector.predict(object())
        if detector.ultimo_erro is not None:
            inferencia_ok = False
    return inferencia_ok


def test_detector_nao_carregado_nao_afirma_conformidade():
    assert _estado(_Falso(pronto=False)) is False


def test_predict_que_explodiu_nao_afirma_conformidade():
    """O caso traiçoeiro: devolveu [] como quem viu um frame limpo."""
    assert _estado(_Falso(explode=True)) is False


def test_frame_realmente_limpo_continua_sendo_conformidade():
    """Sem isto o conserto viraria alarme permanente."""
    assert _estado(_Falso()) is True


def test_erro_nao_vaza_de_um_frame_para_o_seguinte():
    """O laço zera antes de cada predict — senão uma falha contamina para sempre."""
    d = _Falso(explode=True)
    assert _estado(d) is False
    d._explode = False
    assert _estado(d) is True


def test_a_interface_declara_o_campo():
    """Contrato na base: vale para qualquer backend, não só os dois de hoje."""
    assert hasattr(Detector, "ultimo_erro")
    assert Detector.ultimo_erro is None
