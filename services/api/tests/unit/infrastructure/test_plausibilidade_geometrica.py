"""A caixa tem de ter o tamanho E a forma da classe que ela afirma ser.

Observação do dono do produto na folha de contato de campo: "algumas cenas
captam corretamente o uso incorreto de máscara e outras acabam identificando UMA
PESSOA INTEIRA como uso incorreto de máscara". Envelope derivado das anotações
humanas — query e justificativa em `domain/detectors/plausibilidade`.
"""
import numpy as np
import pytest

from app.domain.detectors import plausibilidade as p
from app.infrastructure.queue.tasks import inference

FULL_W, FULL_H = 1920, 1080


def _det(classe: str, w: int, h: int) -> dict:
    return {"class": classe, "confidence": 0.9, "bbox": [10, 20, w, h]}


# ── o envelope, nas três dimensões que ele julga ──────────────────────────────

def test_caixa_dentro_do_envelope_passa():
    """69x58 é o rosto: p50 humano de `Uso incorreto de mascara` é 69x58."""
    assert p.motivo_implausivel(
        "Uso incorreto de mascara", [0, 0, 69, 58], FULL_W, FULL_H
    ) is None


def test_fora_por_tamanho_e_rejeitada():
    """Largura 400px = 0,208 do quadro, contra o teto 0,0734 x 1,5 = 0,110."""
    assert p.motivo_implausivel(
        "mascara", [0, 0, 400, 300], FULL_W, FULL_H
    ) == "larga"


def test_fora_por_forma_e_rejeitada_mesmo_cabendo_no_tamanho():
    """O CASO DO DONO. 120x173px cabe no envelope de TAMANHO (173/1080 = 0,160
    contra o teto 0,1391 x 1,5 = 0,209) e só cai pela FORMA: h/w = 1,44 contra o
    p99 humano de 1,13. É este teste que prova que tamanho sozinho não bastava.
    """
    assert p.motivo_implausivel(
        "Uso incorreto de mascara", [0, 0, 120, 173], FULL_W, FULL_H
    ) == "forma"
    # e a irmã horizontal da mesma classe continua passando
    assert p.motivo_implausivel(
        "Uso incorreto de mascara", [0, 0, 69, 58], FULL_W, FULL_H
    ) is None


def test_o_caso_extremo_real_o_quadro_inteiro():
    """1922x1077 gravada no baseline como `Protetor auditivo` (conf 0,309):
    a caixa é o frame inteiro, 11x mais alta que o p90 humano."""
    assert p.motivo_implausivel(
        "Protetor auditivo", [0, 0, 1922, 1077], FULL_W, FULL_H
    ) == "larga"


def test_classe_sem_envelope_nao_explode_e_passa():
    """6 das 11 classes servidas não têm anotação humana em quadro cheio.
    Sem envelope = fail-open, nunca exceção."""
    assert p.motivo_implausivel("Luvas", [0, 0, 1900, 1000], FULL_W, FULL_H) is None
    assert p.motivo_implausivel("classe inexistente", [0, 0, 5, 5], FULL_W, FULL_H) is None


@pytest.mark.parametrize("bbox", [[0, 0, 0, 10], [0, 0, 10, 0], [0, 0, -5, 10]])
def test_caixa_degenerada_nao_divide_por_zero(bbox):
    assert p.motivo_implausivel("mascara", bbox, FULL_W, FULL_H) == "degenerada"


def test_quadro_sem_dimensao_deixa_passar():
    """Sem W/H não há fração possível — recusar detecção por metadado faltando
    seria apagar alerta por bug nosso."""
    assert p.motivo_implausivel("mascara", [0, 0, 400, 300], 0, 0) is None


def test_bbox_malformado_nao_derruba_o_worker():
    assert p.motivo_implausivel("mascara", [1, 2], FULL_W, FULL_H) is None
    assert p.motivo_implausivel("mascara", None, FULL_W, FULL_H) is None


# ── a escala: o envelope é fração do quadro, a forma é pixel ──────────────────

def test_envelope_atravessa_resolucao():
    """A MESMA máscara física em 1920x1080 e em 1280x720 ocupa a mesma fração —
    as duas têm de receber o mesmo veredito."""
    for w, h, W, H in ((82, 62, 1920, 1080), (55, 41, 1280, 720)):
        assert p.motivo_implausivel("mascara", [0, 0, w, h], W, H) is None


def test_forma_e_medida_em_pixel_nao_em_fracao():
    """82x62px é h/w = 0,76 (horizontal, forma de rosto). Em FRAÇÃO do quadro
    16:9 a mesma caixa daria 1,34 e seria lida como vertical — normalizar a
    forma inverteria o veredito. Este teste trava a unidade."""
    assert p.motivo_implausivel("mascara", [0, 0, 82, 62], FULL_W, FULL_H) is None


# ── o filtro, e a contabilidade da rejeição ──────────────────────────────────

def test_filtro_conta_e_loga_cada_rejeicao(caplog):
    dets = [_det("Uso incorreto de mascara", 120, 173), _det("mascara", 82, 62)]
    with caplog.at_level("INFO", logger=p.__name__):
        mantidas = p.filtrar_implausiveis(dets, FULL_W, FULL_H, "cam-1")
    assert [d["bbox"][2] for d in mantidas] == [82]
    assert "plausibilidade_rejeitou" in caplog.text
    assert "motivo=forma" in caplog.text
    assert "classe=Uso incorreto de mascara" in caplog.text


def test_descartar_tudo_avisa_alto():
    """100% fora é quase sempre envelope desalinhado ou recorte chegando ao
    caminho de quadro cheio — não um turno inteiro implausível."""
    dets = [_det("mascara", 1900, 1000)]
    import logging
    registros = []
    handler = logging.Handler()
    handler.emit = registros.append
    logger = logging.getLogger(p.__name__)
    logger.addHandler(handler)
    try:
        assert p.filtrar_implausiveis(dets, FULL_W, FULL_H, "cam-1") == []
    finally:
        logger.removeHandler(handler)
    assert any("plausibilidade_descartou_tudo" in r.getMessage() for r in registros)


# ── não-regressão: desligada por default ─────────────────────────────────────

def _frame():
    return np.zeros((FULL_H, FULL_W, 3), dtype=np.uint8)


def test_desligada_por_default_nao_altera_nada(monkeypatch):
    """Nasce DESLIGADA: é mudança de comportamento no caminho servido de um
    cliente em onboarding. Sem a env, a lista sai idêntica à que entrou."""
    monkeypatch.delenv("GEOMETRY_GUARD_ENABLED", raising=False)
    entrada = [_det("Protetor auditivo", 1922, 1077), _det("mascara", 82, 62)]
    assert inference._geometria_plausivel("cam-1", entrada, _frame()) is entrada


@pytest.mark.parametrize("valor", ["", "false", "0", "no", "TRUE_ISH"])
def test_so_a_palavra_true_liga(monkeypatch, valor):
    monkeypatch.setenv("GEOMETRY_GUARD_ENABLED", valor)
    entrada = [_det("Protetor auditivo", 1922, 1077)]
    assert inference._geometria_plausivel("cam-1", entrada, _frame()) is entrada


def test_ligada_filtra(monkeypatch):
    monkeypatch.setenv("GEOMETRY_GUARD_ENABLED", "true")
    entrada = [_det("Protetor auditivo", 1922, 1077), _det("mascara", 82, 62)]
    saida = inference._geometria_plausivel("cam-1", entrada, _frame())
    assert [d["bbox"][2] for d in saida] == [82]


def test_ligada_mas_frame_sem_shape_deixa_passar(monkeypatch):
    """Guarda ligada não é licença para chutar a dimensão do quadro."""
    monkeypatch.setenv("GEOMETRY_GUARD_ENABLED", "true")
    entrada = [_det("Protetor auditivo", 1922, 1077)]
    assert inference._geometria_plausivel("cam-1", entrada, object()) is entrada


def test_a_guarda_esta_nos_dois_caminhos_que_viram_alerta():
    """Ao vivo e retroativo. Pegar só um deixaria metade do produto com a caixa
    de pessoa inteira que o dono apontou."""
    import inspect
    fonte = inspect.getsource(inference)
    assert fonte.count("_geometria_plausivel(camera_id, detections, frame") == 2
    # e sempre ANTES do veredito de violação
    for trecho in ("frame)\n                has_violation", "frame_bgr)\n\n        if not _has_violation"):
        assert trecho in fonte
