"""Avaliação por classe de um detector ONNX contra um COCO de teste.

Por que este arquivo existe
---------------------------
A métrica que decide "promover ou não" já existiu uma vez, num scratchpad de
sessão, e evaporou: o baseline `mascara = 0,4375` do TREINO 1 (14/08) saiu de um
harness que nunca foi commitado. Quando foi preciso comparar o TREINO 2 contra
ele, o instrumento não existia mais — e `model_evaluations` (o avaliador do
produto) devolve tp=0 E fp=0 para todo modelo, inclusive o campeão (issue #417).

Calibração conhecida — reproduza antes de confiar numa medida nova
------------------------------------------------------------------
Instrumento novo se calibra contra valor conhecido ANTES da medida que decide.
Este código, apontado para o modelo do TREINO 1 e o gabarito v3, reproduz em
`--thr 0.55` os números do baseline de 14/08:

    mascara: tp=14  fn=92        (exatos)
    mascara: fp=13               (o baseline registrou 18 — divergência conhecida)

`tp` e `fn` exatos em três casas de contagem é o que dá confiança no
pré-processamento, no decode das caixas e no casamento. A divergência de 5 falsos
positivos permanece não explicada e está documentada de propósito: um harness que
esconde o que não fecha não serve como instrumento.

Escolhas que mudam o número — todas explícitas
----------------------------------------------
- Pré-processamento RF-DETR: RGB, 560×560 bilinear, /255, normalização ImageNet.
  (BGR ou 0-255 zera o resultado — é a suspeita principal do issue #417.)
- `sigmoid` sobre os logits, não `softmax`: RF-DETR treina com focal loss.
- `topk` sobre o produto query×classe, como o postprocess do RF-DETR — uma mesma
  query pode emitir mais de uma classe.
- Casamento guloso por score decrescente, IoU ≥ 0,5, **cego à classe**: a caixa
  disputa a GT de maior IoU independente da classe, e só é acerto se a classe
  bater. Se não bater, ela conta como falso positivo E a GT segue não-casada
  (vira fn). É mais severo que casar dentro da classe e é o que o baseline fazia.
"""
from __future__ import annotations

import argparse
import io
import json
import zipfile
from collections import defaultdict
from typing import Any

import numpy as np

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
_LADO = 560


def iou(a: list[float], b: list[float]) -> float:
    """IoU entre duas caixas xyxy."""
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    uniao = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / uniao if uniao > 0 else 0.0


def avalia(
    predicoes: dict[Any, list[tuple[float, str, list[float]]]],
    gabarito: dict[Any, list[tuple[str, list[float]]]],
    limiar_iou: float = 0.5,
) -> dict[str, Any]:
    """Casamento guloso cego à classe. Ver o cabeçalho do módulo.

    predicoes: {image_id: [(score, classe, xyxy), ...]}
    gabarito:  {image_id: [(classe, xyxy), ...]}
    """
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    confusao: dict[tuple[str, str], int] = defaultdict(int)

    for image_id in set(list(predicoes) + list(gabarito)):
        gts = list(gabarito.get(image_id, []))
        casada = [False] * len(gts)

        for _score, classe, caixa in sorted(
            predicoes.get(image_id, []), key=lambda p: -p[0]
        ):
            melhor, indice = limiar_iou, -1
            for j, (_gc, gb) in enumerate(gts):
                if casada[j]:
                    continue
                valor = iou(caixa, gb)
                if valor >= melhor:
                    melhor, indice = valor, j

            if indice >= 0 and gts[indice][0] == classe:
                casada[indice] = True
                tp[classe] += 1
            else:
                fp[classe] += 1
                confusao[(gts[indice][0] if indice >= 0 else "fundo", classe)] += 1

        for j, (gc, _gb) in enumerate(gts):
            if not casada[j]:
                fn[gc] += 1

    classes = sorted(set(tp) | set(fp) | set(fn))
    por_classe = {}
    for c in classes:
        t, f, n = tp[c], fp[c], fn[c]
        precisao = t / (t + f) if t + f else 0.0
        recall = t / (t + n) if t + n else 0.0
        por_classe[c] = {
            "precision": precisao,
            "recall": recall,
            "f1": 2 * precisao * recall / (precisao + recall) if precisao + recall else 0.0,
            "tp": t, "fp": f, "fn": n, "n_gt": t + n,
        }
    return {
        "per_class": por_classe,
        "confusion": {f"{v}->{p}": c for (v, p), c in sorted(confusao.items())},
        "iou_threshold": limiar_iou,
    }


def _carrega_gabarito(zf: zipfile.ZipFile, split: str) -> tuple[dict, dict, dict]:
    coco = json.loads(zf.read(f"{split}/_annotations.coco.json"))
    categorias = {c["id"]: c["name"] for c in coco["categories"]}
    dimensoes = {im["id"]: (im["width"], im["height"]) for im in coco["images"]}
    gabarito: dict[int, list] = defaultdict(list)
    for a in coco["annotations"]:
        x, y, w, h = a["bbox"]
        gabarito[a["image_id"]].append((categorias[a["category_id"]], [x, y, x + w, y + h]))
    return categorias, dimensoes, dict(gabarito), coco["images"]  # type: ignore[return-value]


def infere(
    caminho_onnx: str, zf: zipfile.ZipFile, split: str, imagens: list[dict],
    dimensoes: dict, categorias: dict, limiar: float,
) -> dict[int, list[tuple[float, str, list[float]]]]:
    import onnxruntime as ort  # import tardio: só o CLI precisa
    from PIL import Image

    sessao = ort.InferenceSession(caminho_onnx, providers=["CPUExecutionProvider"])
    entrada = sessao.get_inputs()[0].name
    saida: dict[int, list] = defaultdict(list)

    for im in imagens:
        bruta = Image.open(io.BytesIO(zf.read(f"{split}/{im['file_name']}"))).convert("RGB")
        arr = np.asarray(bruta.resize((_LADO, _LADO), Image.BILINEAR), dtype=np.float32) / 255.0
        x = ((arr.transpose(2, 0, 1) - _MEAN) / _STD)[None]
        caixas, logits = sessao.run(None, {entrada: x})

        prob = 1 / (1 + np.exp(-logits[0]))       # sigmoid: focal, não softmax
        plano = prob.ravel()
        largura, altura = dimensoes[im["id"]]
        for k in np.where(plano >= limiar)[0]:
            query, classe = divmod(int(k), prob.shape[1])
            cx, cy, bw, bh = caixas[0][query]
            saida[im["id"]].append((
                float(plano[k]), categorias.get(classe, f"?{classe}"),
                [(cx - bw / 2) * largura, (cy - bh / 2) * altura,
                 (cx + bw / 2) * largura, (cy + bh / 2) * altura],
            ))
    return dict(saida)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, help="caminho do .onnx")
    p.add_argument("--coco", required=True, help="zip do export COCO")
    p.add_argument("--split", default="test")
    p.add_argument("--thr", type=float, default=0.55,
                   help="limiar de score (0.55 = ponto calibrado contra o baseline)")
    p.add_argument("--cats-de", default=None,
                   help="zip cujas categorias mapeiam os índices do MODELO, se "
                        "diferente do gabarito (comparar modelos treinados em "
                        "exports distintos contra o mesmo gabarito)")
    args = p.parse_args()

    with zipfile.ZipFile(args.coco) as zf:
        cats_gab, dimensoes, gabarito, imagens = _carrega_gabarito(zf, args.split)
        cats_modelo = cats_gab
        if args.cats_de:
            with zipfile.ZipFile(args.cats_de) as outro:
                cats_modelo = _carrega_gabarito(outro, args.split)[0]
        predicoes = infere(args.model, zf, args.split, imagens, dimensoes,
                           cats_modelo, args.thr)

    resultado = avalia(predicoes, gabarito)
    resultado["score_threshold"] = args.thr
    resultado["images_evaluated"] = len(imagens)
    resultado["per_class_eval_split"] = args.split
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
