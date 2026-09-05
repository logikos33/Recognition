"""O split não pode sacrificar classe rara — e o grupo continua indivisível.

Medido no RVB (tenant 63c219d8, módulo `epi`, 4.983 frames, semente
`'rvb-epi:v17'`, alvo val+test = 30%) com o sorteio por posição que existia
antes:

    Protetor auditivo   2.829 caixas → 669 em val+test (24%)
    Sem Óculos            114        →  14             (12%)
    Sem mascara           134        →  30             (22%)
    Sem Luvas             178        →  93             (52%)  ← o dobro

`Sem Luvas` chegava ao treino com **85 de 178** caixas. É a única classe de
ausência que sustenta a régua de precisão de campo (69,7%), então esse era o
gargalo do modelo. Depois da estratificação, na mesma semente e no mesmo pool:
50 em val+test (28%) e **128** no treino.

Estes testes rodam o split DE VERDADE (`_split_by_group`) sobre uma
distribuição sintética que reproduz a forma do problema — classe rara
concentrada em poucos grupos grandes. Com o algoritmo antigo eles REPROVAM.
"""
import pytest

from app.infrastructure.queue.tasks.versioning_v2 import (
    _group_key,
    _split_by_group,
)

SPLIT = {"train": 0.7, "val": 0.2, "test": 0.1}
ALVO_FORA = SPLIT["val"] + SPLIT["test"]  # 0,30

# 10 pontos percentuais. Não é gosto: `_DESVIO_PROPORCAO_MAX` já trata 15 pp
# como degenerado para a proporção GLOBAL do split, e uma classe não pode sair
# pior que o split inteiro. O caso real do RVB desviava 22 pp (52% contra 30%);
# o estratificado desvia no máximo 3 pp sobre o mesmo pool em três sementes
# (25%–33%). 10 pp deixa folga para a granularidade dos grupos sem deixar
# passar o sacrifício que este teste existe para pegar.
TOLERANCIA = 0.10

# Várias sementes de propósito: o sorteio antigo às vezes acerta por sorte, e um
# teste de uma semente só mediria a sorte. A estratificação tem de valer para
# TODAS — é essa a diferença entre os dois algoritmos.
SEMENTES = ("rvb-epi:v17", "rvb-epi:v18", "rvb-epi:v19", "ds:v1", "ds:v2")


def _pool():
    """30 grupos (vídeos). A classe rara vive em 4 deles, e concentrada.

    É a forma do RVB: `Sem Luvas` tem 178 caixas em pouquíssimos pares
    câmera+dia, então um grupo grande caindo em val/test leva metade da classe
    junto. `comum` está espalhada nos 30, e é ela que domina a contagem — o
    algoritmo tem de equilibrar a rara SEM desmontar a comum.
    """
    frames, anns_by_frame = [], {}
    rara_por_grupo = {0: 40, 1: 30, 2: 20, 3: 10}  # 100 caixas da classe rara
    for g in range(30):
        for i in range(20):  # 20 frames por grupo, 600 no total
            fid = f"f-{g}-{i}"
            frames.append({"id": fid, "video_id": f"vid-{g}"})
            caixas = [{"class_name": "comum"} for _ in range(3)]
            anns_by_frame[fid] = caixas
        # a rara mora dentro do grupo — grupo inteiro ou nada
        for n in range(rara_por_grupo.get(g, 0)):
            anns_by_frame[f"f-{g}-{n % 20}"].append({"class_name": "rara"})
    return frames, anns_by_frame


def _contagem(split_frames, anns_by_frame, classe):
    return sum(
        1
        for f in split_frames
        for a in anns_by_frame.get(str(f["id"]), [])
        if a["class_name"] == classe
    )


@pytest.mark.parametrize("seed", SEMENTES)
@pytest.mark.parametrize("classe", ("rara", "comum"))
def test_classe_rara_nao_e_sacrificada_no_holdout(seed, classe):
    """A fração da classe em val+test fica perto do alvo — para toda semente.

    REPROVA com o algoritmo antigo (embaralhar as chaves e cortar por posição):
    a classe rara vive em 4 dos 30 grupos e o sorteio trata todos como
    intercambiáveis, então basta um dos 4 cair fora do treino para a classe
    perder 30 ou 40% de uma vez.
    """
    frames, anns_by_frame = _pool()
    splits = _split_by_group(frames, SPLIT, seed=seed, anns_by_frame=anns_by_frame)

    total = sum(_contagem(splits[s], anns_by_frame, classe) for s in splits)
    fora = sum(_contagem(splits[s], anns_by_frame, classe) for s in ("val", "test"))
    fracao = fora / total

    assert abs(fracao - ALVO_FORA) <= TOLERANCIA, (
        f"'{classe}' com {fora}/{total} ({fracao:.0%}) em val+test contra os "
        f"{ALVO_FORA:.0%} pedidos (semente {seed}) — o split sacrificou a classe"
    )


@pytest.mark.parametrize("seed", SEMENTES)
def test_nenhum_grupo_cai_em_dois_splits(seed):
    """⛔ Anti-leakage: o grupo (vídeo, ou câmera+dia) é indivisível.

    É a razão de o agrupamento existir — frames da mesma câmera no mesmo dia
    são quase idênticos, e separá-los entre train e val faz o dataset MENTIR
    sobre a própria avaliação. Nenhum ganho de equilíbrio de classe compra
    isso.
    """
    frames, anns_by_frame = _pool()
    splits = _split_by_group(frames, SPLIT, seed=seed, anns_by_frame=anns_by_frame)

    onde: dict[str, set[str]] = {}
    for nome, split_frames in splits.items():
        for f in split_frames:
            onde.setdefault(_group_key(f), set()).add(nome)

    vazando = {g: s for g, s in onde.items() if len(s) > 1}
    assert not vazando, f"grupo(s) em mais de um split: {vazando}"

    # e nenhum frame se perdeu ou duplicou no caminho
    ids = [str(f["id"]) for s in splits.values() for f in s]
    assert len(ids) == len(set(ids)) == len(frames)


def test_mesma_semente_mesmo_split():
    """Determinismo: o retry da task reescreve o MESMO COCO (#515)."""
    frames, anns_by_frame = _pool()
    a = _split_by_group(frames, SPLIT, seed="ds:v1", anns_by_frame=anns_by_frame)
    b = _split_by_group(
        list(reversed(frames)), SPLIT, seed="ds:v1", anns_by_frame=anns_by_frame
    )
    assert {k: sorted(str(f["id"]) for f in v) for k, v in a.items()} == {
        k: sorted(str(f["id"]) for f in v) for k, v in b.items()
    }


def test_um_grupo_so_nao_explode(caplog):
    """Base minúscula continua exportando — e AVISA ALTO, nunca em silêncio."""
    frames = [{"id": f"f{i}", "video_id": "vid-unico"} for i in range(10)]
    anns_by_frame = {f["id"]: [{"class_name": "rara"}] for f in frames}

    with caplog.at_level("WARNING"):
        splits = _split_by_group(
            frames, SPLIT, seed="ds:v1", anns_by_frame=anns_by_frame
        )

    total = sum(len(v) for v in splits.values())
    assert total == 10, "frames sumiram num pool de 1 grupo"
    assert any(
        "dataset_export_split_poucos_grupos" in r.message for r in caplog.records
    ), "dataset de 1 grupo degradou em SILÊNCIO"


def test_diagnostico_denuncia_classe_sacrificada():
    """O aviso vale para os DOIS caminhos, inclusive `estavel=True`.

    `_split_estavel` (hash por grupo) não estratifica — é o preço da garantia de
    que um subconjunto herda a mesma partição. Quando ele sacrifica uma classe,
    quem exportou tem de ver, no log e no `result` da task.
    """
    from app.infrastructure.queue.tasks.versioning_v2 import _diagnosticar_split

    # o caso RVB medido: 178 caixas de `Sem Luvas`, 93 em val+test (52%)
    splits = {
        "train": [{"id": f"t{i}"} for i in range(85)],
        "val": [{"id": f"v{i}"} for i in range(60)],
        "test": [{"id": f"s{i}"} for i in range(33)],
    }
    anns = {
        str(f["id"]): [{"class_name": "Sem Luvas"}]
        for lista in splits.values()
        for f in lista
    }
    avisos = _diagnosticar_split(splits, SPLIT, anns)
    assert any("Sem Luvas=93/178 (52%)" in a for a in avisos), avisos

    # e não grita quando a classe está no lugar
    ok = {
        "train": [{"id": f"t{i}"} for i in range(70)],
        "val": [{"id": f"v{i}"} for i in range(20)],
        "test": [{"id": f"s{i}"} for i in range(10)],
    }
    anns_ok = {
        str(f["id"]): [{"class_name": "Sem Luvas"}]
        for lista in ok.values()
        for f in lista
    }
    assert not any("perdendo para val+test" in a
                   for a in _diagnosticar_split(ok, SPLIT, anns_ok))


def test_sem_anotacoes_ainda_reparte_por_frames():
    """Chamador antigo (sem `anns_by_frame`) não quebra e não perde frame."""
    frames = [{"id": f"f-{g}-{i}", "video_id": f"vid-{g}"}
              for g in range(10) for i in range(5)]
    splits = _split_by_group(frames, SPLIT, seed="ds:v1")
    assert sum(len(v) for v in splits.values()) == 50
    assert all(splits[s] for s in ("train", "val", "test"))
