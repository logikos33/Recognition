"""Tests: eval_metrics.py — IoU/greedy matching/AP/confusion matrix (WS-C1)."""
from __future__ import annotations

from app.domain.services.eval_metrics import (
    COCO_IOU_SWEEP,
    average_precision,
    best_f1_threshold,
    confusion_matrix,
    f1_curve,
    greedy_match,
    iou_xywh,
    map_by_size,
    map_over_iou_sweep,
    merge_confusion_matrices,
    merge_match_results,
    precision_recall_map,
    size_bucket,
)


class TestIouXywh:
    def test_identical_boxes_iou_1(self):
        assert iou_xywh([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0

    def test_no_overlap_iou_0(self):
        assert iou_xywh([0, 0, 10, 10], [100, 100, 10, 10]) == 0.0

    def test_partial_overlap(self):
        # dois quadrados 10x10 sobrepostos em 5x10 -> inter=50, union=150
        result = iou_xywh([0, 0, 10, 10], [5, 0, 10, 10])
        assert abs(result - 50 / 150) < 1e-9

    def test_full_containment(self):
        outer = [0, 0, 10, 10]
        inner = [2, 2, 4, 4]
        # inter = área do menor (16), union = área do maior (100)
        assert abs(iou_xywh(outer, inner) - 16 / 100) < 1e-9


class TestGreedyMatch:
    def test_perfect_match_single_class(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        result = greedy_match(preds, gts)
        assert result["helmet"]["tp"] == 1
        assert result["helmet"]["fp"] == 0
        assert result["helmet"]["fn"] == 0

    def test_false_positive_no_gt(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts: list[dict] = []
        result = greedy_match(preds, gts)
        assert result["helmet"]["tp"] == 0
        assert result["helmet"]["fp"] == 1
        assert result["helmet"]["n_gt"] == 0

    def test_false_negative_missed_gt(self):
        preds: list[dict] = []
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        result = greedy_match(preds, gts)
        assert result["helmet"]["fn"] == 1
        assert result["helmet"]["tp"] == 0

    def test_no_cross_class_matching(self):
        """Pred de uma classe nunca casa com GT de outra classe."""
        preds = [{"class": "vest", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "no_vest", "bbox": [0, 0, 10, 10]}]
        result = greedy_match(preds, gts)
        assert result["vest"]["tp"] == 0
        assert result["vest"]["fp"] == 1
        assert result["no_vest"]["fn"] == 1

    def test_confidence_tie_break_higher_confidence_wins_best_gt(self):
        """Duas preds da mesma classe competindo por um único GT — a de
        maior confiança (processada primeiro) fica com o TP."""
        preds = [
            {"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
            {"class": "helmet", "confidence": 0.5, "bbox": [0, 0, 10, 10]},
        ]
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        result = greedy_match(preds, gts)
        assert result["helmet"]["tp"] == 1
        assert result["helmet"]["fp"] == 1
        matches = result["helmet"]["matches"]
        assert matches[0] == (0.9, True)
        assert matches[1] == (0.5, False)

    def test_below_iou_threshold_is_false_positive(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "helmet", "bbox": [50, 50, 10, 10]}]
        result = greedy_match(preds, gts, iou_threshold=0.5)
        assert result["helmet"]["tp"] == 0
        assert result["helmet"]["fp"] == 1
        assert result["helmet"]["fn"] == 1


class TestAveragePrecision:
    def test_no_gt_returns_zero(self):
        assert average_precision([(0.9, True)], n_gt=0) == 0.0

    def test_no_matches_returns_zero(self):
        assert average_precision([], n_gt=5) == 0.0

    def test_perfect_detections_ap_is_1(self):
        matches = [(0.9, True), (0.8, True), (0.7, True)]
        assert average_precision(matches, n_gt=3) == 1.0

    def test_all_false_positives_ap_is_0(self):
        matches = [(0.9, False), (0.8, False)]
        assert average_precision(matches, n_gt=2) == 0.0


class TestPrecisionRecallMap:
    def test_map_averages_only_classes_with_gt(self):
        matches_by_class = greedy_match(
            preds=[
                {"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
                {"class": "vest", "confidence": 0.8, "bbox": [0, 0, 10, 10]},
            ],
            gts=[
                {"class": "helmet", "bbox": [0, 0, 10, 10]},
                # "vest" sem GT no split — classe deve aparecer com ap=None
            ],
        )
        result = precision_recall_map(matches_by_class)
        assert result["per_class"]["helmet"]["ap"] == 1.0
        assert result["per_class"]["vest"]["ap"] is None
        assert result["map50"] == 1.0  # média só considera helmet


class TestMergeMatchResults:
    def test_merges_and_resorts_by_confidence_across_images(self):
        image_1 = greedy_match(
            preds=[{"class": "helmet", "confidence": 0.5, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        image_2 = greedy_match(
            preds=[{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        merged = merge_match_results([image_1, image_2])
        assert merged["helmet"]["n_gt"] == 2
        assert merged["helmet"]["tp"] == 2
        # reordenado por confiança desc, não pela ordem de merge das imagens
        assert merged["helmet"]["matches"][0][0] == 0.9
        assert merged["helmet"]["matches"][1][0] == 0.5

    def test_merges_classes_absent_from_some_images(self):
        image_1 = greedy_match(
            preds=[{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        image_2 = greedy_match(
            preds=[{"class": "vest", "confidence": 0.8, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "vest", "bbox": [0, 0, 10, 10]}],
        )
        merged = merge_match_results([image_1, image_2])
        assert merged["helmet"]["n_gt"] == 1
        assert merged["vest"]["n_gt"] == 1


class TestMergeConfusionMatrices:
    def test_sums_counts_across_images(self):
        m1 = confusion_matrix(
            preds=[{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        m2 = confusion_matrix(
            preds=[{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        merged = merge_confusion_matrices([m1, m2])
        assert merged["helmet"]["helmet"] == 2


class TestConfusionMatrix:
    def test_correct_prediction_diagonal(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        matrix = confusion_matrix(preds, gts)
        assert matrix["helmet"]["helmet"] == 1

    def test_cross_class_confusion_recorded(self):
        """greedy_match NÃO detecta isso (casa só por classe) — confusion_matrix sim."""
        preds = [{"class": "vest", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "no_vest", "bbox": [0, 0, 10, 10]}]
        matrix = confusion_matrix(preds, gts)
        assert matrix["no_vest"]["vest"] == 1

    def test_false_positive_background_row(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts: list[dict] = []
        matrix = confusion_matrix(preds, gts)
        assert matrix["background"]["helmet"] == 1

    def test_false_negative_background_column(self):
        preds: list[dict] = []
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        matrix = confusion_matrix(preds, gts)
        assert matrix["helmet"]["background"] == 1


class TestF1Curve:
    """Caso montado à mão — a aritmética inteira está no comentário.

    matches = 2 acertos de alta confiança + 3 erros de baixa; n_gt = 2.
      limiar <= 0,10 → tp=2 fp=3 → P=0,4    R=1,0 → F1=0,5714
      limiar 0,15-0,20 → tp=2 fp=2 → P=0,5  R=1,0 → F1=0,6667
      limiar 0,25-0,30 → tp=2 fp=1 → P=0,667 R=1,0 → F1=0,8
      limiar 0,35-0,80 → tp=2 fp=0 → P=1,0  R=1,0 → F1=1,0   ← pico
      limiar 0,85-0,90 → tp=1 fp=0 → P=1,0  R=0,5 → F1=0,6667
      limiar 0,95      → tp=0 fp=0 → P=0    R=0   → F1=0
    """

    MATCHES = [(0.9, True), (0.8, True), (0.3, False), (0.2, False), (0.1, False)]

    def test_pontos_conhecidos(self):
        curva = {p["threshold"]: p for p in f1_curve(self.MATCHES, n_gt=2)}
        assert curva[0.10]["f1"] == 0.5714
        assert curva[0.20]["f1"] == 0.6667
        assert curva[0.30] == {
            "threshold": 0.30, "precision": 0.6667, "recall": 1.0,
            "f1": 0.8, "tp": 2, "fp": 1, "fn": 0,
        }
        assert curva[0.50]["f1"] == 1.0
        assert curva[0.90]["f1"] == 0.6667
        assert curva[0.95]["f1"] == 0.0

    def test_pico_no_menor_limiar_do_empate(self):
        """F1=1,0 vale de 0,35 a 0,80 — o limiar escolhido é o de MAIS recall."""
        assert best_f1_threshold(f1_curve(self.MATCHES, n_gt=2)) == 0.35

    def test_grade_completa_de_19_pontos(self):
        curva = f1_curve(self.MATCHES, n_gt=2)
        assert len(curva) == 19
        assert curva[0]["threshold"] == 0.05
        assert curva[-1]["threshold"] == 0.95

    def test_confidence_floor_corta_a_esquerda_da_grade(self):
        """Limiar abaixo do piso do detector é fantasia — não entra na curva."""
        curva = f1_curve(self.MATCHES, n_gt=2, confidence_floor=0.5)
        assert [p["threshold"] for p in curva] == [
            0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95
        ]
        assert best_f1_threshold(curva) == 0.5

    def test_sem_ground_truth_curva_vazia(self):
        assert f1_curve([(0.9, False)], n_gt=0) == []

    def test_sem_predicao_nenhuma_nao_vira_100(self):
        """Classe que o modelo nunca prevê: P/R/F1 = 0 em toda a grade.

        O bug que este teste existe para impedir é 0/0 virando 1,0 —
        ausência de predição lida como acerto perfeito (parente do #417).
        """
        curva = f1_curve([], n_gt=5)
        assert len(curva) == 19
        assert {p["precision"] for p in curva} == {0.0}
        assert {p["f1"] for p in curva} == {0.0}
        assert {p["fn"] for p in curva} == {5}


class TestBestF1Threshold:
    def test_curva_vazia_sem_limiar(self):
        assert best_f1_threshold([]) is None

    def test_f1_zero_em_toda_a_grade_sem_limiar(self):
        """Classe só com falso positivo não ganha limiar inventado."""
        assert best_f1_threshold(f1_curve([(0.9, False), (0.4, False)], n_gt=3)) is None


class TestPrecisionRecallMapCurvas:
    def test_classe_com_gt_e_sem_predicao(self):
        """n_gt=3, zero predições: ap/precision/recall/f1 = 0, limiar None."""
        resultado = precision_recall_map(
            {"luvas": {"matches": [], "n_gt": 3, "tp": 0, "fp": 0, "fn": 3}}
        )
        luvas = resultado["per_class"]["luvas"]
        assert luvas["ap"] == 0.0
        assert luvas["precision"] == 0.0  # ← nunca 1.0
        assert luvas["recall"] == 0.0
        assert luvas["f1"] == 0.0
        assert luvas["n_pred"] == 0
        assert luvas["best_threshold"] is None
        assert resultado["map50"] == 0.0

    def test_classe_sem_gt_nao_ganha_limiar(self):
        resultado = precision_recall_map(
            {"oculos": {"matches": [(0.9, False)], "n_gt": 0, "tp": 0, "fp": 1, "fn": 0}}
        )
        oculos = resultado["per_class"]["oculos"]
        assert oculos["ap"] is None
        assert oculos["n_pred"] == 1
        assert oculos["curve"] == []
        assert oculos["best_threshold"] is None

    def test_limiar_por_classe_sai_do_pico_de_f1(self):
        resultado = precision_recall_map({
            "botas": {
                "matches": TestF1Curve.MATCHES, "n_gt": 2, "tp": 2, "fp": 3, "fn": 0,
            },
        })
        assert resultado["per_class"]["botas"]["best_threshold"] == 0.35
        assert resultado["per_class"]["botas"]["best_f1"] == 1.0
        assert resultado["per_class"]["botas"]["n_pred"] == 5


class TestSizeBucket:
    def test_fronteiras_coco(self):
        assert size_bucket([0, 0, 31, 31]) == "small"       # 961 < 32²
        assert size_bucket([0, 0, 32, 32]) == "medium"      # 1024 == 32²
        assert size_bucket([0, 0, 96, 95]) == "medium"      # 9120 < 96²
        assert size_bucket([0, 0, 96, 96]) == "large"       # 9216 == 96²
        assert size_bucket([0, 0, 200, 200]) == "large"


class TestMapBySize:
    def test_acerto_pequeno_e_erro_grande_com_n_visivel(self):
        """Uma imagem: caixa pequena detectada, caixa grande não detectada."""
        pequena = [0, 0, 20, 20]        # área 400  → small
        grande = [300, 300, 200, 200]   # área 40k  → large
        por_tamanho = map_by_size([(
            [{"class": "luvas", "confidence": 0.9, "bbox": pequena}],
            [{"class": "luvas", "bbox": pequena}, {"class": "luvas", "bbox": grande}],
        )])
        assert por_tamanho["small"] == {
            "map50": 1.0, "n_gt": 1, "n_pred": 1,
            "per_class": {"luvas": {"ap": 1.0, "n_gt": 1, "n_pred": 1}},
        }
        assert por_tamanho["large"]["map50"] == 0.0
        assert por_tamanho["large"]["n_gt"] == 1
        assert por_tamanho["large"]["n_pred"] == 0
        # faixa vazia: map50=0 porque não há o que medir — o n ao lado diz isso
        assert por_tamanho["medium"] == {
            "map50": 0.0, "n_gt": 0, "n_pred": 0, "per_class": {},
        }


class TestMapOverIouSweep:
    def test_caixa_identica_bate_em_todos_os_ious(self):
        resultado = map_over_iou_sweep([(
            [{"class": "botas", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            [{"class": "botas", "bbox": [0, 0, 10, 10]}],
        )])
        assert len(COCO_IOU_SWEEP) == 10
        assert len(resultado["map_por_iou"]) == 10
        assert set(resultado["map_por_iou"].values()) == {1.0}
        assert resultado["map50_95"] == 1.0

    def test_iou_093_passa_em_9_dos_10_limiares(self):
        """pred 10×10 (área 100) × gt 10×9,3 → inter 93, união 100 → IoU 0,93.

        Acerto de IoU 0,50 a 0,90 (9 limiares), erro em 0,95 → mAP50-95 = 0,9.
        """
        resultado = map_over_iou_sweep([(
            [{"class": "botas", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            [{"class": "botas", "bbox": [0, 0, 10, 9.3]}],
        )])
        assert resultado["map_por_iou"]["0.50"] == 1.0
        assert resultado["map_por_iou"]["0.90"] == 1.0
        assert resultado["map_por_iou"]["0.95"] == 0.0
        assert resultado["map50_95"] == 0.9

    def test_map50_da_varredura_bate_com_o_map50_solto(self):
        """A varredura não pode divergir do caminho antigo no IoU 0,5."""
        pares = [(
            [{"class": "botas", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
             {"class": "luvas", "confidence": 0.4, "bbox": [50, 50, 10, 10]}],
            [{"class": "botas", "bbox": [0, 0, 10, 9.3]},
             {"class": "luvas", "bbox": [80, 80, 10, 10]}],
        )]
        solto = precision_recall_map(
            merge_match_results([greedy_match(p, g, 0.5) for p, g in pares])
        )["map50"]
        assert map_over_iou_sweep(pares)["map_por_iou"]["0.50"] == solto
