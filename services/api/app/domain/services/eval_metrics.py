"""
Recognition — Métricas de avaliação campeão×desafiante (WS-C1, ADR-0037).

Puro Python, sem dependência nova (não reusa o NMS de
app/domain/detectors/onnx_yolox.py — aquele resolve supressão de
duplicatas da própria inferência; aqui o problema é casar detecções
contra ground-truth, um job diferente).

Duas passadas de casamento guloso (greedy — maior confiança primeiro),
por razões distintas:
  - greedy_match: casamento POR CLASSE (só compara pred×GT da mesma
    classe) — é a definição padrão usada para calcular AP/mAP.
  - confusion_matrix: casamento CRUZANDO classes (compara contra
    qualquer GT, independente da classe) — é o que permite detectar
    confusão real entre classes (ex.: prever "vest" onde o GT é
    "no_vest"), que o casamento por classe não enxerga.
"""
from __future__ import annotations


def iou_xywh(a: list[float], b: list[float]) -> float:
    """IoU entre duas bboxes [x, y, w, h] em pixels absolutos."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def greedy_match(
    preds: list[dict], gts: list[dict], iou_threshold: float = 0.5
) -> dict[str, dict]:
    """Casamento guloso POR CLASSE — base para AP/mAP.

    preds: [{"class": str, "confidence": float, "bbox": [x,y,w,h]}]
    gts:   [{"class": str, "bbox": [x,y,w,h]}]

    Retorna, por classe: {"matches": [(confidence, is_tp), ...] em ordem
    de confiança desc, "n_gt": int, "tp": int, "fp": int, "fn": int}.
    """
    classes = {p["class"] for p in preds} | {g["class"] for g in gts}
    result: dict[str, dict] = {}

    for cls in classes:
        cls_preds = sorted(
            (p for p in preds if p["class"] == cls),
            key=lambda p: p["confidence"],
            reverse=True,
        )
        cls_gts = [g for g in gts if g["class"] == cls]
        matched = [False] * len(cls_gts)
        matches: list[tuple[float, bool]] = []

        for pred in cls_preds:
            best_iou, best_idx = 0.0, -1
            for idx, gt in enumerate(cls_gts):
                if matched[idx]:
                    continue
                iou = iou_xywh(pred["bbox"], gt["bbox"])
                if iou > best_iou:
                    best_iou, best_idx = iou, idx
            is_tp = best_idx >= 0 and best_iou >= iou_threshold
            if is_tp:
                matched[best_idx] = True
            matches.append((pred["confidence"], is_tp))

        tp_count = sum(1 for _, is_tp in matches if is_tp)
        result[cls] = {
            "matches": matches,
            "n_gt": len(cls_gts),
            "tp": tp_count,
            "fp": len(matches) - tp_count,
            "fn": matched.count(False),
        }

    return result


def average_precision(matches: list[tuple[float, bool]], n_gt: int) -> float:
    """AP por integração contínua da curva precisão×recall (VOC2012).

    `matches` deve estar em ordem de confiança decrescente (garantido por
    greedy_match). Envelope de precisão monotonicamente decrescente da
    direita pra esquerda, depois integração trapezoidal sobre recall.
    """
    if n_gt == 0 or not matches:
        return 0.0

    tp_cum = 0
    fp_cum = 0
    precisions: list[float] = []
    recalls: list[float] = []
    for _, is_tp in matches:
        if is_tp:
            tp_cum += 1
        else:
            fp_cum += 1
        precisions.append(tp_cum / (tp_cum + fp_cum))
        recalls.append(tp_cum / n_gt)

    for i in range(len(precisions) - 2, -1, -1):
        precisions[i] = max(precisions[i], precisions[i + 1])

    ap = 0.0
    prev_recall = 0.0
    for precision, recall in zip(precisions, recalls):
        ap += precision * (recall - prev_recall)
        prev_recall = recall
    return ap


def merge_match_results(per_image_results: list[dict[str, dict]]) -> dict[str, dict]:
    """Agrega resultados de greedy_match rodado POR IMAGEM (bboxes são
    absolutas por imagem — casar entre imagens diferentes seria incorreto).

    Concatena as listas "matches" de cada classe através das imagens e
    reordena por confiança desc no final — AP exige a curva
    precisão×recall ordenada globalmente, não só dentro de cada imagem.
    """
    merged: dict[str, dict] = {}
    for image_result in per_image_results:
        for cls, data in image_result.items():
            acc = merged.setdefault(
                cls, {"matches": [], "n_gt": 0, "tp": 0, "fp": 0, "fn": 0}
            )
            acc["matches"].extend(data["matches"])
            acc["n_gt"] += data["n_gt"]
            acc["tp"] += data["tp"]
            acc["fp"] += data["fp"]
            acc["fn"] += data["fn"]
    for data in merged.values():
        data["matches"].sort(key=lambda m: m[0], reverse=True)
    return merged


def merge_confusion_matrices(
    matrices: list[dict[str, dict[str, int]]],
) -> dict[str, dict[str, int]]:
    """Soma matrizes de confusão de várias imagens em uma só."""
    merged: dict[str, dict[str, int]] = {}
    for matrix in matrices:
        for row, cols in matrix.items():
            for col, count in cols.items():
                merged.setdefault(row, {}).setdefault(col, 0)
                merged[row][col] += count
    return merged


# Grade de limiares da curva P/R/F1. 19 pontos (0,05..0,95) em vez de um ponto
# por predição: cabe no JSONB, dá pra plotar, e o pico serve de limiar de
# produção sem fingir precisão de 4 casas num número que veio de contagem.
_THRESHOLD_GRID = tuple(round(0.05 * i, 2) for i in range(1, 20))


def f1_curve(
    matches: list[tuple[float, bool]],
    n_gt: int,
    confidence_floor: float = 0.0,
) -> list[dict]:
    """Curva P/R/F1 por limiar de confiança, para UMA classe.

    `matches` vem de greedy_match/merge_match_results — pares (confiança,
    é_tp) já ordenados por confiança desc. Subir o limiar só REMOVE as
    predições de menor confiança, que são as últimas da ordem gulosa: o
    casamento das que sobram não muda, então recontar tp/fp por corte é
    exato, não aproximação.

    `confidence_floor` = limiar com que o detector rodou. Ponto de grade
    abaixo dele é fantasia (o detector nunca emitiu aquelas caixas) e é
    descartado — um limiar "ótimo" de 0,05 medido num detector que só
    emite acima de 0,25 seria número sem origem, exatamente o que este
    módulo existe para acabar.

    n_gt == 0 → curva vazia: sem ground-truth não há recall nem F1.
    """
    if n_gt <= 0:
        return []
    pontos: list[dict] = []
    for limiar in _THRESHOLD_GRID:
        if limiar < confidence_floor:
            continue
        tp = sum(1 for conf, is_tp in matches if conf >= limiar and is_tp)
        fp = sum(1 for conf, is_tp in matches if conf >= limiar and not is_tp)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / n_gt
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        pontos.append({
            "threshold": limiar,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": n_gt - tp,
        })
    return pontos


def best_f1_threshold(curve: list[dict]) -> float | None:
    """Limiar do PICO de F1 — a origem do limiar de produção da classe.

    None quando não há pico: curva vazia (classe sem GT) ou F1 zero em
    toda a grade (classe que o modelo não acerta nunca). Devolver um
    número nesses casos seria inventar limiar — é a ausência de medida
    virando medida, o mesmo erro do issue #417.

    Empate → o MENOR limiar (mais recall). Em EPI, deixar de ver é pior
    que ver demais: o falso positivo vira fila de verificação humana, o
    falso negativo vira ninguém sabendo.
    """
    melhor = max(curve, key=lambda p: (p["f1"], -p["threshold"]), default=None)
    if melhor is None or melhor["f1"] <= 0.0:
        return None
    return melhor["threshold"]


def precision_recall_map(
    matches_by_class: dict[str, dict], confidence_floor: float = 0.0
) -> dict:
    """AP por classe + mAP50 (média só das classes com n_gt > 0).

    Classes sem nenhum GT no split não entram na média (não há o que
    avaliar) mas aparecem no resultado com ap=None para transparência.

    Por classe, além do AP: `curve` (P/R/F1 por limiar), `best_threshold`
    (pico de F1 — o limiar de produção daquela classe) e `n_pred` (quantas
    predições entraram na conta). Todo número sai com o n ao lado.
    """
    per_class: dict[str, dict] = {}
    aps: list[float] = []
    for cls, data in matches_by_class.items():
        n_gt = data["n_gt"]
        if n_gt == 0:
            per_class[cls] = {
                "ap": None, "n_gt": 0, "n_pred": len(data["matches"]),
                "tp": data["tp"], "fp": data["fp"], "fn": data["fn"],
                "curve": [], "best_threshold": None, "best_f1": None,
            }
            continue
        ap = average_precision(data["matches"], n_gt)
        aps.append(ap)
        precision = data["tp"] / (data["tp"] + data["fp"]) if (data["tp"] + data["fp"]) else 0.0
        recall = data["tp"] / n_gt if n_gt else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        curve = f1_curve(data["matches"], n_gt, confidence_floor)
        limiar = best_f1_threshold(curve)
        per_class[cls] = {
            "ap": round(ap, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "n_gt": n_gt,
            "n_pred": len(data["matches"]),
            "tp": data["tp"],
            "fp": data["fp"],
            "fn": data["fn"],
            "curve": curve,
            "best_threshold": limiar,
            "best_f1": next(
                (p["f1"] for p in curve if p["threshold"] == limiar), None
            ),
        }
    map50 = round(sum(aps) / len(aps), 4) if aps else 0.0
    return {"map50": map50, "per_class": per_class}


# --------------------------------------------------------- mAP50-95 e tamanho

# COCO: mAP50-95 = média do mAP em IoU 0,50:0,05:0,95 (10 pontos).
COCO_IOU_SWEEP = tuple(round(0.5 + 0.05 * i, 2) for i in range(10))

# COCO: small < 32², medium < 96², large o resto — em pixels de ÁREA da caixa.
_COCO_SMALL_MAX = 32 * 32
_COCO_MEDIUM_MAX = 96 * 96
SIZE_BUCKETS = ("small", "medium", "large")


def size_bucket(bbox: list[float]) -> str:
    """Faixa de tamanho COCO de uma bbox [x, y, w, h] — por área w*h."""
    area = float(bbox[2]) * float(bbox[3])
    if area < _COCO_SMALL_MAX:
        return "small"
    if area < _COCO_MEDIUM_MAX:
        return "medium"
    return "large"


def map_over_iou_sweep(
    per_image: list[tuple[list[dict], list[dict]]],
) -> dict:
    """mAP50-95 COCO + o mAP de cada IoU da varredura.

    `per_image`: [(preds, gts), ...] — uma entrada por imagem, bboxes
    absolutas (casar entre imagens diferentes seria incorreto, por isso o
    casamento é por imagem e só o resultado é agregado).

    Recasar em 10 limiares custa 10 passadas de greedy_match sobre
    detecções que JÁ estão em memória — barato perto da inferência que as
    produziu, e é a única forma de ter o número que o dono pediu.
    """
    por_iou: dict[str, float] = {}
    for limiar in COCO_IOU_SWEEP:
        merged = merge_match_results(
            [greedy_match(preds, gts, iou_threshold=limiar) for preds, gts in per_image]
        )
        por_iou[f"{limiar:.2f}"] = precision_recall_map(merged)["map50"]
    valores = list(por_iou.values())
    return {
        "map50_95": round(sum(valores) / len(valores), 4) if valores else 0.0,
        "map_por_iou": por_iou,
    }


def map_by_size(
    per_image: list[tuple[list[dict], list[dict]]], iou_threshold: float = 0.5
) -> dict[str, dict]:
    """mAP50 e n por faixa de tamanho COCO (small/medium/large).

    APROXIMAÇÃO DOCUMENTADA — não é o pycocotools. O COCO filtra o
    ground-truth pela faixa e IGNORA (não penaliza) predição que casou com
    GT de fora dela; aqui as predições também são filtradas, pela ÁREA DA
    PRÓPRIA CAIXA. Efeito: uma predição cuja GT verdadeira caiu na faixa
    vizinha conta como falso positivo em vez de ser ignorada — o número
    sai igual ou mais SEVERO que o do COCO, nunca mais generoso. Como
    IoU >= 0,5 exige áreas dentro de 2× uma da outra, só caixa em cima da
    fronteira da faixa diverge.

    Cada faixa vem com `n_gt` e `n_pred`: faixa com n_gt=0 tem map50=0,0
    porque não há o que medir, não porque o modelo falhou — ler o mAP sem
    o n ao lado é como o gate aprovava modelo cego.
    """
    saida: dict[str, dict] = {}
    for faixa in SIZE_BUCKETS:
        pares = [
            (
                [p for p in preds if size_bucket(p["bbox"]) == faixa],
                [g for g in gts if size_bucket(g["bbox"]) == faixa],
            )
            for preds, gts in per_image
        ]
        merged = merge_match_results(
            [greedy_match(p, g, iou_threshold=iou_threshold) for p, g in pares]
        )
        resultado = precision_recall_map(merged)
        saida[faixa] = {
            "map50": resultado["map50"],
            "n_gt": sum(len(g) for _, g in pares),
            "n_pred": sum(len(p) for p, _ in pares),
            "per_class": {
                cls: {"ap": d["ap"], "n_gt": d["n_gt"], "n_pred": d["n_pred"]}
                for cls, d in resultado["per_class"].items()
            },
        }
    return saida


_BACKGROUND = "background"


def confusion_matrix(
    preds: list[dict], gts: list[dict], iou_threshold: float = 0.5
) -> dict[str, dict[str, int]]:
    """Matriz de confusão CRUZANDO classes — diagnóstico independente do AP.

    Casa cada predição (maior confiança primeiro) contra o GT não-usado de
    QUALQUER classe com maior IoU >= threshold. Retorna
    matrix[gt_class_or_background][pred_class_or_background] = contagem:
      - matrix[gt][pred] com gt==pred → acerto
      - matrix[gt][pred] com gt!=pred → confusão real entre classes
      - matrix[background][pred] → falso positivo (sem GT correspondente)
      - matrix[gt][background] → falso negativo (GT não detectado)
    """
    cls_preds = sorted(preds, key=lambda p: p["confidence"], reverse=True)
    matched = [False] * len(gts)
    matrix: dict[str, dict[str, int]] = {}

    def _bump(row: str, col: str) -> None:
        matrix.setdefault(row, {}).setdefault(col, 0)
        matrix[row][col] += 1

    for pred in cls_preds:
        best_iou, best_idx = 0.0, -1
        for idx, gt in enumerate(gts):
            if matched[idx]:
                continue
            iou = iou_xywh(pred["bbox"], gt["bbox"])
            if iou > best_iou:
                best_iou, best_idx = iou, idx
        if best_idx >= 0 and best_iou >= iou_threshold:
            matched[best_idx] = True
            _bump(gts[best_idx]["class"], pred["class"])
        else:
            _bump(_BACKGROUND, pred["class"])

    for idx, gt in enumerate(gts):
        if not matched[idx]:
            _bump(gt["class"], _BACKGROUND)

    return matrix
