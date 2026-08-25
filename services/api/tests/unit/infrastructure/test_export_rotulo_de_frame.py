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
    assert _sem_rotulos_de_frame(anns, frames, {"f1"}) == (anns, frames)


def test_frame_esvaziado_por_proveniencia_tambem_sai():
    """Invariante geral: nenhum frame vai ao treino com zero caixas por FILTRO.

    O braço só-humano tira as caixas de proposta aceita. Um frame cujas caixas
    eram TODAS dessa origem chega aqui sem nenhuma anotação — e mantê-lo
    ensinaria o detector a não ver o objeto que está lá. Foi o mesmo dano do
    rótulo de frame, por outra porta.
    """
    anns = [_caixa("f1", 0.3, 0.2)]  # f2 perdeu tudo no filtro de proveniência
    frames = [{"id": "f1"}, {"id": "f2"}]

    restantes, sobraram = _sem_rotulos_de_frame(anns, frames, {"f1", "f2"})

    assert restantes == anns
    assert [f["id"] for f in sobraram] == ["f1"]


def test_negativo_de_verdade_sobrevive_a_invariante():
    """Frame sem nenhuma linha no banco nunca entrou em `tinham_caixa`."""
    anns = [_caixa("f1", 0.3, 0.2)]
    frames = [{"id": "f1"}, {"id": "f_vazio"}]

    _, sobraram = _sem_rotulos_de_frame(anns, frames, {"f1"})

    assert [f["id"] for f in sobraram] == ["f1", "f_vazio"]


def test_split_seed_amarra_dois_exports_na_mesma_particao():
    """A/B justo exige que um SUBCONJUNTO herde a mesma partição.

    Semente compartilhada não bastava: `_split_by_group` decide por posição
    numa lista embaralhada dos grupos PRESENTES, então mudar a população muda
    a atribuição. Medido no v14: dos 2.362 frames presentes nos dois braços do
    A/B do #536, **1.701 caíram em split diferente** — e com isso
    `Sem protetor de ouvido` ficou com MAIS caixas de treino no braço podado
    (337) que no completo (294).
    """
    from app.infrastructure.queue.tasks.versioning_v2 import _split_by_group

    frames = [
        {"id": f"f{i}", "camera_id": f"cam{i % 7}", "captured_at": None,
         "created_at": f"2026-08-{10 + i % 12} 10:00:00", "video_id": None}
        for i in range(120)
    ]
    proporcao = {"train": 0.7, "val": 0.2, "test": 0.1}
    # o braço podado: pouco mais da metade dos frames, como o v14-so-humano
    podado = [f for i, f in enumerate(frames) if i % 5 != 0]

    completo = _split_by_group(frames, proporcao, seed="ab-536", estavel=True)
    subconjunto = _split_by_group(podado, proporcao, seed="ab-536", estavel=True)

    onde_completo = {f["id"]: sp for sp, fs in completo.items() for f in fs}
    onde_sub = {f["id"]: sp for sp, fs in subconjunto.items() for f in fs}

    divergentes = [i for i in onde_sub if onde_completo[i] != onde_sub[i]]
    assert divergentes == [], (
        f"{len(divergentes)} frames mudaram de split ao podar a população — "
        "o A/B mediria o sorteio, não o tratamento"
    )


def test_split_estavel_ainda_respeita_a_semente():
    """Semente diferente continua sorteando diferente — senão não é sorteio."""
    from app.infrastructure.queue.tasks.versioning_v2 import _split_by_group

    frames = [
        {"id": f"f{i}", "camera_id": f"cam{i % 7}", "captured_at": None,
         "created_at": f"2026-08-{10 + i % 12} 10:00:00", "video_id": None}
        for i in range(120)
    ]
    proporcao = {"train": 0.7, "val": 0.2, "test": 0.1}
    a = _split_by_group(frames, proporcao, seed="x", estavel=True)
    b = _split_by_group(frames, proporcao, seed="y", estavel=True)
    assert [f["id"] for f in a["train"]] != [f["id"] for f in b["train"]]


def test_split_estavel_nao_vaza_grupo_entre_splits():
    """A garantia central do split por grupo continua valendo no modo estável."""
    from app.infrastructure.queue.tasks.versioning_v2 import _group_key, _split_by_group

    frames = [
        {"id": f"f{i}", "camera_id": f"cam{i % 7}", "captured_at": None,
         "created_at": f"2026-08-{10 + i % 12} 10:00:00", "video_id": None}
        for i in range(120)
    ]
    splits = _split_by_group(frames, {"train": 0.7, "val": 0.2, "test": 0.1},
                             seed="ab-536", estavel=True)
    grupos = {sp: {_group_key(f) for f in fs} for sp, fs in splits.items()}
    assert not (grupos["train"] & grupos["val"])
    assert not (grupos["train"] & grupos["test"])
    assert not (grupos["val"] & grupos["test"])


def test_split_estavel_exige_semente():
    from app.infrastructure.queue.tasks.versioning_v2 import _split_by_group
    import pytest

    with pytest.raises(ValueError):
        _split_by_group([], {"train": 0.7}, seed=None, estavel=True)
