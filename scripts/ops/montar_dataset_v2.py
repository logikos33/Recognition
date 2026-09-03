#!/usr/bin/env python3
"""montar_dataset_v2.py — o dataset-base das TRÊS variantes, do MESMO pool.

    A  presença (5 classes); ausência é derivada em inferência, não é classe.
    B  presença + ausência como classe do detector ("Sem X").
    C  parte do corpo + EPI; ausência sai por sobreposição (ADR-0065/0067).

O QUE ESTE SCRIPT EXISTE PARA IMPEDIR
────────────────────────────────────────────────────────────────────────────────
1. **Três provas diferentes.** O ranking histórico mediu cada modelo no test set
   do PRÓPRIO dataset — comparação sem valor (é o que a migration 131 e
   `DatasetRepository.get_holdout` documentam). Aqui o split é calculado UMA VEZ,
   sobre o pool bruto do RVB, e as três variantes HERDAM a mesma partição de
   `frame_id`. Não há caminho no código que produza um split por variante: a
   função que divide (`dividir`) é chamada uma vez em `montar`, antes do laço das
   variantes, e devolve `frame_id`s — não anotações. O teste
   `test_montar_dataset_v2.py::test_holdout_identico_nas_tres` compara as listas.

2. **Reimplementar o pool e o split.** Nada aqui reinventa o export: o pool sai
   de `_snapshot_labeled_frames`/`_fetch_annotations` e o split de
   `_split_by_group` — as MESMAS funções que `build_dataset_version_v2` roda em
   produção. Se o produto mudar de critério, este script muda junto. A taxonomia
   das variantes vem de `converter_datasets_publicos`/`converter_variante_c`,
   importadas, nunca recopiadas.

3. **Público entrando na prova.** O Open Images tem mão/rosto/orelha e ZERO EPI.
   Uma imagem dele no holdout faria a derivação da C acusar "Sem Luvas" em toda
   mão, sem gabarito com que comparar. Dado público entra SÓ no train
   (`--publico`), e a procedência (licença + fonte) anda junto do derivado.

O ACHADO QUE GOVERNA O RESULTADO (medido, não estimado)
────────────────────────────────────────────────────────────────────────────────
O modelo é SERVIDO em frame cheio (inference_engine.py chama predict(frame) com o
quadro inteiro; não há recorte de pessoa no caminho servido) e o dono decidiu que
o A/B se decide por ACUSAR CERTO nos frames CHEIOS do holdout. Medido no DEV em
2026-09-02, no pool de export do RVB (4.980 frames / 6.339 caixas):

    frames cheios anotados ......... 204   (4,1% do pool)
    caixas neles ................... 340

    caixas de ACUSAÇÃO em frame cheio:
        Sem protetor de ouvido ...... 30
        Uso incorreto de mascara .... 14
        Sem Luvas ....................  0
        Sem mascara ..................  0
        Sem Óculos ...................  0

`_N_MINIMO` do avaliador (ab_ausencia.py) é 30. Ou seja: mesmo pondo TODOS os 204
frames cheios no holdout (`--holdout-cheios todos`), três das cinco classes de
acusação têm n=0 e as outras duas ficam em 30 e 14. **Nenhuma partição conserta
isso — o material não existe.** O relatório marca as classes NÃO CONCLUSIVAS em
vez de deixar um empate parecer resultado.

Discriminador de frame cheio: repetição de dimensão (>= `_FULL_FRAME_MIN_REPEATS`
frames com a mesma resolução), a mesma heurística de
`FrameRepository.list_images_filtered(only_crops)` — `crop_origin` (migration 132)
é NULL em 100% do acervo (medido), então ele ainda não serve para nada aqui.

USO
────────────────────────────────────────────────────────────────────────────────
    DATABASE_URL=... python3 scripts/ops/montar_dataset_v2.py tabela
    DATABASE_URL=... python3 scripts/ops/montar_dataset_v2.py montar \\
        --saida /dados/v2 --publico /dados/publicos --gravar
    python3 scripts/ops/montar_dataset_v2.py autoteste     # sem banco
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "services" / "api"))


def _carrega(nome: str):
    caminho = Path(__file__).resolve().parent / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(nome, caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_vd = _carrega("converter_datasets_publicos")
_vc = _vd._vc  # converter_variante_c, já carregado por ele — uma cópia só

VARIANTES = _vd.VARIANTES
SPLIT_PADRAO = {"train": 0.7, "val": 0.2, "test": 0.1}
SEED_PADRAO = "rvb-epi-v2-tres-variantes"
TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"
MODULO = "epi"

#: Corte de área da variante C, em fração do frame. Recomendação MEDIDA na
#: amostra visual (converter_variante_c.py modo amostra): abaixo de 0,1% a caixa
#: é clique perdido, acima de 5% ela engole o tronco em vez de marcar a parte do
#: corpo. Parametrizável (`--corte-area-min/max`) porque o aceite da C ainda é
#: HUMANO e o dono pode pedir outro corte — o número não é lei, é proposta.
CORTE_AREA_MIN = 0.001
CORTE_AREA_MAX = 0.05

#: A quais caixas o corte se aplica. A amostra visual que produziu os números
#: acima olhou SÓ as classes de ausência — aplicar o mesmo corte às de presença
#: é uma extrapolação razoável (o problema geométrico é o mesmo: a caixa vira
#: parte do corpo nos dois casos) mas NÃO MEDIDA. `ausencia` é o escopo
#: literalmente evidenciado; `tudo` é o coerente. O dono escolhe — e o relatório
#: imprime quanto cada escopo remove.
CORTE_ESCOPO = ("tudo", "ausencia")
CLASSES_AUSENCIA_RVB = frozenset(
    n for n in _vc.MAPA if n.startswith("Sem ") or n.startswith("Uso ")
)

#: Classes RVB que a variante A aceita. As de ausência não são classe do
#: detector nela (ADR-0067) — a acusação sai por derivação em inferência.
CLASSES_A = set(_vd.PRESENCA)


def classes_da_variante(variante: str) -> list[str]:
    """Delega para o conversor do público — uma tabela de classes só."""
    return _vd.classes_da_variante(variante)


# ── Pool: as MESMAS funções do export de produção ────────────────────────────
def abrir_repos(dsn: str):
    """Repos do produto sobre a DSN dada. Não duplica SQL nenhum."""
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.annotation_repository import (
        AnnotationRepository,
    )
    from app.infrastructure.database.repositories.dataset_repository import (
        DatasetRepository,
    )

    DatabasePool.initialize(dsn, 1, 2)
    pool = DatabasePool.get_instance()
    return AnnotationRepository(pool), DatasetRepository(pool)


def carregar_pool(anotacao_repo, tenant: str, modulo: str) -> dict[str, Any]:
    """Pool de export do tenant, idêntico por construção ao do produto.

    Chama `_snapshot_labeled_frames`, `_fetch_annotations` e
    `_sem_rotulos_de_frame` de versioning_v2 — as três funções que
    `build_dataset_version_v2` usa. Um pool "parecido" montado à mão aqui já
    seria uma segunda verdade divergindo em silêncio.
    """
    from app.infrastructure.queue.tasks.versioning_v2 import (
        _fetch_annotations,
        _sem_rotulos_de_frame,
        _snapshot_labeled_frames,
    )

    frames = _snapshot_labeled_frames(anotacao_repo, tenant, modulo)
    anns, tinham_caixa = _fetch_annotations(anotacao_repo, tenant, modulo)
    anns, frames = _sem_rotulos_de_frame(anns, frames, tinham_caixa)
    frames = [f for f in frames if f.get("width") and f.get("height")]
    validos = {str(f["id"]) for f in frames}
    anns = [a for a in anns if str(a["frame_id"]) in validos]
    return {
        "frames": frames,
        "anns": anns,
        "cheios": frames_cheios(anotacao_repo, tenant, validos),
    }


def frames_cheios(anotacao_repo, tenant: str, ids: set[str]) -> set[str]:
    """Ids dos frames que são QUADRO INTEIRO, não recorte de pessoa.

    Heurística de repetição de dimensão, a mesma de
    `FrameRepository.list_images_filtered(only_crops)` e com a MESMA constante —
    importada de lá, não recopiada. `crop_origin` (migration 132) seria a prova
    por construção, mas é NULL em todo o acervo: ela grava a PRÓXIMA safra.

    ponytail: se o coletor passar a emitir recorte de tamanho fixo (letterbox),
    a heurística o chamaria de frame cheio; aí o discriminador vira
    `crop_origin IS NULL` puro, quando houver safra suficiente com ele gravado.
    """
    from app.infrastructure.database.repositories.frame_repository import (
        FrameRepository,
    )

    rows = anotacao_repo._execute(
        """
        SELECT tf.id
          FROM training_frames tf
         WHERE tf.tenant_id = %s
           AND (tf.width, tf.height) IN (
                 SELECT width, height FROM training_frames
                  WHERE tenant_id = %s AND width IS NOT NULL
                  GROUP BY width, height HAVING COUNT(*) >= %s)
        """,
        (tenant, tenant, FrameRepository._FULL_FRAME_MIN_REPEATS),
    )
    return {str(r["id"]) for r in rows} & ids


# ── O split: UMA vez, herdado pelas três ─────────────────────────────────────
def dividir(
    frames: list[dict[str, Any]],
    anns: list[dict[str, Any]],
    split: dict[str, float],
    seed: str,
    holdout_cheios: str = "estratificado",
) -> dict[str, list[str]]:
    """Divide o pool UMA vez e devolve frame_ids por split.

    Estratifica pelos nomes CRUS do RVB — a partição mais fina que existe. Toda
    classe de toda variante é união de classes cruas (`mao` = `Luvas` +
    `Sem Luvas`), então equilibrar as cruas equilibra as derivadas; estratificar
    por variante daria três splits diferentes, que é exatamente o defeito que
    este script existe para matar.

    `holdout_cheios`:
      * `estratificado` — frame cheio entra como uma classe a mais na
        estratificação (`__frame_cheio__`), então ele se distribui como qualquer
        outra em vez de cair onde calhar.
      * `todos` — todo GRUPO que contém frame cheio vai inteiro para o holdout.
        O grupo continua indivisível (é ele que impede leakage): um recorte da
        mesma câmera no mesmo dia pode ser vizinho do quadro cheio, e separá-los
        vazaria. Medido no RVB: 261 dos 5.405 frames (4,8%) vivem nos 35 grupos
        que têm frame cheio — o preço em treino é pequeno e é a ÚNICA
        configuração em que a prova de frame cheio tem algum n.
    """
    from app.infrastructure.queue.tasks.versioning_v2 import (
        _group_key,
        _split_by_group,
    )

    anns_por_frame: dict[str, list[dict[str, Any]]] = {}
    for a in anns:
        anns_por_frame.setdefault(str(a["frame_id"]), []).append(a)

    if holdout_cheios == "todos":
        return _dividir_cheios_no_holdout(
            frames, anns_por_frame, split, seed, _group_key, _split_by_group
        )

    return {
        nome: sorted(str(f["id"]) for f in lista)
        for nome, lista in _split_by_group(
            frames, split, seed, estavel=False, anns_by_frame=anns_por_frame
        ).items()
    }


def _dividir_cheios_no_holdout(
    frames, anns_por_frame, split, seed, group_key, split_by_group
) -> dict[str, list[str]]:
    """Grupos com frame cheio → test inteiro; o resto reparte train/val."""
    cheios = {f["id"] for f in frames if f.get("__cheio__")}
    grupos_cheios = {group_key(f) for f in frames if f["id"] in cheios}
    holdout = [f for f in frames if group_key(f) in grupos_cheios]
    resto = [f for f in frames if group_key(f) not in grupos_cheios]

    t, v = split.get("train", 0.7), split.get("val", 0.2)
    escala = t + v or 1.0
    parcial = split_by_group(
        resto,
        {"train": t / escala, "val": v / escala, "test": 0.0},
        seed,
        estavel=False,
        anns_by_frame=anns_por_frame,
    )
    # `_garante_val_e_test` pode ter recortado 1 frame para o test com
    # proporção 0; ele volta para val — o holdout aqui é definido, não sorteado.
    val = parcial["val"] + parcial["test"]
    return {
        "train": sorted(str(f["id"]) for f in parcial["train"]),
        "val": sorted(str(f["id"]) for f in val),
        "test": sorted(str(f["id"]) for f in holdout),
    }


# ── Anotações por variante: a MESMA caixa, três taxonomias ───────────────────
def anotacoes_da_variante(
    anns: list[dict[str, Any]],
    variante: str,
    corte_min: float = CORTE_AREA_MIN,
    corte_max: float = CORTE_AREA_MAX,
    corte_escopo: str = "tudo",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Traduz as anotações CRUAS do RVB para a taxonomia da variante.

    Uma caixa pode virar DUAS na C (`Luvas` → `mao` + `luva`) e ZERO na A
    (ausência não é classe lá). Todo descarte é CONTADO — nunca some sem número.
    """
    if variante not in VARIANTES:
        raise ValueError(f"variante deve ser uma de {VARIANTES}, veio {variante!r}")
    permitidas = set(classes_da_variante(variante))
    saida: list[dict[str, Any]] = []
    contas = {"entrada": len(anns), "emitidas": 0, "fora_da_variante": 0, "fora_do_corte": 0}

    for a in anns:
        nome = a["class_name"]
        if variante == "c":
            sob_corte = corte_escopo == "tudo" or nome in CLASSES_AUSENCIA_RVB
            area = float(a["width"]) * float(a["height"])
            if sob_corte and not (corte_min <= area <= corte_max):
                contas["fora_do_corte"] += 1
                continue
            destinos = _vc.MAPA.get(nome, ())
        elif variante == "a":
            destinos = (nome,) if nome in CLASSES_A else ()
        else:
            destinos = (nome,) if nome in permitidas else ()

        if not destinos:
            contas["fora_da_variante"] += 1
            continue
        for destino in destinos:
            saida.append({**a, "class_name": destino})
            contas["emitidas"] += 1
    return saida, contas


# ── COCO ─────────────────────────────────────────────────────────────────────
def montar_coco(
    frames: list[dict[str, Any]],
    anns: list[dict[str, Any]],
    variante: str,
    origem: str = "rvb",
) -> dict[str, Any]:
    """COCO de UM split, no formato que o produto já exporta (âncora id:0)."""
    from app.infrastructure.queue.tasks.versioning_v2 import _yolo_to_coco_bbox

    classes = classes_da_variante(variante)
    id_por_classe = {c: i + 1 for i, c in enumerate(classes)}
    por_frame: dict[str, list[dict[str, Any]]] = {}
    for a in anns:
        por_frame.setdefault(str(a["frame_id"]), []).append(a)

    imagens, anotacoes, proximo = [], [], 1
    for image_id, frame in enumerate(sorted(frames, key=lambda f: str(f["id"])), start=1):
        imagens.append(
            {
                "id": image_id,
                "file_name": f"{frame['id']}.jpg",
                "width": int(frame["width"]),
                "height": int(frame["height"]),
                "origem": origem,
            }
        )
        for a in por_frame.get(str(frame["id"]), []):
            bbox = _yolo_to_coco_bbox(a, int(frame["width"]), int(frame["height"]))
            anotacoes.append(
                {
                    "id": proximo,
                    "image_id": image_id,
                    "category_id": id_por_classe[a["class_name"]],
                    "category_name": a["class_name"],
                    "bbox": bbox,
                    "area": round(bbox[2] * bbox[3], 2),
                    "iscrowd": 0,
                    "origem": origem,
                }
            )
            proximo += 1
    return {
        "info": {"description": f"Recognition v2 · variante {variante.upper()}"},
        "licenses": [],
        "categories": _vd.categorias(variante),
        "images": imagens,
        "annotations": anotacoes,
    }


def somar_publico(
    coco_train: dict[str, Any], entrada: Path, variante: str
) -> dict[str, Any]:
    """Anexa o dado público ao COCO de TREINO. Nunca a val/test.

    O público não tem gabarito de EPI: uma imagem dele no holdout faria a
    derivação da C acusar toda mão de "Sem Luvas" sem nada com que comparar.
    A procedência (licença + fonte) vai em cada imagem — CC BY exige crédito
    também no derivado.
    """
    classes = classes_da_variante(variante)
    id_por_classe = {c: i + 1 for i, c in enumerate(classes)}
    desloc_img = max((i["id"] for i in coco_train["images"]), default=0)
    proximo = max((a["id"] for a in coco_train["annotations"]), default=0) + 1
    contas: dict[str, dict[str, int]] = {}

    for dataset in _vd.MAPA:
        raiz = entrada / dataset
        if not raiz.is_dir():
            continue
        leitor = _vd.le_oid if dataset == "oid" else _vd.le_coco
        brutas, imagens = leitor(raiz)
        if not brutas:
            continue
        novas, c = _vd.converter(brutas, dataset, variante)
        contas[dataset] = {"entrada": c["entrada"], "emitidas": c["emitidas"]}
        if not novas:
            continue

        licenca = _licenca(raiz)
        remap = {}
        for img in imagens:
            desloc_img += 1
            remap[img["id"]] = desloc_img
            coco_train["images"].append(
                {
                    "id": desloc_img,
                    "file_name": f"{dataset}/{img['file_name']}",
                    "width": img.get("width"),
                    "height": img.get("height"),
                    "origem": dataset,
                    "licenca": licenca,
                    "bbox_normalizada": dataset == "oid",
                }
            )
        for a in novas:
            coco_train["annotations"].append(
                {
                    "id": proximo,
                    "image_id": remap.get(a["image_id"], a["image_id"]),
                    "category_id": id_por_classe[a["category_name"]],
                    "category_name": a["category_name"],
                    "bbox": a["bbox"],
                    "area": a["area"],
                    "iscrowd": 0,
                    "origem": dataset,
                    "licenca": licenca,
                }
            )
            proximo += 1
    coco_train["info"]["publico"] = contas
    return coco_train


def _licenca(raiz: Path) -> str:
    arq = raiz / "PROCEDENCIA.json"
    if arq.is_file():
        doc = json.loads(arq.read_text(encoding="utf-8"))
        for chave in ("licenca", "license", "licence"):
            if doc.get(chave):
                return str(doc[chave])
    return "DESCONHECIDA — derivado sem atribuição, ver PROCEDENCIA.json"


# ── Relatório ────────────────────────────────────────────────────────────────
def contar(coco: dict[str, Any]) -> dict[str, dict[str, int]]:
    """classe → {rvb, publico, total} de CAIXAS."""
    out: dict[str, dict[str, int]] = {}
    for a in coco["annotations"]:
        c = out.setdefault(a["category_name"], {"rvb": 0, "publico": 0, "total": 0})
        c["rvb" if a.get("origem") == "rvb" else "publico"] += 1
        c["total"] += 1
    return out


def _n_minimo() -> int:
    """Régua de n do avaliador — importada, não recopiada (ADR-0067)."""
    return _carrega("ab_ausencia")._N_MINIMO


def render_tabela(
    variante: str,
    contagens: dict[str, dict[str, dict[str, int]]],
    cheios: dict[str, dict[str, int]],
    n_minimo: int,
) -> str:
    classes = classes_da_variante(variante)
    larg = max(len(c) for c in classes)
    linhas = [
        f"╔═ VARIANTE {variante.upper()} · {len(classes)} classes "
        f"{'═' * max(0, 52 - len(str(len(classes))))}",
        f"║ {'classe':<{larg}} │ {'train':>7} │ {'val':>6} │ {'holdout':>7} │ "
        f"{'RVB':>7} │ {'público':>8} │ n cheio",
        f"╟{'─' * (larg + 62)}",
    ]
    for c in classes:
        tr = contagens["train"].get(c, {})
        va = contagens["val"].get(c, {})
        ho = contagens["test"].get(c, {})
        rvb = sum(x.get(c, {}).get("rvb", 0) for x in contagens.values())
        pub = sum(x.get(c, {}).get("publico", 0) for x in contagens.values())
        n_cheio = cheios["test"].get(c, 0)
        marca = "" if n_cheio >= n_minimo else "  ← NÃO CONCLUSIVA"
        linhas.append(
            f"║ {c:<{larg}} │ {tr.get('total', 0):>7} │ {va.get('total', 0):>6} │ "
            f"{ho.get('total', 0):>7} │ {rvb:>7} │ {pub:>8} │ {n_cheio:>4}{marca}"
        )
    return "\n".join(linhas)


def montar_variante(
    *,
    frames: list[dict[str, Any]],
    anns: list[dict[str, Any]],
    membresia: dict[str, list[str]],
    variante: str,
    cheios: set[str],
    publico: Path | None = None,
    corte_min: float = CORTE_AREA_MIN,
    corte_max: float = CORTE_AREA_MAX,
    corte_escopo: str = "tudo",
) -> tuple[dict[str, dict[str, Any]], dict[str, int], dict[str, dict[str, int]]]:
    """UMA variante sobre uma membresia JÁ DECIDIDA — o núcleo testável.

    Recebe `membresia` pronta e nunca a recalcula: é por isso que as três
    variantes não conseguem divergir de holdout nem por engano. O público entra
    só em `train` (ver `somar_publico`).
    """
    por_id = {str(f["id"]): f for f in frames}
    traduzidas, contas = anotacoes_da_variante(
        anns, variante, corte_min, corte_max, corte_escopo
    )
    por_frame: dict[str, list[dict[str, Any]]] = {}
    for a in traduzidas:
        por_frame.setdefault(str(a["frame_id"]), []).append(a)

    cocos: dict[str, dict[str, Any]] = {}
    cheios_por_split: dict[str, dict[str, int]] = {}
    for nome, ids in membresia.items():
        fr = [por_id[i] for i in ids if i in por_id]
        an = [a for i in ids for a in por_frame.get(i, [])]
        coco = montar_coco(fr, an, variante)
        if nome == "train" and publico:
            coco = somar_publico(coco, publico, variante)
        cocos[nome] = coco
        so_cheios = [a for a in an if str(a["frame_id"]) in cheios]
        cheios_por_split[nome] = {
            c: sum(1 for a in so_cheios if a["class_name"] == c)
            for c in classes_da_variante(variante)
        }
    return cocos, contas, cheios_por_split


def congelar_split(
    dataset_repo, version_id: str, tenant: str,
    membresia: dict[str, list[str]], gravar: bool,
) -> bool:
    """Congela a membresia em `dataset_versions.split_membership` (migration 131).

    Confere a COLUNA antes de escrever. Medido no DEV em 2026-09-02: a coluna
    NÃO EXISTE lá — a migration 131 está commitada só na branch `v2/treino` e o
    DEV deploya da `develop`. Sem esta guarda, o congelamento morreria com um
    `UndefinedColumn` cru no fim de uma execução de minutos, e é fácil ler isso
    como "o script quebrou" em vez de "a migration não subiu".
    """
    existe = dataset_repo._execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'dataset_versions' AND column_name = 'split_membership'",
        (),
    )
    if not existe:
        print(
            "⛔ NÃO FOI POSSÍVEL congelar o split: a coluna "
            "`dataset_versions.split_membership` não existe neste banco.\n"
            "   A migration 131 ainda não foi aplicada aqui. Aplique-a e repita:\n"
            "   psql $DATABASE_URL -f infra/migrations/"
            "131_dataset_versions_split_membership.sql\n"
            "   (a membresia está em split_membership.json, no diretório de saída)"
        )
        return False
    if not gravar:
        print(f"(dry-run) split_membership NÃO gravado em {version_id}")
        return False
    dataset_repo.update_split_membership(version_id, tenant, membresia)
    print(f"split_membership congelado em dataset_versions {version_id}")
    return True


# ── Modos ────────────────────────────────────────────────────────────────────
def montar(
    dsn: str,
    saida: Path | None,
    publico: Path | None,
    gravar: bool,
    variantes: tuple[str, ...],
    split: dict[str, float],
    seed: str,
    holdout_cheios: str,
    corte_min: float,
    corte_max: float,
    corte_escopo: str,
    tenant: str,
    version_id: str | None,
) -> int:
    anotacao_repo, dataset_repo = abrir_repos(dsn)
    pool = carregar_pool(anotacao_repo, tenant, MODULO)
    frames, anns, cheios = pool["frames"], pool["anns"], pool["cheios"]
    for f in frames:
        f["__cheio__"] = str(f["id"]) in cheios

    print(
        f"POOL RVB (mesmas funções do export de produção): {len(frames)} frames · "
        f"{len(anns)} caixas · {len(cheios)} frames CHEIOS ({len(cheios) / max(len(frames), 1):.1%})"
    )

    membresia = dividir(frames, anns, split, seed, holdout_cheios)
    n_min = _n_minimo()

    print(
        "SPLIT ÚNICO (herdado pelas três): "
        + " · ".join(f"{k}={len(v)}" for k, v in membresia.items())
        + f" · seed={seed!r} · holdout-cheios={holdout_cheios}"
    )
    for nome, ids in membresia.items():
        n = sum(1 for i in ids if i in cheios)
        print(f"  {nome:5} frames cheios: {n}")

    relatorios = []
    for variante in variantes:
        cocos, contas, cheios_por_split = montar_variante(
            frames=frames, anns=anns, membresia=membresia, variante=variante,
            cheios=cheios, publico=publico, corte_min=corte_min,
            corte_max=corte_max, corte_escopo=corte_escopo,
        )
        contagens = {nome: contar(coco) for nome, coco in cocos.items()}

        relatorios.append(render_tabela(variante, contagens, cheios_por_split, n_min))
        relatorios.append(
            f"║ conversão: entrada {contas['entrada']} · emitidas {contas['emitidas']}"
            f" · fora da variante {contas['fora_da_variante']}"
            f" · fora do corte de área {contas['fora_do_corte']}"
            + (f" (corte {corte_min}–{corte_max}, escopo {corte_escopo})" if variante == "c" else "")
        )
        relatorios.append("║ " + _desbalanceamento(contagens["train"], variante))
        relatorios.append("")

        if gravar and saida:
            gravar_variante(saida / f"variante-{variante}", cocos, publico)

    print("\n" + "\n".join(relatorios))

    if gravar and saida:
        # A membresia como ARTEFATO, não só como consequência dos três COCO.
        # É o mesmo formato da coluna `split_membership` (migration 131), para
        # o dia em que a coluna existir no banco ser um `UPDATE`, não uma
        # reconstrução — e para o holdout já parar de ser promessa hoje.
        saida.mkdir(parents=True, exist_ok=True)
        (saida / "split_membership.json").write_text(
            json.dumps(membresia, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        print(f"membresia do split → {saida / 'split_membership.json'}")

    if version_id:
        congelar_split(dataset_repo, version_id, tenant, membresia, gravar)

    if not gravar:
        print("DRY-RUN — nada foi escrito. Repita com --gravar --saida DIR.")
    return 0


def _desbalanceamento(contagem_train: dict[str, dict[str, int]], variante: str) -> str:
    todas = classes_da_variante(variante)
    vals = {c: contagem_train.get(c, {}).get("total", 0) for c in todas}
    zeradas = sorted(c for c, n in vals.items() if n == 0)
    com_caixa = {c: n for c, n in vals.items() if n > 0}
    if len(com_caixa) < 2:
        return "desbalanceamento: n/a"
    maior = max(com_caixa.items(), key=lambda kv: kv[1])
    menor = min(com_caixa.items(), key=lambda kv: kv[1])
    txt = (
        f"desbalanceamento no treino {maior[1] / menor[1]:.1f}:1 "
        f"({maior[0]} {maior[1]} × {menor[0]} {menor[1]})"
    )
    if zeradas:
        txt += f" · ZERO caixas: {', '.join(zeradas)}"
    return txt


def gravar_variante(destino: Path, cocos: dict[str, Any], publico: Path | None) -> None:
    for nome, coco in cocos.items():
        d = destino / nome
        d.mkdir(parents=True, exist_ok=True)
        (d / "_annotations.coco.json").write_text(
            json.dumps(coco, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
    if publico:
        for dataset in _vd.MAPA:
            raiz = publico / dataset
            for arq in ("PROCEDENCIA.json", "ATRIBUICAO.txt"):
                if (raiz / arq).is_file():
                    alvo = destino / "procedencia" / dataset
                    alvo.mkdir(parents=True, exist_ok=True)
                    (alvo / arq).write_text(
                        (raiz / arq).read_text(encoding="utf-8"), encoding="utf-8"
                    )


def autoteste() -> int:
    """Checagem que não precisa de banco nem de download."""
    anns = [
        {"frame_id": "f1", "class_name": "Luvas", "width": 0.1, "height": 0.1,
         "x_center": 0.5, "y_center": 0.5},
        {"frame_id": "f1", "class_name": "Sem Luvas", "width": 0.1, "height": 0.1,
         "x_center": 0.3, "y_center": 0.3},
        {"frame_id": "f2", "class_name": "Capacete", "width": 0.1, "height": 0.1,
         "x_center": 0.5, "y_center": 0.5},
    ]
    a, _ = anotacoes_da_variante(anns, "a")
    assert [x["class_name"] for x in a] == ["Luvas"], a
    b, _ = anotacoes_da_variante(anns, "b")
    assert sorted(x["class_name"] for x in b) == ["Luvas", "Sem Luvas"], b
    c, cc = anotacoes_da_variante(anns, "c")
    assert sorted(x["class_name"] for x in c) == ["luva", "mao", "mao"], c
    assert cc["fora_da_variante"] == 1, cc  # Capacete
    # corte de área da C: 0,01% e 10% saem, o do meio fica
    fora = [
        {"frame_id": "f", "class_name": "Luvas", "width": 0.01, "height": 0.01,
         "x_center": 0.5, "y_center": 0.5},
        {"frame_id": "f", "class_name": "Luvas", "width": 0.5, "height": 0.5,
         "x_center": 0.5, "y_center": 0.5},
    ]
    _, cf = anotacoes_da_variante(fora, "c")
    assert cf["fora_do_corte"] == 2 and cf["emitidas"] == 0, cf
    # "Uso incorreto de mascara" é classe da B (senão o avaliador a mede e a B
    # nunca poderia acusá-la — ab_ausencia.CLASSES_AUSENCIA a inclui)
    assert "Uso incorreto de mascara" in classes_da_variante("b")
    print("autoteste: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="modo", required=True)
    sub.add_parser("autoteste", help="checagens sem banco")
    for nome, ajuda in (("tabela", "só a tabela (dry-run)"), ("montar", "monta os datasets")):
        m = sub.add_parser(nome, help=ajuda)
        m.add_argument("--saida", type=Path)
        m.add_argument("--publico", type=Path, help="raiz do baixar_datasets_publicos")
        m.add_argument("--sem-publico", action="store_true", help="A/B justo: só RVB")
        m.add_argument("--gravar", action="store_true")
        m.add_argument("--variante", choices=[*VARIANTES, "todas"], default="todas")
        m.add_argument("--seed", default=SEED_PADRAO)
        m.add_argument("--train", type=float, default=SPLIT_PADRAO["train"])
        m.add_argument("--val", type=float, default=SPLIT_PADRAO["val"])
        m.add_argument("--test", type=float, default=SPLIT_PADRAO["test"])
        m.add_argument(
            "--holdout-cheios", choices=("estratificado", "todos"), default="estratificado"
        )
        m.add_argument("--corte-area-min", type=float, default=CORTE_AREA_MIN)
        m.add_argument("--corte-area-max", type=float, default=CORTE_AREA_MAX)
        m.add_argument("--corte-escopo", choices=CORTE_ESCOPO, default="tudo")
        m.add_argument("--tenant", default=TENANT_RVB)
        m.add_argument("--version-id", help="dataset_version onde congelar o split (131)")
    args = p.parse_args(argv)

    if args.modo == "autoteste":
        return autoteste()

    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("ERRO: DATABASE_URL não definida.")
        return 1
    if args.gravar and not args.saida:
        print("ERRO: --gravar exige --saida.")
        return 1

    publico = None if args.sem_publico else args.publico
    if publico and not publico.is_dir():
        print(f"ERRO: --publico {publico} não existe.")
        return 1

    variantes = VARIANTES if args.variante == "todas" else (args.variante,)
    return montar(
        dsn=dsn,
        saida=args.saida,
        publico=publico,
        gravar=args.gravar and args.modo == "montar",
        variantes=variantes,
        split={"train": args.train, "val": args.val, "test": args.test},
        seed=args.seed,
        holdout_cheios=args.holdout_cheios,
        corte_min=args.corte_area_min,
        corte_max=args.corte_area_max,
        corte_escopo=args.corte_escopo,
        tenant=args.tenant,
        version_id=args.version_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
