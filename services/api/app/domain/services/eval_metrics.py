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


def precision_recall_map(matches_by_class: dict[str, dict]) -> dict:
    """AP por classe + mAP50 (média só das classes com n_gt > 0).

    Classes sem nenhum GT no split não entram na média (não há o que
    avaliar) mas aparecem no resultado com ap=None para transparência.
    """
    per_class: dict[str, dict] = {}
    aps: list[float] = []
    for cls, data in matches_by_class.items():
        n_gt = data["n_gt"]
        if n_gt == 0:
            per_class[cls] = {
                "ap": None, "n_gt": 0, "tp": data["tp"], "fp": data["fp"], "fn": data["fn"],
            }
            continue
        ap = average_precision(data["matches"], n_gt)
        aps.append(ap)
        precision = data["tp"] / (data["tp"] + data["fp"]) if (data["tp"] + data["fp"]) else 0.0
        recall = data["tp"] / n_gt if n_gt else 0.0
        per_class[cls] = {
            "ap": round(ap, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "n_gt": n_gt,
            "tp": data["tp"],
            "fp": data["fp"],
            "fn": data["fn"],
        }
    map50 = round(sum(aps) / len(aps), 4) if aps else 0.0
    return {"map50": map50, "per_class": per_class}


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
