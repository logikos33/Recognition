"""A caixa [0,0,1,1] da aba Classificar não é alvo de localização.

Medido no RVB em 2026-08-25: 1.095 das 4.629 anotações manuais (23,7%) eram
exatamente cx=0,5 cy=0,5 w=1 h=1 — o FULL_FRAME_BBOX que CropClassifier.tsx
usa como placeholder de recorte de pessoa. Elas chegavam ao treino como
verdade de localização, em 420 frames que não tinham nenhuma outra caixa.
"""
from app.infrastructure.queue.tasks.versioning_v2 import (
    _e_rotulo_de_frame,
    _sem_rotulos_de_frame,
)


def _caixa(frame_id: str, w: float, h: float) -> dict:
    return {"frame_id": frame_id, "class_id": 1, "class_name": "Luvas",
            "x_center": 0.5, "y_center": 0.5, "width": w, "height": h,
            "source": "manual", "reviewed_by": None}


def test_reconhece_o_bbox_do_classificador():
    assert _e_rotulo_de_frame(_caixa("f1", 1.0, 1.0)) is True
    # caixa grande mas ainda desenhada — não é rótulo de frame
    assert _e_rotulo_de_frame(_caixa("f1", 0.9, 0.9)) is False
    assert _e_rotulo_de_frame(_caixa("f1", 0.2, 0.1)) is False


def test_caixa_de_frame_inteiro_nao_vai_para_o_treino():
    anns = [_caixa("f1", 1.0, 1.0), _caixa("f2", 0.2, 0.1)]
    frames = [{"id": "f1"}, {"id": "f2"}]

    restantes, sobraram = _sem_rotulos_de_frame(anns, frames)

    assert [a["frame_id"] for a in restantes] == ["f2"]
    # f1 ficou sem caixa nenhuma: sair é melhor que ensinar que ali não há nada
    assert [f["id"] for f in sobraram] == ["f2"]


def test_frame_com_caixa_real_sobrevive_ao_rotulo():
    """Rótulo de frame e caixa desenhada no MESMO frame: só o rótulo sai."""
    anns = [_caixa("f1", 1.0, 1.0), _caixa("f1", 0.3, 0.2)]
    frames = [{"id": "f1"}]

    restantes, sobraram = _sem_rotulos_de_frame(anns, frames)

    assert len(restantes) == 1 and restantes[0]["width"] == 0.3
    assert [f["id"] for f in sobraram] == ["f1"]


def test_negativo_de_verdade_nao_e_tocado():
    """Frame que nunca teve caixa (negativo deliberado) continua no dataset."""
    anns = [_caixa("f1", 0.3, 0.2)]
    frames = [{"id": "f1"}, {"id": "f_vazio"}]

    restantes, sobraram = _sem_rotulos_de_frame(anns, frames)

    assert len(restantes) == 1
    assert [f["id"] for f in sobraram] == ["f1", "f_vazio"]


def test_sem_rotulo_nada_muda():
    anns = [_caixa("f1", 0.3, 0.2)]
    frames = [{"id": "f1"}]
    assert _sem_rotulos_de_frame(anns, frames) == (anns, frames)
