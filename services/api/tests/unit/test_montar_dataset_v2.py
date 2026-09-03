"""Testes do montador do dataset-base (`scripts/ops/montar_dataset_v2.py`).

O que se prova aqui é a única coisa que faz o A/B valer alguma coisa: **as três
variantes saem do MESMO pool e são medidas na MESMA prova**. Um holdout por
variante foi exatamente o defeito do ranking histórico (cada modelo medido no
test set do próprio dataset — ver migration 131 e `DatasetRepository.get_holdout`),
e ele não volta por descuido: aqui há um teste que REPROVA se voltar.

Pool sintético — sem banco, sem R2, sem download.
"""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "ops" / "montar_dataset_v2.py"


def _carregar():
    spec = importlib.util.spec_from_file_location("montar_dataset_v2", _SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


md = _carregar()

SPLIT = {"train": 0.7, "val": 0.2, "test": 0.1}
SEED = "teste-tres-variantes"

# Uma caixa de cada classe crua do RVB que sobrevive às três taxonomias.
CICLO = [
    "Protetor auditivo", "mascara", "Botas", "Óculos", "Luvas",
    "Sem protetor de ouvido", "Sem Luvas", "Sem mascara", "Sem Óculos",
    "Uso incorreto de mascara",
]


def _pool(n_grupos: int = 20, por_grupo: int = 4):
    """Frames em grupos câmera+dia (é o que `_group_key` usa) + 1 caixa cada.

    `n_grupos=20` não é arbitrário: com 14 grupos o `test` sai vazio do
    estratificado e `_garante_val_e_test` recorta 1 frame solto de `val` — o que
    PARTE um grupo entre val e test. Ver
    `test_garante_val_e_test_parte_grupo_quando_o_test_sai_vazio`, que fixa esse
    defeito conhecido em vez de deixá-lo escondido atrás de um pool conveniente.
    """
    frames, anns = [], []
    for g in range(n_grupos):
        for i in range(por_grupo):
            fid = f"f{g:02d}-{i}"
            frames.append({
                "id": fid,
                "video_id": None,
                "camera_id": f"cam{g % 3}",
                "captured_at": datetime(2026, 1, 1) + timedelta(days=g),
                "created_at": datetime(2026, 1, 1) + timedelta(days=g),
                "width": 1920,
                "height": 1080,
            })
            anns.append({
                "frame_id": fid,
                "class_name": CICLO[(g * por_grupo + i) % len(CICLO)],
                # 1% do frame: dentro do corte de área da variante C
                "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1,
            })
    return frames, anns


def _ids_do_coco(coco):
    """Identidades dos frames a partir do ARTEFATO, não do dicionário em memória.

    O `file_name` é `<frame_id>.jpg` (montar_coco). Ler daqui faz o teste cruzar
    a serialização: um bug que só aparece no JSON escrito não escapa.
    """
    return {img["file_name"].rsplit(".", 1)[0] for img in coco["images"]}


def _tres_variantes(membresia_por_variante=None, **kw):
    frames, anns = _pool()
    membresia = md.dividir(frames, anns, SPLIT, SEED)
    saida = {}
    for v in ("a", "b", "c"):
        m = (membresia_por_variante or {}).get(v, membresia)
        cocos, _, _ = md.montar_variante(
            frames=frames, anns=anns, membresia=m, variante=v, cheios=set(), **kw
        )
        saida[v] = cocos
    return membresia, saida


# ── A invariante: mesmo pool, mesma prova ────────────────────────────────────

def test_as_tres_variantes_saem_do_mesmo_pool():
    _, cocos = _tres_variantes()
    universos = {
        v: set().union(*(_ids_do_coco(c) for c in splits.values()))
        for v, splits in cocos.items()
    }
    assert universos["a"] == universos["b"] == universos["c"]
    assert len(universos["a"]) == 20 * 4


def _exigir_holdout_identico(cocos):
    """A guarda do A/B, numa função só — usada pelo teste E pela mutação.

    Se o teste e a mutação usassem cópias diferentes desta checagem, a mutação
    provaria que a CÓPIA reprova, não que o teste reprova.
    """
    holdouts = {v: _ids_do_coco(splits["test"]) for v, splits in cocos.items()}
    assert holdouts["a"], "holdout vazio não prova identidade de coisa nenhuma"
    assert holdouts["a"] == holdouts["b"] == holdouts["c"], holdouts


def test_holdout_identico_nas_tres():
    """Se as variantes forem avaliadas em provas diferentes, o A/B não vale nada."""
    _, cocos = _tres_variantes()
    _exigir_holdout_identico(cocos)


def test_nenhum_frame_do_holdout_aparece_no_treino_de_nenhuma_variante():
    _, cocos = _tres_variantes()
    for v, splits in cocos.items():
        holdout = _ids_do_coco(splits["test"])
        assert not holdout & _ids_do_coco(splits["train"]), v
        assert not holdout & _ids_do_coco(splits["val"]), v


def _grupos_por_split(frames, membresia):
    onde = {i: nome for nome, ids in membresia.items() for i in ids}
    grupos: dict[str, set[str]] = {}
    for f in frames:
        grupos.setdefault(f["id"][:3], set()).add(onde[f["id"]])
    return grupos


def test_split_nao_quebra_grupo_camera_dia():
    """O grupo é o que impede leakage: um grupo inteiro num split só."""
    frames, anns = _pool()
    grupos = _grupos_por_split(frames, md.dividir(frames, anns, SPLIT, SEED))
    assert all(len(s) == 1 for s in grupos.values()), grupos


def test_garante_val_e_test_parte_grupo_quando_o_test_sai_vazio():
    """DEFEITO CONHECIDO de `versioning_v2._garante_val_e_test` — pré-existente.

    Quando o estratificado deixa `test` vazio, o guard recorta `val[-1:]` — um
    FRAME solto, não um grupo. Isso parte o grupo entre val e test (leakage
    val↔test) e torna a partição dependente da ordem da lista, quebrando a
    idempotência que o #515 comprou.

    Não é introduzido por este script e não dispara no pool real do RVB (test=425
    com 87 grupos, medido em 2026-09-02). Fica FIXADO aqui em vez de escondido
    atrás de um pool conveniente: o dia em que alguém consertar
    `_garante_val_e_test`, este teste vira XPASS e cobra a remoção.
    """
    frames, anns = _pool(n_grupos=14)
    membresia = md.dividir(frames, anns, SPLIT, SEED)
    assert len(membresia["test"]) == 1, membresia  # o recorte de 1 frame solto
    grupos = _grupos_por_split(frames, membresia)
    partidos = {g: s for g, s in grupos.items() if len(s) > 1}
    assert partidos == {"f03": {"val", "test"}}, partidos

    # e a consequência: a mesma população em outra ordem dá outro split
    invertido = md.dividir(list(reversed(frames)), anns, SPLIT, SEED)
    assert invertido["test"] != membresia["test"]


# ── A MUTAÇÃO: dar holdout diferente a uma variante tem de REPROVAR ──────────

def test_mutacao_holdout_diferente_reprova():
    """Guarda permanente: uma variante com outro holdout NÃO passa despercebida.

    Sem este teste, `test_holdout_identico_nas_tres` poderia estar comparando
    conjuntos vazios, ou comparando uma coisa que nunca varia — e passaria para
    sempre sem provar nada. Aqui a mutação é feita de propósito e a asserção que
    protege o A/B é exigida a falhar.
    """
    frames, anns = _pool()
    honesta = md.dividir(frames, anns, SPLIT, SEED)
    # mesma população, OUTRA semente → outra partição
    torta = md.dividir(frames, anns, SPLIT, SEED + "-mutante")
    assert set(torta["test"]) != set(honesta["test"]), (
        "a mutação não mudou nada; o resto do teste não provaria coisa alguma"
    )

    # sem mutação, a guarda passa
    _, limpo = _tres_variantes()
    _exigir_holdout_identico(limpo)

    # com a variante B em outro holdout, a MESMA guarda tem de reprovar
    _, mutado = _tres_variantes(membresia_por_variante={"b": torta})
    with pytest.raises(AssertionError):
        _exigir_holdout_identico(mutado)


# ── Taxonomia por variante ───────────────────────────────────────────────────

def test_variante_a_nao_tem_classe_de_ausencia():
    _, cocos = _tres_variantes()
    nomes = {a["category_name"] for a in cocos["a"]["train"]["annotations"]}
    assert not {n for n in nomes if n.startswith("Sem ") or n.startswith("Uso ")}
    assert nomes <= set(md._vd.PRESENCA)


def test_variante_b_tem_uso_incorreto_e_nao_perde_as_219_caixas():
    """`ab_ausencia` MEDE "Uso incorreto de mascara"; a B tem de poder acusá-la."""
    assert "Uso incorreto de mascara" in md.classes_da_variante("b")
    _, cocos = _tres_variantes()
    nomes = {a["category_name"] for a in cocos["b"]["train"]["annotations"]}
    assert "Uso incorreto de mascara" in nomes


def test_variante_c_emite_parte_do_corpo_e_epi_da_mesma_caixa():
    _, cocos = _tres_variantes()
    anns = cocos["c"]["train"]["annotations"]
    por_img = {}
    for a in anns:
        por_img.setdefault(a["image_id"], []).append(a["category_name"])
    # `Luvas` vira `mao` + `luva` na MESMA caixa
    assert any(set(v) == {"mao", "luva"} for v in por_img.values()), por_img


# ── O corte de área da variante C ────────────────────────────────────────────

def _ann(classe, lado):
    return {"frame_id": "f", "class_name": classe, "x_center": 0.5,
            "y_center": 0.5, "width": lado, "height": lado}


def test_corte_de_area_remove_o_que_promete_e_conta_o_que_removeu():
    anns = [
        _ann("Sem Luvas", 0.02),   # 0,04% — clique perdido, sai
        _ann("Sem Luvas", 0.10),   # 1,00% — fica
        _ann("Sem Luvas", 0.30),   # 9,00% — engole o tronco, sai
    ]
    saida, contas = md.anotacoes_da_variante(anns, "c")
    assert contas["fora_do_corte"] == 2
    assert contas["emitidas"] == 1
    assert [a["class_name"] for a in saida] == ["mao"]


def test_corte_de_area_e_parametrizavel():
    """O aceite da C é HUMANO — o dono pode pedir outro corte sem editar código."""
    anns = [_ann("Sem Luvas", 0.02), _ann("Sem Luvas", 0.30)]
    _, largo = md.anotacoes_da_variante(anns, "c", corte_min=0.0, corte_max=1.0)
    assert largo["fora_do_corte"] == 0 and largo["emitidas"] == 2


def test_corte_por_escopo_ausencia_nao_toca_nas_caixas_de_presenca():
    """A amostra visual que justificou o corte olhou SÓ ausência (ver CORTE_ESCOPO)."""
    anns = [_ann("Sem Luvas", 0.30), _ann("Luvas", 0.30)]
    _, tudo = md.anotacoes_da_variante(anns, "c", corte_escopo="tudo")
    _, so_aus = md.anotacoes_da_variante(anns, "c", corte_escopo="ausencia")
    assert tudo["fora_do_corte"] == 2
    assert so_aus["fora_do_corte"] == 1
    assert so_aus["emitidas"] == 2  # `Luvas` → mao + luva, intactas


def test_corte_nao_se_aplica_as_variantes_a_e_b():
    """A e B treinam a caixa como ela foi anotada; o corte é da geometria da C."""
    anns = [_ann("Luvas", 0.30)]
    for v in ("a", "b"):
        _, c = md.anotacoes_da_variante(anns, v)
        assert c["fora_do_corte"] == 0 and c["emitidas"] == 1, v


# ── Público: procedência e train-only ────────────────────────────────────────

def test_publico_entra_so_no_treino_e_com_procedencia(tmp_path):
    raiz = tmp_path / "oid"
    raiz.mkdir()
    (raiz / "PROCEDENCIA.json").write_text(json.dumps({"licenca": "CC BY 4.0"}))
    (raiz / "validation-3classes.csv").write_text(
        "Split,ImageID,ClassName,XMin,XMax,YMin,YMax\n"
        "validation,abc,Human hand,0.1,0.2,0.1,0.2\n"
    )
    _, cocos = _tres_variantes(publico=tmp_path)

    do_publico = [
        a for a in cocos["c"]["train"]["annotations"] if a.get("origem") == "oid"
    ]
    assert do_publico, "o público não entrou no treino"
    assert all(a["licenca"] == "CC BY 4.0" for a in do_publico)
    for split in ("val", "test"):
        assert not [
            a for a in cocos["c"][split]["annotations"] if a.get("origem") != "rvb"
        ], f"dado público vazou para {split} — não há gabarito de EPI nele"


def test_publico_nao_alimenta_a_nem_b(tmp_path):
    """Medido: o Open Images só tem parte do corpo, que não é classe de A nem B.

    Não é opinião — `converter_datasets_publicos.destinos('parte', X, 'a')` é ().
    O teste existe para que a assimetria do A/B (C ganha 47 mil caixas, A e B
    zero) apareça como fato do código e não como surpresa no relatório.
    """
    raiz = tmp_path / "oid"
    raiz.mkdir()
    (raiz / "validation-3classes.csv").write_text(
        "Split,ImageID,ClassName,XMin,XMax,YMin,YMax\n"
        "validation,abc,Human hand,0.1,0.2,0.1,0.2\n"
    )
    _, cocos = _tres_variantes(publico=tmp_path)
    for v in ("a", "b"):
        assert not [
            a for a in cocos[v]["train"]["annotations"] if a.get("origem") != "rvb"
        ], v


# ── Determinismo (o export tem de ser idempotente — #515) ────────────────────

def test_mesma_semente_mesmo_split():
    frames, anns = _pool()
    um = md.dividir(frames, anns, SPLIT, SEED)
    dois = md.dividir(list(reversed(frames)), anns, SPLIT, SEED)
    assert um == dois


def test_variante_desconhecida_falha_alto():
    with pytest.raises(ValueError):
        md.anotacoes_da_variante([], "z")
